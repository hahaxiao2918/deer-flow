# Shanghai Electric Distribution Guide

This document is the detailed operational guide for the Shanghai Electric
distribution of DeerFlow. The root [AGENTS.md](../AGENTS.md) carries a condensed
rule set; this file owns the full procedures (upstream sync workflow, deployment
safety, config synchronization, branding ownership).

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
- **Branding ownership** — the root route redirects to `/loginsso` (数字底座
  SSO interception; local password login is preserved at `/login` as
  break-glass). The branded login experience is owned by
  `frontend/src/app/(auth)/login/page.tsx`; brand images live under
  `frontend/public/images/branding/`. Do not restore the original public
  landing page or replace Shanghai Electric identity without a user request.
- **Secrets and runtime state** — never commit tokens, `.env`,
  `extensions_config.json`, or `.deer-flow` data. In particular, the local
  `github token.md` is intentionally ignored. Docker builds from the current
  checkout; `docker compose up --build` does not replace source control history.
  Keep `backend/.deer-flow` excluded from the Docker build context: it contains
  live per-thread state and can include sandbox-owned paths that the Docker
  builder cannot read.
- **`config.yaml` 内网 gitea 同步策略(config-gitea-sync 方案)** — 例外:`config.yaml`
  **已纳入版本控制**,dev/prod 共用一份,经 gitea 同步以消除配置漂移。安全前提:(1) 本仓库为
  纯内网私有部署;(2) config.yaml 中所有密钥用 `$ENV_VAR` 占位(已扫描确认无明文 secret),
  真实值只在各机 `.env`(仍不入库,由 `.env.template` 约束变量集);(3) upstream 更新后跑
  `make config-upgrade` 合并新增字段。**严禁**把真实 secret 写进 config.yaml;新增 secret 字段必须用 `$` 占位。

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
- **Version sources must stay in lockstep** — a release version must match identically in
  `backend/pyproject.toml`, `frontend/package.json`, and `deploy/helm/deer-flow/Chart.yaml`
  (`version` + `appVersion`). Pushing a `v*` git tag triggers CI that runs
  `scripts/verify_versions.sh` and **blocks all publishing** if any source drifts. Before
  bumping a version, run `scripts/bump_version.sh <ver>` (aligns all four at once) and
  `scripts/verify_versions.sh <ver>` to catch drift early. See [RELEASING.md](RELEASING.md).
- **Don't edit `CLAUDE.md`** — it only contains `@AGENTS.md`. All agent guidance changes
  belong here in `AGENTS.md`; `CLAUDE.md` is a thin import shim.
