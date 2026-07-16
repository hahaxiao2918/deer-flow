---
name: evidence-based-labeling
description: Apply an explicit rubric to a supplied patent-publication set and produce auditable document-level label decisions. Use for inclusion screening, relevance coding, route tags, or other per-document judgments. Do not use for open-ended corpus discovery, technology landscape synthesis, time trends, or disruption forecasting.
allowed-tools:
  - ask_clarification
  - write_file
  - str_replace
  - present_files
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_get_records
---

# Evidence-Based Labeling

Turn a versioned rubric and a bounded publication set into reproducible `LabelDecision` records.

## Runtime contract

1. Require either an upstream `CorpusManifest`/`EvidenceCard` set or explicit publication identifiers. Never start open-ended discovery.
2. Emit `schema_version: 2.0.0`, `analysis_id`, `artifact_type: label_decisions`, `status`, `rubric_version`, `analysis_unit`, document-level decisions, unresolved conflicts, and aggregate checks.
3. Default the analysis unit to `publication_document`. Preserve `publication_number`, `application_number`, and possible duplicate/family ambiguity as separate fields.
4. When another skill will consume the result, write it to `workspace/patent-analysis/<analysis_id>/label-decisions.json`; otherwise return the same structure inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `partial_data`, `insufficient_evidence`, `unsupported_request`, or `completed`.

## Evidence scale

- `E3`: an independent claim directly limits the feature.
- `E2`: a dependent claim or explicit embodiment directly supports it.
- `E1`: only the abstract, background, or general description supports it.
- `I`: a model interpretation derived from identified evidence.
- `U`: missing, conflicting, or insufficient evidence.

Treat a stated effect as the applicant's assertion unless independently validated. Confidence never replaces the evidence level.

## Workflow

1. Define the rubric before full labeling: single-label or multi-label mode, inclusion and exclusion rules, conflicts and priority, minimum evidence level, and use of `uncertain` and `not_applicable`.
2. If the user supplies no rubric, propose a small provisional rubric from the stated decision goal. Ask for clarification only when different reasonable rubrics would materially change the result; otherwise disclose the provisional rule.
3. Calibrate on a small, diverse sample. Tighten ambiguous rules before applying them to the entire set; record the revision as a new rubric version.
4. Build or reuse one `EvidenceCard` per publication. Separate observed text from model interpretation and distinguish `claimed`, `described`, and `background` relationships.
5. Assign every input document exactly one processing status and all permitted labels. For each substantive label, cite the evidence field and locator plus evidence level. Missing evidence yields `insufficient_evidence`, never an automatic negative.
6. Reconcile aggregates against document-level records. Preserve boundary cases and conflicts rather than forcing a clean classification.
7. Deliver the rubric, decision table, evidence/conflict register, aggregate counts, limitations, and handoff artifact.

## Label decision fields

For each publication include: `publication_number`, `decision_status`, `labels`, `decisive_reason`, `counterevidence`, `ambiguity`, and `review_needed`.

Set `decision_status` to exactly one of `labeled`, `partial`, `insufficient_evidence`, `retrieval_failed`, or `conflict`. Each `labels` entry contains `label`, `decision` (`positive`, `negative`, `uncertain`, or `not_applicable`), `evidence_ids`, `evidence_level`, and `confidence`. Use `negative` only when the rubric defines observable exclusion evidence; absence alone is `uncertain`.

## Guardrails

- Do not infer legal scope from description text; distinguish claim support from general disclosure.
- Do not turn broad concepts such as maturity, strategic value, or risk into labels without observable criteria.
- Do not hide retrieval failures, missing fields, model uncertainty, or conflicting passages inside a negative label.
- Do not let aggregate counts replace the publication-level evidence table.
