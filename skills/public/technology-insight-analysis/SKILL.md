---
name: technology-insight-analysis
description: Convert a bounded patent-publication corpus into an evidence-backed map of technical problems, mechanisms, components, claimed effects, route differences, and evidence gaps. Use when the main deliverable is a technical route map or mechanism comparison. Do not use when the main question is document retrieval, per-document labeling, chronological change, or weak-signal monitoring.
allowed-tools:
  - ask_clarification
  - write_file
  - str_replace
  - present_files
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_search
  - patent-data_patent_get_records
---

# Technology Insight Analysis

Produce a route map from a declared corpus while separating documentary evidence from interpretation.

## Runtime contract

1. Prefer an upstream `CorpusManifest`, `EvidenceCard` set, or user-supplied corpus. Build a bounded corpus only when no adequate artifact exists; never repeat completed upstream work.
2. Emit `schema_version: 2.0.0`, `analysis_id`, `artifact_type: route_map`, `status`, `research_brief`, corpus reference, taxonomy version, `route_cards`, `analysis_claims`, counterevidence, and limitations.
3. Default to `publication_document` as the analysis unit. Keep family normalization, date basis, and sampling method explicit.
4. When the analysis will be reused, write it to `workspace/patent-analysis/<analysis_id>/route-map.json`; otherwise return the same structure inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `partial_data`, `insufficient_evidence`, `unsupported_request`, or `completed`.

## Workflow

1. Frame one answerable technical question and the expected route-comparison deliverable. Define technical inclusions/exclusions, corpus boundary, cutoff date, analysis unit, and whether results are qualitative or count-bearing.
2. Ask one consolidated clarification only when the technical boundary would produce materially different route systems. Apply and disclose safe defaults otherwise.
3. For every included publication, create or reuse evidence cards covering: problem, technical means, components, constraints, and stated effect. Record field/locator and classify the relationship as `claimed`, `described`, or `background`.
4. Create a versioned route taxonomy with hierarchical definitions, multi-label policy, and `other`/`uncertain` buckets. Do not force mutually exclusive routes when a publication implements multiple mechanisms.
5. Build `route_cards` with: `route_id`, `name`, `definition`, `mechanism`, `evidence_ids`, `publication_numbers`, `differentiators`, `counterexamples`, `boundary_cases`, and `evidence_gaps`.
6. Build each `analysis_claim` with: `claim_id`, `claim_type`, `text`, `evidence_ids`, `counterevidence_ids`, `confidence`, and `limitations`. Mark model synthesis as interpretation.
7. Stop when each supported route has a definition, evidence, differentiators, and limitations, and another pass adds no new answer-changing evidence. Return unsupported routes as hypotheses, not findings.
8. Deliver an executive answer, route matrix, evidence register, counterevidence, limitations, and bounded next-step recommendations.

## Quantitative boundary

- With a selected, sampled, or truncated corpus, say “within the analyzed corpus” and avoid industry prevalence, share, leadership, growth, or white-space claims.
- Without declared family normalization, counts describe publication records, not inventions.
- Call missing support an `evidence gap`; do not automatically label it a technology gap, patent gap, market opportunity, or freedom-to-operate space.

## Guardrails

- Patent text can support disclosed and claimed mechanisms; it does not by itself prove performance, novelty, commercial adoption, validity, or freedom to operate.
- Treat stated benefits as applicant assertions unless independently validated.
- Route definitions must remain falsifiable and traceable to publication-level evidence.
- Route-over-time questions belong to `tech-evolution-analysis`; abnormal or discontinuous signals belong to `black-swan-tech-radar`.
