#!/usr/bin/env python3
"""Fail-fast checks before enabling Deerflow's patent-data MCP sidecar."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


SKILLS = (
    "evidence-based-labeling",
    "applicant-tech-patent-retrieval",
    "technology-insight-analysis",
    "tech-evolution-analysis",
    "black-swan-tech-radar",
)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        fail(f"{name} is required")
    return value


def budget_map(raw: str) -> dict[str, float]:
    try:
        value: Any = json.loads(raw)
    except json.JSONDecodeError:
        fail("DEERFLOW_PATENT_MCP_PROJECT_BUDGETS_JSON must be valid JSON")
    if not isinstance(value, dict) or not value:
        fail("DEERFLOW_PATENT_MCP_PROJECT_BUDGETS_JSON must be a non-empty object")
    result: dict[str, float] = {}
    for project_id, amount in value.items():
        if not isinstance(project_id, str) or not project_id.strip() or not isinstance(amount, (int, float)) or amount < 0:
            fail("each project budget must have a non-empty string id and a non-negative numeric amount")
        result[project_id] = float(amount)
    return result


def main() -> None:
    require("ZHIHUIYA_API_KEY")
    token = require("DEERFLOW_PATENT_MCP_TOKEN")
    if len(token) < 24:
        fail("DEERFLOW_PATENT_MCP_TOKEN must be at least 24 characters")
    budgets = budget_map(require("DEERFLOW_PATENT_MCP_PROJECT_BUDGETS_JSON"))

    config_path = Path(os.getenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", "extensions_config.json"))
    if not config_path.is_file():
        fail(f"runtime extension config is missing: {config_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        fail(f"runtime extension config is invalid JSON: {config_path}")
    mcp = (config.get("mcpServers") or {}).get("patent-data")
    if not isinstance(mcp, dict) or not mcp.get("enabled"):
        fail("runtime config must contain enabled mcpServers.patent-data")
    if mcp.get("url") != "http://patent-data-mcp:8092/mcp":
        fail("patent-data MCP URL must remain internal")
    if mcp.get("headers", {}).get("Authorization") != "$DEERFLOW_PATENT_MCP_AUTHORIZATION":
        fail("patent-data MCP must use the complete dedicated authorization placeholder")
    disabled = [name for name in SKILLS if not (config.get("skills") or {}).get(name, {}).get("enabled")]
    print(f"PASS: budgets={len(budgets)}; mcp=patent-data; disabled_skills={len(disabled)}")
    if disabled:
        print("INFO: disabled skills=" + ",".join(disabled))


if __name__ == "__main__":
    main()
