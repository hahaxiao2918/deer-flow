---
name: evidence-based-labeling
description: Apply multi-dimensional, evidence-cited labels to a frozen patent corpus. Use when a RetrievalManifest already exists and records need technical relevance, component, mechanism, role, or confidence labels with unknown, mixed, not_applicable, and conflict states. Do not use to discover or expand patents.
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

# Evidence-Based Labeling

Consume a frozen `RetrievalManifest`; produce evidence records and auditable label decisions.

## Workflow

1. Require `corpus_id`, ordered PN set, label dimensions, and decision rubric. If corpus or coverage is insufficient, emit `search_gap_request`; do not search.
2. Read `references/methodology.md`. Work through cached D114 passages in 10–20-record checkpoints.
3. Create each `evidence_id` from PN, field, locator, and text hash. Separate direct textual evidence from analyst inference.
4. Decide every requested dimension using `supported`, `not_supported`, `unknown`, `mixed`, or `not_applicable`; record conflicts and confidence rationale.
5. Emit JSON matching `references/output.schema.json` and a user-readable report. Every non-unknown conclusion cites `corpus_id` and one or more `evidence_ids`.

## Stop rules

- Do not automatically retry paid failures. Retry once only when the error says \`retryable=true\` and \`charged=false\`, after the stated delay.
- Never call `patent_search` or `patent_validate_query`.
- Do not convert missing text into a negative label.
- Do not resolve conflicting evidence silently.
- Never call web, AMiner, P025, D007, D009, D021, legal-status, family, or citation capabilities.

Read the output Schema immediately before finalization and validate the JSON.
