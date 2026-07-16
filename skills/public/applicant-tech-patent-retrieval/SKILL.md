---
name: applicant-tech-patent-retrieval
description: Build an auditable patent-publication corpus for a named applicant and technology scope. Use when the primary deliverable is a candidate list, retrieval set, or corpus manifest. Do not use as the primary skill when the user already supplied an adequate corpus or mainly wants route, time-evolution, labeling, or weak-signal analysis.
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

# Applicant Technology Patent Retrieval

Produce a bounded `CorpusManifest`, not a claim of exhaustive ownership or portfolio size.

## Runtime contract

1. Treat this as the corpus-building stage. Emit `schema_version: 2.0.0`, `analysis_id`, `artifact_type: corpus_manifest`, `status`, scope, assumptions, query log, document identifiers, accounting, and limitations.
2. Use the runtime-provided run identifier when visible. Otherwise generate a stable analysis identifier; never ask the user for an internal project or run ID.
3. Default the analysis unit to `publication_document`. Identify documents by `publication_number` with country code and kind code when available. Keep application and grant-publication identifiers separate.
4. Set `family_normalized: false` unless an authorized source explicitly supplies the declared family definition. Never convert publication counts into invention counts when family normalization is unavailable.
5. Reuse an adequate upstream corpus instead of retrieving it again. When another skill will consume the result, write the manifest to `workspace/patent-analysis/<analysis_id>/corpus-manifest.json`; otherwise return the same fields inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `no_results`, `partial_data`, `unsupported_request`, or `completed`.

## Workflow

1. Build a `ResearchBrief` from the request: applicant, technical inclusions and exclusions, jurisdictions, date window, intended deliverable, cutoff date, and stop rule. Apply disclosed defaults for non-blocking omissions.
2. Resolve the applicant as an entity table: canonical name, aliases, former names, included subsidiaries, excluded homonyms, joint-applicant policy, and unresolved ambiguity. Treat the result as `applicant_as_published`, not current owner or ultimate parent.
3. Ask one consolidated clarification only when entity or technology ambiguity would materially change the corpus. Do not silently merge subsidiaries, joint ventures, or similarly named organizations.
4. Create a versioned query set rather than one monolithic query. Separate applicant aliases, technical concepts, exclusions, and any seed-document checks. Record each query revision and why it changed.
5. Run at most three corpus-building rounds by default: initial retrieval, one gap/ambiguity pass, and one counterexample pass. Stop sooner when a round adds no evidence relevant to the research question or the requested boundary is reached.
6. Deduplicate on the declared analysis unit. Preserve unresolved possible duplicates instead of inventing family links.
7. Screen every retained record as `included`, `boundary`, or `excluded` with a short reason. Record truncation and missing coverage explicitly.
8. Deliver the entity-resolution table, query log, corpus funnel, candidate table, limitations, and `CorpusManifest` handoff. Do not expand into a full technology landscape unless a downstream analysis skill is selected.

## Corpus accounting

Report, when available: `raw_hits`, `unique_publications`, `reviewed`, `included`, `boundary`, `excluded`, and `truncated`. State whether multi-applicant documents use full or fractional counting whenever aggregate counts are shown.

## Guardrails

- Say “publication records in the retrieved corpus,” not “inventions,” “all patents,” or “current holdings,” unless the supporting normalization and ownership data exist.
- Do not equate applicant as published with current assignee, patent holder, ultimate parent, or beneficial owner.
- Do not claim global or exhaustive coverage. Disclose jurisdictions, languages, date scope, query limits, and untested aliases.
- Do not answer legal status, freedom-to-operate, validity, infringement, or commercial-adoption questions from this corpus.
