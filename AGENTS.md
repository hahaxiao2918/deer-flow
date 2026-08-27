# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, and others) when working with code in this repository. It is the source of truth; the sibling `CLAUDE.md` imports it via `@AGENTS.md`.

It is the **monorepo orientation layer**: it maps the repo and points to the module guides that own the depth. For anything inside a module, read that module's guide:

- **[backend/AGENTS.md](backend/AGENTS.md)** — harness/app split, agent & middleware chain, sandbox, MCP, skills, memory, IM channels, persistence/migrations, config system, test layout.
- **[frontend/AGENTS.md](frontend/AGENTS.md)** — Next.js App Router layout, thread/streaming data flow, code style, commands.

## What is DeerFlow

DeerFlow is a LangGraph-based AI super-agent system: a backend "super agent" with sandboxed execution, persistent memory, subagent delegation, and extensible tools (built-in, MCP, community), all per-thread isolated; a Next.js chat frontend; and IM bridges (Feishu, Slack, Telegram, Discord, DingTalk) into the same agent through the Gateway.

## Service Topology

A single `make dev` / Docker stack runs four cooperating services:

| Service         | Port (`make dev`; Docker) | Role                                                                |
| --------------- | ------------------------- | ------------------------------------------------------------------- |
| **Nginx**       | `12026`; `2026`           | Unified reverse-proxy entry — open this in the browser               |
| **Gateway API** | `18001`; `8001`           | FastAPI REST API + embedded LangGraph-compatible agent runtime       |
| **Frontend**    | `13000`; `3000`           | Next.js web interface                                                |
| **Provisioner** | `8002`                    | Optional — only when sandbox is configured for provisioner/K8s mode  |

Nginx serves the frontend, proxies `/api/langgraph/*` to the Gateway's LangGraph runtime (rewritten to native `/api/*` routes), and passes other `/api/*` straight to the Gateway REST routers (detail in [backend/AGENTS.md](backend/AGENTS.md)). It compresses HTML and configured textual assets, deliberately leaving SSE, fonts, images, audio, and video uncompressed at the proxy layer.

Both compose files publish the entry as `"${BIND_HOST:-127.0.0.1}:${PORT:-2026}:2026"` — **loopback by default**; a bare `"${PORT}:2026"` binds `0.0.0.0`. The root `PORT` value is Docker ingress only; local orchestration pins Next.js to `13000` (`FRONTEND_PORT` in `scripts/serve.sh`), so loading `.env` cannot make `make dev` wait on the wrong port. Any new published port needs an explicit bind address — `backend/tests/test_compose_default_bind_host.py` pins this for every service in both compose files.

Local `make dev`: browse to `http://localhost:12026`. Docker/production: `http://localhost:2026`.

## Repository Map

```
deer-flow/
├── Makefile / scripts/             # Root orchestration: full stack + configure/doctor/deploy/setup wizards
├── config.example.yaml             # Template → copy to config.yaml (gitignored) at repo root
├── extensions_config.example.json  # Template → extensions_config.json (gitignored): MCP servers + skills
├── backend/                        # Python: packages/harness (deerflow.*), packages/extension-api, app/ (Gateway + IM)
├── frontend/                       # Next.js frontend (pnpm)
├── docker/                         # compose files, nginx config, provisioner
├── skills/                         # public/ (committed), custom/ (gitignored); managed packs in .deer-flow/integrations/skills/
├── contracts/                      # Cross-component JSON contracts (subagent status, skill review)
├── examples/deerflow-extension-example/  # Reference extension demonstrating all contribution kinds
├── tests/                          # Root-level tests (tests/skills/ — public skill tests)
└── docs/                           # Cross-cutting docs, plans, design notes
```

Third-party extensions load from the top-level `plugins:` list in `config.yaml` — operator-controlled on purpose: that list causes code to be imported, so it stays out of the API-writable `extensions_config.json`. Extensions can contribute middleware, task lifecycle, system-model observers, Gateway services, and FastAPI HTTP routers; manage them with `deerflow extensions ...` or the `make extension-*` wrappers. Every mutation requires a Gateway restart, and build hooks + extension code run with Gateway privileges — only trusted operator sources belong here. Transaction/lock discipline and the contribution contract: [the extensions guide](backend/packages/harness/deerflow/extensions/AGENTS.md).

Runtime config lives at the repo root: `config.yaml` (main app) + `extensions_config.json` (MCP servers + skills), both editable at runtime via the Gateway API. Config schema and resolution order: [backend/AGENTS.md](backend/AGENTS.md).

Skill quality review: `skills/public/skill-reviewer/` is the built-in read-only reviewer (harness `review_skill_package` tool, contracts in `contracts/skill_review/`); see backend/AGENTS.md for the non-activation, SkillScan, and `skill-creator` ownership boundaries.

Scheduled tasks: workspace page `/workspace/scheduled-tasks` + background scheduler gated by `config.yaml -> scheduler.enabled`. Scheduled runs are intentionally non-interactive — `ask_clarification` is excluded when `context.non_interactive=true`, honored only for internally-authenticated callers (client-supplied values are dropped). Busy occurrences persist as `queued`; `launching` is a short lease-fenced claim; waiting rows never count against `max_concurrent_runs`. `scheduler.recursion_limit` (default 1000, clamped by `max_recursion_limit`) is read at dispatch, so a YAML edit applies to the next scheduled run without a Gateway restart.

## Commands: Root vs. Module

**Root `make` targets drive the whole stack** (from the repo root): `make setup` (interactive wizard) · `make config` (copy templates) · `make install` · `make dev` (hot-reload) · `make start` / `make stop` · `make up` / `make down` (production Docker) · `make docker-start` / `docker-stop` / `docker-logs` (Docker dev) · `make doctor` · `make check` · `make support-bundle` · `make config-upgrade` · `make extension-{install,list,enable,disable,remove}`. Full list: `make help`.

First-time setup order: `make config` → `make install` → `make dev`. Without `config.yaml` present, services fail to boot.

**Per-module commands** (run inside the module):

```bash
cd backend && make dev        # Gateway API with reload (port 8001)
cd backend && make test       # Backend test suite
cd backend && make lint       # ruff check; make format to fix

cd frontend && pnpm dev       # Dev server with Turbopack (port 3000)
cd frontend && pnpm check     # Lint + type check (run before committing)
cd frontend && pnpm test      # Unit tests
```

**Single test**: backend `cd backend && python -m pytest tests/path/test.py::test_func -q`; frontend `cd frontend && pnpm rstest run <pattern>`.

**Logs**: Docker stack — `make docker-logs`. Local `make dev` — per-service panes; Turbopack errors surface in the browser console, backend tracebacks in the Gateway terminal.

Production startup uses the image's pre-built Python environment (`uv run --no-sync`), gives the Gateway a real `/health` probe, and makes `make up` wait for that probe before printing success — a readiness failure must surface Compose status and recent Gateway logs instead of claiming the stack is running.

Rule of thumb: **root `make` = the full application**; **backend/Makefile and frontend `pnpm` = per-module work**. Host-side pnpm consumers (root/frontend Makefiles, diagnostic scripts) must run through `scripts/pnpm.py` — it preserves direct-pnpm/corepack resolution and keeps diagnostic scripts independent of the caller's cwd.

## Where to Go Next

- Backend work → **[backend/AGENTS.md](backend/AGENTS.md)**; Frontend work → **[frontend/AGENTS.md](frontend/AGENTS.md)**
- Setup & install → [Install.md](Install.md), [CONTRIBUTING.md](CONTRIBUTING.md)
- Project overview & usage → [README.md](README.md) (Shanghai Electric distribution; upstream READMEs archived under [.readme-archive/](.readme-archive/ARCHIVE_NOTE.md) — AI reference only)
- Security policy → [SECURITY.md](SECURITY.md); changes → [CHANGELOG.md](CHANGELOG.md); releases → [RELEASING.md](RELEASING.md)

## Shanghai Electric Distribution and Upstream Sync

This checkout is the Shanghai Electric distribution; the full operational guide is [docs/shanghai-electric-distribution.md](docs/shanghai-electric-distribution.md). Non-negotiable summary:

- **Branch flow** — `main` is the pristine upstream mirror (upstream-only, no 二开); `codex/prod-canonical` is the customization and production trunk (what starl-38 runs); features branch off prod and merge back only after the full regression passes. Keep `origin`, `gitea`, and the deploy host on the same prod SHA.
- **Upstream updates** — the agent owns the whole workflow: fetch `upstream`, fast-forward `main` and push to `origin`/`gitea`, **merge** (never rebase, never piecemeal cherry-pick) `main` into prod, resolve conflicts keeping local customizations, then run the full regression before pushing: `cd backend && make test` and `cd frontend && pnpm install && pnpm check` (`pnpm install` is mandatory after any merge touching `frontend/package.json`). Restart the dev gateway (`make stop && make dev`) after harness changes — `uvicorn --reload` does not watch `packages/harness/`. Never `reset --hard` to update.
- **Remotes** — `origin` = writable fork, `upstream` = read-only bytedance/deer-flow (push disabled), `gitea` = internal mirror. Never change remote URLs or force-push without explicit user approval.
- **Production deployment** — `scripts/deploy.sh` is the only supported entry point for the prod stack; never ad-hoc `docker compose up/down/stop/rm` on `gateway`/`frontend`/`nginx`, and never touch unrelated containers. The script must verify `config.yaml`/`extensions_config.json` are regular host files mounted at the exact resolved paths; a directory at either path is a hard failure.
- **Branding** — the root route and unauthenticated workspace guard redirect to `/loginsso`; the branded login is `frontend/src/app/(auth)/login/page.tsx` with assets in `frontend/public/images/branding/`. Do not restore the upstream landing page or change the SynForge·思铸 identity without a user request.
- **Secrets & config** — never commit tokens, `.env`, `extensions_config.json`, or `.deer-flow` data. Any `config.yaml` shared via gitea must carry every secret as a `$ENV_VAR` placeholder — never write a plaintext secret into it. After upstream updates run `make config-upgrade`. Keep `backend/.deer-flow` out of the Docker build context.
- **Docs & quality gates** — update `README.md` (user-facing) and the relevant `AGENTS.md` (architecture) in the same change set; register dev-only flags in `docs/production-deployment.md`; backend TDD is mandatory; run `make format` (backend) / `pnpm check` (frontend) before pushing — CI enforces `ruff format --check`.
