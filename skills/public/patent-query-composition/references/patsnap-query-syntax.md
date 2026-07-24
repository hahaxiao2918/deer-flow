# 智慧芽 (PatSnap) Search-Query Syntax — Full Reference

> **On-demand reference** for the `patent-query-composition` skill. The SKILL.md core covers most intents; read this file only when triggered:
> - a `query_text` returned a **syntax error** (see §9 Error codes),
> - you need a **field the core does not cover** (date, classification, jurisdiction, legal status, citation, family, litigation, etc.),
> - you need **advanced operators** (wildcards, proximity, frequency, event-group `GAND`, company-tree `TREE@`).
>
> Source: 智慧芽 in-product search help (verified, 280 searchable fields) cross-checked against the 智慧芽开放平台 P002 API docs. This reference documents the **中文智慧芽** product syntax, which is what the `patent-data` search tool targets.

## 1. Text fields — choose by recall vs precision

| Field | Matches | Notes |
| --- | --- | --- |
| `TACD_ALL:<term>` | Title + abstract + claims + description, **原文 + 机翻** | Broadest recall; novelty default |
| `TAC_ALL:<term>` | Title + abstract + claims, 原文 + 机翻 | |
| `TA_ALL:<term>` | Title + abstract, 原文 + 机翻 | |
| `TTL_ALL` / `ABST_ALL` / `CLMS_ALL` / `DESC_ALL` / `ICLMS_ALL` | Single text field, 原文 + 机翻 | Drill into one section |
| `TACD` / `TAC` / `TA` / `TTL` / `ABST` / `CLMS` / `DESC` / `ICLMS` | Same fields, **原文 only** (no translation) | Sharper precision when recall is too noisy |
| `MAINF_ALL:<term>` | Main fields (title/abstract/claims/description + numbers + applicant/inventor + IPC/UPC/LOC), 原文+机翻 | This is the **default scope** when a query specifies no field |
| `PATSNAP_TTL` / `PROBLEM_SUM` / `METHOD_SUM` / `BENEFIT_SUM` | PatSnap-extracted title / 技术问题 / 技术手段 / 技术功效 | Global patents with full text only |
| `DESC_F` / `DESC_B` / `DESC_S` / `DESC_D` / `DESC_E` | 技术领域 / 背景技术 / 发明内容 / 附图说明 / 具体实施方式 | **CN-filed patents only** |

> **`_ALL` suffix = 原文 + 机翻** (covers Chinese + English + machine-translated text). Without `_ALL`, only the original-language field is searched. `ICLMS` (独立权利要求) is English-only + CN-filed.

## 2. Applicant / inventor / attorney

| Field | Matches | Notes |
| --- | --- | --- |
| `ALL_AN:<name>` | Applicant/assignee — **union**: standardized-current, current, standardized-original, original, **historical** | Broadest applicant match (transfers, pledges, changes) |
| `ANCS` / `ANCS_EXACT` | [标]当前申请人 / 精准当前申请人 | Use `*_EXACT` for symbol/case-exact matching |
| `ANS` / `ANS_EXACT` | [标]原始申请人 / 精准原始 | |
| `ANC` / `AN` / `AN_HIST` | 当前 / 原始 / 历史申请人 | |
| `F_AN` / `F_ANC` | 第一(原始/当前)申请人 | |
| `ANS_TYPE` / `ANCS_TYPE` | 申请人类型 | `ACADEMY` `COMPANY` `GOVERNMENT` `PERSON` `HOSPITAL` `BANK` |
| `IN:<name>` / `INC` / `IN_EXACT` / `F_IN` | 发明人 / 当前 / 精准 / 第一 | |
| `AT` / `ATC` / `ATCS` / `ATCC` | 代理人 / 代理机构 / [标]代理机构 / 当前代理机构 | |
| `AUTHORITY:<code>` | 受理局(jurisdiction) | `AUTHORITY:(US OR CN OR EP OR WO)` |
| `PRIORITY_COUNTRY:<code>` | 优先权国家/地区 | |
| `EPDS:<country>` | EP 指定国家/地区 | e.g. `EPDS:DE` |
| `AN_COUNTRY` / `AN_PROVINCE` / `AN_CITY` / `AN_DISTRICT` | 申请人区域 (CN province/city/district; US state/county) | CN/US only |
| `GNAME:<name>` | 自定义申请人组 | |

> **Company tree** — `TREE@"公司全名"` expands a company to **itself + all subsidiaries** in the PatSnap company tree. Works under `ANS` / `ANCS` / `ALL_AN`. Example: `ALL_AN:(TREE@"拜耳股份公司")`. The name must be the exact PatSnap-tree node name.

## 3. Date fields — range syntax, 8-digit YYYYMMDD

| Field | Meaning | Example |
| --- | --- | --- |
| `APD` / `APD_Y` / `APD_YM` | 申请日 / 年 / 年月 | `APD:[20150101 TO 20251231]` ; `APD_Y:[2018 TO *]` |
| `PBD` / `PBD_Y` / `PBD_YM` | 公开日 / 年 / 年月 | `PBD:[* TO 20241231]` |
| `F_PBD` | 首次公开日 | `F_PBD:20150101` |
| `PRIORITY_DATE` / `E_PRIORITY_DATE` | 优先权日 / 最早优先权日 | `PRIORITY_DATE:[20200101 TO 20201231]` |
| `ISD` | 授权日 | `ISD:[* TO 20201231]` |
| `EXPD` / `EXDT` | 失效日 / 预计到期日 | |
| `EXAMINE_DATE` | 实质审查生效日 | partial jurisdictions |
| `PCTENTRY_DATE` | PCT 进入国家阶段日 | |
| `LEGAL_STATUS_DATE` | 法律状态更新日 | |
| `EFAM_EPBD` / `EFAM_EPRD` | 同族最早公开日 / 最早优先权日 | |

> **Format**: the 中文智慧芽 product uses **8-digit `YYYYMMDD`** (no dashes): `APD:20150101`, `APD:[20150101 TO 20251231]`, open-ended `APD:[* TO 20251231]` or `APD_Y:[2018 TO *]`. The English PatSnap help shows ISO `YYYY-MM-DD`; if one form errors, try the other.

## 4. Classification fields — range syntax for groups

| Field | Meaning | Example |
| --- | --- | --- |
| `IPC:<code>` | IPC 分类号 | `IPC:H04W` ; range `IPC:[H01L31/0203 TO H01L31/042]` |
| `IPC_SECTION` / `IPC_CLASS` / `IPC_SUB_CLASS` / `IPC_GROUP` / `IPC_SUB_GROUP` | IPC 部 / 大类 / 小类 / 大组 / 小组 | `IPC_SUB_CLASS:F01D` ; `IPC_CLASS:H04` |
| `MIPC` (+ `_SECTION/_CLASS/_SUB_CLASS`) | IPC **主**分类号 + 层级 | `MIPC:A61K` |
| `IPC_LOW` / `MIPC_LOW` | 下位组(当前类 + 子类) | `IPC_LOW:A01B1/02` |
| `CPC` (+ `_SECTION/_CLASS/_SUB_CLASS/_GROUP/_SUB_GROUP`/`_LOW`/`_ALL`) | CPC 分类号 + 层级 | `CPC:G10L15/193` ; `CPC_ALL` = 官方 + PatSnap 预测 |
| `MCPC` | CPC 主分类号 | |
| `IPC_CPC:<code>` | 同时检索 IPC + CPC | `IPC_CPC:B01B1/00` |
| `CLASS:<code>` | 联合分类号(IPC+CPC+洛迦诺+FI+F-TERM+UPC) | `CLASS:A21B3/04` |
| `LOC` | 洛迦诺(外观) | `LOC:[04-01 TO 04-03]` — design patents only |
| `UPC` / `FI` / `FTERM` | 美 / 日 分类 | UPC US-only; FI/FTERM JP-only |
| `ADC` / `TTC` / `SEIC` / `SEIC_ALL` | 应用领域 / 技术主题 / 战略新兴产业(主/全) | `SEIC:"人工智能"` |
| `GBC` | 国民经济行业分类号 | `GBC:A0119` |

> For the IPC code of a technology area, read `references/ipc-classification.md`. Subclass level (e.g. `IPC_SUB_CLASS:F01D`) is the usual composition granularity.

## 5. Number / family / citation

| Field | Meaning |
| --- | --- |
| `PN` `APNO` `PRNO` `KD` | 公开号 / 申请号 / 优先权号 / 文献代码 |
| `PCT_PN` `PCT_APNO` | PCT 公开号 / 申请号 |
| `FAM_ID` `IFAM_ID` `EFAM_ID` | 简单 / INPADOC / PatSnap 同族编号 |
| `FAM` `IFAM` `EFAM` | 同族(按号) |
| `FAM_COUNT` `IFAM_COUNT` `EFAM_COUNT` `FAM_COUNTRY_COUNT` | 同族申请数 / 国家数 |
| `B_CITES` `F_CITES` `BF_CITES` | 引用 / 被引用 / 引用或被引用(按号) |
| `B_CITES_COUNT` `F_CITES_COUNT` | 引用数 / 被引用数 |
| `CITE_CATEGORY` | 引用类别 `X Y A D E L R T 101 102 103`(见 §8) |
| `F_CITES_ANC` `B_CITES_ANC` | 引用某当前申请人的专利 / 某当前申请人引用的专利 |

## 6. Status / quality / type

| Field | Meaning | Example |
| --- | --- | --- |
| `SIMPLE_LEGAL_STATUS` | 简单法律状态 | `0`失效 `1`有效 `2`审中 `220/221` PCT `999`未确认 |
| `LEGAL_STATUS` | 详细法律状态 | code table §8 |
| `LEGAL_EVENT` | 法律事件 | `61`权利转移 `52`许可 `63`质押 `66`复审 `72`无效 … |
| `PATENT_TYPE` | 专利类型 | `A`发明申请 `B`授权发明 `U`实用新型 `D`外观设计 |
| `PV` | 专利价值 | `PV:[10000 TO 50000]` |
| `CLAIM_COUNT` `ICLMS_COUNT` `FCLMS_WORDCOUNT` | 权利要求数 / 独权数 / 首权字数 | |
| `IPC_COUNT` `CPC_COUNT` `PAGE_COUNT` | 分类数 / CPC数 / 文献页数 | |
| `SEP` `SEP_NUMBER` `SEP_TITLE` `SEP_SOURCE` `SEP_PROJECT` `SEP_DECLARANT` | 标准必要专利 / 标准号 / 标题 / 数据源 / 项目 / 持有者 | |
| `ENTRY_COUNTRY` `PCTENTRY_TYPE` `EP_ENTRY` `PC_ENTRY` | 进入国家 / PCT / EP / 巴黎公约路径 | |

> Full litigation / licensing / reexamination / pledge field families exist (诉讼、许可&权利转移、复审无效、质押) — see the source help doc when those scopes are needed.

## 7. Operators (complete)

**Boolean** — `AND` / `OR` / `NOT`; precedence `NOT > AND > OR`; `()` raises local precedence; a bare space between terms acts as `AND`.
- `太阳能 AND 电池` · `发动机 OR 引擎` · `电视 NOT 等离子` · `AN:华为科技 NOT ABST:手机`

**Phrase** — `"..."` fixes word order: `"electric vehicle"`.

**Range** — `[a TO b]` for dates, numbers, classification groups; open-ended `[* TO x]` / `[x TO *]`:
- `PBD:[20010101 TO 20101231]` · `IPC:[H01L31/0203 TO H01L31/042]` · `PV:[10000 TO 50000]`

**Wildcards** (not inside quotes):
- `*` = 0+ chars — max **2** per word; mid/end needs **2+** chars before it; word-initial is English-only and needs **3+** chars after; two `*` need **3+** chars between. `electr*` `小*车`.
- `?` = exactly 1 char — must be consecutive; word-initial English-only. `gra???ne`.
- `#` = 0 or 1 char — one per word. `Colo#r`.

**Proximity** (precedence above boolean; 0≤n≤99):
- `$Wn` within n words, any order: `ABST:(太阳能 $W2 电池)`
- `$PREn` within n words, fixed order
- `$WS` within 99 words; `$SEN` same sentence; `$PARA` same paragraph

**Frequency** — `$FREQn`: term appears **≥n** in title/abstract/claims/description; n≤50; **not** on 机翻 fields; public library only. `TTL:("car" $FREQ2)`.

**Event group** — `GAND` restricts to matching members of a tightly-coupled event set:
- `EPDS:DE GAND EPDS_SLS:1` (EP designated DE AND valid in DE)
- Event groups: 奖励(AWARD_*), EP指定国(EPDS+EPDS_LS/SLS), 引用(CITE+CITE_CATEGORY), 企业自定义字段(CCF+CWS).

**Optional separator** `_` — `T_shirt` matches `T shirt` / `T-shirt` / `Tshirt` (one per word; not inside quotes or with wildcards).

**截词 (truncation)** — on by default for English (`come`→`come/comes/came/coming`); off = exact; **not** on applicant/inventor names; wildcards disable 截词 on the wildcarded term.

**Company tree** — `TREE@"全名"` under `ANS`/`ANCS`/`ALL_AN` = company + subsidiaries.

**Searchable special chars** — `- / °C °F % ± ° ™ ® mg/l @`.

## 8. Code tables (quick)

**`SIMPLE_LEGAL_STATUS`**: `0`失效 / `1`有效 / `2`审中 / `220` PCT指定期满 / `221` PCT指定期内 / `999`未确认.
**`LEGAL_STATUS`**: `1`公开 `2`实审 `3`授权 `8`避免重复授权 `11/12/17/18`撤回 `13`驳回 `14`全部撤销 `15`期限届满 `16`未缴年费 `21`权利恢复 `22`权利终止 `23`部分无效 `24`申请终止 `30/19/20/25`放弃 `222-225` PCT进入/未进入.
**`PATENT_TYPE`**: `A`发明申请 `B`授权发明 `U`实用新型 `D`外观设计.
**`CITE_CATEGORY`**: `X`特别相关(单独否定新颖/创造) `Y`结合否定创造性 `A`背景技术 `D`申请人引证 `E`在先抵触 `L`优先权相关 `R`同样发明 `T`理解用 `101/102/103` 美国条款.
**`ANS_TYPE`/`ANCS_TYPE`**: `ACADEMY` `COMPANY` `GOVERNMENT` `PERSON` `HOSPITAL` `BANK`.

## 9. Error codes — syntax-error diagnosis

The `patent-data` search tool always returns HTTP 2xx; failures surface in `diagnostics`. Relevant codes:

| error_code | Meaning | Action |
| --- | --- | --- |
| `68300004` | 参数异常(**检索式语法错** / 字段误用) | diagnose below |
| `67200002` | QPS 超限 | back off, retry |
| `67200004` | 无权限 | check token/scope |
| `67200005` / `67200007` | 余额 / 当天额度不足 | stop, report |
| `68300008` | 服务中断 | retry later |

**`68300004` diagnostic flow** — re-read this reference and check, in order:
1. Field code valid? Use only codes listed here; applicant must be `ALL_AN`/`ANCS`/… (the old `PA`/`CSR`/`APS` error — use `ALL_AN`).
2. Parentheses balanced; every `(` has a matching `)`; field-scoped groups use `FIELD:(...)`.
3. Date format — prefer 8-digit `YYYYMMDD`; try ISO `YYYY-MM-DD` if it errors.
4. Wildcard limits — `*`≤2/word, leading-`*` English-only + 3 chars after; no wildcards inside `"..."`.
5. `$FREQn` not on `_ALL`/机翻 fields; `$`-operators only between terms.
6. Length — `query_text` max **12000** chars; split into a versioned query set.
7. Narrow to a single field-scoped clause to isolate the offending segment; re-expand once it runs.

## 10. Gotchas

- `_ALL` = 原文 + 机翻; without `_ALL` = 原文 only.
- `ALL_AN` is a union (current + original + standardized + historical) — broad; for exact-current use `ANCS_EXACT`.
- Date format: 8-digit `YYYYMMDD` (中文产品); ISO `YYYY-MM-DD` is an alt.
- Wildcards not inside quotes; leading wildcards English-only.
- `$FREQn` not on 机翻 fields.
- Default scope (no field) = `MAINF`/`MAINF_ALL` main fields.
- `query_text` ≤ 12000 chars.
- `PA` / `CSR` / `APS` applicant fields are not in the current field set → syntax error; use `ALL_AN`.
