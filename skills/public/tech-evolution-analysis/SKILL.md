---
name: tech-evolution-analysis
description: Analyze an evidence-linked trajectory of patent application and publication documents across time slices. Use when a frozen corpus and RouteMap exist and the user needs changes in documented routes, applicants, mechanisms, or claim emphasis. Do not describe true invention priority, market adoption, market share, or commercialization evolution.
metadata:
  contract_version: patent-research.v2
allowed-tools:
  - tool_search
  - ask_clarification
  - write_file
  - str_replace
  - present_files
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_get_records
  - patent-data_patent_get_passages
---

# Patent Document Trajectory Analysis

Produce `TimelineAnalysis` using only application/publication-date evidence.

## Workflow

1. Require `corpus_id`, frozen documents, evidence, RouteMap, date field, cutoff, and slice rule. Emit `search_gap_request` for missing coverage; do not retrieve.
2. Read `references/methodology.md`. State whether each view uses application date or publication date and never mix them silently.
3. Compare route presence, evidence density, applicant participation, mechanism/claim emphasis, persistence, entry, and disappearance across slices.
4. Separate observed document changes from interpretations. Register date/coverage bias and late-publication censoring.
5. Emit Schema-valid `TimelineAnalysis` JSON plus a report headed “专利公开文献轨迹”. Cite `corpus_id` and `evidence_ids` for every change claim.

## Stop rules

- Do not automatically retry paid failures. Retry once only when the error says \`retryable=true\` and \`charged=false\`, after the stated delay.
- Never call `patent_search` or `patent_validate_query`.
- Never claim the first real invention date, commercial maturity, market share, product adoption, or causal evolution.
- Never call web, AMiner, P025, D007, D009, D021, legal-status, family, or citation capabilities.

Read and validate against `references/output.schema.json` before presentation.
