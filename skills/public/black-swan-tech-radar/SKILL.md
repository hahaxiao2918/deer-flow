---
name: black-swan-tech-radar
description: Register evidence-based patent weak-signal candidates from a frozen corpus, RouteMap, and TimelineAnalysis. Use for unusual mechanisms, sparse emerging route combinations, discontinuities, counter-consensus evidence, falsification conditions, and monitoring triggers. Do not output black-swan probabilities, investment advice, or deterministic disruption predictions.
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

# Patent Weak-Signal Radar

Produce a falsifiable `WeakSignalRegister`, not a disruption forecast.

## Workflow

1. Require `corpus_id`, frozen evidence, RouteMap, TimelineAnalysis, cutoff, and monitoring horizon. Emit `search_gap_request` if material evidence is absent; do not retrieve.
2. Read `references/methodology.md`. Screen novelty relative to this corpus, evidence quality, route distance, temporal persistence, and alternative explanations.
3. Register each candidate with supporting and contradictory evidence, uncertainty, falsification condition, and an observable monitoring trigger.
4. Keep sparse evidence visible; do not turn a single document into probability or certainty.
5. Emit Schema-valid `WeakSignalRegister` JSON and a report titled “专利弱信号候选”. Cite `corpus_id` and `evidence_ids` throughout.

## Stop rules

- Do not automatically retry paid failures. Retry once only when the error says \`retryable=true\` and \`charged=false\`, after the stated delay.
- Never call `patent_search` or `patent_validate_query`.
- Never assign black-swan probability, investment rating, valuation, or deterministic disruption outcome.
- Never call web, AMiner, P025, D007, D009, D021, legal-status, family, or citation capabilities.

Read and validate against `references/output.schema.json` before presentation.
