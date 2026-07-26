"""Red-line provisioning tests for the oauth2 (数字底座/IPD) path.

The oauth2 adapter produces an ``OIDCIdentity``, so ``get_or_provision_oidc_user``
is reused unchanged. These tests pin the security red lines for the IPD flow:
``roleCodes`` NEVER elevate to a DeerFlow admin, email collisions block, an
existing admin's role is never overwritten, and first login creates a plain
``user`` with no password.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.gateway.auth.models import User
from app.gateway.auth.oidc import OIDCIdentity
from app.gateway.auth.user_provisioning import get_or_provision_oidc_user
from deerflow.config.auth_config import OIDCProviderConfig


def _oauth2_cfg(**overrides):
    base = {
        "display_name": "数字底座",
        "provider_type": "oauth2",
        "client_id": "c",
        "authorization_endpoint": "https://a",
        "token_endpoint": "https://t",
        "userinfo_endpoint": "https://u",
        "require_verified_email": False,  # IPD cannot assert email verification
    }
    base.update(overrides)
    return OIDCProviderConfig(**base)


def _ipd_identity(**overrides):
    values = {
        "provider": "shanghai-electric-ipd",
        "subject": "1",
        "email": "u@example.com",
        "email_verified": False,
        "name": "test",
        "claims": {"id": 1, "roleCodes": ["super_admin"], "dept": {"name": "研发部"}},
    }
    values.update(overrides)
    return OIDCIdentity(**values)


@pytest.mark.asyncio
async def test_ipd_rolecodes_super_admin_never_elevates_to_deerflow_admin():
    local_provider = AsyncMock()
    local_provider.get_user_by_oauth.return_value = None
    local_provider.get_user_by_email.return_value = None
    created = User(
        email="u@example.com",
        password_hash=None,
        system_role="user",
        oauth_provider="shanghai-electric-ipd",
        oauth_id="1",
    )
    local_provider.create_oauth_user.return_value = created

    result = await get_or_provision_oidc_user("shanghai-electric-ipd", _oauth2_cfg(), _ipd_identity(), local_provider)

    assert result["created"] is True
    assert result["user"].system_role == "user"  # super_admin roleCode did NOT elevate
    local_provider.create_oauth_user.assert_awaited_once_with(
        email="u@example.com",
        oauth_provider="shanghai-electric-ipd",
        oauth_id="1",
        system_role="user",
    )


@pytest.mark.asyncio
async def test_ipd_first_login_creates_user_with_null_password():
    local_provider = AsyncMock()
    local_provider.get_user_by_oauth.return_value = None
    local_provider.get_user_by_email.return_value = None
    local_provider.create_oauth_user.return_value = User(email="u@example.com", password_hash=None, oauth_provider="shanghai-electric-ipd", oauth_id="1")

    result = await get_or_provision_oidc_user("shanghai-electric-ipd", _oauth2_cfg(), _ipd_identity(), local_provider)

    assert result["user"].password_hash is None


@pytest.mark.asyncio
async def test_ipd_email_collision_with_local_account_blocks_with_409():
    local_user = User(email="u@example.com", password_hash="hash")
    local_provider = AsyncMock()
    local_provider.get_user_by_oauth.return_value = None
    local_provider.get_user_by_email.return_value = local_user

    with pytest.raises(HTTPException) as exc_info:
        await get_or_provision_oidc_user("shanghai-electric-ipd", _oauth2_cfg(), _ipd_identity(), local_provider)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_ipd_existing_admin_role_not_overwritten_on_relogin():
    admin = User(
        email="admin@example.com",
        password_hash=None,
        system_role="admin",
        oauth_provider="shanghai-electric-ipd",
        oauth_id="9",
    )
    local_provider = AsyncMock()
    local_provider.get_user_by_oauth.return_value = admin  # existing link wins, skips all create logic

    result = await get_or_provision_oidc_user(
        "shanghai-electric-ipd",
        _oauth2_cfg(),
        _ipd_identity(subject="9", email="admin@example.com", claims={"roleCodes": ["super_admin"]}),
        local_provider,
    )

    assert result["created"] is False
    assert result["user"].system_role == "admin"  # untouched even though roleCodes=super_admin
    local_provider.create_oauth_user.assert_not_called()


@pytest.mark.asyncio
async def test_ipd_repeated_login_is_idempotent():
    user = User(email="u@example.com", password_hash=None, oauth_provider="shanghai-electric-ipd", oauth_id="1")
    local_provider = AsyncMock()
    local_provider.get_user_by_oauth.return_value = user

    r1 = await get_or_provision_oidc_user("shanghai-electric-ipd", _oauth2_cfg(), _ipd_identity(), local_provider)
    r2 = await get_or_provision_oidc_user("shanghai-electric-ipd", _oauth2_cfg(), _ipd_identity(), local_provider)

    assert r1["user"].id == r2["user"].id
    local_provider.create_oauth_user.assert_not_called()


@pytest.mark.asyncio
async def test_ipd_admin_emails_still_honored_when_explicitly_configured():
    """admin_emails is the ONLY auto-admin path; it still works for oauth2 if explicitly set (not via roleCodes)."""
    local_provider = AsyncMock()
    local_provider.get_user_by_oauth.return_value = None
    local_provider.get_user_by_email.return_value = None
    local_provider.create_oauth_user.return_value = User(email="boss@example.com", system_role="admin", oauth_provider="shanghai-electric-ipd", oauth_id="2")

    await get_or_provision_oidc_user(
        "shanghai-electric-ipd",
        _oauth2_cfg(admin_emails=["boss@example.com"]),
        _ipd_identity(subject="2", email="boss@example.com"),
        local_provider,
    )

    local_provider.create_oauth_user.assert_awaited_once_with(email="boss@example.com", oauth_provider="shanghai-electric-ipd", oauth_id="2", system_role="admin")
