# 专利与 AMiner 检索链路审计

日期：2026-09-02

## 结论

这次故障不是 `patent-query-composition` 把申请人字段写成了 `PA`。当前 Skill
及其智慧芽参考已经明确使用 `ALL_AN`，并明确禁止 `PA`、`CSR`、`APS`。问题会话
`da40f2b5-3faa-4486-8e88-2488ab48058b` 的实际根因是：负责专利与学术检索的
通用子代理没有激活或读取该 Skill，直接凭模型先验组合了工具参数。

同时存在两个放大器：

1. `patent_validate_query` 是免费的本地结构校验器，不验证智慧芽字段是否存在。
   它会把 `PA`、`CSR`、`APS` 全部判为成功；真正的 P002 搜索随后才付费失败。
2. AMiner `search_paper` 的 `title` 参数默认值是 `"LLM"`。模型只传 `keyword`
   时，实际查询隐式带上 `title=LLM`，造成大量无结果或只返回 LLM 相关论文。

另发现并修复一处独立、可确定复现的 Skill 错误：排序字段必须是
`PBDT_YEARMONTHDAY` / `APD_YEARMONTHDAY`，不能写成 `PBDT` / `APD`。

## 现场证据

问题 run `eef1291a-28d2-4f85-a5ae-1c85f8c942e0` 的持久化事件显示：

- `patent-query-composition`、其 `SKILL.md` 和
  `references/patsnap-query-syntax.md` 的读取/激活记录均为 0。
- 子代理第一批调用直接使用 `PA:(...)` 和仅含 `keyword` 的
  `aminer_search_paper`。
- 子代理反复得到“validate success”，随后 `patent_search` 返回
  `Parameter query invalid: query syntax error`，又继续换括号和引号重试。
- 同一 run 至少出现数十次 AMiner paper 调用；keyword-only 调用多次返回
  `success=true, msg="no data"`，改为 title-only 后部分查询才返回数据。

这也解释了该会话为何长时间循环工具：错误被免费的浅层 validator 误标为可执行，
模型把付费 P002 失败理解成括号/引号问题，而不是字段字典错误，因而没有形成有效的
停止条件。

## 智慧芽字段审计矩阵

字段依据为用户提供的 280 行智慧芽结构化字段表、当前 Skill/参考、MCP capability
以及真实 P002 最小探针。

| 维度 | Skill/参考 | 字段表 | 真实探针 | 结论 |
| --- | --- | --- | --- | --- |
| 广义申请人 | `ALL_AN` | 存在 | 成功，上海电气 14,931 条原始结果 | 正确 |
| 当前/原始/历史申请人 | `ANCS`, `ANCS_EXACT`, `ANS`, `ANS_EXACT`, `ANC`, `AN`, `AN_HIST` | 均存在 | 未发现静态冲突 | 正确 |
| 第一申请人 | `F_AN`, `F_ANC` | 均存在 | 未发现静态冲突 | 正确 |
| 旧申请人字段 | 明确禁止 `PA`, `CSR`, `APS` | 三者均不存在 | 三者均付费返回 P002 syntax error | 禁止是正确的 |
| 文本范围 | `TACD_ALL`, `TAC_ALL`, `TA_ALL` 等 | 均存在 | 与字段表一致 | 正确 |
| 日期 | `APD`, `PBD`, `E_PRIORITY_DATE`, `ISD` | 均存在 | 与字段表一致 | 正确 |
| 分类 | `IPC_CPC`, `IPC`, `CPC`, `CPC_ALL` 等 | 均存在 | 与字段表一致 | 正确 |
| 地域/FTO | `AUTHORITY`, `ENTRY_COUNTRY`, `EPDS`, `EPDS_SLS` | 均存在 | 与字段表一致 | 正确 |
| 引用/同族 | `B_CITES`, `F_CITES`, `BF_CITES`, `FAM`, `IFAM`, `EFAM` | 均存在 | capability 中“unavailable”指没有独立对象 API，不代表查询字段不可用 | 正确但文案需避免混淆 |
| 排序 | Skill 原写 `PBDT/APD/ISD/SCORE` | 排序键不属于搜索字段表 | `PBDT` 失败；`PBDT_YEARMONTHDAY` 成功 | 已修复 |

最小 P002 探针共 6 次、实际收费 1.20 CNY：4 次申请人字段探针和 2 次排序字段探针。
免费 `patent_validate_query` 对 `ALL_AN/PA/CSR/APS` 全部返回成功，证明不能把它当
字段字典校验器。

## AMiner 工具契约审计

AMiner 没有智慧芽式字段表达式，不能把 `ALL_AN` 或任何智慧芽字段套给它。它是
一组分步实体 API：

| 意图 | 正确工具/参数 | 重要限制 |
| --- | --- | --- |
| 论文多条件检索 | `search_paper(title, keyword, abstract, author, org, venue, page, size, order)` | 不使用 title 时必须显式传 `title=""`；page 从 0 开始 |
| 标题精确检索 | `search_paper_by_title(title, page, size)` | page 从 1 开始，最大 10；size 最大 20 |
| 机构解析 | `search_organization(orgs)` 或消歧工具 | 先取标准机构 ID |
| 机构论文 | `get_organization_papers(org_id, offset)` | 每次固定返回 10 条 |
| 机构专利 | `get_organization_patents(id, page, page_size, source)` | `source=app/ass`；数据覆盖可能为空 |
| 专利关键词发现 | `search_patent(query, page, size)` | query 是标题/关键词文本，不支持智慧芽字段或布尔字段语法 |
| 专利详情 | `get_patent_detail(id)` | 输入是 AMiner 专利 ID，不是公开号 |

最小探针验证：

- `search_paper(keyword="gas turbine")` 保留默认 `title="LLM"` 时仅返回 2 条、
  标题都包含 LLM；显式 `title=""` 后返回常规燃气轮机论文。
- `search_organization(["上海电气"])` 正确解析为 `Shanghai Electric`；但
  `get_organization_patents` 对 `source=app/ass` 均返回 `no data`，说明 AMiner
  机构专利覆盖不能替代智慧芽申请人检索。
- `search_patent(query="上海电气")` 能返回文本相关结果，但它不能证明结果中的
  申请人就是上海电气。

## 修复边界与建议

本分支只修改已被真实 API 确认的排序字段错误，并用契约测试锁定
`ALL_AN` 与两个完整排序字段。没有改生产配置、MCP schema 或公共 API。

后续建议按优先级执行：

1. 在 AMiner MCP 服务端把可选字符串参数的示例默认值改为空字符串，尤其是
   `search_paper.title="LLM"`；示例应进入 description/examples，而不是运行默认值。
2. 把 `patent_validate_query` 描述改成“只校验结构，不校验字段存在性”，并在返回值
   中显式加入 `field_dictionary_checked=false`。这需要修改 patent-data MCP 服务，
   不应在 DeerFlow 仓库伪装成已解决。
3. 为“专利检索式/申请人检索”增加确定性 Skill 路由：委派提示应显式要求先读取
   `patent-query-composition`，或在 task prompt 中携带所选 Skill；仅把 Skill 放在
   enabled 列表不保证模型会读取。
4. 为 AMiner 增加独立的轻量使用指南或 routing hint，至少覆盖空 title、页码基准、
   机构 ID 两阶段流程和“不得使用智慧芽字段”。在改 MCP 默认值前，这一指南只能
   降低错误概率，不能消除 schema 默认值本身的风险。
5. 对不可重试的 P002 syntax error 设置同一规范化查询的单次失败熔断，避免模型只改
   引号/括号后重复付费；字段未知时要求读取参考或停止并报告。

## 验收

- `ALL_AN`、`PA`、`CSR`、`APS` 与两个排序字段已用当前生产 MCP 实测。
- Skill/字段参考与用户字段表其余核心字段未发现确定性冲突。
- 新契约测试锁定完整排序字段，并继续由 manifest SHA 锁定 Skill 内容。
