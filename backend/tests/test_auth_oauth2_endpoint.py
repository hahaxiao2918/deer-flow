"""Tests for the non-OIDC OAuth2 (数字底座/IPD) auth endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.auth.config import AuthConfig, set_auth_config
from app.gateway.auth.models import User
from app.gateway.auth.oauth2 import OAuth2ProviderError
from app.gateway.auth.oidc import OIDCIdentity
from app.gateway.routers import auth as auth_module
from app.gateway.routers.auth import router
from deerflow.config.auth_config import AuthAppConfig, OIDCAuthConfig, OIDCProviderConfig


@pytest.fixture(autouse=True)
def _fixed_jwt_secret():
    set_auth_config(AuthConfig(jwt_secret="test-secret-oauth2"))
    yield


def _oauth2_cfg(**overrides):
    base = {
        "display_name": "数字底座",
        "provider_type": "oauth2",
        "client_id": "cid",
        "client_secret": "csec",
        "authorization_endpoint": "https://portal.example.com/login",
        "token_endpoint": "https://portal.example.com/admin-api/system/oauth2/token",
        "userinfo_endpoint": "https://portal.example.com/admin-api/system/oauth2/user/get",
        "redirect_uri": "https://app.example.com/loginsso",
        "require_verified_email": False,
        "default_tenant_id": 1,
        "default_organize_id": 100,
        "odm_login_endpoint": "https://portal.example.com/admin-api/system/odm-api-wrap/account/login",
    }
    base.update(overrides)
    return OIDCProviderConfig(**base)


def _app_config(provider_cfg):
    fake = MagicMock()
    fake.auth = AuthAppConfig(
        oidc=OIDCAuthConfig(
            enabled=True,
            frontend_base_url="https://app.example.com",
            providers={"ipd": provider_cfg},
        )
    )
    return fake


def _client(monkeypatch, provider_cfg, *, service=None, local_provider=None):
    monkeypatch.setattr("deerflow.config.app_config.get_app_config", lambda: _app_config(provider_cfg))
    if service is not None:
        monkeypatch.setattr(auth_module, "_get_oauth2_service", lambda: service)
    if local_provider is not None:
        monkeypatch.setattr("app.gateway.routers.auth.get_local_provider", lambda: local_provider)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _fake_identity():
    return OIDCIdentity(
        provider="ipd",
        subject="1",
        email="u@example.com",
        email_verified=False,
        name="test",
        claims={"roleCodes": ["super_admin"]},
    )


def test_providers_lists_oauth2_type(monkeypatch):
    client = _client(monkeypatch, _oauth2_cfg())
    resp = client.get("/api/v1/auth/providers")
    assert resp.status_code == 200
    assert resp.json()["providers"] == [{"id": "ipd", "display_name": "数字底座", "type": "oauth2"}]


def _fake_odm_account():
    """The ODM account-login (§5.1) account shape for the LTPA SSO path."""
    return {
        "userId": "276392",
        "code": "03010633",  # workId (工号) — the globally-unique subject
        "name": "林鑫",
        "email": "linxin3@shanghai-electric.com",
        "dept": {"code": "22BE6", "name": "知识产权研究部"},
        "company": {"code": "3500", "name": "上海电气中央研究院(本部)"},
    }


def test_oauth2_start_without_ltpa_redirects_to_base_login_with_returnurl(monkeypatch):
    """No LtpaToken cookie → redirect to the base login page with returnUrl back
    to /loginsso (NOT the OAuth authorize URL, and no nonce cookie in LTPA mode)."""
    client = _client(monkeypatch, _oauth2_cfg())
    resp = client.get("/api/v1/auth/oauth2/ipd/start", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://portal.example.com/login?")
    assert "returnUrl=" in location
    assert "loginsso" in location
    # LTPA mode: no OAuth authorize params, no nonce cookie, no session.
    assert "clientId" not in location
    cookie_headers = resp.headers.get_list("set-cookie")
    assert not any("access_token=" in c for c in cookie_headers)


def test_oauth2_start_with_ltpa_token_logs_in_seamlessly(monkeypatch):
    """Browser carries a base LtpaToken → /start resolves it via ODM (server-side),
    maps workId→subject, provisions, sets the session — all WITHOUT a base redirect."""
    cfg = _oauth2_cfg()
    service = MagicMock()
    service.odm_login_with_ltpa = AsyncMock(return_value=_fake_odm_account())
    user = User(email="linxin3@shanghai-electric.com", password_hash=None, system_role="user", oauth_provider="ipd", oauth_id="03010633")
    local_provider = MagicMock()
    local_provider.get_user_by_oauth = AsyncMock(return_value=user)

    client = _client(monkeypatch, cfg, service=service, local_provider=local_provider)
    client.cookies.set("LtpaToken", "LTPA-VALUE")
    resp = client.get("/api/v1/auth/oauth2/ipd/start", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/callback?next=" in resp.headers["location"]
    cookie_headers = resp.headers.get_list("set-cookie")
    assert any("access_token=" in c for c in cookie_headers)

    service.odm_login_with_ltpa.assert_awaited_once()
    kwargs = service.odm_login_with_ltpa.await_args
    assert kwargs.args[1] == "LTPA-VALUE"  # the cookie value is forwarded to ODM


def test_oauth2_start_ltpa_rejected_falls_back_to_base_login(monkeypatch):
    """Expired/foreign LtpaToken (ODM rejects) → fall back to the base-login
    redirect instead of erroring or looping."""
    cfg = _oauth2_cfg()
    service = MagicMock()
    service.odm_login_with_ltpa = AsyncMock(side_effect=OAuth2ProviderError("账号或密码错误!"))
    client = _client(monkeypatch, cfg, service=service)
    client.cookies.set("LtpaToken", "STALE")
    resp = client.get("/api/v1/auth/oauth2/ipd/start", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://portal.example.com/login?")
    assert "returnUrl=" in location
    cookie_headers = resp.headers.get_list("set-cookie")
    assert not any("access_token=" in c for c in cookie_headers)


def test_oauth2_start_rejects_oidc_provider(monkeypatch):
    oidc_cfg = OIDCProviderConfig(display_name="K", issuer="https://i.example.com", client_id="c")
    client = _client(monkeypatch, oidc_cfg)
    resp = client.get("/api/v1/auth/oauth2/ipd/start", follow_redirects=False)
    assert resp.status_code == 400


def test_oauth2_start_404_when_disabled(monkeypatch):
    fake = _app_config(_oauth2_cfg())
    fake.auth.oidc.enabled = False
    monkeypatch.setattr("deerflow.config.app_config.get_app_config", lambda: fake)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/auth/oauth2/ipd/start", follow_redirects=False)
    assert resp.status_code == 404


def test_oauth2_callback_missing_code_returns_400(monkeypatch):
    client = _client(monkeypatch, _oauth2_cfg())
    resp = client.get("/api/v1/auth/oauth2/ipd/callback?tenant-id=1&organize-id=100", follow_redirects=False)
    assert resp.status_code == 400


def test_oauth2_callback_without_nonce_cookie_is_allowed_as_ipd_initiated_flow(monkeypatch):
    """Official 用例一/用例二 path: the portal mints the code and opens /loginsso
    in a fresh tab that never called /start — so there is no nonce cookie. The
    callback must ALLOW this (the one-time code + client_secret is the defense),
    provision the user, and set the session."""
    cfg = _oauth2_cfg()
    service = MagicMock()
    service.authenticate_callback = AsyncMock(return_value=_fake_identity())
    user = User(email="u@example.com", password_hash=None, system_role="user", oauth_provider="ipd", oauth_id="1")
    local_provider = MagicMock()
    local_provider.get_user_by_oauth = AsyncMock(return_value=user)

    client = _client(monkeypatch, cfg, service=service, local_provider=local_provider)
    # NOTE: no /start call first → no df_oauth2_state_ipd cookie (IPD-initiated).
    resp = client.get("/api/v1/auth/oauth2/ipd/callback?code=C&tenant-id=1&organize-id=100", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/callback?next=" in resp.headers["location"]
    cookie_headers = resp.headers.get_list("set-cookie")
    assert any("access_token=" in c for c in cookie_headers)
    service.authenticate_callback.assert_awaited_once()


def test_oauth2_callback_forwards_ipd_state_to_token_exchange(monkeypatch):
    """Doc 2.3: the code exchange echoes the IPD-issued `state` back to the token
    endpoint. The callback must forward the `state` query param it received."""
    cfg = _oauth2_cfg()
    service = MagicMock()
    service.authenticate_callback = AsyncMock(return_value=_fake_identity())
    user = User(email="u@example.com", password_hash=None, system_role="user", oauth_provider="ipd", oauth_id="1")
    local_provider = MagicMock()
    local_provider.get_user_by_oauth = AsyncMock(return_value=user)

    client = _client(monkeypatch, cfg, service=service, local_provider=local_provider)
    resp = client.get("/api/v1/auth/oauth2/ipd/callback?code=C&state=ipd-nonce-99&tenant-id=1&organize-id=100", follow_redirects=False)
    assert resp.status_code == 302
    assert service.authenticate_callback.await_args.kwargs["state"] == "ipd-nonce-99"


def test_oauth2_callback_full_flow_sets_session_and_redirects(monkeypatch):
    cfg = _oauth2_cfg()
    service = MagicMock()
    service.authenticate_callback = AsyncMock(return_value=_fake_identity())
    user = User(email="u@example.com", password_hash=None, system_role="user", oauth_provider="ipd", oauth_id="1")
    local_provider = MagicMock()
    local_provider.get_user_by_oauth = AsyncMock(return_value=user)

    client = _client(monkeypatch, cfg, service=service, local_provider=local_provider)

    # Full success path (no /start needed — the callback is IPD-initiated, and the
    # nonce cookie is optional since 54bfd3a).
    resp = client.get("/api/v1/auth/oauth2/ipd/callback?code=C&tenant-id=1&organize-id=100", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/callback?next=" in resp.headers["location"]
    cookie_headers = resp.headers.get_list("set-cookie")
    assert any("access_token=" in c for c in cookie_headers)

    service.authenticate_callback.assert_awaited_once()
    kwargs = service.authenticate_callback.await_args.kwargs
    assert kwargs["provider_id"] == "ipd"
    assert kwargs["code"] == "C"
    assert kwargs["tenant_id"] == 1
    assert kwargs["organize_id"] == 100


def test_oauth2_callback_rejects_non_whitelisted_tenant(monkeypatch):
    cfg = _oauth2_cfg(allowed_tenant_ids=[1])
    service = MagicMock()
    service.authenticate_callback = AsyncMock(return_value=_fake_identity())
    client = _client(monkeypatch, cfg, service=service)

    resp = client.get("/api/v1/auth/oauth2/ipd/callback?code=C&tenant-id=999&organize-id=100", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login?error=sso_failed" in resp.headers["location"]
    service.authenticate_callback.assert_not_awaited()


def test_resolve_oauth2_redirect_uri_uses_configured_value():
    from app.gateway.routers.auth import _resolve_oauth2_redirect_uri

    req = MagicMock()
    assert _resolve_oauth2_redirect_uri(req, _oauth2_cfg()) == "https://app.example.com/loginsso"


def test_resolve_oauth2_redirect_uri_falls_back_to_origin():
    from app.gateway.routers.auth import _resolve_oauth2_redirect_uri

    cfg = _oauth2_cfg(redirect_uri=None)
    req = MagicMock()
    req.url.scheme = "https"
    req.headers = {"host": "ipd.nebula-starlink.shanghai-electric.com"}
    # _request_origin reads forwarded headers; with none it falls back to host
    assert _resolve_oauth2_redirect_uri(req, cfg).endswith("/loginsso")
