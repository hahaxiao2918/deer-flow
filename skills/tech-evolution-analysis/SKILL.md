---
name: tech-evolution-analysis
description: Trace a technology's patent-based evolution over time using publication and application dates plus text evidence. Use for technology trajectory, phase, transition, and emerging-route analysis requests.
allowed-tools:
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_search
  - patent-data_patent_get_records
---

# Technology Evolution Analysis

Build a dated, evidence-backed trajectory. A patent date is a document event, not proof that an invention entered the market.

## Workflow

1. Require a technology scope, time window, `project_id`, and the question to be answered (for example, route transition or recent emergence).
2. Call `patent-data_data_capabilities`. Retrieve dated candidates through documented P002 queries; retain `application_date` and `publication_date` as returned.
3. Estimate text cost before D114. Sample or retrieve up to 100 candidate texts per batch, prioritizing boundary years and representative routes.
4. Build time slices from returned dates. For each slice, compare evidence cards for problems, means, effects, and route prevalence. Mark thin samples and missing years.
5. Return a chronology table, transition claims with supporting patent numbers, counter-evidence, and an explicit distinction between observed patent signals and forecasts.

## Guardrails

- Do not convert application/publication dates into priority, family, grant, legal-status, or commercialization claims.
- Do not fabricate a continuous curve when retrieval coverage is uneven.
- Do not use AMiner or web evidence unless a separately enabled capability is added and the user asks for it.
- Keep P025, D007, D009, and D021 disabled.
