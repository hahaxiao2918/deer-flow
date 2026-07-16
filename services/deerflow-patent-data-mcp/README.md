# Deerflow Patent Data MCP

Internal HTTP MCP sidecar for Deerflow patent workflows. It exposes only external facts and cost controls; it does not call an LLM.

## M1A scope

- P002 search, P012 bibliography, and D114 batch text only.
- Project-budget reservations and persistent TTL cache in SQLite.
- No legal/family/citation, AMiner, vendor AI, or public port.

## Required runtime configuration

```text
ZHIHUIYA_API_KEY=<secret, service environment only>
ZHIHUIYA_BASE_URL=https://connect.zhihuiya.com
MCP_TOKEN=<internal MCP bearer token>
DATA_MCP_STATE_PATH=/data/deerflow-patent-data-mcp.sqlite3
DATA_MCP_PROJECT_BUDGETS_JSON={"demo-project":50.0}
DATA_MCP_CACHE_TTL_SECONDS=2592000
```

`DATA_MCP_PROJECT_BUDGETS_JSON` is operator configuration. An unconfigured project is denied before a billable upstream request. The SQLite path must be mounted on a dedicated persistent internal volume.

## Deerflow activation

The tracked compose file requires two new operator variables before it will start the sidecar:

```text
DEERFLOW_PATENT_MCP_TOKEN=<new internal bearer token; do not reuse a historical MCP token>
DEERFLOW_PATENT_MCP_AUTHORIZATION=Bearer <the same internal token>
DEERFLOW_PATENT_MCP_PROJECT_BUDGETS_JSON={"approved-project-id":10.00}
```

`ZHIHUIYA_API_KEY` remains in the sidecar environment only. The Gateway receives only `DEERFLOW_PATENT_MCP_TOKEN` and the complete `DEERFLOW_PATENT_MCP_AUTHORIZATION` header value so that it can call `http://patent-data-mcp:8092/mcp` on the private `deer-flow` network. The complete header variable is required because Deerflow expands environment variables only when the whole configured header value is a variable reference.

The tracked `extensions_config.example.json` contains a disabled `patent-data` entry. After the sidecar is healthy, an operator must copy that entry into the ignored runtime `extensions_config.json`, change `enabled` to `true`, and restart/reload the Gateway using the normal deployment procedure. This deliberate last step prevents an unreviewed branch checkout from changing the active MCP registry.

Before that change, run `scripts/preflight.py` from the repository root with the production environment loaded. It validates the dedicated token, non-empty project budget map, internal-only MCP URL, and runtime Skill states without making an upstream request.

## External MCP reverse proxy

When deployed on the shared proxy host, the sidecar also joins `web-network` so the host-level `nginx-proxy` can reach it by the Docker name `patent-data-mcp`. Install `nginx/ipmcp.conf` as `/home/share/nginx/conf.d/ipmcp.conf`, validate it in `nginx-proxy`, then reload that container. It serves both `http://ipmcp.server.starlove.top/mcp` and HTTPS. The public route still requires the dedicated MCP bearer token; use HTTPS for any client outside the trusted internal network.

## Validation sequence

1. Install service and test dependencies in an isolated environment; run `pytest -q`.
2. Build the container and import `create_server()` without credentials.
3. Start only on the internal `deer-flow` network; do not publish a host port.
4. Configure a small project budget and make one D114 smoke call using a public topic.
5. Register the HTTP MCP in Deerflow only after the service health check and record the actual generated tool names before creating Skill allowlists.
