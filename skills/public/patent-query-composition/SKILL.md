---
name: patent-query-composition
description: Compose validated patent search-query expressions (检索式) for the patent-data search tool from a research intent, using professional block-search methodology and search-probes (family-level count + sample records) to calibrate recall and confirm the matched documents are on-topic. Use when the deliverable is a reusable set of search-query expressions before running a corpus search. Do not use when a corpus already exists or the user mainly wants applicant corpus building, per-document labeling, route mapping, time evolution, or weak-signal analysis.
allowed-tools:
  - ask_clarification
  - write_file
  - str_replace
  - present_files
  - patent-data_patent_search
---

# Patent Search-Query Composition

Compose a versioned set of validated patent search-query expressions (检索式) with the **block-search** method used by patent examiners (EPO / CNIPA 查新), and calibrate each block's recall with `patent_search` probes (small `limit` — each returns the family-level count from `data.coverage.total_search_result_count` plus a few sample records). Hand off a `query_plan`; do not run the full corpus search.

## Runtime contract

1. Treat this as the query-authoring stage that precedes corpus building. Emit `schema_version: 2.0.0`, `analysis_id`, `artifact_type: query_plan`, `status`, the scope intake, the versioned block set + combinations, probe volumes (family-level counts) + sample publication numbers, and limitations.
2. Use the runtime-provided run identifier when visible. Otherwise generate a stable analysis identifier; never ask the user for an internal run or account identifier.
3. Every block and combination must be a copyable `query_text` string the patent-data search tool accepts. Separately record each block's purpose, field codes, its family-level hit volume (from `patent_search` -> `data.coverage.total_search_result_count`), and a few sample publication numbers.
4. When another skill will consume the result, write the plan to `workspace/patent-analysis/<analysis_id>/query-plan.json`; otherwise return the same fields inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `no_results`, `partial_data`, `insufficient_evidence`, `unsupported_request`, or `completed`.

## Scope intake (one consolidated ask)

Ask ONE consolidated question covering the dimensions that materially change the query set; apply disclosed defaults for anything omitted and record them in `defaults_applied`. Only block (status `needs_input` / `scope_ambiguous`) when ambiguity would change the answer. Capture:
- inventive subject + its core technical features (the 基本检索要素);
- applicant / inventor (if any) — flag homonym ambiguity;
- jurisdictions (default: broad), date window (default: open), and the intended goal — 查新 / invalidation / FTO / landscape / monitoring (see `references/search-strategy-playbook.md` for goal→strategy);
- recall-vs-precision goal (default: recall-oriented for novelty).

## Goal → strategy (dispatch first)

Identify the goal (captured in scope intake), then pick the strategy. **Block-search below is the default for 查新/novelty**; other goals change the field choices — read this table before composing:

| Goal | Strategy this skill composes |
| --- | --- |
| **查新 / novelty** | Block-search: 全要素 / 部分 / 单要素 combos (see method below) + an E-type 抵触申请 check; calibrate each with `patent_search` (small `limit` + collapse). |
| **Invalidation / invalidity** | Backward-citation (`B_CITES:<pn>` / `BF_CITES:<pn>`) ∩ Boolean blocks; candidate date **`PBD:[* TO <target E_PRIORITY_DATE>]`** (公开日 ≤ 最早优先权日 — **not** `APD`; APD admits early-filed-but-later-published docs that are NOT prior art). |
| **FTO / freedom-to-operate** | Boolean precision on the exact claims/features + jurisdiction **`ENTRY_COUNTRY:<code>`** (not `AUTHORITY`, which is the filing office; for an EP member-state use `EPDS:<c> GAND EPDS_SLS:1`) + **`SIMPLE_LEGAL_STATUS:(1 OR 2)`** (有效 + 审中 — pending can mature into enforceable rights; do **not** narrow to `PATENT_TYPE:B`, it drops utility models `U`) + date. |
| **Landscape / white-space** | Classification-driven (CPC first); `patent_search` per subclass/slice for density (read `coverage.total_search_result_count`; use `collapse_type` for family-level density); mind family inflation when comparing slices. |
| **Competitor / portfolio monitoring** | Applicant `ALL_AN:(TREE@"公司全名")` + date window + optional classification; `patent_search` with `sort` by date for volume trends. |

Per-goal rationale and worked examples: `references/search-strategy-playbook.md`.

## Block-search method

1. **Decompose** the invention into basic search elements — technical field (前序), core inventive features (特征), and technical problem / effect. Each element becomes one **block**.
2. **Build each block** as `(keywords OR classification)`, OR-combined inside the block:
   - Keywords — expand on three dimensions: form (singular/plural, spelling, word class), meaning (synonyms, near-synonyms, hypernyms/hyponyms), function (problem / effect / use); cover BOTH Chinese and English.
   - Classification — prefer CPC (more granular, better for search); IPC as backup. Map the technology area to codes via `references/ipc-classification.md` or harvest them from seed patents. Use several codes per block; never rely on a single one.
3. **Combine blocks** — combination tactics (CNIPA 6.3.3), decoupled from citation categories:
   - **全要素检索** (all-elements): `Block1 AND Block2 AND Block3` — highest precision.
   - **部分要素检索** (partial): `Block1 AND Block2`, `Block1 AND Block3` — recall floor when all-elements is sparse.
   - **单要素检索** (single-element): one block alone — last-resort recall; run it when AND-all returns near-zero so you do not conclude "no prior art" from a single conjunction.
   - **Citation categories ≠ combination tactics.** X = a reference that *alone* destroys novelty **or** inventive step; Y = a reference that must *combine* with another Y for inventive step; **E = 抵触申请 / Art.54(3)** (earlier priority, published in the 18-month window). For novelty, also probe an E-type view (same classification, `PBD` within the 18-month window, or `CITE_CATEGORY:E`). Do **not** equate "X-type" with novelty or "Y-type" with inventive step.
   - A near-zero all-elements count ⇒ **expand first** (add synonyms, broaden classification, add 功能类似 / neighbouring fields), then re-probe — never infer absence of prior art from one AND-all.
4. **Calibrate with `patent_search`** (¥0.20/probe, so be economical): probe each block and combination with `patent_search(query_text, limit=3-5, collapse_type, collapse_by, collapse_order)` — read the family-level count from `data.coverage.total_search_result_count` (**not** `data.total_search_result_count`, which is null for `patent_search`) and skim the few returned records to confirm they are on-topic (a right-count / wrong-documents check). Too few hits → expand synonyms / add classifications / relax; too many → narrow keywords / add classification / add proximity. Re-probe after each revision and record the family-level volume per expression. (Caps: `limit <= 1000`, `offset+limit <= 20000` — both hard-error `68300004` beyond; `sort` options: PBDT/APD/ISD/SCORE.)
5. Deliver the block table, the combination `query_text` set (全要素 all-elements / partial / single-element), per-block family-level count volumes + sample publication numbers, assumptions, limitations, and the `query_plan` handoff. Use only small-limit `patent_search` probes for calibration + sanity samples — do not run full corpus pulls (large `limit` / deep pagination); that is the corpus skill's job.

## Query-text syntax — core (verified on the patent-data API)

| Field code | Matches |
| --- | --- |
| `TACD_ALL:<term>` | Title + abstract + claims + description, 原文 + 机翻 (broadest recall; default for novelty) |
| `TAC_ALL` / `TA_ALL` | Title+abstract / title only (原文 + 机翻) |
| `ALL_AN:<name>` | Applicant/assignee — union of current, original, standardized, historical |
| `IN:<name>` | Inventor |
| `CPC:<code>` / `IPC:<code>` / `IPC_SUB_CLASS:<code>` | Classification (CPC preferred); group range `IPC:[H01L31/0203 TO H01L31/042]` |
| `AUTHORITY:(CN OR US OR EP OR WO)` | Jurisdiction |
| `APD:[20150101 TO 20251231]` / `PBD:[...]` | Date (8-digit YYYYMMDD; year-only `APD_Y:[2018 TO *]`) |
| `ALL_AN:(TREE@"公司全名")` | Applicant + all subsidiaries |

`_ALL` = 原文 + 机翻 (covers Chinese and English + machine translation). Operators: `AND` / `OR` / `NOT` (precedence `NOT > AND > OR`), `()` groups, `"..."` phrase. Cross-field example: `TACD_ALL:(深度学习 AND 神经网络) AND ALL_AN:华为 AND IN:张三`. The old `PA` / `CSR` / `APS` applicant fields error — always use `ALL_AN`.

Every field and operator above is verified to run on the patent-data API. For the full field list, advanced operators (wildcards `* ? #`, proximity `$Wn $PREn $SEN $PARA`, frequency `$FREQn`, event-group `GAND`), code tables, and the syntax-error diagnostic flow, read `references/patsnap-query-syntax.md` on demand.

## Guardrails

- Do not invent field codes — use the verified core above, or codes from the on-demand reference.
- Do not claim exhaustive or global coverage; disclose the concepts, synonyms, applicant aliases, jurisdictions, and classifications actually covered.
- Do not turn the query set into a novelty, freedom-to-operate, validity, or infringement conclusion — it only defines what the search tool will match.
- Do not report fabricated hit counts beyond what `patent_search`'s `coverage.total_search_result_count` returns.
- Keep every `query_text` copyable verbatim; never paraphrase a field code or operator into prose the tool would reject.

## Progressive references (read on demand)

- `references/patsnap-query-syntax.md` — full 智慧芽 field/operator reference, the `patent_search` count field (`data.coverage.total_search_result_count`) + caps, and error diagnosis. **Read when** a query errors, you need a field/operator beyond the core, or a probe returns an unexpected count.
- `references/ipc-classification.md` — IPC hierarchy (CPC preferred for search). **Read when** mapping a technology area to a classification code.
- `references/search-strategy-playbook.md` — goal→strategy map, hybrid patterns, pitfalls, worked example. **Read when** the goal implies a non-default strategy (invalidation / FTO / landscape / monitoring).
