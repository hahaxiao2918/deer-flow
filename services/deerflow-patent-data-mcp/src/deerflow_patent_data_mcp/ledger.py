"""Persistent, fail-closed project budget reservations for billable API calls."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def _cents(value: float) -> int:
    return round(value * 100)


def _money(cents: int) -> float:
    return round(cents / 100, 2)


@dataclass(frozen=True)
class Reservation:
    ok: bool
    reservation_id: int | None = None
    reason: str = ""
    budget_limit: float | None = None
    budget_remaining: float | None = None


class BudgetLedger:
    """SQLite ledger. A failed upstream call remains charged conservatively."""

    def __init__(self, path: str, project_budgets_json: str) -> None:
        self._path = path
        self._budget_cents = self._parse_budgets(project_budgets_json)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _parse_budgets(raw: str) -> dict[str, int]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("DATA_MCP_PROJECT_BUDGETS_JSON must be a JSON object") from exc
        if not isinstance(data, dict):
            raise ValueError("DATA_MCP_PROJECT_BUDGETS_JSON must be a JSON object")
        result: dict[str, int] = {}
        for project_id, value in data.items():
            if not isinstance(project_id, str) or not project_id.strip() or not isinstance(value, (int, float)) or value < 0:
                raise ValueError("project budget entries must be non-negative numeric values")
            result[project_id] = _cents(float(value))
        return result

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5, isolation_level=None)

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS reservations (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, operation TEXT NOT NULL, cost_cents INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT, outcome TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS cache_entries (cache_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, expires_at INTEGER NOT NULL, created_at TEXT NOT NULL)")
        finally:
            conn.close()

    def quote_budget(self, project_id: str, estimated_cost: float) -> Reservation:
        cap = self._budget_cents.get(project_id)
        if cap is None:
            return Reservation(ok=False, reason="budget_unconfigured")
        conn = self._connect()
        try:
            row = conn.execute("SELECT COALESCE(SUM(cost_cents), 0) FROM reservations WHERE project_id=? AND status IN ('reserved','completed')", (project_id,)).fetchone()
        finally:
            conn.close()
        remaining = cap - int(row[0])
        if _cents(estimated_cost) > remaining:
            return Reservation(ok=False, reason="budget_exceeded", budget_limit=_money(cap), budget_remaining=_money(max(remaining, 0)))
        return Reservation(ok=True, budget_limit=_money(cap), budget_remaining=_money(remaining))

    def reserve(self, project_id: str, operation: str, estimated_cost: float) -> Reservation:
        if not project_id.strip():
            return Reservation(ok=False, reason="project_id_required")
        cap = self._budget_cents.get(project_id)
        if cap is None:
            return Reservation(ok=False, reason="budget_unconfigured")
        cost = _cents(estimated_cost)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            used = int(conn.execute("SELECT COALESCE(SUM(cost_cents), 0) FROM reservations WHERE project_id=? AND status IN ('reserved','completed')", (project_id,)).fetchone()[0])
            remaining = cap - used
            if cost > remaining:
                conn.execute("ROLLBACK")
                return Reservation(ok=False, reason="budget_exceeded", budget_limit=_money(cap), budget_remaining=_money(max(remaining, 0)))
            cursor = conn.execute("INSERT INTO reservations(project_id,operation,cost_cents,status,created_at) VALUES(?,?,?,?,?)", (project_id, operation, cost, "reserved", datetime.now(UTC).isoformat()))
            conn.execute("COMMIT")
        finally:
            conn.close()
        return Reservation(ok=True, reservation_id=int(cursor.lastrowid), budget_limit=_money(cap), budget_remaining=_money(remaining - cost))

    def complete(self, reservation_id: int | None, outcome: str) -> None:
        if reservation_id is None:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE reservations SET status='completed', completed_at=?, outcome=? WHERE id=? AND status='reserved'", (datetime.now(UTC).isoformat(), outcome, reservation_id))
        finally:
            conn.close()

    def get_cache(self, cache_key: str) -> object | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT payload_json FROM cache_entries WHERE cache_key=? AND expires_at>?", (cache_key, int(time.time()))).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            conn.close()

    def put_cache(self, cache_key: str, payload: object, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        conn = self._connect()
        try:
            conn.execute("INSERT INTO cache_entries(cache_key,payload_json,expires_at,created_at) VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json, expires_at=excluded.expires_at, created_at=excluded.created_at", (cache_key, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), int(time.time()) + ttl_seconds, datetime.now(UTC).isoformat()))
        finally:
            conn.close()
