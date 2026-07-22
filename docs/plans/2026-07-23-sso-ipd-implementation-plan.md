# 数字底座(IPD) SSO 三方登录 · 实施计划

> **状态：pending approval**（omc-plan direct mode 产出，等待项目负责人批准开工）
> **分支：`codex/sso-login`**（从 prod `668e2eedc` 重建，基线 `aa82e7676`）。SSO 工作只在此分支，不合 prod、不 push，直到联调通过。
> **主输入：** [`2026-07-22-digital-foundation-sso-todo.md`](2026-07-22-digital-foundation-sso-todo.md)（冻结 todo，权威）。本计划是其阶段 B/C/D 的可执行展开。
> **日期：** 2026-07-23

---

## 1. 背景与范围

为 DeerFlow 接入上海电气"数字底座"(IPD) 三方登录，入口模式 = **用例二**（三态：sso 路径→重定向底座登录→底座带 code 跳回 `/loginsso`；非 sso 路径未登录→本地登录页；已登录→进入）。SSO 是**可选入口**，本地登录完全保留不动。

范围：新增一个非 OIDC 的 OAuth2 provider 适配"数字底座"协议，复用 DeerFlow 现有 session/CSRF/provisioning/隔离链路。**不含** RBAC 接入（roleCodes 仅作外部证据，首期不映射权限）、不含 refresh_token 持久化（登录时用一次即丢）。

**预编码策略**：协议已明确，可先写绝大部分代码；IT 待提供的外部输入用占位 + `# ASSUMPTION` 标注 + 配置开关回填，不阻塞编码，只阻塞联调。

## 2. 设计决策

| 决策点 | 选定方案 | 理由 / 备选 |
|---|---|---|
| provider 类型区分 | **方案 A**：在现有 `OIDCProviderConfig` 加 `provider_type: Literal["oidc","oauth2"]` 判别字段 + 少量 oauth2 专属字段 | 现有 schema 已支持 endpoint overrides，加判别最省、复用 provisioning 字段。备选 B（平行 `OAuth2ProviderConfig` + `auth.oauth2` 段）隔离更纯但重复多，暂不取 |
| 回调形态 | **前端 `/loginsso` 拦截 + 后端换会话端点**（非后端 GET callback） | 官方文档第 1 章「应用访问地址=前端拦截 code 的地址」+ 时序图第 5 步明确 |
| `/loginsso` 行为 | **单页双行为**：带 `code`→换会话；不带 `code`→重定向底座登录页 | 底座登记的回调地址即 `/loginsso`，用例二 sso 路径也指向它。备选：拆 `/sso/login` 触发 + `/loginsso` 回调，**待 B1 确认 sso 入口路径后定稿** |
| state/CSRF | **不依赖底座 state**，DeerFlow 自建一次性 nonce（cookie 绑定）+ 现有 double-submit | 底座 state 示例为空/0/1，语义不可靠 |
| 换 token 传参 | **新增"全 query + tenant-id header"模式** | 底座要求 `grant_type..state` 全走 query；现有 `exchange_code` 仅 post/basic/none |
| 身份映射 | `oauth_provider="shanghai-electric-ipd"`，`oauth_id` 来自配置字段（默认 `id`） | 复用现有 `(oauth_provider, oauth_id)` 唯一索引，不需迁移 |

## 3. 验收标准（testable）

1. 配置 `auth.oidc.providers.shanghai-electric-ipd.provider_type="oauth2"` 启用后，`GET /api/v1/auth/providers` 返回含 `{id:"shanghai-electric-ipd", type:"oauth2", display_name:...}`。
2. 前端 `/loginsso?code=X&tenant-id=1&organize-id=100` 调后端换会话端点 → 后端用 code 换 token（全 query + tenant-id header）→ 取 userinfo（Bearer+tenant-id+organize-id+carryRole=true）→ 返回 DeerFlow session cookie；底座 token 不出现在响应体/前端。
3. 首次登录的底座用户自动创建 `system_role="user"`、`password_hash=null`、`oauth_provider="shanghai-electric-ipd"` 的账号；`(oauth_provider,oauth_id)` 二次登录命中同一账号（幂等）。
4. userinfo `roleCodes=["super_admin"]` 时，新建/已有用户 `system_role` 仍为 `user`（不提权）；既有 admin 登录后 `system_role` 不变。
5. 底座 userinfo email 与既有本地账号邮箱冲突 → 返回 409，不自动绑定、不接管管理员。
6. email 为空时按 `email_synthesis_pattern`（默认 `{id}@ipd.local`）合成 + `require_verified_email=false`，建号成功。
7. 无 code 访问 `/loginsso` → 重定向到配置的底座登录 URL（B1 占位）。
8. state/nonce 不匹配、code 重放、非白名单 tenant/organize、底座不可用 → 安全失败（4xx，无敏感信息泄露）。
9. 本地登录、初始化、登出、改密码、现有 OIDC（keycloak 等）全不回归。
10. 日志/错误响应/support bundle 中无 `code`/`access_token`/`refresh_token`/`client_secret`/明文用户资料（grep 验证）。
11. SSO 用户的 thread/文件/memory/sandbox 隔离与本地登录一致（`users/{user_id}/...`）。

## 4. 实施阶段

> 依赖链：**阶段 1 → 2 → 3 → 4**（后端）；**阶段 5** 依赖 3 的端点契约（可并行起步）；**阶段 6** 随时；**阶段 7** 被 P0 blocker 门禁。每阶段测试先行。

### 阶段 1 · 配置 schema

- **改** `backend/packages/harness/deerflow/config/auth_config.py`：`OIDCProviderConfig` 加 `provider_type: Literal["oidc","oauth2"]="oidc"`；oauth2 专属字段 `authorize_endpoint`/`token_endpoint`/`userinfo_endpoint`（显式 URL，无 issuer/discovery）、`tenant_id_header`/`organize_id_header`、`subject_field`、`email_synthesis_pattern`、`namespace_with_tenant`、`allowed_tenant_ids`/`allowed_organize_ids`。`$ENV` 解析复用现有机制。
- **测** `backend/tests/test_auth_config_oauth2.py`：provider_type 判别、oauth2 必填字段校验、`$IPD_CLIENT_SECRET` 解析、默认值。
- **交付** 可独立加载的 oauth2 provider 配置模型。
- **blocker** 无（schema 独立）。**ASSUMPTION**：`subject_field` 默认 `"id"`（待 B6）、`namespace_with_tenant` 默认 `false`（待 B6）。

### 阶段 2 · OAuth2 adapter（核心）

- **新建** `backend/app/gateway/auth/oauth2.py`，`OAuth2Service`：
  - `build_authorization_url(cfg, state, redirect_uri)` — 用 `cfg.authorize_endpoint`（B1 占位），不带 nonce。
  - `exchange_code(cfg, code, redirect_uri, state, tenant_id)` — **全 query 传参**（`grant_type/client_id/client_secret/code/redirect_uri/state`）+ `tenant-id` header；解析 `{code,data:{access_token,...},msg}` 响应，`code!=0` 抛归一错误。
  - `fetch_userinfo(cfg, access_token, tenant_id, organize_id)` — Bearer + tenant-id + organize-id header + `carryRole=true` query；解析 `data`。
  - `authenticate_callback(...)` — exchange → fetch_userinfo → 映射成 identity（`subject`=按 `subject_field` 取，`email`=取或按 `email_synthesis_pattern` 合成，`claims` 透传 roleCodes/dept 等）；**不要求 id_token**、**不强制 sub 匹配**。
  - 错误归一：`OAuth2Error`/`OAuth2ProviderError`/`OAuth2ValidationError`（对齐 `oidc.py` 的错误层级）。
  - httpx client 复用 `oidc.py` 的模式；**日志脱敏**：query 中的 `client_secret`/`code` 在异常/日志里 mask（复用 `tools.py::mask_secret_values` 思路）。
- **测** `backend/tests/test_oauth2_adapter.py`：用官方示例响应（`id:1/workId/email:"1@qq.com"/roleCodes:["super_admin"]`）mock；覆盖全 query 换 token、userinfo 映射、subject_field 切换、email 合成、`code!=0` 错误归一、超时。
- **交付** 纯协议 adapter，无 HTTP server 依赖，可单测。
- **blocker** B2/B3（URL 占位）、B1（authorize URL 占位）。**ASSUMPTION** A1/A2/A3。

### 阶段 3 · 换会话端点 + CSRF 自建

- **改** `backend/app/gateway/routers/auth.py`（现 868 行）：
  - 抽共享 helper `_complete_sso_login(request, user, remember_me, next_path)`：provision → `create_access_token` → `set_session_cookie` → `_set_csrf_cookie` → 删 state cookie → 重定向（复用现有 OIDC callback 尾部逻辑，`session_cookie.py::set_session_cookie`、`jwt.py::create_access_token`）。
  - 新增换会话端点（POST，接收 `code`/`state`/`tenant_id`/`organize_id`/`redirect_uri`）：校验自建 nonce → `OAuth2Service.authenticate_callback` → `get_or_provision_*` → `_complete_sso_login`。
  - `list_auth_providers` 补 `type:"oauth2"` 条目。
- **新建** `backend/app/gateway/auth/sso_state.py`（或复用 `oidc_state.py` 的签名 cookie 机制）：DeerFlow 自建一次性 nonce（JWT 签名、短 TTL、消费即失效），cookie 名按 provider 命名空间。
- **改** `backend/app/gateway/auth_middleware.py`：新端点路径加入 `_PUBLIC_PATH_PREFIXES`/exact 公开列表；确认 CSRF 豁免与 Origin 校验对齐（参照 `csrf_middleware.py` 的 auth-endpoint 处理）。
- **测** `backend/tests/test_auth_sso_endpoint.py`：nonce 校验、code 重放拒绝、开放重定向（`next` 白名单，复用 `validate_next_param`）、非白名单 tenant/organize、provision 成功路径、底座不可用降级。
- **交付** 可端到端（mock adapter）跑通的换会话端点。
- **blocker** 依赖阶段 1/2。B4/B5（白名单值占位）。

### 阶段 4 · provisioning 适配 + 红线测试

- **改** `backend/app/gateway/auth/user_provisioning.py`：若 `get_or_provision_oidc_user` 签名强类型于 `OIDCIdentity`/`OIDCProviderConfig`，把 oauth2 identity 适配进该形状（优先不动签名，构造 `OIDCIdentity`-shaped 对象传入）；确认邮箱冲突 409、`admin_emails` 仅显式名单（数字底座**不**注入 admin_emails）、`auto_create_users`/`require_verified_email` 走配置。
- **测** `backend/tests/test_sso_provisioning.py`：首次创建、重复登录幂等、并发首次登录（唯一索引兜底）、邮箱冲突 409、roleCodes 不提权、既有 admin 不被覆盖、email 合成、管理员账号保护。
- **交付** 红线全部有回归测试。
- **blocker** 无（用 mock）。**ASSUMPTION** A3。

### 阶段 5 · 前端 `/loginsso` 双行为

- **新建** `frontend/src/app/loginsso/page.tsx`（或 `(auth)/loginsso`）：
  - 带 `code` → 调后端换会话端点 → 成功跳 `next`（默认 `/workspace`）/ 失败跳 `/login?error=sso_failed`（对齐现有 `/auth/callback` 行为，见 `SSO.md` Frontend Callback Flow）。
  - 不带 `code` → 判定 sso 入口 → 重定向到配置的底座登录 URL（B1 占位）。
- **不改** `frontend/src/app/(auth)/login/page.tsx`（本地登录页原样保留；是否加"数字底座登录"按钮取决于 B1 是否提供可主动访问入口，首期可不加）。
- **测** `frontend/tests/` 双行为单测。
- **交付** 前端入口可用（B1 未回填时重定向到占位）。
- **blocker** B1（不带 code 的重定向目标）。**ASSUMPTION** A7。

### 阶段 6 · 文档与配置示例

- **改** `config.example.yaml`：补 `auth.oidc.providers.shanghai-electric-ipd` 段（provider_type=oauth2、端点占位、`$IPD_CLIENT_SECRET`）；bump `config_version`。
- **改** `backend/docs/SSO.md`：新增"自定义 OAuth2 provider（数字底座）"段。
- **改** `docs/production-deployment.md`：登记 `IPD_CLIENT_ID`/`IPD_CLIENT_SECRET`/`auth.local.allow_registration` 等 dev-only/部署参数（按 AGENTS.md「Dev-only 参数必须 production-documented」）。
- **改** `README.md` / 相关 `AGENTS.md`（用户/开发面向变更）。
- **交付** 文档与代码同步。

### 阶段 7 · 联调与发布（🚫 P0 blocker 门禁）

- **前置**：B1/B2/B3/B4/B5 回填 + B8 测试账号到位。
- 场景：正常登录 / 拒绝 / code 过期 / 重复回调 / 底座不可用 / 缺邮箱 / 重复邮箱 / 多角色。
- 验证：HTTPS、反代头、Secure/SameSite cookie、CSRF；thread/文件/memory/sandbox 按 `user_id` 隔离；日志/support bundle 脱敏（grep 验证）。
- 部署：`./scripts/deploy.sh`（唯一入口，禁临时 docker compose）。
- 回滚方案：确认回滚不删已建用户、不覆盖 admin 角色。
- **交付** 生产可用 + 验收标准 1–11 全绿。

## 5. 占位与回填清单（ASSUMPTION）

| ID | 占位内容 | 默认/策略 | 待回填 |
|---|---|---|---|
| A1 | subject 字段 | `subject_field="id"` | B6 |
| A2 | subject 唯一范围 | `namespace_with_tenant=false`（全局唯一） | B6 |
| A3 | email 缺失 | 合成 `{id}@ipd.local` + `require_verified_email=false` | B7 |
| A4 | state 语义 | 自建 nonce，不依赖底座 state | B11（确认无强制） |
| A5 | token/userinfo URL | config 占位 `<TODO 待 IT>` | B2/B3 |
| A6 | tenant/organize | 地址栏透传 + 配置白名单（值占位） | B4/B5 |
| A7 | sso 入口重定向 URL | config 占位 | B1 |
| A8 | client 凭据 | `$IPD_CLIENT_ID` / `$IPD_CLIENT_SECRET` 环境变量 | 已拿到 |

> 回填流程：IT 答复 → 改 `config.yaml`（生产）+ 删对应 `# ASSUMPTION` 注释 → 跑 `grep -rn ASSUMPTION backend/app/gateway/auth/` 确认清零 → 联调。

## 6. 威胁模型

| 威胁 | 缓解 |
|---|---|
| state 重放 / CSRF | 自建一次性 nonce（签名 cookie + 消费即失效）+ double-submit |
| code 重放 | 底层 token 接口一次性；DeerFlow 侧可选短期 code 去重 |
| 开放重定向 | `next` 走 `validate_next_param` 白名单（相对路径，禁 `//`/`:`） |
| 账号接管 | 邮箱冲突 409（复用 provisioning）；roleCodes 不提权；不注入 admin_emails |
| 租户/组织混淆 | `allowed_tenant_ids`/`allowed_organize_ids` 白名单校验 |
| 日志泄密 | query 中 `client_secret`/`code`/token mask；异常归一不带敏感字段 |
| SSRF | token/userinfo URL 来自受信配置；启动校验 schema |
| 超时/重试 | 配置 httpx timeout；底座不可用安全降级 |

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| IT 实际协议与假设出入（subject 非 id、参数位置不同） | 全 ASSUMPTION 标注 + 配置开关；mock 测试用真响应跑一遍即暴露偏差；不回填不联调 |
| `exchange_code` 全 query 模式改造影响现有 OIDC | 新模式仅 provider_type=oauth2 走，OIDC 路径不动；现有 OIDC 测试作回归 |
| `/loginsso` 双行为与 B1 冲突 | 设计留拆路径备选；B1 确认前重定向用占位 |
| client_secret 走 query 被网关日志记录 | 部署确认全程 HTTPS（B10）；DeerFlow 侧日志 mask；access log 过滤 |
| 半成品误入 prod | 只在 sso-login 分支；不合 prod/不 push 直到阶段 7 全绿 |

## 8. 验证步骤

1. `cd backend && make test`（含新增 oauth2/endpoint/provisioning 单测）全绿。
2. `cd frontend && pnpm install && pnpm check`（lint+tsc）+ `pnpm test` 全绿。
3. 现有 OIDC（keycloak）回归不破坏（`test_oidc_auth.py`）。
4. `grep -rn ASSUMPTION backend/app/gateway/auth/` 在回填后清零。
5. 阶段 7：真实测试账号走完整用例二链路 + 验收标准 1–11 全绿。
6. 部署后 grep 日志/support bundle 确认无敏感字段。

## 9. blocker 追踪（与 todo 第 6 节对齐）

- **不阻塞编码（阶段 1–6 可推进）**：B1–B7、B10、B11（用占位/ASSUMPTION）。
- **阻塞联调（阶段 7）**：B1、B2、B3、B4、B5（P0）+ B8（测试账号）。
- **已解**：client_id/client_secret（A8）。

---

**批准开工后**：按阶段 1→2→3→4→5→6 顺序在 `codex/sso-login` 分支实现，每阶段测试先行；阶段 7 等 P0 blocker 回填。本计划批准前不修改任何源码。
