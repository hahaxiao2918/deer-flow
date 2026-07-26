# 数字底座三方登录改造待办与证据

> 状态：需求与证据已固化，尚未开始实现。
>
> 实施门禁：先完成本地主线收敛，再完成 upstream 升级与回归；只有项目负责人明确说“开工”后，才能修改 SSO 相关代码、配置或数据库。

## 1. 恢复入口

本文件是后续会话和上下文压缩后的恢复锚点。继续本任务前必须依次阅读：

1. 本文件；
2. 仓库根目录 `AGENTS.md`；
3. 涉及后端时阅读 `backend/AGENTS.md`，涉及登录页时阅读 `frontend/AGENTS.md`；
4. 原始《数字底座对接文档 v1》附件；
5. 当时唯一 canonical 分支的实际代码和最新 upstream 鉴权实现，不能仅依赖本文件中的历史行号。

当前阶段只允许分支调查、收敛方案和 upstream 升级准备。不得提前实现三方登录。

## 2. 已确认需求

- [x] 业务域名：`https://ipd.nebula-starlink.shanghai-electric.com/`。
- [x] 数字底座不是唯一登录入口。
- [x] 保留本地管理员登录、初始化和管理员角色管理能力。
- [x] 所有合法数字底座用户首次成功登录时自动创建 DeerFlow 账号。
- [x] 新建的数字底座用户固定创建为 DeerFlow 普通 `user`。
- [x] 数字底座返回的 `roleCodes` 不得自动提升为 DeerFlow `admin`。
- [x] 已存在 DeerFlow 管理员的 `system_role` 不得被 SSO 登录、资料同步或角色映射覆盖。
- [x] 数字底座用户与本地管理员入口并存，不把 SSO 改造成唯一入口。
- [x] 用户基本信息及角色信息来自对接文档 4.2 的用户信息接口。

## 3. 外部协议证据

### 3.1 原始材料

- 文件：`/home/lxdd/.codex/attachments/511d0dbd-8c5b-478d-8d6d-32594dfe7ded/未命名文档(29).docx`
- 标题：数字底座对接文档 v1
- SHA-256：`358c904f980305728bb9df3c772a2b60f2f3dd8d69ca0208c0a5179fa3473cda`
- 文档内含接口密钥、令牌和用户数据示例；本待办不复制任何示例值。实现时不得把真实或示例凭据提交到 Git。

### 3.2 已确认的协议流程

该对接是数字底座自定义的 OAuth2 授权码流程，不是可直接套用的标准 OIDC：

1. 数字底座前端把用户跳转到第三方回调地址，并携带 `code`、`state`、`redirect_uri`、`organize-id`、`tenant-id`。
2. 第三方后端调用 `POST /admin-api/system/oauth2/token`，用授权码换取 `access_token` 和 `refresh_token`。
3. 第三方后端调用 `GET /admin-api/system/oauth2/user/get` 获取用户基本信息和角色。
4. 文档另提供通过 `refresh_token` 刷新访问令牌的流程。

它与 DeerFlow 现有 OIDC 的关键差异：文档没有提供 OIDC discovery、issuer、JWKS、ID token、audience 或 nonce 语义。因此不能只新增一段 `auth.oidc.providers` 配置来完成对接，需实现数字底座专用 OAuth2 adapter，并复用 DeerFlow 已有会话、CSRF 和用户隔离链路。

### 3.3 Token 接口证据

授权码换令牌需要：

- query：`grant_type=authorization_code`、`client_id`、`client_secret`、`code`、`redirect_uri`、`state`；
- header：`tenant-id`；
- 成功响应：`access_token`、`refresh_token`、`token_type`、`expires_in`、`refresh_expires_in`；
- `redirect_uri` 必须与申请授权码时一致。

安全约束：

- `client_secret` 只能保存在服务端密钥配置中；
- token 交换必须由 DeerFlow 后端完成；
- 日志、错误响应和遥测不得记录授权码、访问令牌、刷新令牌或客户端密钥；
- 回调必须校验一次性 `state`、有效租户/组织上下文和受控的回跳路径；
- 除非后续确实需要代表用户持续调用数字底座 API，登录完成后不持久化外部 `refresh_token`。

### 3.4 用户与角色接口证据（文档 4.2）

请求 `GET /admin-api/system/oauth2/user/get`：

- header：`Authorization: Bearer <access_token>`；
- header：`tenant-id`，必填；
- header：`organize-id`，必填；
- query：`carryRole`，需要角色信息时传 `true`。

响应截图展示的 `data` 字段包括：

- 稳定身份候选：`id`、`workId`、`username`；
- 资料：`nickname`、`email`、`mobile`、`sex`、`avatar`；
- 组织：`dept.id`、`dept.name`；
- 岗位：`posts[].id`、`posts[].name`；
- 角色：`roleCodes[]`。

`roleCodes` 当前只作为外部身份/权限证据，不映射 DeerFlow `system_role`。新用户始终是 `user`，既有管理员角色保持不变。

## 4. DeerFlow 现状证据

以下证据基于收敛前 `codex/prod-canonical@4159b8952`，升级后必须重新核验：

- `backend/app/gateway/auth/models.py`：用户邮箱必填且唯一；`system_role` 只有 `admin/user`；已有 `oauth_provider/oauth_id` 字段。
- `backend/packages/harness/deerflow/persistence/user/model.py`：邮箱唯一；`(oauth_provider, oauth_id)` 有非空唯一索引。
- `backend/app/gateway/auth/user_provisioning.py`：现有 OIDC 已支持按外部身份查找、首次登录自动创建；新用户默认 `user`，但邮箱冲突会阻止自动绑定。
- `backend/app/gateway/routers/auth.py`：已有 Provider 列表、OIDC 发起和回调、state/nonce/PKCE、DeerFlow JWT、session cookie 和 CSRF cookie 链路。
- `backend/app/gateway/auth/oidc.py`：现有实现强依赖 discovery、ID token 和 JWKS，不能直接兼容数字底座协议。
- `frontend/src/app/(auth)/login/page.tsx`：同一品牌登录页已经同时承载本地登录/注册和 SSO Provider 按钮，可保留管理员入口并增加数字底座入口或处理底座主动回跳。
- `docs/superpowers/specs/2026-06-19-guardrail-request-attribution-design.md`：服务端认证后的 `user_id/user_role/oauth_provider/oauth_id` 可进入运行上下文，客户端传入值不得覆盖认证态。

### 4.1 upstream 升级相关证据

在开始 SSO 前，应先把以下 upstream 鉴权变化合入 canonical 并验证：

- `a028dfd5f`：统一 session cookie、remember-me 与 CSRF 生命周期；
- `09e25b8a3`：新增 `auth.local.allow_registration`，可关闭普通访客自注册，同时保留初始化和既有管理员登录；
- `1300c6d36`、`10890e10a`、`92c8f2f03`：可信 principal、授权 Provider 与内置 RBAC 基础设施。

数字底座首期无需把 `roleCodes` 接入 DeerFlow RBAC。不要只 cherry-pick RBAC 提交后直接做 SSO；先完整升级并跑回归，避免重复改登录页、session/CSRF 和认证配置。

## 5. 目标设计边界

### 5.1 登录入口

- 本地管理员登录继续可用。
- 系统首次初始化入口继续可用。
- 推荐升级后设置 `auth.local.allow_registration: false`，关闭普通用户公开自注册；是否启用由部署配置决定。
- 数字底座可以从其应用列表主动跳入；是否还在 DeerFlow 登录页展示“数字底座登录”按钮，取决于底座是否提供可主动访问的授权入口。

### 5.2 账号与角色

- 外部身份键必须使用稳定且跨会话不变的字段，不能只用昵称、手机号或展示用户名。
- 推荐身份命名空间至少包含 provider 与底座用户稳定 ID；是否还必须包含 `tenant-id`、`organize-id`，需要底座确认 ID 的全局唯一范围。
- 首次登录：创建 DeerFlow `user`，`password_hash=null`，写入外部身份映射。
- 后续登录：按外部身份映射命中同一 DeerFlow 用户。
- 不根据 `roleCodes` 创建或提升 DeerFlow 管理员。
- 既有本地账号邮箱冲突时默认拒绝自动绑定，尤其不能自动接管管理员账号。
- 管理员继续使用独立本地入口；未来若要允许管理员绑定 SSO，必须设计显式、由管理员本人确认的绑定流程，不能在本次首期中隐式完成。

### 5.3 会话与隔离

- 外部认证成功后只签发 DeerFlow 自己的 JWT/session cookie，不把数字底座 token 暴露给前端。
- DeerFlow 内部继续以本地用户 UUID 作为 `user_id`，保持线程、文件、记忆和沙箱隔离。
- 用户资料变化不得改变本地 UUID，也不得覆盖 `system_role`。
- 登出至少清理 DeerFlow 会话；是否还需要数字底座单点登出，须由底座补充协议。

### 5.4 建议组件边界（待升级后最终定稿）

- 数字底座 Provider 配置模型：授权/令牌/用户信息端点、客户端凭据、允许的租户与组织、超时等。
- OAuth2 adapter：授权码交换、用户信息获取、响应校验与错误归一。
- state 上下文：绑定 provider、tenant、organization、redirect URI、next path 和过期时间。
- callback/router：校验回调、调用 adapter、provision 用户、签发 DeerFlow session。
- provisioning：复用现有仓储和唯一约束，固定普通用户角色，保留管理员。
- 登录页：保留本地管理员路径，按最终入口模式展示按钮或仅处理主动回跳。

#### 5.4.1 官方文档核对后的实现修正（2026-07-22）

核对《数字底座对接文档 v1》后，对组件边界的三处关键修正：

1. **回调形态改为前端拦截**：底座要求的「应用访问地址」是三方**前端**拦截 code 的路由（`/loginsso`），不是后端 GET callback。实现形态为「前端 `/loginsso` 页面解析地址栏 code 等参数 → 调用后端换会话端点」，而非照搬现有 OIDC 的 `GET /api/v1/auth/callback/{provider}`。后端新增一个接收 code 的换会话端点；session/CSRF/provisioning 尾部逻辑仍可抽成共享 helper 复用。
2. **token 交换需支持「全参数走 query」**：底座 token 接口把 `grant_type/client_id/client_secret/code/redirect_uri/state` 全部放在 query、`tenant-id` 放 header。现有 `OIDCService.exchange_code` 仅支持 `client_secret_post`/`client_secret_basic`/`none`，不覆盖此模式，需为底座 adapter 新增 query 传参方式，并确保日志脱敏 client_secret。
3. **state 语义非标准，需自建 CSRF**：文档示例 `state=` 为空、`state=0`，且用例一/二均由底座发起跳转，DeerFlow 无法用标准 OAuth2 state 做 CSRF 防护。改为 DeerFlow 自建一次性 nonce（cookie 绑定）+ 现有 double-submit CSRF，不依赖底座 state。

附带确认：token 接口仅需 `tenant-id` header（不需 organize-id）；userinfo 接口需 `tenant-id` + `organize-id` 两个 header；`tenant-id`/`organize-id` 源自地址栏参数（动态透传），同时支持配置覆盖与白名单校验。

4. **`/loginsso` 为双行为入口**：根据用例二三态逻辑，`/loginsso` 同时承担两个角色 —— 带 `code` 参数时（底座跳回）处理换 token、provision、签 session；不带 `code` 参数时（用户主动访问 sso 入口）判定为 sso 路径并重定向到底座登录页。实现时需在同一页面区分这两种行为，或拆分为两个路径（如 `/sso/login` 触发重定向 + `/loginsso` 处理回调）。具体形态待 B1（sso 入口触发重定向的底座登录 URL）确认后定稿。

## 6. 与 IT 的对接清单

入口模式已确定为**用例二**。完整版文档（`数字底座对接文档v1.md`）2.2 流程图揭示用例二是**三态判断**，而非"未登录即跳底座"：

1. 用户访问 DeerFlow 某路径 → 判定**是否为 sso 路径**：
   - **是** → 重定向到数字底座登录页 → 登录后在底座门户点击 DeerFlow 应用 → 底座携带 `code` 跳转 DeerFlow 前端 `/loginsso`（即用例一的后半段）。
   - **否** → 判定**用户是否已登录 DeerFlow**：
     - **已登录** → 进入系统。
     - **未登录** → 重定向到 **DeerFlow 本地登录页**（不是底座）。

由此确认：SSO 是**可选入口**（仅走 sso 路径才触发底座重定向），**本地登录完全保留**，与第 2 节红线「保留本地管理员登录」自洽；DeerFlow 本地登录页无需改动。

### 6.1 已确认（官方对接文档 v1 + 已取证）

- [x] 协议为自定义 OAuth2 授权码，非标准 OIDC；无 discovery / issuer / JWKS / ID token / nonce。
- [x] 回调入口为**前端 `/loginsso` 拦截模式**（文档第 1 章「应用访问地址=前端拦截授权码 code 的地址」），不是后端 GET callback。
- [x] token 接口：`POST /admin-api/system/oauth2/token`，`grant_type/client_id/client_secret/code/redirect_uri/state` 全部走 **query**，`tenant-id` 走 header；**不需要** organize-id。
- [x] userinfo 接口：`GET /admin-api/system/oauth2/user/get`，header `tenant-id` + `Authorization: Bearer <token>` + `organize-id`，query `carryRole=true`。
- [x] `Authorization` 严格使用标准 `Bearer <token>`。
- [x] 换 token 时 `redirect_uri` 必须与申请 code 时登记的一致（文档 4.1.3.1）。
- [x] `client_id` / `client_secret` 已由 IT 分配（存于本地 `三方登录client_id.md`，已 gitignore；部署时用环境变量引用，不入 `config.yaml` 明文）。
- [x] 底座域名：测试 `newportal.nebula-starlink.shanghai-electric.com`，生产 `portal.nebula-starlink.shanghai-electric.com`（与 DeerFlow 对外域名 `ipd.*` 不同；DeerFlow 是三方系统，底座在 portal/newportal）。

### 6.2 DeerFlow 需提供给 IT（清单 A）

- [ ] **A1 回调地址**：DeerFlow 前端 `/loginsso` 路由。生产 `https://ipd.nebula-starlink.shanghai-electric.com/loginsso`；**测试环境域名待确认**后一并提交。须与后端 `redirect_uri` 配置逐字符一致。
- [ ] **A2 应用图标**：png，整体 260×260 透明、实体 172×172。
- [ ] **A3 应用名称**：底座门户列表显示名。
- [ ] **A4 应用上架**：让 IT 在底座门户注册上架 DeerFlow，使用例二「登录后点击三方」可见入口。
- [ ] **A5 对外域名**：向 IT 确认 DeerFlow 生产/测试对外域名。
- [ ] **A6 入口模式声明**：告知 IT 采用用例二，未登录时需重定向到底座登录页（同时索取登录发起 URL，见 B1）。

### 6.3 IT 需提供给 DeerFlow（清单 B，按优先级）

**P0 — 不补齐则用例二无法实现：**

- [ ] **B1 sso 入口触发重定向的底座登录 URL（格式 + 参数）**：用例二中"是 sso 路径 → 重定向到数字底座登录页面"的具体 URL 是什么？需带哪些参数（`client_id`/`redirect_uri`/`response_type`/`tenant-id`/`scope`）？sso 入口路径是 `/loginsso` 本身还是单独路径？官方文档未给出，是用例二的关键缺口。
- [ ] **B2 token 接口完整 URL（生产 + 测试）**：文档示例为内网 IP，需真实生产/测试地址。
- [ ] **B3 userinfo 接口完整 URL（生产 + 测试）**：同上。
- [ ] **B4 `tenant-id` 的值**：DeerFlow 接入哪个租户（示例 `1`）。
- [ ] **B5 `organize-id` 的值**：DeerFlow 接入哪个组织（示例 `100`）。

**P1 — 影响正确性与数据模型：**

- [ ] **B6 稳定用户标识字段 + 唯一范围**：userinfo 的 `id`/`workId`/`username` 哑个跨会话不变？全局唯一还是租户/组织内唯一？（决定 `oauth_id` 取值与是否需拼接 tenant 维度）
- [ ] **B7 email 必填性 + 唯一性**：所有用户都有 email 吗？全局唯一吗？DeerFlow 强制 email 非空唯一，不确认则需做合成邮箱兜底（`{id}@ipd.local` + `require_verified_email: false`）。

**P2 — 测试联调：**

- [ ] **B8 测试账号**：能在 `newportal` 登录的测试用户，覆盖普通/缺邮箱/重复邮箱/禁用/多角色。
- [ ] **B9 client 是否测试/生产同一套**：已拿到的 client_id/secret 是 newportal 专用、portal 专用还是通用？

**P3 — 运维与安全：**

- [ ] **B10 生产全程 HTTPS**：token 接口走 query 传 client_secret，非 HTTPS 会明文泄露。
- [ ] **B11 state 行为**：底座是否校验 state？文档示例 `state=` 为空、`state=0`，DeerFlow 倾向自建 CSRF 不依赖底座 state，需确认底座无强制要求。
- [ ] **B12 code 有效期 + 是否一次性**。
- [ ] **B13 接口超时建议 / 限流 / 错误码全集**（文档仅给出一条 redirect_uri 不一致错误）。
- [ ] **B14 是否要求单点登出**：DeerFlow 登出时是否需通知底座。
- [ ] **B15 是否要求 refresh_token 续期**：DeerFlow 首期倾向登录时用一次 token 即丢弃，不持久化 refresh_token，需确认底座无强制续期。

## 7. 实施待办（当前全部冻结）

### 阶段 A：主线与 upstream 前置

- [ ] 将本地分支收敛为唯一 canonical；已同意以 `codex/prod-canonical` 为内容基线。
- [ ] 审核并选择性回收 `codex/shanghai-electric` 中有价值的内容，不整体合并实验提交。
- [ ] 解决 Gitea `prod-canonical` 上加密秘密包与仓库秘密政策的冲突。
- [ ] 合并最新 upstream，完成后端、前端、数据库、部署与鉴权回归。
- [ ] 重新核验本文件第 4 节的代码路径、约束和 upstream commit 是否仍适用。

### 阶段 B：设计冻结

- [ ] 补齐第 6 节外部协议问题。
- [ ] 确定稳定外部身份键和邮箱缺失策略。
- [ ] 确定 callback 路由和登录页入口模式。
- [ ] 确定租户/组织白名单及配置承载方式。
- [ ] 形成威胁模型：state 重放、code 重放、开放重定向、账号接管、租户混淆、日志泄密、SSRF、超时与重试。
- [ ] 明确数据库是否需要迁移；优先复用 `(oauth_provider, oauth_id)`，避免不必要扩表。

### 阶段 C：测试先行与实现

- [ ] 为配置校验、token 响应、userinfo 响应和错误归一编写单元测试。
- [ ] 为 state、tenant/organization 绑定、回调重放和开放重定向编写安全测试。
- [ ] 为首次自动创建、重复登录幂等、并发首次登录、邮箱冲突编写 provisioning 测试。
- [ ] 验证所有新 SSO 用户均为 `user`，外部 `roleCodes` 不能提权。
- [ ] 验证既有管理员和本地账号角色不被覆盖。
- [ ] 验证本地管理员登录、初始化、登出、密码修改不回归。
- [ ] 实现数字底座 OAuth2 adapter、callback、配置和前端入口。
- [ ] 更新 `README.md`、相关 `AGENTS.md` 和 `docs/production-deployment.md`。

### 阶段 D：联调与发布

- [ ] 使用测试租户完成正常、拒绝、过期、重复回调和底座不可用场景。
- [ ] 验证 HTTPS、反向代理头、Secure/SameSite cookie 和 CSRF 行为。
- [ ] 验证用户线程、文件、记忆、沙箱均按本地 UUID 隔离。
- [ ] 验证日志与支持包中没有 code、token、client secret 和敏感用户资料。
- [ ] 使用 `./scripts/deploy.sh` 部署；禁止临时 Docker Compose 操作。
- [ ] 制定回滚方案，确认回滚不会删除已创建用户或覆盖管理员角色。

## 8. 验收标准

- 数字底座合法用户首次登录自动创建普通 DeerFlow 用户并进入工作区。
- 同一外部身份重复或并发登录不会创建多个账号。
- 数字底座角色无论为何值，都不能自动获得 DeerFlow 管理员权限。
- 既有管理员角色、管理员登录和系统初始化入口保持可用。
- 非白名单租户/组织、错误 state、重放 code、无效 token 和异常用户响应均安全失败。
- 外部 token 和客户端密钥不进入浏览器、本地用户数据、日志、错误消息或 Git。
- 账号的线程、文件、记忆和沙箱隔离与本地登录一致。
- 升级后的 session、remember-me、CSRF 和退出行为通过前后端回归。

## 9. 当前停点

- 已完成：需求访谈结论、原始文档与截图取证、DeerFlow 现状调查、upstream 鉴权差异调查、本地主线收敛（`a2acd3d51`）、upstream 合入 prod（`9cd1ddfab`）与回归、官方对接文档 v1 核对、与 IT 的对接清单整理（第 6 节）、第 5.4.1 节实现修正。
- 阶段 A（主线与 upstream 前置）实际已完成；本文件此前未回填，现补记。
- 入口模式确定为用例二；`client_id`/`client_secret` 已由 IT 分配。
- 阶段 B/C 已实现（commit `eb4c3b7b0`，分支 `codex/sso-login`）：配置 schema、`oauth2.py` adapter、换会话端点 + 自建 CSRF nonce、前端 `/loginsso` 双行为、provisioning 红线测试、SSO.md/config.example/production-deployment 文档；37 个新单测，全量回归 8999 passed / 53 skipped / 1 预存 422（无关）。
- 待办：阶段 D 联调发布——补齐第 6.3 节 P0 项（B1–B5）+ B8 测试账号后，回填 config 占位、真实联调、部署。
- 解冻条件：项目负责人明确说“开工”。
