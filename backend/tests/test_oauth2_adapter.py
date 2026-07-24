"""Tests for the custom OAuth2 (数字底座/IPD) adapter."""

from unittest.mock import AsyncMock

import httpx
import pytest

from app.gateway.auth.oauth2 import (
    OAuth2Error,
    OAuth2ProviderError,
    OAuth2Service,
    OAuth2ValidationError,
)
from deerflow.config.auth_config import OIDCProviderConfig


def _cfg(**overrides):
    base = {
        "display_name": "数字底座",
        "provider_type": "oauth2",
        "client_id": "cid",
        "client_secret": "csec",
        "authorization_endpoint": "https://portal.example.com/login",
        "token_endpoint": "https://portal.example.com/admin-api/system/oauth2/token",
        "userinfo_endpoint": "https://portal.example.com/admin-api/system/oauth2/user/get",
    }
    base.update(overrides)
    return OIDCProviderConfig(**base)


class _Resp:
    """Minimal httpx.Response stand-in."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "https://portal.example.com/x")
            raise httpx.HTTPStatusError(
                "error",
                request=req,
                response=httpx.Response(self.status_code, request=req),
            )

    def json(self):
        return self._payload


def _official_userinfo():
    """The exact response shape from 数字底座对接文档v1 §4.2."""
    return {
        "code": 0,
        "data": {
            "id": 1,
            "workId": "03000111",
            "username": "test",
            "nickname": "test",
            "email": "1@qq.com",
            "mobile": "1",
            "sex": 1,
            "avatar": "xx.png",
            "dept": {"id": 1, "name": "研发部"},
            "posts": [{"id": 1, "name": "开发"}],
            "roleCodes": ["super_admin"],
        },
        "msg": "string",
    }


# ── exchange_code ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_code_sends_all_params_in_query_and_tenant_id_in_header(monkeypatch):
    svc = OAuth2Service()
    captured = {}

    async def fake_post(url, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        return _Resp({"code": 0, "data": {"access_token": "AT", "refresh_token": "RT", "expires_in": 16000}})

    monkeypatch.setattr(svc._http, "post", fake_post)

    data = await svc.exchange_code(_cfg(), code="C", redirect_uri="https://app/loginsso", state="0", tenant_id=1)

    assert data["access_token"] == "AT"
    url = captured["url"]
    # All credentials/params must travel in the query string (IPD convention)
    assert url.startswith("https://portal.example.com/admin-api/system/oauth2/token?")
    assert "grant_type=authorization_code" in url
    assert "client_id=cid" in url
    assert "client_secret=csec" in url
    assert "code=C" in url
    assert "redirect_uri=" in url
    assert "state=0" in url
    # tenant-id travels in the header, NOT the query
    assert captured["headers"]["tenant-id"] == "1"
    assert "tenant-id" not in url
    await svc.close()


@pytest.mark.asyncio
async def test_exchange_code_raises_on_business_error(monkeypatch):
    svc = OAuth2Service()

    async def fake_post(url, headers=None):
        return _Resp({"code": 400, "msg": "invalid code"})

    monkeypatch.setattr(svc._http, "post", fake_post)

    with pytest.raises(OAuth2ProviderError, match="code=400"):
        await svc.exchange_code(_cfg(), "C", "https://app/loginsso", "0", 1)
    await svc.close()


@pytest.mark.asyncio
async def test_exchange_code_raises_when_access_token_missing(monkeypatch):
    svc = OAuth2Service()

    async def fake_post(url, headers=None):
        return _Resp({"code": 0, "data": {}})

    monkeypatch.setattr(svc._http, "post", fake_post)

    with pytest.raises(OAuth2ValidationError, match="access_token"):
        await svc.exchange_code(_cfg(), "C", "https://app/loginsso", "0", 1)
    await svc.close()


@pytest.mark.asyncio
async def test_exchange_code_normalizes_http_error_without_leaking_secret(monkeypatch):
    svc = OAuth2Service()

    async def fake_post(url, headers=None):
        return _Resp({}, status_code=500)

    monkeypatch.setattr(svc._http, "post", fake_post)

    with pytest.raises(OAuth2Error, match="HTTP 500") as exc_info:
        await svc.exchange_code(_cfg(), "C", "https://app/loginsso", "0", 1)
    # The secret must never appear in the exception message.
    assert "csec" not in str(exc_info.value)
    await svc.close()


# ── fetch_userinfo ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_userinfo_sends_bearer_tenant_organize_and_carryrole(monkeypatch):
    svc = OAuth2Service()
    captured = {}

    async def fake_get(url, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        return _Resp(_official_userinfo())

    monkeypatch.setattr(svc._http, "get", fake_get)

    userinfo = await svc.fetch_userinfo(_cfg(), "AT", tenant_id=1, organize_id=100)

    assert userinfo["id"] == 1
    assert userinfo["roleCodes"] == ["super_admin"]
    assert captured["headers"]["Authorization"] == "Bearer AT"
    assert captured["headers"]["tenant-id"] == "1"
    assert captured["headers"]["organize-id"] == "100"
    assert "carryRole=true" in captured["url"]
    await svc.close()


# ── authenticate_callback ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticate_callback_maps_official_ipd_response(monkeypatch):
    svc = OAuth2Service()
    monkeypatch.setattr(svc._http, "post", AsyncMock(return_value=_Resp({"code": 0, "data": {"access_token": "AT"}})))
    monkeypatch.setattr(svc._http, "get", AsyncMock(return_value=_Resp(_official_userinfo())))

    identity = await svc.authenticate_callback("shanghai-electric-ipd", _cfg(), "C", "https://app/loginsso", "0", tenant_id=1, organize_id=100)

    assert identity.provider == "shanghai-electric-ipd"
    assert identity.subject == "1"  # id field, stringified
    assert identity.email == "1@qq.com"
    assert identity.email_verified is False  # oauth2 cannot assert verification
    assert identity.name == "test"
    assert identity.claims["roleCodes"] == ["super_admin"]
    assert identity.claims["dept"]["name"] == "研发部"
    await svc.close()


@pytest.mark.asyncio
async def test_subject_field_is_configurable(monkeypatch):
    svc = OAuth2Service()
    monkeypatch.setattr(svc._http, "post", AsyncMock(return_value=_Resp({"code": 0, "data": {"access_token": "AT"}})))
    monkeypatch.setattr(svc._http, "get", AsyncMock(return_value=_Resp(_official_userinfo())))

    identity = await svc.authenticate_callback("p", _cfg(subject_field="workId"), "C", "r", "0", tenant_id=1, organize_id=100)
    assert identity.subject == "03000111"
    await svc.close()


@pytest.mark.asyncio
async def test_namespace_with_tenant_prefixes_subject(monkeypatch):
    svc = OAuth2Service()
    monkeypatch.setattr(svc._http, "post", AsyncMock(return_value=_Resp({"code": 0, "data": {"access_token": "AT"}})))
    monkeypatch.setattr(svc._http, "get", AsyncMock(return_value=_Resp(_official_userinfo())))

    identity = await svc.authenticate_callback("p", _cfg(namespace_with_tenant=True), "C", "r", "0", tenant_id=7, organize_id=100)
    assert identity.subject == "7:1"  # tenant:subject
    await svc.close()


@pytest.mark.asyncio
async def test_email_synthesis_when_email_absent(monkeypatch):
    svc = OAuth2Service()
    monkeypatch.setattr(svc._http, "post", AsyncMock(return_value=_Resp({"code": 0, "data": {"access_token": "AT"}})))
    userinfo = _official_userinfo()
    userinfo["data"]["email"] = ""
    monkeypatch.setattr(svc._http, "get", AsyncMock(return_value=_Resp(userinfo)))

    identity = await svc.authenticate_callback(
        "p",
        _cfg(email_synthesis_pattern="{id}@ipd.shanghai-electric.com", require_verified_email=False),
        "C",
        "r",
        "0",
        tenant_id=1,
        organize_id=100,
    )
    assert identity.email == "1@ipd.shanghai-electric.com"
    assert identity.claims["_email_synthesized"] is True
    await svc.close()


@pytest.mark.asyncio
async def test_email_synthesis_off_by_default_yields_empty_email(monkeypatch):
    """ASSUMPTION A3: synthesis off by default; empty email surfaces for provisioning to reject."""
    svc = OAuth2Service()
    monkeypatch.setattr(svc._http, "post", AsyncMock(return_value=_Resp({"code": 0, "data": {"access_token": "AT"}})))
    userinfo = _official_userinfo()
    userinfo["data"]["email"] = ""
    monkeypatch.setattr(svc._http, "get", AsyncMock(return_value=_Resp(userinfo)))

    identity = await svc.authenticate_callback("p", _cfg(), "C", "r", "0", tenant_id=1, organize_id=100)
    assert identity.email == ""
    assert identity.claims["_email_synthesized"] is True
    await svc.close()


# ── build_authorization_url ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_authorization_url_uses_configured_endpoint_and_params():
    svc = OAuth2Service()
    url = svc.build_authorization_url(_cfg(), "cid", "https://app/loginsso", "state123")
    assert url.startswith("https://portal.example.com/login?")
    assert "clientId=cid" in url
    assert "redirectUri=https%3A%2F%2Fapp%2Floginsso" in url
    assert "state=state123" in url
    await svc.close()


@pytest.mark.asyncio
async def test_build_authorization_url_omits_scope_when_none():
    svc = OAuth2Service()
    url = svc.build_authorization_url(_cfg(), "cid", "https://app/loginsso", "s")
    assert "scopes" not in url
    await svc.close()
