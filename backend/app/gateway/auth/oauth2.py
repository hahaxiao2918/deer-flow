"""Custom OAuth2 (non-OIDC) authentication service.

For providers that implement the OAuth2 authorization-code flow WITHOUT OIDC
(no discovery / issuer / JWKS / ID token / nonce), e.g. the Shanghai Electric
"数字底座" (IPD) platform.

Key differences from the OIDC service (oidc.py):

- No discovery: endpoints come from config (authorization/token/userinfo).
- Token exchange sends grant_type/client_id/client_secret/code/redirect_uri/
  state ALL in the query string, with ``tenant-id`` in a header (IPD
  convention). The response is an IPD-style envelope ``{code, data:{...}, msg}``
  where ``code==0`` means success.
- No ID token validation; userinfo is the sole identity source.
- ``state`` is provider-generated and NOT trusted for CSRF — the caller (the
  router) enforces CSRF via DeerFlow's own nonce cookie.
- Produces an ``OIDCIdentity`` so the existing provisioning path
  (``get_or_provision_oidc_user``) is reused unchanged. ``roleCodes`` are
  carried in ``claims`` but are NEVER mapped to a DeerFlow admin role
  (provisioning only honours the explicit ``admin_emails`` list).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.gateway.auth.oidc import OIDCIdentity
from deerflow.config.auth_config import OIDCProviderConfig

logger = logging.getLogger(__name__)


class OAuth2Error(Exception):
    """Base error for OAuth2 operations. Message is safe for API responses."""


class OAuth2ProviderError(OAuth2Error):
    """The provider returned a business error (response envelope code != 0)."""


class OAuth2ValidationError(OAuth2Error):
    """The provider response was missing required identity fields."""


# Sensitive query keys that must never appear in logs or exception text.
_SENSITIVE_QUERY_KEYS = frozenset({"client_secret", "code", "refresh_token", "access_token", "client_id"})


def _redact_query(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of query params with sensitive values masked (for logging)."""
    return {k: ("***" if k in _SENSITIVE_QUERY_KEYS else v) for k, v in params.items()}


class OAuth2Service:
    """Custom OAuth2 authentication service for non-OIDC providers."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    # ── Authorization URL ─────────────────────────────────────────────────

    def build_authorization_url(
        self,
        provider_config: OIDCProviderConfig,
        client_id: str,
        redirect_uri: str,
        state: str,
        scopes: list[str] | None = None,
    ) -> str:
        """Build the provider authorization URL.

        IPD redirects the browser here; the browser returns to the configured
        front-end interception route (``/loginsso``) carrying ``code``/``state``.
        """
        # IPD (yudao) uses camelCase query params on its authorize endpoint:
        # the backend /admin-api/system/oauth2/authorize rejects snake_case
        # `client_id` with "Required request parameter 'clientId' ... not present".
        params: dict[str, str] = {
            "clientId": client_id,
            "redirectUri": redirect_uri,
            "responseType": "code",
            "state": state,
        }
        if scopes:
            params["scopes"] = " ".join(scopes)
        endpoint = provider_config.authorization_endpoint
        if not endpoint:  # pragma: no cover — enforced by config model_validator
            raise OAuth2Error("provider_config.authorization_endpoint is not set")
        return f"{endpoint}?{urlencode(params)}"

    # ── Token exchange ────────────────────────────────────────────────────

    async def exchange_code(
        self,
        provider_config: OIDCProviderConfig,
        code: str,
        redirect_uri: str,
        state: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Exchange an authorization code for tokens.

        IPD sends grant_type/client_id/client_secret/code/redirect_uri/state in
        the QUERY string and ``tenant-id`` in a header. Returns the ``data``
        object from the IPD envelope (containing ``access_token`` etc.).
        """
        client_secret = provider_config.client_secret or ""
        params: dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": provider_config.client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        headers = {"tenant-id": str(tenant_id), "Accept": "application/json"}
        endpoint = provider_config.token_endpoint
        if not endpoint:  # pragma: no cover — enforced by config model_validator
            raise OAuth2Error("provider_config.token_endpoint is not set")
        url = f"{endpoint}?{urlencode(params)}"
        try:
            resp = await self._http.post(url, headers=headers)
            resp.raise_for_status()
            envelope = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OAuth2 token exchange failed: HTTP %s (redacted params=%s)",
                exc.response.status_code,
                _redact_query(params),
            )
            raise OAuth2Error(f"Token exchange failed: HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise OAuth2Error(f"Token exchange failed: {exc}") from exc

        _raise_for_business_error(envelope, "token exchange")
        token_data = envelope.get("data") or {}
        if not token_data.get("access_token"):
            raise OAuth2ValidationError("Token response is missing access_token")
        return token_data

    # ── UserInfo ──────────────────────────────────────────────────────────

    async def fetch_userinfo(
        self,
        provider_config: OIDCProviderConfig,
        access_token: str,
        tenant_id: int,
        organize_id: int,
    ) -> dict[str, Any]:
        """Fetch user info via the provider userinfo endpoint.

        IPD: ``Authorization: Bearer``, ``tenant-id`` + ``organize-id`` headers,
        ``carryRole=true`` query.
        """
        endpoint = provider_config.userinfo_endpoint
        if not endpoint:  # pragma: no cover — enforced by config model_validator
            raise OAuth2Error("provider_config.userinfo_endpoint is not set")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "tenant-id": str(tenant_id),
            "organize-id": str(organize_id),
            "Accept": "application/json",
        }
        url = f"{endpoint}?{urlencode({'carryRole': 'true'})}"
        try:
            resp = await self._http.get(url, headers=headers)
            resp.raise_for_status()
            envelope = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("OAuth2 userinfo fetch failed: HTTP %s", exc.response.status_code)
            raise OAuth2Error(f"UserInfo fetch failed: HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise OAuth2Error(f"UserInfo fetch failed: {exc}") from exc

        _raise_for_business_error(envelope, "userinfo fetch")
        userinfo = envelope.get("data") or {}
        if not userinfo:
            raise OAuth2ValidationError("UserInfo response is missing data")
        return userinfo

    # ── Orchestrated callback ─────────────────────────────────────────────

    async def authenticate_callback(
        self,
        provider_id: str,
        provider_config: OIDCProviderConfig,
        code: str,
        redirect_uri: str,
        state: str,
        tenant_id: int,
        organize_id: int,
    ) -> OIDCIdentity:
        """Orchestrate the full non-OIDC callback: token exchange + userinfo.

        Returns a normalized ``OIDCIdentity`` so the existing provisioning path
        (``get_or_provision_oidc_user``) is reused unchanged.
        """
        token_data = await self.exchange_code(provider_config, code, redirect_uri, state, tenant_id)
        access_token = token_data["access_token"]

        userinfo = await self.fetch_userinfo(provider_config, access_token, tenant_id, organize_id)

        subject = _resolve_subject(provider_config, userinfo, tenant_id)
        if not subject:
            raise OAuth2ValidationError(f"UserInfo is missing the configured subject field '{provider_config.subject_field}'")

        email, email_synthesized = _resolve_email(provider_config, userinfo, subject)

        # Carry the full userinfo (incl. roleCodes/dept/posts) as claims, plus a
        # private flag so callers can tell synthesized emails apart. roleCodes
        # are intentionally NOT used for role assignment — provisioning only
        # honours the explicit admin_emails list.
        claims: dict[str, Any] = dict(userinfo)
        claims["_email_synthesized"] = email_synthesized

        return OIDCIdentity(
            provider=provider_id,
            subject=subject,
            email=email,
            email_verified=False,  # oauth2/IPD cannot assert email verification
            name=userinfo.get("nickname") or userinfo.get("username"),
            claims=claims,
        )

    # ── ODM account-login (LTPA SSO, use-case 2 seamless entry) ────────────

    async def odm_login_with_ltpa(
        self,
        provider_config: OIDCProviderConfig,
        ltpa_token: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Resolve a base ``LtpaToken`` cookie to the user's account (ODM doc §5.1).

        Use-case 2 seamless entry: after the user logs into the portal, the base
        sets an ``LtpaToken`` cookie on the parent ``.shanghai-electric.com``
        domain. The browser carries it to DeerFlow; the backend forwards it
        (server-side) to the ODM account-login endpoint to resolve the identity.
        Auth is ``Authorization: Bearer base64(client_id:client_secret)``.

        Returns the ``account`` object from the ODM envelope. Raises
        ``OAuth2Error`` on transport/business/validation failure (e.g. expired
        or foreign token) so the caller can fall back to a base-login redirect.
        """
        endpoint = provider_config.odm_login_endpoint
        if not endpoint:
            raise OAuth2Error("provider_config.odm_login_endpoint is not set")
        body = {
            "timestamp": int(time.time()),
            "token": ltpa_token,
            "userCode": "",
            "password": "",
            "hasCompanyInfo": True,
            "hasAuthInfo": True,
            "logInfo": {},
        }
        headers = {
            "Authorization": _odm_auth_header(provider_config),
            "tenant-id": str(tenant_id),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            resp = await self._http.post(endpoint, json=body, headers=headers)
            resp.raise_for_status()
            envelope = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("ODM ltpa login failed: HTTP %s", exc.response.status_code)
            raise OAuth2Error(f"ODM login failed: HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise OAuth2Error(f"ODM login failed: {exc}") from exc

        _raise_for_business_error(envelope, "ODM ltpa login")
        data = envelope.get("data") or {}
        if data.get("isError"):
            msg = envelope.get("msg") or "isError"
            raise OAuth2ProviderError(f"ODM ltpa login rejected: {msg}")
        account = data.get("account") or {}
        if not account:
            raise OAuth2ValidationError("ODM login response is missing account")
        return account


def _raise_for_business_error(envelope: dict[str, Any], op: str) -> None:
    """Raise OAuth2ProviderError when the IPD-style envelope reports failure.

    IPD envelope: ``code==0`` means success. A missing ``code`` is tolerated
    for non-IPC oauth2 providers that return a raw token/userinfo object.
    """
    code = envelope.get("code")
    if code not in (0, None, "0"):
        msg = envelope.get("msg") or "unknown error"
        raise OAuth2ProviderError(f"{op} rejected by provider: code={code} msg={msg}")


def _resolve_subject(provider_config: OIDCProviderConfig, userinfo: dict[str, Any], tenant_id: int) -> str:
    """Resolve the stable external subject from userinfo per config.

    ASSUMPTION (pending B6): defaults to ``userinfo['id']``, globally unique.
    ``namespace_with_tenant`` prefixes the tenant id when the subject is only
    unique within a tenant.
    """
    raw = userinfo.get(provider_config.subject_field)
    if raw is None or raw == "":
        return ""
    subject = str(raw)
    if provider_config.namespace_with_tenant:
        subject = f"{tenant_id}:{subject}"
    return subject


def _resolve_email(provider_config: OIDCProviderConfig, userinfo: dict[str, Any], subject: str) -> tuple[str, bool]:
    """Resolve email from userinfo, synthesizing one per config when absent.

    Returns ``(email, synthesized)``. ASSUMPTION (pending B7): synthesis is off
    by default; a provider with email-less users must set
    ``email_synthesis_pattern`` (e.g. ``'{id}@ipd.local'``) plus
    ``require_verified_email: false``.
    """
    raw_email = userinfo.get("email")
    if isinstance(raw_email, str) and raw_email.strip():
        return raw_email.strip().lower(), False

    pattern = provider_config.email_synthesis_pattern
    if not pattern:
        # No email and no synthesis pattern -> empty; provisioning's
        # missing-email guard rejects it. Callers serving an email-less IdP
        # must configure a pattern + require_verified_email=false.
        return "", True
    fmt_args: dict[str, Any] = {"id": subject, "subject": subject}
    for key, value in userinfo.items():
        if key not in fmt_args:
            fmt_args[key] = value
    try:
        return pattern.format(**fmt_args).lower(), True
    except (KeyError, IndexError, ValueError):
        # A malformed pattern must never crash login; fall back to the literal.
        logger.warning("email_synthesis_pattern %r could not be formatted; using literal", pattern)
        return pattern.lower(), True


def _odm_auth_header(provider_config: OIDCProviderConfig) -> str:
    """Build the ODM ``Authorization: Bearer base64(client_id:client_secret)`` header (doc §5.1.1.3)."""
    raw = f"{provider_config.client_id}:{provider_config.client_secret or ''}".encode()
    return "Bearer " + base64.b64encode(raw).decode()


def identity_from_odm_account(
    provider_id: str,
    provider_config: OIDCProviderConfig,
    account: dict[str, Any],
    tenant_id: int,
) -> OIDCIdentity:
    """Map an ODM ``account`` object to an ``OIDCIdentity`` for provisioning.

    The ODM account carries the workId （工号， globally unique) in ``code`` and a
    real ``email`` (unlike the OAuth2 userinfo path, synthesis is normally not
    needed). ``roleCodes``/org fields are passed through as claims but are never
    mapped to a DeerFlow admin role.
    """
    subject = str(account.get("code") or account.get("userId") or "")
    if not subject:
        raise OAuth2ValidationError("ODM account is missing the workId 'code' field")
    if provider_config.namespace_with_tenant:
        subject = f"{tenant_id}:{subject}"

    email, _synthesized = _resolve_email(provider_config, account, subject)

    claims: dict[str, Any] = dict(account)
    claims["_auth_via"] = "ltpa"
    return OIDCIdentity(
        provider=provider_id,
        subject=subject,
        email=email,
        email_verified=False,  # LTPA/ODM cannot assert email verification
        name=account.get("name") or account.get("name_EN"),
        claims=claims,
    )
