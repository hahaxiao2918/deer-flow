"""Read-only, content-free run facts for the central IP portal."""

from __future__ import annotations

import base64
import os
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select

from deerflow.persistence.engine import get_session_factory
from deerflow.persistence.run.model import RunRow
from deerflow.persistence.user.model import UserRow

router = APIRouter(prefix="/api/internal/portal-analytics", tags=["portal-analytics"])
_TOKEN_ENV = "DEER_FLOW_PORTAL_ANALYTICS_TOKEN"
_TERMINAL_STATUSES = ("success", "error", "timeout", "interrupted")


class PortalAnalyticsFact(BaseModel):
    source_id: str
    employee_code: str | None = None
    occurred_at: datetime
    action: str = "agent_run"
    succeeded: bool
    duration_ms: int | None = Field(default=None, ge=0)
    model_name: str | None = None
    total_tokens: int | None = Field(default=None, ge=0)


class PortalAnalyticsPage(BaseModel):
    items: list[PortalAnalyticsFact]
    next_cursor: str
    has_more: bool


def _authorize(authorization: str | None) -> None:
    expected = os.environ.get(_TOKEN_ENV, "")
    supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not expected:
        raise HTTPException(503, "Portal analytics export is not configured")
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(401, "Invalid portal analytics token")


def _encode_cursor(updated_at: datetime, run_id: str) -> str:
    aware = updated_at.replace(tzinfo=UTC) if updated_at.tzinfo is None else updated_at
    raw = f"{aware.astimezone(UTC).isoformat()}\n{run_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, str] | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
        timestamp, run_id = raw.split("\n", 1)
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None or not run_id or len(run_id) > 64:
            raise ValueError
        return parsed, run_id
    except (ValueError, UnicodeError):
        raise HTTPException(422, "Invalid analytics cursor") from None


def _duration_ms(created_at: datetime, updated_at: datetime) -> int:
    created = created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at
    updated = updated_at.replace(tzinfo=UTC) if updated_at.tzinfo is None else updated_at
    return max(0, int((updated - created).total_seconds() * 1000))


@router.get("/runs", response_model=PortalAnalyticsPage)
async def portal_run_facts(
    cursor: str = Query(default="", max_length=2000),
    limit: int = Query(default=500, ge=1, le=500),
    authorization: str | None = Header(default=None),
) -> PortalAnalyticsPage:
    _authorize(authorization)
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(503, "Portal analytics requires SQL persistence")
    decoded = _decode_cursor(cursor)
    statement = select(RunRow, UserRow.oauth_id).outerjoin(UserRow, UserRow.id == RunRow.user_id).where(RunRow.status.in_(_TERMINAL_STATUSES)).order_by(RunRow.updated_at.asc(), RunRow.run_id.asc()).limit(limit + 1)
    if decoded:
        timestamp, run_id = decoded
        statement = statement.where(or_(RunRow.updated_at > timestamp, and_(RunRow.updated_at == timestamp, RunRow.run_id > run_id)))
    async with session_factory() as session:
        rows = (await session.execute(statement)).all()
    has_more = len(rows) > limit
    selected = rows[:limit]
    items = [
        PortalAnalyticsFact(
            source_id=row.run_id,
            employee_code=oauth_id,
            occurred_at=row.updated_at,
            succeeded=row.status == "success",
            duration_ms=_duration_ms(row.created_at, row.updated_at),
            model_name=row.model_name,
            total_tokens=max(0, row.total_tokens),
        )
        for row, oauth_id in selected
    ]
    next_cursor = _encode_cursor(selected[-1][0].updated_at, selected[-1][0].run_id) if selected else cursor
    return PortalAnalyticsPage(items=items, next_cursor=next_cursor, has_more=has_more)
