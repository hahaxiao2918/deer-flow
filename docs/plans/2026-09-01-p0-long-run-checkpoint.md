# P0 长程工作检查点

更新时间：2026-09-02 00:00 CST  
当前分支：`codex/p0-stream-cancel-fixes`  
当前 HEAD：`2308562d0edb58dd35f05ce2e78f34392aac4afe`

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
- [ ] 修复并提交 SSO-first / break-glass 认证测试隔离。
- [ ] 组装 `codex/p0-release-candidate`。
- [ ] 发布候选全量后端、前端、Playwright 和本地栈回归全绿。
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
- 两个用户未跟踪文件必须一直保留且不纳入提交。

## 下一步

1. 在 `/home/lxdd/deerflow-sso-auth-test-baseline` 阅读 backend 指南与认证测试，
   用测试专用 fixture 显式启用本地注册并隔离 `_login_attempts`。
2. 先运行 17 项失败相关测试以及 SSO/local-registration 定向测试。
3. 定向全绿后提交测试隔离改动，再组装发布候选。
