---
name: patent-query-composition
description: Compose validated patent search-query expressions (检索式) for the patent-data search tool from a research intent. Use when the deliverable is a reusable set of search-query expressions before running a corpus search. Do not use when a corpus already exists or the user mainly wants applicant corpus building, per-document labeling, route mapping, time evolution, or weak-signal analysis.
allowed-tools:
  - ask_clarification
  - write_file
  - str_replace
  - present_files
---

# Patent Search-Query Composition

Turn a research intent into a versioned set of validated patent search-query expressions (检索式) that the patent-data search tool can run verbatim.

## Runtime contract

1. Treat this as the query-authoring stage that precedes corpus building. Emit `schema_version: 2.0.0`, `analysis_id`, `artifact_type: query_plan`, `status`, intent decomposition, the versioned query set, validation notes, and limitations.
2. Use the runtime-provided run identifier when visible. Otherwise generate a stable analysis identifier; never ask the user for an internal run or account identifier.
3. Every expression must be a copyable `query_text` string the patent-data search tool accepts unchanged. Separate the expression from its plain-language purpose, the field codes it relies on, and its expected recall/precision behaviour.
4. Keep at least one recall-oriented expression, and document the trade-off when adding precision-oriented or exclusion variants.
5. When another skill will consume the result, write the plan to `workspace/patent-analysis/<analysis_id>/query-plan.json`; otherwise return the same fields inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `no_results`, `partial_data`, `insufficient_evidence`, `unsupported_request`, or `completed`.

## Query-text syntax — core

The patent-data search tool runs a `query_text` string in PatSnap (智慧芽) syntax. These verified field codes cover most intents:

| Field code | Matches |
| --- | --- |
| `TACD_ALL:<term>` | Title + abstract + claims + description, 原文 + 机翻 (broadest recall; default for novelty) |
| `TAC_ALL:<term>` | Title + abstract, 原文 + 机翻 |
| `TA_ALL:<term>` | Title only, 原文 + 机翻 |
| `ALL_AN:<name>` | Applicant/assignee — union of current, original, standardized, and historical names |
| `IN:<name>` | Inventor |

The `_ALL` suffix means "原文 + 机翻" (covers Chinese and English + machine translations); without it, only the original-language field is searched.

**Operators** — `AND` / `OR` / `NOT` (precedence: `NOT > AND > OR`); `()` groups; a bare space between terms acts as `AND`; `"..."` fixes phrase order.
- Same-field: `TACD_ALL:(深度学习 AND 神经网络)` · `TACD_ALL:(VR OR 虚拟现实)`
- Phrase: `TACD_ALL:"完整短语"`
- Cross-field: `TACD_ALL:(深度学习 AND 神经网络) AND ALL_AN:华为 AND IN:张三`
- Exclude: `TACD_ALL:电视 NOT ABST:等离子`

**Common scoping fields (verified):**
- Jurisdiction: `AUTHORITY:(CN OR US OR EP OR WO)`; applicant region `AN_COUNTRY:CN`.
- Date (8-digit `YYYYMMDD`, range with `TO`, open-ended with `*`): `APD:[20150101 TO 20251231]` (application), `PBD:[* TO 20241231]` (publication), `PRIORITY_DATE:[...]`. Year-only: `APD_Y:[2018 TO *]`.
- Classification: `IPC:H04W` or `IPC_SUB_CLASS:F01D`; group range `IPC:[H01L31/0203 TO H01L31/042]`. For the IPC code of a technology area, read `references/ipc-classification.md`.
- Applicant + subsidiaries: `ALL_AN:(TREE@"公司全名")` expands the company to itself + all subsidiaries.

The older applicant fields `PA` / `CSR` / `APS` are not in the current field set and return a syntax error; always use `ALL_AN`.

## Progressive references (read on demand)

The core above covers most intents. Read these support files with `read_file` only when triggered — never load them by default:

- **`references/patsnap-query-syntax.md`** — the full 智慧芽 field-code reference and complete operator set. **Read when**: a `query_text` returned a syntax error; you need a field the core does not cover (legal status, citation, family, litigation, licensing, etc.); or you need advanced operators (wildcards `* ? #`, proximity `$Wn $PREn $SEN $PARA`, frequency `$FREQn`, event-group `GAND`).
- **`references/ipc-classification.md`** — the IPC section/class/subclass hierarchy. **Read when**: the intent names a technology area and you want to scope by classification code.

## Workflow

1. Decompose the intent: technical concepts (and their synonyms), applicant, inventor, jurisdiction, date window, classification, the intended deliverable, and the recall-versus-precision goal.
2. Ask one consolidated clarification only when entity or concept ambiguity would materially change the query set — for example an applicant name with common homonyms, or a concept described by a generic term that also names an unrelated field. Otherwise apply disclosed defaults and record them.
3. Compose using the **core** field codes first. Only read a reference file when the core is insufficient (a needed field or operator is not there) or a query errored.
4. Select a field code per dimension: `TACD_ALL` for concepts by default, `ALL_AN` (or `TREE@` for a company + subsidiaries) for applicant, `IN` for inventor, `AUTHORITY` / date / `IPC` for scoping. Expand each concept into a synonym OR group so recall does not hinge on a single wording.
5. Author a versioned query set rather than one monolithic query. Keep separate expressions for recall, precision, applicant/inventor scoping, and exclusion. Record each revision and why it changed.
6. For every expression record: the `query_text` verbatim, its purpose, the field codes used, its expected behaviour (broad recall, scoped, exclusion), and any dimension whose field code you took from a reference file rather than the core.
7. Add a validation note for each expression: whether the syntax uses only verified field codes, and which expression the caller should run first to sanity-check hit counts.
8. Deliver the intent decomposition, the versioned query set, validation notes, assumptions, limitations, and the `query_plan` handoff. Do not run the search yourself; hand the expressions to the caller or to `applicant-tech-patent-retrieval`.

## Guardrails

- Do not fabricate field codes. Use only verified codes — the core set above, or codes taken from an on-demand reference file when the core is insufficient.
- Do not claim the query set is exhaustive or global. Disclose the concepts, synonyms, applicant aliases, jurisdictions, date windows, and classifications actually covered.
- Do not turn the query set into a novelty, freedom-to-operate, validity, or infringement conclusion. It only defines what the search tool will match.
- Do not report a fabricated hit count. Hit counts come only from running the search tool, which this skill does not do.
- Keep every `query_text` copyable verbatim; never paraphrase a field code or operator into prose that the tool would reject.
