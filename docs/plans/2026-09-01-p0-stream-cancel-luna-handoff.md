# P0 流式排序与子任务取消：Luna 验收交接

日期：2026-09-01  
工作分支：`codex/p0-stream-cancel-fixes`  
基线：`codex/prod-canonical` / `7741455e8`

## 已完成的复杂实现

分支目前有三个清晰提交：

1. `5ee3373dd feat(frontend): rebrand workspace as 智海·观澜`
2. `f469dfbb7 fix(frontend): preserve turn order while streaming`
3. `fe36bfc8e fix(harness): cancel subagents outside registry lock`

前端排序修复：

- token 用量基线仍只取 SDK `persistedMessages`。
- 本地轮次排序基线由同一纯函数统一构建，取当前线程的 SDK 消息、分页历史和已提交渲染快照的身份并集。
- 其他线程的渲染快照不会进入基线。
- 普通发送、重新生成和编辑重放共用同一基线构建逻辑。
- 已移植官方 #4834 的 synthetic `run_id` 重连保护。
- 未修改后端 SSE 协议、消息结构或数据库。

后端取消修复：

- `_background_tasks_lock` 内只读取 `result` / `future` 引用。
- `cancel_event.set()`、`Future.cancel()` 和日志均在锁外执行。
- `forget_future` 仍负责清理 `_background_futures`。
- 保持普通 `Lock`，没有换成 `RLock`。
- 仅移植官方 #5076 的最小死锁修复，没有引入 receipt verification。

## 已完成验证

- 品牌改动：`pnpm check` 通过；相关定向测试通过。
- 前端排序定向单测：`message-merge.test.ts` 共 85 项通过。
- 后端取消探针：旧实现会立即断言失败，不会真实挂死；新实现通过。
- `test_subagent_executor.py`：82 项全部通过。
- `make format`：通过，1260 个 Python 文件无需重排。
- `pnpm install --frozen-lockfile`：通过，锁文件无变化。
- `pnpm check`：通过。
- `pnpm test`：139 个文件、1068 项全部通过。
- `pnpm build`：通过；本机约耗时 3 分钟，Playwright 默认 120 秒 webServer 超时不足。
- 后端全量 `make test` 按用户要求停止；停止前已运行到约 99%，未观察到失败，但没有最终 pytest 汇总，因此不能记为全绿。

## 生产与本地服务状态

- 生产紧急恢复已经完成：通过生产仓库的 `./scripts/deploy.sh check`、`down`、`start` 重建 DeerFlow Compose 服务；Gateway、Frontend、Nginx、Redis 恢复健康。
- 重启前再次确认死锁堆栈为 `forget_future -> Future.cancel -> request_cancel_background_task`，涉事会话/run 现场已记录。
- 当前生产仍是旧代码；正式修复未部署，死锁理论上仍可复发。
- 本地开发栈已执行 `make stop`，当前处于停止状态。
- 不要操作仓库中的用户未跟踪文件：`config.yaml` 和 `docs/pr-evidence/智慧芽搜索帮助_结构化_核对修订版.md`。

## Luna 适合执行的剩余简单任务

### 1. 修好并运行新增 Playwright 用例

用例：`frontend/tests/e2e/two-turn-stream-order.spec.ts`。

目标断言：

1. 第二轮早期 AI/tool step 先于第二轮 human 的服务端事件到达时，DOM 始终保持 `human1 -> steps1 -> human2 -> steps2`。
2. 第二轮流式中刷新页面，重连后顺序不变。
3. 流结束后再刷新，最终顺序与流式期间一致。

当前用例是可继续修订的草稿，尚未通过。它目前超时在等待受控 SSE 服务的 `initialConnected`，页面快照中第二轮尚未提交/呈现。优先做以下简单排查：

- 给 `page.on("request")` 临时记录实际 POST stream URL 和 method，确认前端究竟请求 `/api/langgraph/runs/stream` 还是 `/api/langgraph/threads/{id}/runs/stream`。
- 更推荐把受控 POST handler 直接作为 `mockLangGraphAPI(page, { runStreamHandler })` 传入，而不是再用多层 `page.route(...).continue({ url })` 覆盖；该 option 会同时覆盖 generic/thread submit 入口。
- reconnect GET 仍单独拦截 `/threads/{thread}/runs/{run}/stream`。
- `requestSubmit()` 前可等待一次可见的 input state/submit-button enable；若继续使用 Enter，沿用其他 chat E2E 的提交方式。
- 补 mock 或明确忽略 `/token-usage`、`/mcp-tasks`、`/workspace-changes` 请求，避免它们代理到未启动的本地 Gateway 产生噪声。
- 修好后删除临时 request 日志。

推荐运行方式（避免 Playwright 自己重新 build 超时）：

```bash
cd frontend
SKIP_ENV_VALIDATION=1 DEER_FLOW_AUTH_DISABLED=1 pnpm build
SKIP_ENV_VALIDATION=1 DEER_FLOW_AUTH_DISABLED=1 ./node_modules/.bin/next start --port 3000
```

另一个终端：

```bash
cd frontend
PLAYWRIGHT_SKIP_WEB_SERVER=1 pnpm exec playwright test tests/e2e/two-turn-stream-order.spec.ts --project=chromium --reporter=line
```

### 2. 重跑完整机械回归

```bash
cd backend && make format && make test
cd frontend && pnpm install --frozen-lockfile && pnpm check && pnpm test
cd /home/lxdd/deerflow && git diff --check
```

记录完整的最终摘要；后端上次没有最终汇总，必须重跑后才能宣称全绿。

### 3. 本地服务与真实路径冒烟

Harness 已变更，必须完整重启而不是依赖 Uvicorn reload：

```bash
cd /home/lxdd/deerflow
make stop
make dev
```

然后验证：

- `/health` / 本地统一入口正常。
- 普通非子任务对话可完成。
- 两轮带工具步骤的流式顺序正确。
- 第二轮中途刷新后顺序正确。
- 停止/取消一次后台子任务后 Gateway 仍持续响应。

不要为了冒烟调用大量真实模型；用最小确定性路径即可。

### 4. 简单静态检查

- `git status --short` 只允许上述两个用户未跟踪文件存在。
- `git diff --check` 必须通过。
- 检查提交范围不含 `.env`、token、运行数据、`config.yaml` 或 `.deer-flow`。
- `rg -ni "deerflow" frontend/src frontend/public` 只报告技术协议/内部标识等允许残留；若发现新的用户可见品牌字符串，单独列出，不要机械替换内部 API 名称。
- 浏览器简单检查 About 未出现在设置导航，展开/折叠品牌保持单行，欢迎语正确，原“你好，欢迎回来！”保持未改。

## 不交给 Luna 自动执行的高风险步骤

以下步骤等所有回归结果交回主会话审阅后再做：

- 合并 `codex/prod-canonical`。
- push `origin` / `gitea`。
- 更新生产仓库 SHA。
- 生产构建部署或回滚。
- 更新 `main` 或合并 upstream 57 个提交。

## 最终验收门槛

只有满足以下全部条件才可进入正式合并部署：

- 后端全量测试有最终通过摘要。
- 前端 check 与全量单测有最终通过摘要。
- 新增 Playwright 第二轮/刷新/重连场景通过。
- 本地 Gateway 重启后取消子任务不会失去响应。
- `git diff --check` 和敏感文件检查通过。
- 工作树除两个已知用户未跟踪文件外干净。
