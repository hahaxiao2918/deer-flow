# Patent Search Strategy Playbook — on-demand

> **On-demand reference** for `patent-query-composition`. The SKILL.md core teaches the default strategy (Boolean block-search, calibrated by `patent_search` (family-level count + sample records)). Read this when the user's **goal** implies a different strategy, or you need to combine strategies / avoid common pitfalls.
>
> Sources: EPO Guidelines for Examination Part B (search), CNIPA 查新检索 methodology, WIPO patent-search guidance. Field/operator syntax is the verified 智慧芽 set — see `references/patsnap-query-syntax.md`.

## What the patent-data MCP actually exposes

Strategy is constrained by the tools at hand. The `patent-data` MCP provides:
- `patent_search` — **this skill's calibration tool** (in `allowed-tools`). A small-`limit` probe (3-5) with `collapse_type`/`collapse_by`/`collapse_order` returns the family-level count at `data.coverage.total_search_result_count` AND a few sample records (a right-count / wrong-documents check). Full pulls (large `limit` / pagination; `limit<=1000`, `offset+limit<=20000`) are the corpus skill's job.
- `patent_count` — count-only probe (exists on the MCP; ¥0.01/call, cheaper than `patent_search` ¥0.20) — **not in this skill's allowed-tools**; noted for awareness.
- `patent_get_records` / `patent_get_passages` — fetch bibliographics / text for known patent numbers.
- Query fields include citation (`B_CITES` / `F_CITES` / `BF_CITES`), family (`FAM`/`IFAM`/`EFAM`), legal status (`SIMPLE_LEGAL_STATUS`), dates, classification (IPC/CPC), applicant (`ALL_AN`, `TREE@`), jurisdiction (`AUTHORITY`).

**Not available via this MCP**: semantic/concept search (no `search_patent_semantic` here), dedicated citation-walk, legal-status/family as first-class objects (only as query fields). If a goal truly needs semantic search, flag it as out-of-scope for this skill.

## Goal → primary strategy

| Goal | Primary strategy (this skill composes the queries) | Why |
| --- | --- | --- |
| **查新 / novelty / patentability** | Block-search: 全要素/部分/单要素 combos (the X-type search is all-elements AND) + an E-type 抵触申请 check; calibrate each with `patent_search` (small limit + collapse). | An all-elements X-reference contains every basic element; a Y-reference combines some; E = earlier-priority same-class (抵触申请). |
| **Invalidation / invalidity** | Backward-citation (`B_CITES:<pn>` / `BF_CITES:<pn>`, optionally `B_CITES:<pn> GAND CITE_CATEGORY:X`) ∩ Boolean blocks; candidate date **`PBD:[* TO <target E_PRIORITY_DATE>]`** — 公开日 ≤ 最早优先权日, **not** `APD`. | Prior art the examiner/applicant already touched, plus the surrounding art; prior art must be *published* before the target's earliest priority. |
| **FTO / freedom-to-operate** | Boolean precision on the exact claims/features + jurisdiction **`ENTRY_COUNTRY:<code>`** (or `EPDS:<c> GAND EPDS_SLS:1` for an EP member-state; `AUTHORITY` is the filing office and under-counts EP national validations) + **`SIMPLE_LEGAL_STATUS:(1 OR 2)`** (有效 + 审中) + date; narrow hard. | Needs live-or-pending, enforceable, in-jurisdiction claims — precision dominates. |
| **Landscape / white-space** | Classification-driven (CPC first): define the technology space by CPC ranges, then `patent_search` per subclass/slice (read `coverage.total_search_result_count`; collapse for family-level density) to map density and find sparse areas; layer applicant counts. | Classification gives the stable technology map; counts reveal density. |
| **Competitor / portfolio monitoring** | Applicant-scoped: `ALL_AN:(TREE@"公司全名")` + date window + optional classification; `patent_search` (sort by date) for volume trends. | Portfolio = applicant boundary over time. |

This skill **composes** the query expressions for whichever strategy the goal implies; it still hands off a `query_plan`. Running the full corpus search is `applicant-tech-patent-retrieval`'s job.

## Strategy building blocks

- **Block-search (default)** — see SKILL.md core. Best when the invention can be decomposed into explicit elements with findable keywords + classifications.
- **Classification-driven** — start from CPC/IPC to define the technology space (recall), then keyword-refine (precision). Best for landscapes and when keywords are ambiguous. Use `patent_search` (small limit + collapse) per classification slice.
- **Applicant/portfolio** — `ALL_AN` / `ALL_AN:(TREE@…)` + `APD`/`PBD` + classification. Best for competitor and portfolio work. Remember `ALL_AN` is applicant-as-published (current + original + historical union), not necessarily current owner.
- **Citation-based** — `B_CITES:<pn>` (what a patent cites), `F_CITES:<pn>` (what cites it), `BF_CITES:<pn>` (both). Best for invalidation and for expanding a known relevant seed into its neighborhood.
- **Hybrid** — combine: e.g. classification-space ∩ keyword-blocks ∩ jurisdiction; or seed-patent classifications harvested into a block, then Boolean-refined. Intersect with `AND`, broaden with `OR`.

## Common pitfalls

- **Over-narrowing** — too many blocks `AND`ed → misses art that doesn't state every element. Start broader; use Y-type partial combos; watch the `patent_search` coverage count.
- **Missing synonyms / terminology** — expand on form + meaning + function, both CN and EN. Seed-patent language often reveals non-obvious terms.
- **Ignoring classification** — keyword-only searches miss art drafted with different wording. Always include CPC/IPC blocks; cross-check keyword-only vs classification-inclusive counts.
- **Keyword ambiguity / polysemy** — bind multi-word concepts with phrase `"…"` or proximity `$Wn`, and disambiguate with classification or jurisdiction.
- **Applicant-as-published ≠ current owner** — mergers/transfers change ownership; `ALL_AN` is the published-name union, not the current assignee.
- **18-month publication lag** — recently filed applications are unpublished; note the blind spot, especially for novelty.
- **Do not equate semantic/concept similarity with legal relevance** — (semantic isn't exposed here anyway) never assert novelty/obviousness from similarity; that is a legal judgment, not a query result.

## Worked example — gas-turbine blade cooling (智慧芽 fields)

Invention: high-pressure turbine blade with internal serpentine cooling channels, film-cooling holes, and a thermal-barrier coating.

Decompose into 4 blocks (keywords CN+EN ∪ classification, OR within each block):

- **B1 — turbine blade**: `TACD_ALL:(燃气轮机 OR 涡轮叶片 OR 透平 OR "gas turbine" OR blade OR bucket OR vane) OR CPC:F01D5/18 OR IPC_SUB_CLASS:F01D`
- **B2 — internal cooling**: `TACD_ALL:(冷却通道 OR 冷却流道 OR 蛇形 OR 迷宫 OR "cooling channel" OR serpentine OR "internal cooling") OR CPC:F01D5/20`
- **B3 — film cooling**: `TACD_ALL:(气膜冷却 OR 气膜孔 OR 发散冷却 OR "film cooling" OR "film hole" OR "effusion cooling")`
- **B4 — thermal-barrier coating**: `TACD_ALL:(热障涂层 OR TBC OR 陶瓷涂层 OR "thermal barrier coating" OR "ceramic coating") OR CPC:F01D5/28`

Combine & calibrate with `patent_search` (limit=3-5 + collapse):
- X-type: `(B1) AND (B2) AND (B3) AND (B4)` — probe family-level count; if ≈ 0, relax (drop a block, widen synonyms); if huge, add `AUTHORITY:(CN OR US OR EP OR JP)` or proximity.
- Y-type: `(B1) AND (B2) AND (B3)` , `(B1) AND (B2) AND (B4)`, … — for inventive-step coverage.
- Optional scope: applicant `AND ALL_AN:(TREE@"西门子")` , date `AND PBD:[20150101 TO 20251231]`.

Deliver the block table, the X/Y `query_text` set, each block's family-level `patent_search` count + sample PNs, assumptions, and the `query_plan` handoff.
