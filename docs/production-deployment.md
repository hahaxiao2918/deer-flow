# 生产部署手册 — 上海电气分发版

本文档是上海电气分发版 DeerFlow 的生产部署检查清单与操作手册，覆盖从代码推送、构建、启动到验证的完整链路，以及从本地 `DEER_FLOW_AUTH_DISABLED=1` 开发环境切换到真实生产环境时需要移除/替换的所有项。

> **总原则：** 任何只为本地开发方便而存在的参数、开关或配置值，上线前必须移除或替换。新增此类参数时，必须立即登记到本文末尾的 dev-only 参数清单。

---

## 1. 部署入口：`scripts/deploy.sh`（唯一支持的操作方式）

**所有生产环境的构建、启动、停止操作都必须通过 `./scripts/deploy.sh` 完成，且必须从仓库根目录运行。**

```bash
cd ~/deerflow

./scripts/deploy.sh          # 无参数 = build + start（完整重建并启动）
./scripts/deploy.sh build    # 仅构建全部镜像（与 sandbox 模式无关）
./scripts/deploy.sh check    # 校验部署输入与运行中容器的挂载，不改动容器
./scripts/deploy.sh start    # 用已构建好的镜像启动
./scripts/deploy.sh down     # 停止并移除容器
```

脚本独占管理以下事项，**禁止绕过脚本对 gateway / frontend / nginx 执行临时的 `docker compose up / down / stop / rm`**：

- `.env` 环境文件（缺失时直接拒绝运行，需从 `.env.example` 复制并配置）；
- host-path 导出（如 `DEER_FLOW_HOME` 等）；
- sandbox overlay：sandbox 模式（local / aio / provisioner）从 `config.yaml` 自动探测，aio 模式自动追加 `docker/docker-compose.dood.yaml`；
- Compose 项目名固定为 `deer-flow`；
- 挂载校验（见下）。

**挂载硬校验：** 脚本必须确认 `config.yaml` 与 `extensions_config.json` 是宿主机上的常规文件，且运行中的 `deer-flow-gateway` 容器挂载的正是这些解析后的确切路径。任一对应路径是**目录**即为硬失败 —— 不得删除该目录、不得直接替换，先检查其内容再处理（Docker 会为缺失的宿主机路径自动创建目录，这会让 gateway "看似启动"但配置为空）。

**操作边界：** 所有操作只针对 `deer-flow` Compose 项目。**绝不允许**停止、重启或重建无关容器（例如同主机的 `ipa-gateway`）。

---

## 2. 生产主机与服务拓扑

| 项 | 值 |
|----|----|
| 主机 | starl-38（`starl@10.84.91.38`，主机名 `zhihai`） |
| 仓库路径 | `~/deerflow` |
| 入口地址 | `http://localhost:2026`（nginx 绑定 localhost 并加入 `web-network`，仅经域名对外暴露） |
| Compose 项目 | `deer-flow` |

运行中的四个容器：

| 容器 | 角色 |
|------|------|
| `deer-flow-nginx` | 统一反向代理入口（2026 端口） |
| `deer-flow-gateway` | FastAPI REST API + 内嵌 LangGraph 运行时 |
| `deer-flow-frontend` | Next.js Web 界面 |
| `deer-flow-redis` | 缓存/队列 |

---

## 3. 分支与远程仓库

- **唯一生产与长期定制分支：`codex/prod-canonical`** —— 上游同步、品牌与企业定制维护、生产部署都只使用该分支。
- `origin` = `github.com/hahaxiao2918/deer-flow`（可写 fork）。
- `upstream` = `github.com/bytedance/deer-flow`（只读，push 已禁用）。
- 服务器上的仓库另配置有 `gitea` 远程（见下节），这是日常部署的实际拉取来源。

不要更改远程 URL、不要 force-push，除非用户明确批准。

---

## 4. Gitea 镜像部署链路（日常部署主通道，2026-07-20 建立）

**背景：** 服务器到 github.com 的 HTTPS 出口不稳定，push 后服务器经常拉不到。为此在 starl-38 本机部署了 Gitea 作为镜像，日常部署完全走内网回环，不再依赖 GitHub 出口。

**Gitea 服务：**

- 运行在 starl-38 本机，私有仓库 `hahaxiao/deer-flow`；
- Web/HTTP 端口 `7022`，SSH 端口 `7023`。

**开发机（lxdd）侧 —— 双远程推送：**

```bash
git push origin <branch> && git push gitea <branch>
```

- 开发机的 `gitea` 远程 = `ssh://git@10.84.91.38:7023/hahaxiao/deer-flow.git`（lxdd 密钥，读写权限）。
- 注意：本机访问 `http://10.84.91.38:7022`（Gitea Web）需绕过本机 `http_proxy`，例如 `curl --noproxy '*'` 或在浏览器代理设置中排除该地址。

**服务器（starl-38）侧 —— 回环拉取：**

- 服务器的 `gitea` 远程 = `ssh://git@localhost:7023/hahaxiao/deer-flow.git`（starl 密钥，只读）；
- 服务器上 `codex/prod-canonical` 的跟踪上游 = `gitea/codex/prod-canonical`；
- 日常部署只走 Gitea：`git fetch gitea && git pull`；`origin`（GitHub）仅保留用于对账（reconciliation）。
- 注意：服务器 git 的 fetch refspec 已修复为全分支（`+refs/heads/*:refs/remotes/origin/*`）。**若重建服务器上的仓库克隆，必须复查该 refspec**，否则只能 fetch 到部分分支。

**标准发布流程：**

```bash
# 开发机
git push origin codex/prod-canonical && git push gitea codex/prod-canonical

# 服务器
ssh starl@10.84.91.38
cd ~/deerflow
git fetch gitea && git pull            # 跟踪 gitea/codex/prod-canonical
./scripts/deploy.sh check              # 先校验，不动容器
./scripts/deploy.sh                    # build + start
```

---

## 5. GitHub 断连应急方案（备用，已被 Gitea 取代，保留作参考）

当 Gitea 也不可用、必须离线把某个提交送上服务器时：

```bash
# 开发机：导出补丁并拷贝
git format-patch -1 <sha> --stdout > /tmp/x.patch
scp /tmp/x.patch starl@10.84.91.38:/tmp/

# 服务器：应用补丁
cd ~/deerflow
git am /tmp/x.patch
```

若需要与 `origin` 上的提交 SHA 完全一致（例如后续还要与 GitHub 对账），用显式提交者信息 amend 复现：

```bash
GIT_COMMITTER_NAME='<name>' GIT_COMMITTER_EMAIL='<email>' \
GIT_COMMITTER_DATE='<unix-ts> +0800' \
git commit --amend --no-edit
```

**时区必须显式写 `+0800`**，否则 reconstruct 出的 SHA 会对不上。

---

## 6. 认证 —— 移除 auth-disabled 模式

本地开发用以下方式启动：

```bash
DEER_FLOW_AUTH_DISABLED=1 make dev-daemon
```

**生产环境：**

- **不要**设置 `DEER_FLOW_AUTH_DISABLED`（确认 `.env` 与 shell 环境中均无此变量）；
- 使用 `./scripts/deploy.sh`（Docker 生产）而不是 `make dev` / `make dev-daemon`；
- 配置真实认证（本地账号、SSO 或企业身份源）；
- 验证 `app/gateway/auth_disabled.py` 的 `is_auth_disabled()` 返回 `False`（部署后验证见第 10 节：`/api/config` 应返回 401）。

**为什么重要：** `DEER_FLOW_AUTH_DISABLED=1` 会让所有请求以合成管理员（`default`）身份运行。artifact 文件解析会回落到 `default` 用户桶，导致真实用户 ID 创建的会话文件访问异常。在生产中这既是功能问题也是安全问题。

---

## 7. 运行时配置

`config.yaml` 与 `extensions_config.json` 是 gitignored 的宿主机文件，位于仓库根目录，可通过 Gateway API 热更新，无需重建镜像。

### `config.yaml`

- 用生产凭据替换开发用的模型端点与密钥；
- 确认 `log_level` 适合生产（`info` 或 `warning`）；
- 按需启用生产级速率限制 / token 预算；
- 不要直接照抄示例文件：从 `config.example.yaml` 复制后填入真实值。

### `extensions_config.json`

- 移除所有示例 MCP server（`github`、`postgres` 等），除非确有需要且已正确配置；
- 添加生产 MCP server 及真实凭据；
- 审查 `skills` 块：示例模板中默认禁用的技能（如 `skill-reviewer`、`skill-creator`、媒体生成类）仅在业务需要时启用。

### 已知教训：不要添加代码未消费的配置键

曾出现 AI 幻觉在 `config.yaml` 中添加 `default_agent` 配置块的情况 —— 代码中没有任何地方读取该键，属于死配置（已于 2026-07-20 清理）。**新增任何配置键之前，先在代码中全局搜索确认有消费方。**

### 技能与默认值

- 示例 `extensions_config.json` 默认禁用多个 public 技能，上线前审查哪些应对最终用户启用；
- 带 `allowed-tools` 限制的技能（如 `skill-reviewer`）仅在用户明确需要该工作流时启用。

---

## 8. 前端构建自检（血泪教训，强制执行）

**事故：** 2026-07-19 一次品牌提交误改了 `frontend/pnpm-lock.yaml` 中 `h3` 包的 integrity 哈希，导致生产构建 `ERR_PNPM_TARBALL_INTEGRITY` 失败。

**强制规定：**

1. 任何涉及 `frontend/` 的提交，提交前必须在本地验证：

   ```bash
   cd frontend && pnpm install --frozen-lockfile
   # 或
   cd frontend && pnpm check
   ```

2. `pnpm-lock.yaml` **只允许由 pnpm 自身改写，禁止任何文本级手工编辑**（包括合并冲突时 —— 用 pnpm 重新生成，不要手改哈希）。

---

## 9. Docker 构建上下文

`.dockerignore` 必须排除 `backend/.deer-flow`（gateway 挂载的运行时状态目录，其中包含 Docker builder 无权读取的 sandbox 文件；不排除会导致镜像构建失败）。当前 `.dockerignore` 已包含该条目，修改 `.dockerignore` 时不得移除。

---

## 10. 部署后验证

每次部署后按顺序执行：

```bash
# 1. 四个容器全部 Up
docker ps --filter name=deer-flow --format 'table {{.Names}}\t{{.Status}}'

# 2. 入口 307 重定向到 /login
curl -sI http://localhost:2026/ | head -5
# 期望：HTTP/1.1 307 ... 且 Location: /login

# 3. 认证保护正常（未带凭据应 401）
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:2026/api/config
# 期望：401

# 4. gateway 日志无报错、启动完成
docker logs deer-flow-gateway 2>&1 | tail -50
# 期望：无 traceback，出现 "Application startup complete"
```

四项全部通过才算部署成功。

---

## 11. 上海电气品牌定制

以下定制必须保留（直接维护并发布于 `codex/prod-canonical`）：

- **登录页**：`frontend/src/app/(auth)/login/page.tsx`
- **品牌素材**：`frontend/public/images/branding/`
- **根路由重定向**：`/` → `/login`
- **工作区导航**：左下下拉菜单仅保留 Settings

未经用户明确要求，**不要**恢复上游公开落地页或替换上海电气品牌标识。

---

## 12. 数据持久化

- 确保 `.deer-flow/`（或 `DEER_FLOW_HOME` 覆盖值）挂载在持久卷上；
- 确认 `users/`、`threads/`、`memory/` 目录在容器重启后存活；
- 设置正确的文件系统权限，保证 Gateway 进程可读写。

---

## 13. 安全与密钥

- 永不提交 `config.yaml`、`extensions_config.json`、`.env`、`.deer-flow/` 数据；
- 轮换所有在本地开发中使用过的凭据；
- 确认 `github token.md` 之类的本地备忘不在部署镜像内。

---

## 14. 命令速查

```bash
# 本地开发（免认证、热重载）
DEER_FLOW_AUTH_DISABLED=1 make dev-daemon

# 生产（starl-38，唯一支持入口）
cd ~/deerflow
./scripts/deploy.sh check     # 部署前校验
./scripts/deploy.sh           # build + start
./scripts/deploy.sh down      # 停止并移除
```

---

## 15. Dev-Only 参数清单（运维交接的 source of truth）

| Parameter | Local value | Production value | Where to set | Rationale |
|-----------|-------------|------------------|--------------|-----------|
| `DEER_FLOW_AUTH_DISABLED` | `1` | unset / absent | shell env / `.env` | Bypasses auth in dev; must be off in production. |

### 新增 dev-only 参数登记规则

如果引入了新的环境变量、配置开关或仅本地安全的快捷方式，必须**在同一个变更集内**按上表格式在此登记一行。本表是运维交接时"上线前必须移除项"的唯一权威来源。

---

最后更新：2026-07-20
