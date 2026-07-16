"""FastMCP HTTP entry point for Deerflow's internal patent-data sidecar."""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from . import __version__
from .config import load_settings
from .tools import data_capabilities, data_cost_estimate, patent_get_records, patent_search

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    settings = load_settings()
    auth = None
    if settings.mcp_token:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

        tokens = [token.strip() for token in settings.mcp_token.split(",") if token.strip()]
        auth = StaticTokenVerifier(tokens={token: {"client_id": f"deerflow-{index}"} for index, token in enumerate(tokens)})

    mcp = FastMCP(name="deerflow-patent-data-mcp", version=__version__, auth=auth, instructions="Cost-governed external patent facts for Deerflow. Use data_cost_estimate before large record requests. Never infer facts that tools did not return.")
    for tool in (data_capabilities, data_cost_estimate, patent_search, patent_get_records):
        mcp.add_tool(tool)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):  # noqa: ANN001
        from starlette.responses import JSONResponse

        return JSONResponse({"service": "deerflow-patent-data-mcp", "version": __version__, "status": "ok", "has_upstream_key": bool(settings.zhihuiya_api_key), "auth_enabled": bool(settings.mcp_token)})

    return mcp


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    create_server().run(transport="http", host="0.0.0.0", port=settings.server_port, path="/mcp")
