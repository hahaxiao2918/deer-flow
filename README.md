# DeerFlow — 上海电气分发版

DeerFlow 是基于 LangGraph 架构的 AI super-agent 系统:后端运行一个"超级代理",具备沙箱执行、持久记忆、子代理委派与可扩展工具(内置 / MCP / 社区)能力,全部按线程隔离;前端是 Next.js 聊天界面;外部 IM 平台经 Gateway 桥接同一个 agent。

本仓库是上海电气内部分发版,fork 自 [bytedance/deer-flow](https://github.com/bytedance/deer-flow)。相对上游,本分发版提供 SynForge 品牌登录体验、专利分析套件、定时任务、技能治理等企业定制,详见[分发版特性](#分发版特性)。

读者对象:企业内部用户、运维与开发同事。上游面向公网用户的文档(官网、多语种 README、公网安装与贡献引导)不适用于本仓库。

## 目录

- [快速开始](#快速开始)
  - [首次配置](#首次配置)
  - [本地开发模式](#本地开发模式)
  - [生产部署](#生产部署)
- [服务拓扑](#服务拓扑)
- [分发版特性](#分发版特性)
- [分支、远程与推送纪律](#分支远程与推送纪律)
- [运行时配置](#运行时配置)
- [仓库结构](#仓库结构)
- [文档地图](#文档地图)
- [上游归属](#上游归属)

## 快速开始

前提:已克隆本仓库(内网克隆源 `ssh://git@10.84.91.38:7023/hahaxiao/deer-flow.git`,或 GitHub fork `https://github.com/hahaxiao2918/deer-flow.git`)。

### 首次配置

```bash
make setup       # 交互式安装向导(推荐新环境)
make doctor      # 检查配置与系统依赖
```

也可以手动生成配置文件后自行编辑:

```bash
make config      # 从 config.example.yaml / extensions_config.example.json 生成本地配置
```

首次打开 Web 界面时会进入 `/setup` 向导完成初始化。

### 本地开发模式

```bash
make dev         # 启动 Gateway(18001)+ Frontend(13000)+ Nginx(12026),热重载
make stop        # 停止全部服务
```

浏览器打开 `http://localhost:12026`(Nginx 统一入口)。

模块级命令(在对应模块目录内执行):

```bash
cd backend && make dev        # 仅 Gateway,热重载(端口 8001)
cd backend && make test       # 后端测试
cd backend && make lint       # ruff check
cd backend && make format     # ruff format

cd frontend && pnpm dev       # 仅前端开发服务器(端口 3000)
cd frontend && pnpm check     # lint + 类型检查(提交前必跑)
cd frontend && pnpm test      # 前端单元测试
```

经验法则:根目录 `make` 驱动全栈;`backend/Makefile` 与 `frontend/`(pnpm)驱动单模块。完整列表见 `make help`。

### 生产部署

`./scripts/deploy.sh` 是重建、启动、停止生产栈的**唯一支持入口**(Compose 项目名固定 `deer-flow`):

```bash
./scripts/deploy.sh check    # 校验部署输入与运行中挂载,不动容器
./scripts/deploy.sh          # 无参 = build + start
./scripts/deploy.sh down     # 停止并移除容器
```

必须遵守的纪律(完整说明见 [docs/production-deployment.md](docs/production-deployment.md)):

- **禁止**对 `gateway` / `frontend` / `nginx` 执行临时 `docker compose up/down/stop/rm`;部署脚本统一管理 `.env`、host 路径导出、sandbox overlay 与挂载校验。
- 操作范围仅限 `deer-flow` Compose 项目;不得停止、重启或重建无关容器(如 `ipa-gateway`)。
- `.dockerignore` 必须排除 `backend/.deer-flow`(当前已配置;改动构建上下文时复查)。
- 部署成功的判据:脚本确认 `config.yaml` 与 `extensions_config.json` 是宿主机普通文件,且运行中的 gateway 挂载的正是这两个解析后的路径——对应路径出现目录是硬失败,不要在未检查内容的情况下删除或替换。

## 服务拓扑

| 服务 | `make dev` | Docker 生产 | 角色 |
| --- | --- | --- | --- |
| Nginx | `12026` | `2026` | 统一反向代理入口;将 `/api/langgraph/*` 重写转发到 Gateway 的 `/api/*`,其余 `/api/*` 直连 Gateway REST 路由 |
| Gateway API | `18001` | `8001` | FastAPI REST API + 内嵌 LangGraph 兼容 agent 运行时 |
| Frontend | `13000` | `3000` | Next.js Web 界面 |
| Provisioner | `8002` | `8002` | 可选,仅 provisioner/K8s 沙箱模式启用 |

生产 Docker 栈另含 `deer-flow-redis` 容器(缓存/队列)。

生产机 starl-38(`10.84.91.38`)上,Nginx 绑定 localhost 并加入 `web-network`,仅经域名对外暴露;入口为 `http://localhost:2026`。详见 [docs/production-deployment.md](docs/production-deployment.md)。

## 分发版特性

以下为相对上游 `bytedance/deer-flow` 的增量(截至 2026-07-20,`codex/prod-canonical` 领先 `upstream/main` 29 个提交)。

### 品牌与登录(SynForge)

- 根路由重定向到 `/login`;品牌登录页为 `frontend/src/app/(auth)/login/page.tsx`,品牌资源在 `frontend/public/images/branding/`。
- 不要恢复上游公共落地页或替换上海电气品牌标识,除非有明确需求。

### 技能系统企业化

- 技能运行时策略:`allowed-tools` 仅对当前激活的技能生效。
- 技能显示名/描述支持 i18n overlay。
- 默认禁用非必要公共技能(见 `extensions_config.example.json` 中各技能的 `enabled: false`)。
- `skill-reviewer` 技能质量审核:只读,基于 harness 层 `review_skill_package` 工具与 `contracts/skill_review/` 契约;模型可见的审核数据经压缩与标签中和,完整原始载荷保留在工具 artifact 中。

### 专利分析套件(patent-research.v2)

- `skills/public/` 下五个技能:`applicant-tech-patent-retrieval`、`evidence-based-labeling`、`technology-insight-analysis`、`tech-evolution-analysis`、`black-swan-tech-radar`。
- 运行时契约 `contracts/patent_skill_runtime/`(v2 schema + manifest)。
- 专利数据 MCP(`extensions_config.json` 中 `patent-data`,默认禁用):成本管控(专用 token + 项目预算映射)、共享代理网络暴露、授权头解析、部署预检。启用前必须配置专用 token 与预算映射。

### 定时任务

- 工作区页面 `/workspace/scheduled-tasks` + 由 `config.yaml` 中 `scheduler.enabled` 门控的后台调度服务。
- 后台定时运行为非交互模式:lead agent 工具集在 `context.non_interactive=true` 时排除 `ask_clarification`;该键仅对内部鉴权调用方(调度器启动链路)生效,客户端传入的 `context.non_interactive` 会被丢弃。

### MCP 远程工具媒体内联

- HTTP/SSE MCP 工具看不到 Gateway 的线程级 `/mnt/user-data` 挂载。当这类工具收到线程 `/mnt/user-data` 下的图片/视频时,网关将其解析为当前线程文件并内联为内存 `data:` URL(上限 4 MiB,超限在发起远程调用前拒绝);原始虚拟路径保留在 agent 状态与持久化历史中,载荷字节不进入模型可见的工具参数、checkpoint 或运行记录。
- exa 工具支持 `base_url` 覆盖(hub 出口迁移)。

### 认证与多用户

- auth-disabled 模式下跳过 thread `owner_check`,artifact 解析支持跨 user bucket 回退。
- 注意:`DEER_FLOW_AUTH_DISABLED=1` 等 dev-only 参数**上生产前必须移除**,完整清单见 [docs/production-deployment.md](docs/production-deployment.md)。

### IM 频道

Feishu、Slack、Telegram、Discord、DingTalk 经 Gateway 桥接同一个 agent(实现位于 `backend/app/channels/`)。

### 前端

- 子任务时间线展示 tool-call 参数。
- favicon 替换与设置菜单精简。

## 分支、远程与推送纪律

| 项 | 值 |
| --- | --- |
| 生产规范分支 | `codex/prod-canonical`(生产部署只从该分支构建) |
| 长期定制分支 | `codex/shanghai-electric`(品牌与定制提交在此维护,合入规范分支后发布) |
| `origin` | `github.com/hahaxiao2918/deer-flow`(可写 fork) |
| `upstream` | `github.com/bytedance/deer-flow`(只读,push 已禁用) |
| `gitea` | `ssh://git@10.84.91.38:7023/hahaxiao/deer-flow.git`(starl-38 本机 Gitea 镜像,2026-07-20 起为部署主通道) |

纪律:

- **双远程推送**:每次推送须同时推到 GitHub 与 Gitea——`git push origin <branch> && git push gitea <branch>`。生产服务器从本机 Gitea 回环拉取,不受 GitHub 出口抖动影响。
- 不要更改远程 URL、不要 force-push,除非获得明确批准;企业变更只推送到 `origin`(与 `gitea`),绝不推送 `upstream`。
- 同步上游时:`fetch upstream` 后将 `upstream/main` 合入 `codex/shanghai-electric`,保留本地定制并解决冲突,跑检查后再发布;不得用全新克隆替换本仓库或用 `reset --hard` 更新。

标准发布流程(细节与应急方案见 [docs/production-deployment.md](docs/production-deployment.md)):

```bash
# 开发机
git push origin codex/prod-canonical && git push gitea codex/prod-canonical

# 生产机 starl-38
cd ~/deerflow
git fetch gitea && git pull
./scripts/deploy.sh check
./scripts/deploy.sh
```

## 运行时配置

运行时配置位于仓库根目录,均为 gitignored 文件:

- `config.yaml` — 主应用配置,由 `config.example.yaml` 复制生成。
- `extensions_config.json` — MCP servers 与技能开关,由 `extensions_config.example.json` 复制生成。

两个文件可在运行时经 Gateway API 热更新;配置 schema 与解析顺序见 [backend/AGENTS.md](backend/AGENTS.md)。

纪律:绝不提交 token、`.env`、`config.yaml`、`extensions_config.json` 或 `.deer-flow` 运行数据。新增 dev-only 的环境变量/配置开关时,必须同步登记到 [docs/production-deployment.md](docs/production-deployment.md) 的生产部署清单。

## 仓库结构

```
backend/packages/harness/   # deerflow-harness 包(import: deerflow.*)— agent 框架
backend/app/                # FastAPI Gateway + IM 频道(import: app.*)
backend/tests/              # 后端测试(后端实行 TDD)
frontend/                   # Next.js 前端(pnpm)
docker/                     # docker-compose 文件、nginx 配置、provisioner
skills/public/              # 随仓库分发的技能(含专利分析套件、skill-reviewer)
skills/custom/              # 本地自定义技能(gitignored)
contracts/                  # 跨组件 JSON 契约(subagent 状态、技能审核、专利技能运行时)
scripts/                    # 根编排脚本(deploy.sh、check、doctor、setup_wizard 等)
docs/                       # 跨模块文档(含生产部署手册)
Makefile                    # 根编排:驱动全栈(dev/start/stop、docker、setup)
config.example.yaml         # 主配置模板
extensions_config.example.json  # MCP + 技能模板
```

## 文档地图

- [AGENTS.md](AGENTS.md) — 仓库导览与跨模块约定,开发侧事实源(本 README 的工程化补充)。
- [backend/AGENTS.md](backend/AGENTS.md) — 后端深度:harness/app 分层、agent 与中间件链、沙箱、MCP、技能、记忆、IM 频道、持久化与迁移、配置系统、测试布局。
- [frontend/AGENTS.md](frontend/AGENTS.md) — 前端深度:Next.js App Router 布局、线程/流式数据流、代码风格、命令。
- [docs/production-deployment.md](docs/production-deployment.md) — 生产部署手册:部署入口、主机拓扑、Gitea 链路、认证清单、部署后验证、密钥与持久化,是运维交接的事实源。
- [SECURITY.md](SECURITY.md) — 安全策略(沿用上游)。

## 上游归属

本项目是 [bytedance/deer-flow](https://github.com/bytedance/deer-flow) 的 fork,遵循上游 MIT 许可证(见 [LICENSE](LICENSE),版权归 Bytedance 及 DeerFlow 作者所有)。上游原版多语种 README 已归档至 `.readme-archive/`,仅供 AI agent 参考,不作为面向用户的文档。
