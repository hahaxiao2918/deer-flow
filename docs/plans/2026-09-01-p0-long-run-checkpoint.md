# P0 长程工作检查点

更新时间：2026-09-02 06:22 CST
当前分支：`codex/p0-release-candidate`
当前 HEAD：`55e3c05f830f5e9382261a1bf564d80cb2b0210c`

## 不可变约束

- 不使用子代理。
- 不更新 `main`，不合并本轮范围外的 upstream 提交。
- 不修改或提交用户文件 `config.yaml` 与
  `docs/pr-evidence/智慧芽搜索帮助_结构化_核对修订版.md`。
- 不提交 token、`.env`、`.deer-flow` 数据或其他运行数据。
- 生产服务只通过 `./scripts/deploy.sh` 操作，不触碰其他容器。

## 自动续跑状态

- 当前 Codex 任务的持续 Goal 已创建并处于 active。
- 计划要求的 2026-09-02 02:17 Asia/Shanghai 当前聊天 Scheduled task
  尚未创建：当前任务未暴露任何 automation/Scheduled 创建工具，无法在应用的
  Scheduled 列表中确认。不得用仓库脚本伪装为 Codex 会话唤醒器。
- 若平台在额度恢复后自动续跑，先读本文件、根与模块 `AGENTS.md`，再从下方
  第一个未完成项目继续，不重复已经有最终摘要的验证。

## 阶段状态

- [x] 收紧并提交 Luna 的两轮流式 Playwright 用例。
- [x] 在修复前提交上运行负向对照，证明旧实现失败。
- [x] 修复并提交 SSO-first / break-glass 认证测试隔离。
- [x] 组装 `codex/p0-release-candidate`。
- [ ] 发布候选全量后端、前端、Playwright 和本地栈回归全绿（仅剩本地栈）。
- [ ] 合入 `codex/prod-canonical`，同步远端并正式部署。
- [ ] 完成生产验收与观察。
- [ ] 完成专利/Aminer 字段调查报告。
- [ ] 完成 Ultra 委派行为调查报告。

## 当前事实

- P0 核心提交：
  - `5ee3373dd` 品牌改动。
  - `f469dfbb7` 前端流式排序修复。
  - `fe36bfc8e` 子任务取消锁外执行修复。
- E2E 收口提交：`2308562d0 test(frontend): cover two-turn stream order across reconnect`。
- 当前修复版本 Playwright：`1 passed (5.2s)`。SSE `values` 已移除第一轮
  `step1`，并在 route URL 改写前断言普通提交为 POST
  `/api/langgraph/threads/{thread}/runs/stream`、重连为 GET
  `/api/langgraph/threads/{thread}/runs/{run}/stream`。
- 修复前 `5ee3373dd` 的 detached worktree 使用同一测试失败：第一轮步骤
  `y=396`、第二轮用户消息 `y=276`，证明旧实现确有跨轮搬运且回归测试有效。
- 负向对照的 production build 编译完成后在 TypeScript 阶段因内存压力收到
  exit 137；随后改用旧源码 dev server 完成有效对照。临时 worktree 已删除。
- Luna 后端全量结果为 `12594 passed, 78 skipped, 17 failed`；失败集中于认证
  测试读取生产 `allow_registration: false` 及共享 `_login_attempts` 状态，不能
  宣称全绿。
- 认证基线分支 `codex/sso-auth-test-baseline` 已形成三个独立提交：
  - `66070a2fb`：本地认证契约显式启用测试注册并隔离 `_login_attempts`；
  - `282684b10`：subagent middleware policy 测试显式传入 `AppConfig`，不再
    隐式读取宿主配置；
  - `34c93a26d`：IPD `/loginsso` start/callback 前端 E2E。
- 后端认证、SSO、注册门禁与 subagent policy 定向结果：`209 passed`。
- SSO 前端 E2E：`2 passed`；该 worktree 的 `pnpm check` 通过。
- 一次显式指向主 `config.yaml` 的实验因当前 shell 缺少配置引用的
  `HUB_EGRESS_TOKEN` 而在配置解析阶段失败，结果无效且未改配置；不要把它
  计入回归结论。
- 发布候选合并提交：`9d55046cc`（P0）与 `0120b0128`（认证基线）；
  `55e3c05f8` 仅修复两份计划文档的行尾空格，`git diff --check` 通过。
- 发布候选定向后端：`291 passed`；`make format` 通过，1260 文件无变化。
- 发布候选前端：frozen install、`pnpm check`、139 文件 1068/1068 单测、
  production build 全部通过。
- 发布候选 Playwright：两轮流式/刷新/重连与两项 SSO entry 共 `3 passed`。
- 发布候选后端全量：`12611 passed, 78 skipped, 30 warnings`，耗时
  `806.94s (0:13:26)`，零失败。
- Goal 在额度恢复后于 06:22 CST 自动续跑并取回完整 pytest 汇总；计划中的
  02:17 Scheduled task 因当前客户端未暴露 automation 工具，未能创建。
- 两个用户未跟踪文件必须一直保留且不纳入提交。

## 下一步

1. 在发布候选 worktree 通过根级 `make stop && make dev` 完整启动本地栈。
2. 验证 Gateway/Nginx 健康、普通对话 SSE、后台 run 立即取消后 Gateway
   持续响应；完成后停止本地栈。
3. 做最终静态/敏感文件审计；全绿后合入 `codex/prod-canonical`。
