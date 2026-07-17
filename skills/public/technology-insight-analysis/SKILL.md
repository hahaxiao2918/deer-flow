---
name: technology-insight-analysis
description: Build a static patent technology RouteMap from an existing frozen corpus and evidence set. Use for technical architecture, mechanisms, applicant positioning, route clustering, and competition-route comparison at the corpus cutoff. Do not use for new retrieval, market share, legal conclusions, or time-evolution claims.
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

# Technology Insight Analysis

Produce a static `RouteMap` from frozen patent evidence.

## Workflow

1. Require `corpus_id`, RetrievalManifest, evidence records/label decisions, and the analysis question. Emit `search_gap_request` if coverage is insufficient; do not retrieve.
2. Read `references/methodology.md`. Define route dimensions before clustering: problem, component, mechanism, control variable, and claimed outcome.
3. Group patents by evidence-supported technical similarity, preserve hybrids and outliers, and distinguish applicant concentration from market dominance.
4. Compare route structure, evidence density, applicant participation, unresolved alternatives, and counter-evidence.
5. Emit Schema-valid `RouteMap` JSON and a user-readable report; all route claims cite `corpus_id` and `evidence_ids`.

## Stop rules

- Do not automatically retry paid failures. Retry once only when the error says \`retryable=true\` and \`charged=false\`, after the stated delay.
- Never call `patent_search` or `patent_validate_query`.
- Do not infer commercial adoption, market share, legal strength, or patent-family counts.
- Never call web, AMiner, P025, D007, D009, D021, legal-status, family, or citation capabilities.

Read and validate against `references/output.schema.json` before presentation.
