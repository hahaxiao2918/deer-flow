"""Contract tests for the content-free central portal analytics endpoint."""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.gateway.routers import portal_analytics
from deerflow.persistence.base import Base
from deerflow.persistence.run.model import RunRow
from deerflow.persistence.user.model import UserRow


def _run(coro):
    return asyncio.run(coro)


def test_portal_analytics_auth_cursor_and_redaction(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'portal.db'}", poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as session:
            session.add(UserRow(id="00000000-0000-0000-0000-000000000001", email="user@example.com", system_role="user", oauth_provider="ipd", oauth_id="030T0170"))
            session.add_all(
                [
                    RunRow(
                        run_id="r1",
                        thread_id="t1",
                        user_id="00000000-0000-0000-0000-000000000001",
                        status="success",
                        model_name="safe-model",
                        total_tokens=12,
                        first_human_message="SECRET PROMPT",
                        last_ai_message="SECRET ANSWER",
                        error="SECRET ERROR",
                        created_at=now - timedelta(seconds=5),
                        updated_at=now - timedelta(seconds=4),
                    ),
                    RunRow(run_id="r2", thread_id="t1", user_id="00000000-0000-0000-0000-000000000001", status="error", total_tokens=0, error="PRIVATE STACK", created_at=now - timedelta(seconds=3), updated_at=now - timedelta(seconds=1)),
                    RunRow(run_id="active", thread_id="t2", user_id=None, status="running", created_at=now, updated_at=now),
                ]
            )
            await session.commit()

    _run(seed())
    monkeypatch.setenv("DEER_FLOW_PORTAL_ANALYTICS_TOKEN", "test-token")
    monkeypatch.setattr(portal_analytics, "get_session_factory", lambda: sf)
    app = FastAPI()
    app.include_router(portal_analytics.router)
    client = TestClient(app)
    assert client.get("/api/internal/portal-analytics/runs").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    first = client.get("/api/internal/portal-analytics/runs?limit=1", headers=headers)
    assert first.status_code == 200
    page = first.json()
    assert page["has_more"] is True
    assert page["items"][0]["employee_code"] == "030T0170"
    assert "SECRET" not in first.text and "prompt" not in first.text.lower()
    second = client.get("/api/internal/portal-analytics/runs", params={"cursor": page["next_cursor"], "limit": 10}, headers=headers)
    assert [item["source_id"] for item in second.json()["items"]] == ["r2"]
    assert client.get("/api/internal/portal-analytics/runs?cursor=bad", headers=headers).status_code == 422
    _run(engine.dispose())
