---
name: black-swan-tech-radar
description: Screen a bounded patent corpus for weak, discontinuous, or cross-domain technical signals with evidence and uncertainty. Use for early-warning technology radar or potential disruption screening, not deterministic prediction.
allowed-tools:
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_search
  - patent-data_patent_get_records
---

# Black Swan Technology Radar

Produce a falsifiable signal register, not a claim that a black-swan event will occur.

## Workflow

1. Require the focal technology or business boundary, a time horizon, `project_id`, and a practical action threshold. Define what counts as a signal before searching.
2. Call `patent-data_data_capabilities`. Use documented P002 searches to assemble a bounded corpus and preserve dates, applicant fields, and query provenance.
3. Estimate D114 cost before retrieval. Pull text for a diverse, bounded shortlist; do not request every result by default.
4. Score only evidence-backed dimensions: technical discontinuity, cross-domain recombination, unusual claimed mechanism, and recent emergence in the retrieved corpus. State the evidence and counter-evidence for each signal.
5. Return a radar register with signal, patents, confidence, why it matters, disconfirming evidence, monitoring trigger, and recommended low-regret action.

## Guardrails

- Label results as `signal`, `hypothesis`, or `insufficient_evidence`; never call a signal a forecast or probability.
- Patent corpus novelty is not market novelty, legal status, competitive intent, or commercial feasibility.
- Literature and web corroboration are not enabled in this version; say so instead of improvising a source.
- Do not use P025, D007, D009, D021, or unapproved per-item full-text fallbacks.
