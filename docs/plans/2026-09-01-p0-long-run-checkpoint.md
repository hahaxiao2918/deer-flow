# P0 长程工作检查点

更新时间：2026-09-02 07:24 CST
当前分支：`codex/prod-canonical`
当前 HEAD：`a72e2bb5d`（本次检查点提交前）

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
- [x] 发布候选全量后端、前端、Playwright 和本地栈回归全绿。
- [x] 合入 `codex/prod-canonical`，同步远端并正式部署 P0。
- [x] 完成 P0 生产验收与观察。
- [x] 完成专利/Aminer 字段调查报告及确定性字段修正。
- [x] 完成 Ultra 委派行为调查报告。
- [ ] 同步并部署专利 Skill 的确定性排序字段修正。
- [ ] 完成最终生产健康核验、远端 SHA 对齐与检查点收口。

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
- 发布候选本地栈通过根级 `make dev` 完整启动：Gateway `:18001/health`、
  Nginx `:12026/health` 均为 200，根路径 307 到 `/loginsso`，登录页 200。
- 使用本地临时账户执行真实 API 冒烟：普通 stream POST 为 200、收到
  `event: end`；后台 run 立即取消为 204，状态转为 `interrupted`，随后连续
  5 次 Gateway 健康检查均为 200。
- 浏览器核验通过：展开品牌 `WavesInsight`、折叠品牌“观澜”均为单行且无
  溢出；首页描述为智海·观澜 2.0 文案，用户撤销修改的原问候语保持不变；
  设置页不存在“关于/About”。
- 本地栈已经停止，12026/13000/18001 均未监听；仅在发布候选 worktree
  创建的配置软链接、临时数据库、临时账户及 smoke thread 已全部清理，未触碰
  主工作区运行数据。
- Goal 在额度恢复后于 06:22 CST 自动续跑并取回完整 pytest 汇总；计划中的
  02:17 Scheduled task 因当前客户端未暴露 automation 工具，未能创建。
- 两个用户未跟踪文件必须一直保留且不纳入提交。
- P0 发布候选已通过 `--no-ff` 合入生产主干，P0 生产提交为
  `f37d260fdad28db662b92c9080506267a1659de6`；部署前计划基线为
  `7741455e8`，但部署主机实际源代码停在 `ea7ce02eb`，已按生产现场事实记录。
- `origin`、`gitea` 与生产源代码均已同步到 P0 提交 `f37d260fd`，全程未更新
  `main`，生产只调用 `./scripts/deploy.sh check/build/down/start`。
- P0 生产验收通过：Gateway/Frontend/Nginx 健康；外部 SSO 登录成功；确定性
  Playwright 两轮流式、第二轮中刷新、重连和最终刷新通过；普通真实 stream
  收到 `event:end`。
- 生产显式 Ultra 探针成功启动 task 子代理，取消返回 204，run 进入
  `interrupted`；之后 50 秒内 5 次健康检查全为 200，未再出现 Gateway 死锁。
- 专利/Aminer 调查分支 `codex/patent-aminer-audit`，提交 `d063a2446`：
  运行证据表明问题会话没有激活或读取 `patent-query-composition` Skill；本地
  validator 错误地接受 `PA/CSR/APS`，而付费最小探针确认三者均被智慧芽拒绝、
  `ALL_AN` 成功。另确认排序字段必须是 `PBDT_YEARMONTHDAY` /
  `APD_YEARMONTHDAY`，已修正 Skill、manifest 并补契约断言，定向测试 6 passed。
- Aminer 是独立实体 API，不能套用智慧芽字段。生产 schema 中
  `search_paper.title` 默认值为 `"LLM"`，只传 keyword 会被默认 title 污染；
  显式 `title=""` 才得到预期结果。详细矩阵见
  `docs/investigations/2026-09-02-patent-aminer-query-audit.md`。
- Ultra 调查分支 `codex/ultra-delegation-audit`，报告提交 `0c9734ca7`、格式收口
  `0723dc3cf`。结论是 Ultra 开放 task 能力但不保证每次委派；收益路由明确
  “默认直接执行”。Web 前端会显式展开四项能力字段，但原始 API 只发
  `mode=ultra` 不会由后端推导 `subagent_enabled=true`。定向契约测试 10 passed。
- 两个调查分支已分别推送到 `origin` 与 `gitea`，并以独立 merge commit 合入
  `codex/prod-canonical`；当前功能整合提交为 `a72e2bb5d`，尚待最终推送和生产
  Skill 更新。

## 下一步

1. 提交本检查点并完成最终静态、敏感文件及目标分支审计。
2. 将 `codex/prod-canonical` 同步到 `origin`、`gitea`，确认 SHA 一致。
3. 生产仓库快进后只通过 `./scripts/deploy.sh check/build/down/start` 部署专利
   Skill 修正，核验健康与 Skill 投影。
4. 写入最终部署 SHA/结果，推送检查点收口提交并再次确认远端与生产源代码一致。
