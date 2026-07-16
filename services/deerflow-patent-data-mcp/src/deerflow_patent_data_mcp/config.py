"""Runtime settings. Credentials stay in the service environment only."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    zhihuiya_api_key: str
    zhihuiya_base_url: str
    server_port: int
    mcp_token: str
    http_timeout: float
    state_path: str
    project_budgets_json: str
    cache_ttl_seconds: int


def load_settings() -> Settings:
    return Settings(
        zhihuiya_api_key=os.getenv("ZHIHUIYA_API_KEY", "").strip(),
        zhihuiya_base_url=os.getenv("ZHIHUIYA_BASE_URL", "https://connect.zhihuiya.com").rstrip("/"),
        server_port=int(os.getenv("SERVER_PORT", "8092")),
        mcp_token=os.getenv("MCP_TOKEN", "").strip(),
        http_timeout=float(os.getenv("HTTP_TIMEOUT", "30")),
        state_path=os.getenv("DATA_MCP_STATE_PATH", "/data/deerflow-patent-data-mcp.sqlite3").strip(),
        project_budgets_json=os.getenv("DATA_MCP_PROJECT_BUDGETS_JSON", "{}").strip() or "{}",
        cache_ttl_seconds=int(os.getenv("DATA_MCP_CACHE_TTL_SECONDS", "2592000")),
    )
