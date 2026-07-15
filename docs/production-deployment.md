# Production Deployment Checklist — Shanghai Electric Distribution

This checklist covers the extra steps and removals required when moving from the local `DEER_FLOW_AUTH_DISABLED=1` development setup to a real production deployment for the Shanghai Electric distribution.

> **Rule of thumb:** any parameter, flag, or config value that exists only to make local development easier must be removed or replaced before production. When you add such a parameter, document it here immediately.

---

## 1. Authentication — Remove auth-disabled mode

Local development currently starts the stack with:

```bash
DEER_FLOW_AUTH_DISABLED=1 make dev-daemon
```

**Production:**

- Do **not** set `DEER_FLOW_AUTH_DISABLED`.
- Use `make start` or `make up` (Docker production) instead of `make dev` / `make dev-daemon`.
- Configure real authentication (local accounts, SSO, or the enterprise identity provider).
- Verify that `app/gateway/auth_disabled.py` behavior is bypassed: `is_auth_disabled()` must return `False`.

**Why it matters:** `DEER_FLOW_AUTH_DISABLED=1` makes every request run as a synthetic admin user (`default`). Among other things, artifact file resolution falls back to the `default` user bucket, which can break access to threads created under real user IDs. In production this would be both a functional and security issue.

---

## 2. Runtime Configuration

### `config.yaml`

- Replace development model endpoints and keys with production credentials.
- Confirm `log_level` is appropriate for production (`info` or `warning`).
- Enable production rate limits / token budgets if required.
- Do **not** use the example file verbatim; copy from `config.example.yaml` and fill in real values.

### `extensions_config.json`

- Remove all example MCP servers (`github`, `postgres`, etc.) unless they are explicitly needed and configured.
- Add production MCP servers with real credentials.
- Review the `skills` block: default-disabled skills in the example template (e.g. `skill-reviewer`, `skill-creator`, media generators) should be enabled only if the business requires them.

---

## 3. Shanghai Electric Branding & Customization

These customizations live on the `codex/shanghai-electric` branch and must be preserved:

- **Login page**: `frontend/src/app/(auth)/login/page.tsx`
- **Brand assets**: `frontend/public/images/branding/`
- **Root redirect**: `/` redirects to `/login`
- **Workspace nav**: only Settings in the lower-left dropdown

Do **not** restore the upstream public landing page or replace Shanghai Electric identity without an explicit request.

---

## 4. Data Persistence

- Ensure `.deer-flow/` (or `DEER_FLOW_HOME` if overridden) is mounted on a persistent volume.
- Confirm `users/`, `threads/`, and `memory/` directories survive container restarts.
- Set correct filesystem permissions so the Gateway process can read/write.

---

## 5. Skills & Defaults

- The example `extensions_config.json` disables several public skills by default. Before production, review which skills should actually be enabled for end users.
- Any skill with `allowed-tools` restrictions (e.g. `skill-reviewer`) should only be enabled when users explicitly need that workflow.

---

## 6. Security & Secrets

- Never commit `config.yaml`, `extensions_config.json`, `.env`, or `.deer-flow/` data.
- Rotate any credentials that were used during local development.
- Confirm `github token.md` and similar local notes are not in the deployed image.

---

## 7. Pre-flight Command Reference

```bash
# Local development (auth disabled, hot reload)
DEER_FLOW_AUTH_DISABLED=1 make dev-daemon

# Production local foreground
make start

# Production Docker
make up
```

---

## Adding New Dev-Only Parameters

If you introduce a new environment variable, config flag, or shortcut that is only safe for local development, add a row here:

| Parameter | Local value | Production value | Where to set | Rationale |
|-----------|-------------|------------------|--------------|-----------|
| `DEER_FLOW_AUTH_DISABLED` | `1` | unset / absent | shell env | Bypasses auth in dev; must be off in production. |

This table is the source of truth for operations handoff.
