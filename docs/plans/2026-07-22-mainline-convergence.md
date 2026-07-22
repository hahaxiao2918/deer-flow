# DeerFlow 本地主线收敛记录

> 开始日期：2026-07-22
>
> 决策：`codex/prod-canonical` 是唯一长期定制与生产分支；`codex/shanghai-electric` 退出活动开发，只保留审计归档。

## 基线与证据

- 干净代码基线：`codex/prod-canonical@4159b8952ac654c6aca507b033760de5af9d6653`。
- 待归档实验分支：`codex/shanghai-electric@c853d5011e7b1fd5c3eaeab754f6b0a4ee651859`。
- 审计标签：`archive/shanghai-electric-pre-convergence-20260722`。
- Gitea 曾在 `prod-canonical` 上多出两个仅用于临时交付的运维提交，其中包含不再需要的加密秘密包。项目负责人已批准删除，不得传播到 GitHub 或新的 canonical 历史。
- 数字底座 SSO 的需求和证据冻结在 `docs/plans/2026-07-22-digital-foundation-sso-todo.md`，主线升级完成前不实施。

## 分支差异结论

两个分支从 `4b7120677469` 分叉。原始差异为 prod 独有 19 个提交、Shanghai 独有 10 个提交；排除四组补丁等价提交后，分别为 15 与 6。直接合并会在治理文档、登录页、扩展配置和五套专利技能中产生冲突，因此禁止整体 merge。

### 已在 prod 中等价存在

- 本地媒体内联；
- Exa `base_url`；
- 远程 MCP 媒体处理；
- SynForge 登录页品牌化。

### 不进入 canonical

- `c68bc2013` 多 Agent 渐进 Skill 运行时：Agent 构造时向 `build_middlewares()` 传入不存在的 `available_subagents` 参数，并且没有把白名单传入最终提示词，属于未闭环实验实现。
- `055add25e` 专利运行时强化：依赖上述实验运行时，不整体移植。
- ZAI/fire 等阶段性交接文档：保留在归档历史，不进入活动产品文档。

### 审核后暂不激活

- 五份专利 methodology 内容具有参考价值，但配套的五份 `output.schema.json` 使用 `contract_version` 等独立顶层结构，与 prod 已发布的 Patent Runtime Contract v2（`schema_version`、`analysis_id`、`status`、`payload`）不兼容。
- 这些材料继续保存在归档分支。未来升级专利套件时，应把 methodology 吸收到统一契约，并重新生成 manifest 哈希与测试，不能直接复制旧 schema。
- 中性 Agent 身份、默认 Agent 能力过滤、子代理白名单、严格 Skill 解析和远程工具结果清洗保留为设计需求；待合并最新 upstream 后按新架构重新评估，不复用旧提交。

## 收敛完成标准

- Origin、Gitea 和部署机使用同一个 `codex/prod-canonical` SHA。
- 活动分支历史不包含已废弃的加密秘密包。
- `AGENTS.md`、README 和部署文档只声明一个 canonical。
- 上海电气品牌、专利 MCP、安全部署入口、媒体处理等生产定制保留。
- upstream 合并、相关测试和 `scripts/deploy.sh` 部署验证完成。
- `codex/shanghai-electric` 仅以审计归档存在，不再作为同步或发布目标。
