---
name: black-swan-tech-radar
description: Screen a bounded patent-publication corpus for weak, discontinuous, or cross-domain technical signals and define falsifiable monitoring triggers. Use when the primary deliverable is an early-warning signal register or low-regret monitoring plan. Do not use to predict event probabilities, choose future winners, or replace a conventional route or evolution analysis.
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

# Technology Weak-Signal and Discontinuity Radar

Produce a falsifiable `WeakSignalRegister`, not a prediction that a black-swan event will occur.

## Runtime contract

1. Prefer an upstream `CorpusManifest`, `EvidenceCard` set, route taxonomy, and evolution baseline. Build a bounded corpus only when no adequate artifact exists; never repeat completed upstream work.
2. Emit `schema_version`, `analysis_id`, `artifact_type: weak_signal_register`, `status`, baseline, corpus reference, signal records, counterevidence, alternative explanations, falsifiers, monitoring triggers, and limitations.
3. Default the analysis unit to `publication_document`. State family-normalization, sampling, date basis, and publication-lag limitations.
4. When the analysis will be reused, write it to `workspace/patent-analysis/<analysis_id>/weak-signal-register.json`; otherwise return the same structure inline.

Use status values consistently: `needs_input`, `scope_ambiguous`, `ready`, `partial_data`, `insufficient_evidence`, `unsupported_request`, or `completed`.

## Signal states

- `isolated_hypothesis`: one document or one potentially dependent source.
- `candidate_signal`: multiple evidence items but independence, persistence, or baseline contrast remains uncertain.
- `monitored_signal`: evidence persists across the declared baseline, time slices, or independently resolved applicants.
- `insufficient_evidence`: the signal cannot be distinguished from noise.

Do not express these states as event probabilities.

## Workflow

1. Define the focal business/technology boundary, comparison baseline, time horizon, cutoff date, and practical action threshold before scoring signals.
2. If no defensible baseline exists, produce a monitoring design rather than ranked signals. Ask one consolidated clarification only when the boundary or action threshold is outcome-determinative.
3. Create or reuse evidence cards and compare them with the established route/evolution baseline. Screen for technical discontinuity, cross-domain recombination, unusual claimed mechanism, and recent corpus emergence.
4. For each candidate, test whether the apparent anomaly could result from query design, terminology change, translation, duplicate publications, family relationships, classification drift, or a single applicant's drafting style.
5. Build each signal record with: state, mechanism, baseline contrast, supporting publications/evidence, counterevidence, alternative explanations, independence assessment, falsification condition, monitoring trigger, and reversible low-regret action.
6. Keep a single publication at `isolated_hypothesis` unless independent corroboration exists. Do not count similar publication records as independent inventions without declared family/entity normalization.
7. Stop when each retained signal has both supporting and disconfirming analysis plus a monitorable trigger; otherwise return it as insufficient evidence.
8. Deliver the radar register, evidence/counterevidence, monitoring plan, low-regret actions, and explicit non-prediction disclaimer.

## Guardrails

- Patent-corpus novelty is not market novelty, commercial feasibility, competitive intent, legal strength, or adoption.
- Do not forecast winners, disruption probability, timing certainty, or financial impact from patent text alone.
- Treat stated effects as applicant assertions and cross-domain similarity as a hypothesis until the mechanism is evidenced.
- Use `technology-insight-analysis` for the current route structure and `tech-evolution-analysis` for ordinary chronological change.
