---
name: applicant-tech-patent-retrieval
description: Retrieve a bounded patent candidate set for a named applicant and technology theme with explicit query, cost, and provenance controls. Use for competitor, applicant, or organization technology patent retrieval requests.
allowed-tools:
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_search
  - patent-data_patent_get_records
---

# Applicant Technology Patent Retrieval

Build a traceable candidate set, not an assertion that a search is exhaustive.

## Workflow

1. Require the applicant identity, technology scope, target jurisdictions or dates if material, `project_id`, and a desired candidate limit. Distinguish original applicant from current assignee when the request is ambiguous.
2. Call `patent-data_data_capabilities`. Form one documented P002 query using the supplied identifiers and technical synonyms. Do not invent an unsupported search grammar.
3. Call `patent-data_data_cost_estimate` for the planned search and selected text bundle before billable retrieval. Explain the estimate and stop if the project budget rejects it.
4. Call `patent-data_patent_search`; preserve the query, result count, and candidate-level applicant/date fields. Deduplicate by patent number.
5. Fetch D114 text only for the shortlisted set, maximum 100 per batch. Use titles, abstracts, and claims to classify technical relevance; retain non-matches with a reason.
6. Deliver the search expression, selection rule, candidate table, relevance decision, source APIs, and cost/cache metadata.

## Guardrails

- P002 is a retrieval operation, not proof of complete ownership or global coverage.
- Do not claim legal status, family consolidation, or applicant changes without an authorized capability.
- Do not add AMiner, web, P025, D007, D009, or D021 as a fallback.
- If the applicant name is not disambiguated, return candidate ambiguity instead of choosing a company silently.
