---
name: evidence-based-labeling
description: Label a user-supplied or retrieved patent set against explicit technical, strategic, or evidence criteria. Use when the user needs auditable inclusion, relevance, maturity, route, or risk labels rather than unsupported summaries.
allowed-tools:
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_get_records
---

# Evidence-Based Labeling

Turn an explicit label rubric into a reproducible patent-level decision table. This skill analyzes evidence; it does not perform open-ended discovery.

## Workflow

1. Require a label rubric, a `project_id`, and patent numbers. If the user has no rubric, propose a small mutually exclusive label set and ask for confirmation before retrieval.
2. Call `patent-data_data_capabilities` once. State unavailable capabilities rather than silently substituting other sources.
3. Call `patent-data_data_cost_estimate` before an uncached text request. Retrieve at most 100 patent numbers per call with `patent-data_patent_get_records`.
4. Inspect title, abstract, claims, and only the description passages necessary for each rubric criterion. A missing field is `insufficient_evidence`, never a negative fact.
5. Return a table: patent number, label, confidence, decisive evidence, source API, and unresolved ambiguity. Quote or tightly paraphrase evidence and identify the field used.

## Guardrails

- Every substantive label needs patent-number-level evidence from `D114` or `P012` provenance.
- Do not use P025, D007, D009, D021, web search, or literature as a hidden substitute.
- Do not claim legal status, family membership, ownership history, or citation impact: those capabilities are unavailable.
- Prefer cached records. Do not request the same text twice in one task.
- Report aggregate label counts separately from the evidence table; never let an aggregate replace the table.
