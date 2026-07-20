# 专利分析套件使用手册（patent-research.v2）

上海电气分发版内置的专利分析能力，由三部分组成：**五个分析技能**（`skills/public/`）、**v2 运行时契约**（`contracts/patent_skill_runtime/`）、**专利数据 MCP sidecar**（`patent-data`，成本管控的数据网关）。本文面向使用与运维，方法学与契约细节以 [RUNTIME_ARCHITECTURE_V2.md](patent-skill-runtime/RUNTIME_ARCHITECTURE_V2.md) 为准。

## 组成

| 组件 | 位置 | 说明 |
| --- | --- | --- |
| 申请人技术检索 | `skills/public/applicant-tech-patent-retrieval` | 语料构建阶段，产出 `CorpusManifest` |
| 证据标注 | `skills/public/evidence-based-labeling` | 逐件文献的纳入/相关性/路线标注 |
| 技术洞察分析 | `skills/public/technology-insight-analysis` | 技术机理与路线对比（`RouteMap`） |
| 技术演进分析 | `skills/public/tech-evolution-analysis` | 时间切片、阶段与跃迁（`EvolutionMap`） |
| 黑天鹅雷达 | `skills/public/black-swan-tech-radar` | 可证伪弱信号与监测触发器（`WeakSignalRegister`） |
| 运行时契约 | `contracts/patent_skill_runtime/`（v2 JSON Schema + manifest）、`docs/patent-skill-runtime/` | 产物流水线、状态机、放行门禁 |
| 数据 sidecar | `extensions_config.json → mcpServers.patent-data` | 内部 HTTP MCP，不调用 LLM，只暴露外部事实与成本管控 |

## 启用与配置

1. **技能开关**：示例配置 `extensions_config.example.json` 中五个技能默认 `enabled: false`；生产与本地运行配置均已启用。改动经 Gateway API 热更新即可生效。
2. **数据通道**：`mcpServers.patent-data` 以 `type: http` 注册，经共享代理网络暴露（当前为 `https://mcphub.server.starlove.top/patent/mcp`），鉴权头为内部 bearer token。
3. **sidecar 环境**（仅服务端持有，绝不进入 Gateway 配置）：`ZHIHUIYA_API_KEY`（智慧芽数据源密钥）、`MCP_TOKEN`、`DATA_MCP_CLIENT_TOKENS_JSON`（token → client_id 映射）、`DATA_MCP_CLIENT_PROJECTS_JSON`（client_id → 项目映射）、`DATA_MCP_PROJECT_BUDGETS_JSON`（项目预算，美元）。完整清单见 `services/deerflow-patent-data-mcp-v2/README.md`。
4. **成本纪律**：MCP 工具不接受 `project_id`；未配置 client 或项目的请求在任何计费调用前被拒绝。`D114` 批量文本只返回轻量 `BatchManifest`，正文经 `patent_get_passages` 从零成本的本地 TTL 缓存读取。

## 在 Web UI 中使用

- **斜杠激活**：消息以 `/技能名 任务` 开头（如 `/applicant-tech-patent-retrieval 检索某申请人固态电池方向专利`），本轮强制激活该技能。
- **自然语言路由**：lead agent 按"交付物"选择唯一主技能：

| 你要的交付物 | 主技能 |
| --- | --- |
| 候选清单、可审计语料 | `applicant-tech-patent-retrieval` |
| 逐件纳入/相关性/路线标注 | `evidence-based-labeling` |
| 技术机理与路线对比 | `technology-insight-analysis` |
| 时间切片、阶段与跃迁 | `tech-evolution-analysis` |
| 可证伪弱信号与监测触发器 | `black-swan-tech-radar` |

复合请求按 DAG 执行（先产 `CorpusManifest`，下游技能必须复用上游产物，不得静默重建语料）。

## 产物契约（v2.0.0）

流水线：`ResearchBrief → CorpusManifest → EvidenceCard[] → LabelDecision[] | RouteMap | EvolutionMap | WeakSignalRegister → AnalysisClaim[] + limitations + handoff`。

- 多阶段/多轮产物存放于 `workspace/patent-analysis/<analysis_id>/`；单阶段小结果可内联返回。
- 证据等级：`E3` 独立权利要求直接限定 / `E2` 从属权利要求或实施例直接支持 / `E1` 仅摘要背景或说明书 / `I` 模型解释 / `U` 证据缺失。置信度与证据等级相互独立——有把握的解读仍是 `I`，证据缺失记 `U` 而不是反向事实。
- 状态机：`needs_input`、`scope_ambiguous`、`ready`、`no_results`、`partial_data`、`insufficient_evidence`、`unsupported_request`、`completed`。部分产物可续跑，记录上游产物 ID、假设、局限与下一缺失条件。
- 每个技能对阻塞性歧义至多发起一次合并澄清；非阻塞缺省使用显式默认值并记入 `ResearchBrief.defaults_applied`。

## 方法学红线（技能内建不变量）

- 默认以**公开文献**为分析单元；公开号、申请号、授权公告号、同族号严格分开。
- 只有在明确命名同族定义时才报同族计数（DOCDB 简单同族 ≠ INPADOC 扩展同族）；无同族归一化时不得把公开件数换算成发明件数。
- 申请人角色以公布文本为准；时间线只用一种主日期基准；近 18 个月公开数据标记为可能不完整（申请通常约 18 个月才公开）。
- 专利自述效果视为申请人主张，不作为经独立验证的性能。

## 已知限制

- v2 暂不进行 general-purpose 子代理委派（当前运行时的 `skill_context` 会把读过的技能跨轮激活并合并工具权限）；可靠委派等待后续运行时改造（见架构文档"Current runtime limitation"）。
- 数据范围：P002 检索、P012 著录、D114 批量文本；不含法律状态/同族/引文、AMiner、供应商 AI 接口。
- 放行门禁（release gates）见架构文档第 5 节；版本沿革见 [VERSION_HISTORY.md](patent-skill-runtime/VERSION_HISTORY.md)。

## 资料索引

- 架构与契约：[RUNTIME_ARCHITECTURE_V2.md](patent-skill-runtime/RUNTIME_ARCHITECTURE_V2.md)、`contracts/patent_skill_runtime/v2/runtime-contract.schema.json`、`contracts/patent_skill_runtime/manifest.json`
- 数据 sidecar：`services/deerflow-patent-data-mcp-v2/README.md`（V2 范围与运行配置）
- 评估记录：`docs/patent-skill-runtime/V2_EVALUATION.md`

最后更新：2026-07-20
