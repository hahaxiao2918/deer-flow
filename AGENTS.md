# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, and others) when working with code in this repository. It is the source of truth; the sibling `CLAUDE.md` imports it via `@AGENTS.md`.

It is the **monorepo orientation layer**: it maps the whole repo and points to the
module guides that own the depth. For anything inside a module, read that module's
guide rather than expecting full detail here:

- **[backend/AGENTS.md](backend/AGENTS.md)** — backend depth: harness/app split, agent &
  middleware chain, sandbox, MCP, skills, memory, IM channels, persistence/migrations,
  config system, test layout.
- **[frontend/AGENTS.md](frontend/AGENTS.md)** — frontend depth: Next.js App Router layout,
  thread/streaming data flow, code style, commands.

## What is DeerFlow

DeerFlow is a LangGraph-based AI super-agent system with a full-stack architecture. The
backend runs a "super agent" with sandboxed execution, persistent memory, subagent
delegation, and extensible tools (built-in, MCP, community), all per-thread isolated. The
frontend is a Next.js chat UI. External IM platforms (Feishu, Slack, Telegram, Discord,
DingTalk) bridge into the same agent through the Gateway.

## Service Topology

A single `make dev` / Docker stack runs four cooperating services:

| Service         | Port                                                              | Role                                                                 |
| --------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Nginx**       | `12026` (`make dev`); `2026` (Docker)                            | Unified reverse-proxy entry point — open this in the browser        |
| **Gateway API** | `18001` (`make dev`); `8001` (Docker)                            | FastAPI REST API + embedded LangGraph-compatible agent runtime      |
| **Frontend**    | `13000` (`make dev`); `3000` (Docker)                            | Next.js web interface                                               |
| **Provisioner** | `8002`                                                            | Optional — only when sandbox is configured for provisioner/K8s mode |

Nginx is the single public entry: it serves the frontend and proxies `/api/langgraph/*`
to the Gateway's LangGraph runtime, rewriting it to Gateway's native `/api/*` routes; all
other `/api/*` go straight to the Gateway REST routers. See
[backend/AGENTS.md](backend/AGENTS.md) for the runtime and router detail.

For the current local `make dev` setup, browse to `http://localhost:12026`.
Production and Docker Compose continue to expose `http://localhost:2026` by default.

## Repository Map

```
deer-flow/
├── Makefile                        # Root orchestration: drives the full stack (dev/start/stop, docker, setup)
├── config.example.yaml             # Template → copy to config.yaml (gitignored) at repo root
├── extensions_config.example.json  # Template → copy to extensions_config.json (gitignored): MCP servers + skills
├── backend/                        # Python backend — see backend/AGENTS.md
│   ├── Makefile                    # Per-module backend commands (dev, gateway, test, lint, migrate-rev)
│   ├── packages/harness/           # deerflow-harness package (import: deerflow.*) — agent framework
│   └── app/                        # FastAPI Gateway + IM channels (import: app.*)
├── frontend/                       # Next.js frontend (pnpm) — see frontend/AGENTS.md
├── docker/                         # docker-compose files, nginx config, provisioner
├── skills/                         # Agent skills: public/ (committed), custom/ (gitignored)
├── contracts/                      # Cross-component JSON contracts (e.g. subagent status, skill review)
├── scripts/                        # Root orchestration scripts invoked by the Makefile (check, configure, doctor, support_bundle, serve, nginx, docker, deploy, setup_wizard)
├── tests/                          # Root-level tests (currently tests/skills/ — public skill tests)
└── docs/                           # Cross-cutting docs, plans, and design notes
```

Runtime config lives at the **repo root**: copy `config.example.yaml` → `config.yaml`
(main app config) and `extensions_config.example.json` → `extensions_config.json` (MCP
servers + skills). Both real files are gitignored and may be edited at runtime via the
Gateway API. Config schema and resolution order are documented in
[backend/AGENTS.md](backend/AGENTS.md).

Skill quality review note:
- `skills/public/skill-reviewer/` is the built-in read-only skill quality reviewer.
  It uses the harness-layer `review_skill_package` tool and contracts in
  `contracts/skill_review/`. Model-visible review data is compact and
  tag-neutralized; full raw payloads stay in tool artifacts. See
  [backend/AGENTS.md](backend/AGENTS.md) for the non-activation, SkillScan, and
  `skill-creator` ownership boundaries.

Scheduled-task note:
- The scheduled-task MVP adds a workspace page at `/workspace/scheduled-tasks` plus a background scheduler service gated by `config.yaml -> scheduler.enabled`.
- Scheduled background runs are intentionally non-interactive: they execute through the normal run lifecycle, but the lead-agent toolset excludes `ask_clarification` when `context.non_interactive=true`. The key is honored only for internally-authenticated callers (the scheduler launch path); client-supplied `context.non_interactive` is dropped.

## Commands: Root vs. Module

**Root `make` targets drive the whole stack** (run from the repo root):

```bash
make setup       # Interactive setup wizard (recommended for new users)
make doctor      # Check configuration and system requirements
make support-bundle  # Generate redacted troubleshooting summary, AI issue draft, and optional zip
make config      # Generate local config files from the examples
make check       # Check that required tools are installed
make install     # Install all dependencies (frontend + backend + pre-commit hooks)
make dev         # Start all services with hot-reload (Gateway + Frontend + Nginx)
make start       # Start all services in production mode (local, optimized)
make stop        # Stop all running services
make up / down   # Build/stop the production Docker stack (browser at localhost:2026)
make docker-start / docker-stop / docker-logs   # Docker development environment
```

Run `make help` for the full list.

**Per-module commands drive a single module** (run inside that module):

```bash
# Backend (see backend/AGENTS.md for the full set)
cd backend && make dev        # Gateway API with reload (port 8001)
cd backend && make test       # Backend test suite
cd backend && make lint       # ruff check
cd backend && make format     # ruff format

# Frontend (see frontend/AGENTS.md for the full set)
cd frontend && pnpm dev       # Dev server with Turbopack (port 3000)
cd frontend && pnpm check     # Lint + type check (run before committing)
cd frontend && pnpm test      # Unit tests
```

Rule of thumb: **root `make` = the full application**; **`backend/Makefile` and `frontend/`
(`pnpm`) = per-module work.**

## Where to Go Next

- Backend work → **[backend/AGENTS.md](backend/AGENTS.md)**
- Frontend work → **[frontend/AGENTS.md](frontend/AGENTS.md)**
- Setup & install → **[Install.md](Install.md)**, **[CONTRIBUTING.md](CONTRIBUTING.md)**
- Project overview & usage → **[README.md](README.md)** (Shanghai Electric distribution).
  The upstream bytedance/deer-flow original README and its translations (`README_zh.md`,
  `README_ja.md`, `README_fr.md`, `README_ru.md`) are archived under
  [`.readme-archive/`](.readme-archive/ARCHIVE_NOTE.md) — AI-agent reference only, not
  user-facing docs.
- Security policy → **[SECURITY.md](SECURITY.md)**
- Changes → **[CHANGELOG.md](CHANGELOG.md)**
- Cutting a release → **[RELEASING.md](RELEASING.md)**

## Cross-Cutting Conventions

These apply repo-wide; module guides own the module-specific detail.

## Shanghai Electric Distribution and Upstream Sync

This checkout is the Shanghai Electric distribution of DeerFlow. It uses a
three-branch flow:

- `main` — pristine upstream mirror; tracks `upstream/main` and receives ONLY
  official upstream updates (no 二开 lands here). `git diff main..codex/prod-canonical`
  is the pure customization delta.
- `codex/prod-canonical` (the "prod" branch) — the long-lived customization and
  production trunk; this is what the deploy host (starl-38) runs.
- feature branches — short-lived, branched off `codex/prod-canonical`, merged
  back only after the full regression passes.

- **Remotes** — `origin` is the writable Fork (`hahaxiao2918/deer-flow`).
  `upstream` is the read-only `bytedance/deer-flow` source. Never change remote
  URLs or force-push without explicit user approval. The local `upstream`
  push URL is deliberately disabled; always push enterprise changes only to
  `origin`.
- **Update workflow** — when the user asks to update, synchronize upstream, or
  continue maintenance, the agent owns the full workflow without asking the
  user to run commands: fetch `upstream`, fast-forward `main` to `upstream/main`
  and push `main` to `origin`/`gitea`, then merge `main` into
  `codex/prod-canonical` (never piecemeal cherry-pick; merge, never rebase),
  retain local customizations while resolving conflicts, run the full
  regression (`cd backend && make test`; `cd frontend && pnpm install && pnpm
  check`) and do not push until it is green — `pnpm check` (lint + tsc) does NOT
  catch stale `node_modules` or unresolvable CSS/package imports, so `pnpm
  install` must run after any merge that touches `frontend/package.json` (and
  `make test`'s `uv run` auto-syncs backend deps). Also restart the local dev
  gateway (`make stop && make dev`) after a merge that changes harness code
  (`packages/harness/`) — `uvicorn --reload` watches only `backend/app/`, not the
  editable harness package, so agent/middleware/skill changes are NOT hot-reloaded
  and a stale gateway will keep running pre-merge code — upstream routinely
  changes shared classes (agent middleware, mcp, skill policy) that local code
  depends on — then commit, push
  `codex/prod-canonical` to `origin`, and rebuild the local Docker stack from
  the repository root with `./scripts/deploy.sh`.
  Never replace this checkout with a fresh upstream clone or use
  `reset --hard` to update it. Ask the user only when a new credential,
  permission, external approval, or a genuinely product-defining conflict is
  required; report all other outcomes after completing the work.
- **Branch discipline** — `codex/prod-canonical` (prod) is the deployment and
  integration trunk; keep `origin`, `gitea`, and the deploy host on the same
  prod SHA. `main` stays a pristine upstream mirror (upstream-only). Develop
  each discrete feature (e.g. SSO) on a short branch off `codex/prod-canonical`
  and merge it back only after the full regression passes — never push
  half-finished work to prod, and never land 二开 on `main`.
  `codex/shanghai-electric` is retired and survives only at archive tag
  `archive/shanghai-electric-pre-convergence-20260722`; it is not a development,
  sync, or release target.
- **Branding ownership** — the root route redirects to `/login`. The branded
  login experience is owned by `frontend/src/app/(auth)/login/page.tsx`; brand
  images live under `frontend/public/images/branding/`. Do not restore the
  original public landing page or replace Shanghai Electric identity without a
  user request.
- **Secrets and runtime state** — never commit tokens, `.env`, `config.yaml`,
  `extensions_config.json`, or `.deer-flow` data. In particular, the local
  `github token.md` is intentionally ignored. Docker builds from the current
  checkout; `docker compose up --build` does not replace source control history.
  Keep `backend/.deer-flow` excluded from the Docker build context: it contains
  live per-thread state and can include sandbox-owned paths that the Docker
  builder cannot read.

- **Production deployment safety** — `scripts/deploy.sh` is the only supported
  entry point for rebuilding, starting, or stopping the production DeerFlow
  stack. Do not run ad-hoc `docker compose up`, `down`, `stop`, or `rm` commands
  for `gateway`, `frontend`, or `nginx`; the deployment script owns the `.env`
  file, host-path exports, sandbox overlay, project name, and mount validation.
  Before considering a deployment successful, the script must confirm that
  `config.yaml` and `extensions_config.json` are regular host files and that the
  running gateway mounts those exact resolved paths. A directory at either file
  path is a hard failure; never delete it or replace it without inspecting its
  contents. Operations in this repository must target only the `deer-flow`
  Compose project and must not stop, restart, or recreate unrelated containers
  such as `ipa-gateway`.

- **Documentation update policy** — keep docs in sync with code: update `README.md` for
  user-facing changes and the relevant `AGENTS.md` for development/architecture changes in
  the same change set.
- **Dev-only parameters must be production-documented** — any environment variable, config
  flag, or shortcut that is only safe for local development (e.g. `DEER_FLOW_AUTH_DISABLED=1`)
  must be added to the production-deployment checklist in `docs/production-deployment.md`
  as part of the same change set. The checklist is the operations handoff source of truth
  for removing these parameters before deploying to production.
- **Test-driven development** — features and bug fixes ship with tests. Backend tests live
  in `backend/tests/` (TDD is mandatory there; see [backend/AGENTS.md](backend/AGENTS.md));
  frontend tests live in `frontend/tests/`.
- **Format before pushing** — run `make format` (backend) / `pnpm check` (frontend). Backend
  CI enforces `ruff format --check`, so formatting must be clean before a push.
