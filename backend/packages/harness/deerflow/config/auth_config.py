"""OIDC / SSO authentication configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OIDCProviderConfig(BaseModel):
    """Configuration for a single identity provider.

    Two provider types share this model, discriminated by ``provider_type``:

    - ``oidc`` (default): standard OpenID Connect with discovery, ID token,
      JWKS validation, and nonce. Requires ``issuer``.
    - ``oauth2``: a custom OAuth2 authorization-code provider that does NOT
      implement OIDC (no discovery / issuer / JWKS / ID token / nonce), e.g.
      the Shanghai Electric "数字底座" (IPD). Requires explicit
      ``authorization_endpoint`` / ``token_endpoint`` / ``userinfo_endpoint``.
      Token exchange sends all params in the query string with ``tenant-id``
      in a header (IPD convention). state is provider-generated and NOT
      trusted for CSRF — DeerFlow issues its own nonce cookie.
    """

    display_name: str = Field(description="Human-readable name shown on the login button")
    provider_type: Literal["oidc", "oauth2"] = Field(
        default="oidc",
        description="Protocol family: 'oidc' (standard OIDC) or 'oauth2' (custom non-OIDC, e.g. 数字底座/IPD)",
    )

    # ── OIDC ──────────────────────────────────────────────────────────
    issuer: str | None = Field(
        default=None,
        description="OIDC issuer URL. Required for provider_type='oidc'; unused for 'oauth2'.",
    )

    # ── Shared OAuth2/OIDC client settings ─────────────────────────────
    client_id: str = Field(description="OAuth2 client ID assigned by the provider")
    client_secret: str | None = Field(default=None, description="OAuth2 client secret ($ENV_VAR references supported)")
    redirect_uri: str | None = Field(default=None, description="Callback URL the provider will redirect to after auth")
    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "email", "profile"],
        description="OIDC scopes to request. oauth2 providers typically override this (IPD uses none).",
    )
    token_endpoint_auth_method: Literal["client_secret_post", "client_secret_basic", "none"] = Field(
        default="client_secret_post",
        description="How the client authenticates at the token endpoint (OIDC only; oauth2/IPD always sends credentials in the query string).",
    )

    # ── User provisioning (shared by both provider types) ──────────────
    auto_create_users: bool = Field(
        default=True,
        description="Automatically create a DeerFlow user on first SSO login",
    )
    require_verified_email: bool = Field(
        default=True,
        description="Reject authentication if the provider does not report the email as verified. oauth2 providers that cannot assert verification should set this to false.",
    )
    allowed_email_domains: list[str] = Field(
        default_factory=list,
        description="If non-empty, only allow users whose email domain is in this list (e.g. ['example.com'])",
    )
    admin_emails: list[str] = Field(
        default_factory=list,
        description="Users with these email addresses are automatically granted the admin role on first login. roleCodes from an oauth2 provider are NEVER mapped to admin.",
    )

    # ── PKCE / nonce (OIDC semantics; ignored by the oauth2 path) ──────
    pkce_enabled: bool = Field(default=True, description="Enable PKCE (S256) for the authorization code flow")
    nonce_enabled: bool = Field(default=True, description="Include and validate the nonce claim in ID tokens")

    # ── Endpoint overrides / explicit endpoints ───────────────────────
    # For provider_type='oidc' these are optional overrides on top of
    # discovery. For provider_type='oauth2' these are the PRIMARY (and
    # required) endpoint sources — there is no discovery document.
    authorization_endpoint: str | None = Field(default=None)
    token_endpoint: str | None = Field(default=None)
    userinfo_endpoint: str | None = Field(default=None)
    jwks_uri: str | None = Field(default=None)

    # ── oauth2 / 数字底座(IPD) specific ────────────────────────────────
    # All fields below are ASSUMPTIONS pending IT confirmation (todo §6 B6/B7):
    subject_field: str = Field(
        default="id",
        description="userinfo field used as the stable external subject (oauth_id). ASSUMPTION default 'id' — pending B6 confirmation of which of id/workId/username is immutable+unique.",
    )
    namespace_with_tenant: bool = Field(
        default=False,
        description="Prefix oauth_id with tenant-id when the subject is only unique within a tenant (e.g. '{tenant}:{id}'). ASSUMPTION default false (global-unique) — pending B6.",
    )
    email_synthesis_pattern: str | None = Field(
        default=None,
        description="When userinfo returns no email, synthesize one with this pattern, e.g. '{id}@ipd.local'. Requires require_verified_email=false. ASSUMPTION — pending B7 (IPD email availability/uniqueness).",
    )
    default_tenant_id: int | None = Field(
        default=None,
        description="Fallback tenant-id header value when the callback does not carry one (IPD).",
    )
    default_organize_id: int | None = Field(
        default=None,
        description="Fallback organize-id header value when the callback does not carry one (IPD).",
    )
    allowed_tenant_ids: list[int] = Field(
        default_factory=list,
        description="If non-empty, only allow these tenant-id values (IPD).",
    )
    allowed_organize_ids: list[int] = Field(
        default_factory=list,
        description="If non-empty, only allow these organize-id values (IPD).",
    )
    http_timeout_seconds: float = Field(
        default=15.0,
        description="Per-request timeout for IPD token/userinfo HTTP calls.",
    )

    @model_validator(mode="after")
    def _validate_provider_type_requirements(self) -> OIDCProviderConfig:
        """Enforce per-type required fields."""
        if self.provider_type == "oidc":
            if not self.issuer:
                raise ValueError("issuer is required when provider_type='oidc'")
        else:  # oauth2 — no discovery, endpoints must be explicit
            missing = [
                name
                for name, val in (
                    ("authorization_endpoint", self.authorization_endpoint),
                    ("token_endpoint", self.token_endpoint),
                    ("userinfo_endpoint", self.userinfo_endpoint),
                )
                if not val
            ]
            if missing:
                raise ValueError("provider_type='oauth2' requires explicit endpoints (no discovery): " + ", ".join(missing))
        return self


class OIDCAuthConfig(BaseModel):
    """Top-level OIDC authentication configuration."""

    enabled: bool = Field(default=False, description="Enable OIDC SSO authentication")
    frontend_base_url: str | None = Field(
        default=None,
        description="Base URL of the frontend (used for callback redirects when behind a reverse proxy)",
    )
    providers: dict[str, OIDCProviderConfig] = Field(
        default_factory=dict,
        description="Map of provider IDs to their configuration (e.g. keycloak, google, azure)",
    )


class LocalAuthConfig(BaseModel):
    """Configuration for the built-in email/password authentication provider."""

    allow_registration: bool = Field(
        default=True,
        description=(
            "Allow visitors to self-register a local account via POST /api/v1/auth/register. "
            "Set to false when accounts are provisioned exclusively through SSO — the OIDC "
            "provisioning policy (allowed_email_domains, require_verified_email, auto_create_users) "
            "does not apply to local registration."
        ),
    )


class AuthAppConfig(BaseModel):
    """Authentication configuration section for the DeerFlow app config."""

    oidc: OIDCAuthConfig = Field(default_factory=OIDCAuthConfig, description="OIDC SSO authentication settings")
    local: LocalAuthConfig = Field(default_factory=LocalAuthConfig, description="Built-in email/password authentication settings")
