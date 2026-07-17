---
name: applicant-tech-patent-retrieval
description: Build and freeze a cost-bounded patent corpus for a named applicant and technical scope. Use for applicant or competitor patent retrieval, query design, pagination, applicant normalization, corpus freezing, or search-gap fulfillment. Do not use for legal status, family consolidation, novelty/FTO opinions, literature, or downstream route/evolution/signal analysis.
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
  - patent-data_patent_validate_query
  - patent-data_patent_search
  - patent-data_patent_get_records
  - patent-data_patent_get_passages
---

# Applicant Technology Patent Retrieval

Produce a frozen `RetrievalManifest`, not a claim of exhaustive ownership or legal coverage.

## Workflow

1. Confirm applicant identity, technical scope, jurisdictions/date cutoff, recall target, and stopping rule. Clarify unresolved applicant aliases.
2. Read `references/methodology.md` before designing a query. Call capabilities and cost estimate; validate every P002 expression locally before search.
3. Run P002 discovery and pagination only here. Record every query run, coverage boundary, page, and cost. Normalize applicant fields without collapsing uncertain identities.
4. Deduplicate by publication number. Plan D114 in batches of at most 100; 101 records are quoted and executed as 100+1.
5. Fetch D114 manifests, then inspect cached passages in 10–20-record working sets. Maintain requested, returned, missing, and processed sets at every checkpoint.
6. Freeze scope, query runs, cutoff, and the ordered PN set. Compute `corpus_id` as specified in methodology. Emit JSON matching `references/output.schema.json` plus a concise user report.

## Stop rules

- Stop before paid work when the server budget rejects the estimate.
- Do not automatically retry a paid failure. Retry once only when the error says `retryable=true` and `charged=false`, after the stated delay.
- Stop and report partial coverage when P002/D114 is partial, when the applicant remains ambiguous, or when the stated recall boundary is reached.
- Never call web, AMiner, P025, D007, D009, D021, legal-status, family, or citation capabilities.

Read `references/output.schema.json` immediately before writing the final JSON. Validate it before presentation.
