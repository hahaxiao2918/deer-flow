# Ultra 模式未派遣子任务调查

日期：2026-09-02（Asia/Shanghai）  
范围：Ultra 的前后端配置映射、`task` 工具装配、委派提示策略、生产运行证据。  
结论性质：证据调查；本分支不改变委派策略或公共接口。

## 结论

当前没有发现 Ultra 模式下 `task` 工具被错误隐藏或委派链路失效。

Ultra 的真实语义是：在 Pro 的思考和计划能力之上，**开放**子代理委派能力；它不是“每个请求必须派遣子任务”。启用后，系统提示仍明确要求默认直接执行，仅在并行节省、专门能力或上下文隔离的收益明显大于启动、重复发现、协调、合成和冲突风险时才调用 `task`。因此，简单任务、父 Agent 已掌握上下文的任务、步骤相互依赖或会修改重叠文件的任务不派遣，是当前设计预期，而不是回归。

生产验证也表明链路可用：前端式显式 Ultra 上下文被 Gateway 解析为 `is_plan_mode=True, subagent_enabled=True`，`task` 成功启动子代理并产生子代理 token；取消后 Gateway 持续健康。用户报告的“很多时候不派遣”更符合模型遵循收益路由策略后的选择，而不是工具不可用。

有一个需要明确的接口边界：仅向原始 HTTP API 发送 `context.mode="ultra"` **不会**由后端推导其他开关。Web 前端会把模式展开为 `thinking_enabled=true`、`is_plan_mode=true`、`subagent_enabled=true` 和默认 `reasoning_effort=high`；第三方调用方必须发送这些显式字段。只发 `mode` 的原始 API 调用会以 `subagent_enabled=False` 创建 Agent，这不是 Web UI 的问题，但容易造成集成方误判。

## 配置流证据

### 1. Web 前端会显式展开 Ultra

`frontend/src/core/threads/hooks.ts` 的普通提交和重新生成入口使用同一映射：

| 模式 | thinking_enabled | is_plan_mode | subagent_enabled | 默认 reasoning_effort |
| --- | ---: | ---: | ---: | --- |
| flash | false | false | false | 未指定 |
| thinking | true | false | false | low |
| pro | true | true | false | medium |
| ultra | true | true | true | high |

因此，从当前 Web UI 正常发送的 Ultra 请求不会只携带 `mode`。

前端录制测试 `frontend/tests/e2e-record/record-write-read-file.spec.ts` 和后端 replay helper `backend/tests/_replay_fixture.py` 也固定了相同契约，并特别说明 `mode` 本身只是前端状态，真正改变 Agent prompt/toolset 的是显式 `is_plan_mode` 与 `subagent_enabled`。

### 2. Gateway 转发开关，但不从 mode 推导

`backend/app/gateway/services.py` 将 `mode`、`thinking_enabled`、`is_plan_mode`、`subagent_enabled` 等列入允许的运行上下文字段，并双写到运行时 `context` 和兼容用 `configurable`。这里没有 `mode == ultra` 的后端推导逻辑。

这个边界解释了生产测试中的两种结果：

- 只发送 `mode=ultra` 的原始 API 请求：日志为 `is_plan_mode=False, subagent_enabled=False`。
- 发送前端式完整 Ultra 上下文：日志为 `is_plan_mode=True, subagent_enabled=True`。

建议所有非 Web 调用方复用前端的模式映射，不能把 `mode` 当成后端能力开关。

### 3. Custom Agent 可以收窄委派权限

`backend/packages/harness/deerflow/agents/lead_agent/agent.py` 将请求开关与 Custom Agent 的 `allowed_subagents` 相交：

- `None`：允许使用所有已启用子代理；
- `[]`：硬禁用委派，即使请求发送 `subagent_enabled=true`；
- 非空列表：只允许列出的子代理。

默认 Lead Agent 没有空 allowlist。生产验证使用默认 Agent，日志显示 `subagent_enabled=True`，所以本次现象不是 allowlist 导致。若以后只在某个 Custom Agent 上复现，应首先检查这个字段。

## 工具装配与策略证据

### 1. 开关为 true 时会装配 task

`backend/packages/harness/deerflow/tools/tools.py::get_available_tools()` 在 `subagent_enabled=true` 时加入 `SUBAGENT_TOOLS`。Lead Agent factory 同时加入 `SubagentLimitMiddleware` 和绑定到进程执行容量的 `task` 工具。`task` 不是 MCP deferred tool，不需要 `tool_search` 晋升。

工具仍可能被服务器授权策略或 Custom Agent 空 allowlist 收窄；当前默认生产运行没有命中这些限制。

### 2. 路由规则刻意不保证委派

`backend/packages/harness/deerflow/agents/lead_agent/prompt.py`、`task_tool.py`、两个内置子代理描述和 `backend/packages/harness/deerflow/subagents/AGENTS.md` 使用一致的收益路由策略：

- 子代理是可选优化，默认直接执行；
- 复杂、多步骤、输出长或仓库大，本身都不是委派理由；
- 有效收益是独立并行带来的延迟下降、专门能力和上下文隔离；
- 重复仓库发现、协调与合成、重叠状态和副作用都是成本；
- 使用尽可能少的子代理，并在每批后重新评估。

因此 UI 文案“可调用子代理分工协作”与实现一致；若产品期待“Ultra 必定派遣”，那是产品策略变更，而不是缺陷修复，并会显著增加额度消耗和共享状态风险。

## 生产证据

P0 部署后的 Gateway 日志和运行账本提供了以下样本（日志时间换算为东八区）：

| 样本 | 上下文/结果 | 证据 |
| --- | --- | --- |
| 原始 API 边界探针 | 只发送 `mode=ultra`，未展开能力字段 | Agent 日志显示 `is_plan_mode=False, subagent_enabled=False`；无子代理 token |
| 前端式 Ultra 取消探针 | 显式发送 Ultra 四项上下文，要求一个可取消的后台步骤 | Agent 日志显示 `is_plan_mode=True, subagent_enabled=True`；成功启动 `task`，运行账本记录 18,154 subagent tokens；取消后 Gateway 维持健康 |
| 用户问题会话 `da40f2b5…` | 发生过长工具循环和取消死锁的历史运行 `eef1291a…` | 账本记录 979,577 subagent tokens；现场堆栈位于 `task_tool` 取消路径，证明该运行实际派遣了子代理，而不是 Ultra 工具缺失 |

生产容器在本次 P0 重建后只保留少量新日志，运行表也不会持久化完整请求 context，因此无法从历史数据准确计算“所有 Ultra 请求中委派比例”。不能用 `subagent_tokens=0` 反推某次历史运行一定是 Ultra，也不能把用户主观观察伪装成统计结论。

一次尝试用内部系统身份创建额外的简单 Ultra 探针被资源授权层以 HTTP 403 拒绝，未创建线程或运行；没有绕过权限继续测试。已有显式 Ultra 成功样本、代码契约和测试足以判断工具链路。

## 验证

在当前生产代码基线执行了以下定向测试：

```text
backend/tests/test_subagent_routing_prompt.py
backend/tests/test_gateway_services.py::test_context_merges_into_configurable
backend/tests/test_tool_deduplication.py::test_subagent_async_only_tool_gets_sync_wrapper

10 passed
```

这些测试分别固定了“默认直接执行/净收益才委派”的 prompt 契约、Ultra 相关上下文的 Gateway 传递，以及启用时子代理工具的装配。

## 建议

1. 不修改当前收益路由，不强制 Ultra 的每个请求创建子任务。
2. 为第三方 API 文档增加模式展开表，或未来提供一个服务端共享的 `resolve_mode_context()`；若实施，需定义显式字段与 mode 冲突时的优先级并补兼容测试，本轮不扩展公共接口。
3. 生产排查时以 `Create Agent(... subagent_enabled=...)` 日志作为第一层判断：
   - `false`：检查调用方是否只发了 `mode`，或 Custom Agent 是否 `allowed_subagents=[]`；
   - `true` 但无 task：结合用户任务判断收益路由，不能直接判为故障；
   - `true` 且模型发出 task 但未执行：再查授权、并发/总量限制和 executor 日志。
4. 若产品希望提高复杂任务的委派概率，应先定义可度量目标和基准任务集，再调整收益阈值；不要使用“所有 Ultra 强制派遣”作为替代指标。

