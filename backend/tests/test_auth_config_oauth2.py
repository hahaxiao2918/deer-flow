"""Tests for provider_type discrimination and oauth2 (数字底座/IPD) config fields."""

import pytest

from deerflow.config.auth_config import OIDCProviderConfig


def _oidc(**overrides):
    base = {"display_name": "Keycloak", "issuer": "https://issuer.example.com", "client_id": "deer-flow"}
    base.update(overrides)
    return OIDCProviderConfig(**base)


def _oauth2(**overrides):
    base = {
        "display_name": "数字底座",
        "provider_type": "oauth2",
        "client_id": "Starlink@SynForge1357g",
        "authorization_endpoint": "https://portal.example.com/login",
        "token_endpoint": "https://portal.example.com/admin-api/system/oauth2/token",
        "userinfo_endpoint": "https://portal.example.com/admin-api/system/oauth2/user/get",
    }
    base.update(overrides)
    return OIDCProviderConfig(**base)


def test_default_provider_type_is_oidc():
    cfg = _oidc()
    assert cfg.provider_type == "oidc"


def test_oidc_requires_issuer():
    with pytest.raises(Exception):
        OIDCProviderConfig(display_name="X", client_id="c")  # no issuer, default type oidc


def test_oauth2_does_not_require_issuer():
    cfg = _oauth2()
    assert cfg.provider_type == "oauth2"
    assert cfg.issuer is None  # issuer unused for oauth2


def test_oauth2_requires_explicit_endpoints():
    with pytest.raises(Exception, match="authorization_endpoint"):
        OIDCProviderConfig(display_name="X", provider_type="oauth2", client_id="c")

    with pytest.raises(Exception, match="token_endpoint"):
        OIDCProviderConfig(
            display_name="X",
            provider_type="oauth2",
            client_id="c",
            authorization_endpoint="https://a",
        )


def test_oauth2_assumption_defaults():
    """Default ASSUMPTION values pending IT confirmation (B6/B7)."""
    cfg = _oauth2()
    assert cfg.subject_field == "id"  # ASSUMPTION A1
    assert cfg.namespace_with_tenant is False  # ASSUMPTION A2 (global-unique)
    assert cfg.email_synthesis_pattern is None  # ASSUMPTION A3 (off by default)
    assert cfg.allowed_tenant_ids == []
    assert cfg.allowed_organize_ids == []


def test_oauth2_provisioning_fields_inherit_shared_defaults():
    """oauth2 providers share the OIDC provisioning policy fields."""
    cfg = _oauth2()
    assert cfg.auto_create_users is True
    assert cfg.require_verified_email is True
    assert cfg.admin_emails == []


def test_oauth2_rolecodes_are_not_an_admin_source():
    """admin_emails is the ONLY auto-admin path; there is no roleCodes->admin field."""
    cfg = _oauth2()
    # Confirm no field exists that would map provider roles to DeerFlow admin.
    serialised = cfg.model_dump()
    assert "admin_emails" in serialised
    assert not any("role" in k.lower() and "code" in k.lower() for k in serialised)


def test_client_secret_stores_env_reference_for_app_config_resolution():
    """$ENV references are stored verbatim and resolved by the app-config loader (same as OIDC)."""
    cfg = _oauth2(client_secret="$IPD_CLIENT_SECRET")
    assert cfg.client_secret == "$IPD_CLIENT_SECRET"


def test_oauth2_assumption_overrides_are_respected():
    cfg = _oauth2(
        subject_field="workId",
        namespace_with_tenant=True,
        email_synthesis_pattern="{id}@ipd.shanghai-electric.local",
        require_verified_email=False,
        allowed_tenant_ids=[1],
    )
    assert cfg.subject_field == "workId"
    assert cfg.namespace_with_tenant is True
    assert cfg.email_synthesis_pattern == "{id}@ipd.shanghai-electric.local"
    assert cfg.require_verified_email is False
    assert cfg.allowed_tenant_ids == [1]
