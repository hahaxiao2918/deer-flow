# Patent Skill Runtime v2 Evaluation

## Evaluation method

Fresh subagents received only the revised skill path and a user-like task. They were not given the review findings or expected output. No external patent or paid data tools were called.

## Scenario results

| Scenario | Skills | Result |
| --- | --- | --- |
| Ambiguous applicant name, uncertain group boundary, request for “currently owned inventions” | Applicant retrieval | Passed: returned `needs_input`, asked one consolidated clarification, distinguished publication records, families, and current ownership, and did not invent a count |
| Three synthetic publications with independent-claim, dependent-claim, embodiment, and background evidence | Evidence labeling | Passed after iteration: used multi-label decisions, E3/E2/E1/U levels, treated missing as uncertain, separated embodiment disclosure from claim scope, and emitted v2 fields |
| Same three-document corpus summarized into routes | Technology insight | Passed: produced route definitions, evidence links, boundary cases, counterevidence, and corpus-limited conclusions |
| Sparse 2021–2024 application timeline with 2024–2026 publication dates | Technology evolution | Passed: selected one date basis, warned about recent-period lag, treated a single R2 record as insufficient for a mutation-period conclusion, and rejected winner prediction |
| One cross-domain additive-manufacturing record against an R1 baseline | Weak-signal radar | Passed: classified it as `isolated_hypothesis`, supplied alternatives, falsification and monitoring triggers, and proposed only low-regret actions |

## Iterations caused by evaluation

1. First-pass agents invented `schema_version: 1.0` because the skills required a version but did not fix its value. The contract now requires `2.0.0` explicitly.
2. Labeling agents interpreted processing status differently. The contract now uses `decision_status` with a fixed enum and structured per-label assignments.
3. A second-pass labeling agent used numeric confidence. The contract now restricts confidence to `low`, `medium`, or `high`.

## Remaining runtime limitation

These evaluations validate skill behavior in isolated contexts. They do not validate general-purpose Deerflow subagent delegation. The original reason for keeping it disabled in the v2 suite manifest — subagents preloading all enabled skills without activating the associated `allowed-tools` policy — has since been fixed in the framework: commit `b7679504a` moves subagent tool policy to runtime via `SkillToolPolicyMiddleware`, and upstream `65afc9b1d`/#4098 applies `allowed-tools` only to active skills. Subagents now filter tools by active-skill state at runtime, the same as the lead agent. The suite-level `general_subagent_delegation` flag therefore reflects an outstanding product decision (run-scoped primary-skill state), not the original technical blocker.
