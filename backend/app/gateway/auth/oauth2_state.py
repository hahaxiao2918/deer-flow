"""OAuth2 (non-OIDC) state cookie for 数字底座/IPD CSRF protection.

Unlike OIDC state, the IPD provider generates its own ``state`` and does not
echo a DeerFlow-issued value back, so CSRF protection relies on the presence
of a DeerFlow-signed nonce cookie (set at flow start, verified + consumed at
callback) rather than a state round-trip. An attacker cannot set a cookie on
the DeerFlow origin, and a valid IPD authorization ``code`` cannot be forged,
so this is sufficient defense-in-depth on top of the existing CSRF middleware.

The cookie uses ``path=/`` so both the ``/oauth2/{provider}/start`` setter and
the ``/oauth2/callback/{provider}`` reader can access it, and ``samesite=lax``
so IPD's top-level cross-site redirect back to DeerFlow carries it.
"""

from __future__ import annotations

import secrets
import time

import jwt
from fastapi import Request, Response
from pydantic import BaseModel, Field

from app.gateway.auth.config import get_auth_config
from app.gateway.csrf_middleware import is_secure_request

OAUTH2_STATE_COOKIE_PREFIX = "df_oauth2_state_"
OAUTH2_STATE_MAX_AGE = 600  # 10 minutes — IPD login may take longer than OIDC
OAUTH2_NONCE_BYTES = 32


class OAuth2StatePayload(BaseModel):
    """Payload stored inside the signed oauth2 nonce cookie."""

    provider: str = Field(description="oauth2 provider ID this nonce was issued for")
    nonce: str = Field(description="Cryptographically random nonce — CSRF proof of a DeerFlow-initiated flow")
    next_path: str = Field(default="/workspace", description="Redirect target after successful auth")
    remember_me: bool = Field(default=True, description="Whether the resulting DeerFlow session should be persistent")
    issued_at: float = Field(default_factory=time.time, description="Unix timestamp of cookie creation")


def _sign(payload: OAuth2StatePayload) -> str:
    """Sign the payload with the JWT secret to prevent tampering."""
    return jwt.encode(payload.model_dump(), get_auth_config().jwt_secret, algorithm="HS256")


def _verify(signed: str, max_age: int = OAUTH2_STATE_MAX_AGE) -> OAuth2StatePayload | None:
    """Verify a signed payload, returning None if invalid or expired."""
    try:
        decoded = jwt.decode(signed, get_auth_config().jwt_secret, algorithms=["HS256"])
        payload = OAuth2StatePayload(**decoded)
        if time.time() - payload.issued_at > max_age:
            return None
        return payload
    except jwt.PyJWTError:
        return None


def generate_oauth2_nonce() -> str:
    """Generate a cryptographically random nonce."""
    return secrets.token_urlsafe(OAUTH2_NONCE_BYTES)


def _cookie_name(provider: str) -> str:
    return f"{OAUTH2_STATE_COOKIE_PREFIX}{provider}"


def set_oauth2_state_cookie(response: Response, request: Request, payload: OAuth2StatePayload) -> None:
    """Set the signed oauth2 nonce cookie on the response (path=/)."""
    signed = _sign(payload)
    response.set_cookie(
        key=_cookie_name(payload.provider),
        value=signed,
        httponly=True,
        secure=is_secure_request(request),
        samesite="lax",
        max_age=OAUTH2_STATE_MAX_AGE,
        path="/",
    )


def get_oauth2_state_cookie(request: Request, provider: str) -> OAuth2StatePayload | None:
    """Read and verify the signed oauth2 nonce cookie for the given provider."""
    signed = request.cookies.get(_cookie_name(provider))
    if not signed:
        return None
    return _verify(signed)


def delete_oauth2_state_cookie(response: Response, request: Request, provider: str) -> None:
    """Delete the oauth2 nonce cookie (one-time consumption)."""
    response.delete_cookie(
        key=_cookie_name(provider),
        secure=is_secure_request(request),
        samesite="lax",
        path="/",
    )
