---
name: tech-evolution-analysis
description: Trace how technical routes in a bounded patent-publication corpus change across declared time slices, with explicit date semantics and transition evidence. Use when chronology, phases, emergence, persistence, or route transition is the main question. Do not use for a static route map, simple retrieval, per-document labels, or deterministic technology forecasting.
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

# Technology Evolution Analysis

Produce a dated `EvolutionMap`; never turn document dates into proof of invention, adoption, or commercialization.

## Runtime contract

1. Prefer an upstream `CorpusManifest`, `EvidenceCard` set, and route taxonomy. Build missing inputs only when necessary and do not repeat completed upstream work.
2. Emit `schema_version: 2.0.0`, `analysis_id`, `artifact_type: evolution_map`, `status`, corpus reference, one declared primary date basis, time-slice rules, `transition_claims`, counterevidence, sparse periods, and limitations.
3. Default the analysis unit to `publication_document`. Keep application, publication, priority, grant, and commercial-event dates semantically separate.
4. When the analysis will be reused, write it to `workspace/patent-analysis/<analysis_id>/evolution-map.json`; otherwise return the same structure inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `partial_data`, `insufficient_evidence`, `unsupported_request`, or `completed`.

## Date policy

Choose exactly one primary date basis for a timeline:

1. Use earliest priority date for technical-activity timing only when explicitly available and normalized.
2. Otherwise use application date as a disclosed proxy.
3. Use publication date only for when a document became publicly observable.

Never mix these fields in one trend series. Mark the most recent 18–24 months as potentially incomplete when publication lag can affect the corpus.

## Workflow

1. Define the evolution question, technology boundary, time window, cutoff date, analysis unit, date basis, and minimum comparable time slices.
2. Ask one consolidated clarification if the date basis or technology boundary is outcome-determinative. If only one valid period is present, downgrade to a static description or return `insufficient_evidence`.
3. Create or reuse evidence cards and a stable route taxonomy. Apply the same classification rules across all time slices.
4. Divide time using a declared, reproducible rule. Record corpus size, missingness, truncation, and route evidence per slice.
5. Form a `transition_claim` only when at least two comparable slices support a change. Include exactly: `claim_id`, `claim_type`, `text`, `evidence_ids`, `counterevidence_ids`, `confidence`, `date_basis`, `prior_period`, `later_period`, `alternative_explanations`, and `limitations`.
6. Use cautious emergence language: “first observed in the retrieved corpus under the chosen date basis,” not “invented,” “originated,” or “first appeared globally.”
7. Stop when every claimed transition is supported across comparable slices and another pass adds no answer-changing evidence. Do not interpolate across empty or methodologically inconsistent periods.
8. Deliver the timeline, transition register, counterevidence, recent-period warning, limitations, and monitoring implications.

## Quantitative boundary

- Discuss route prevalence only when corpus construction and classification are consistent across slices and coverage is adequate.
- With sampled text, describe case changes rather than industry growth rates or market direction.
- Without family normalization, counts describe publication records and may include multiple documents related to one invention.

## Guardrails

- A patent date is a document/procedure event, not proof of R&D start, technical readiness, product launch, or adoption.
- Do not call a sparse or truncated series a continuous trend.
- Do not claim a decline from recent publication data without addressing publication lag.
- Use `technology-insight-analysis` first when no stable route taxonomy exists.
