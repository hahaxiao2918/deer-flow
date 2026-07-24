# Patent Skill Runtime Version History

## Suite expansion 2026-07-23 (runtime contract stays 2.0.0)

- Added `patent-query-composition` (v2.0.0) as the query-authoring stage that precedes corpus building, turning a research intent into a versioned set of validated PatSnap search-query expressions (检索式) the `patent-data` search tool can run verbatim.
- Added a new `query_plan` artifact type to `v2/runtime-contract.schema.json`, plus `queryPlan` / `queryExpression` `$defs`. This is an additive enum value, so the runtime contract, suite release, and `schema_version` all stay `2.0.0`; the new skill is another v2.0.0 skill, not a version bump. Release evidence is in `contracts/patent_skill_runtime/manifest.json` and the contract test.

## v1.0.0 — baseline

- Source commit: `2beac6d4`.
- Added five initial patent-analysis skill prompt cards under `skills/<skill-name>`.
- Known release defect: current Deerflow only discovers skill packages below `skills/public`, `skills/custom`, or `skills/legacy`; the v1 directories were therefore not active in runtime despite enabled extension entries.
- The five prompts did not share machine-readable intermediate artifacts, routing precedence, consistent stop conditions, or patent-analysis units.

The Git commit is the immutable v1 snapshot; no files inside the distributed skill packages contain a changelog.

## v2.0.0 — composable evidence runtime

- Moves all five packages to `skills/public/<skill-name>` so Deerflow can discover them.
- Routes by intended deliverable and separates corpus building, evidence labeling, route analysis, evolution analysis, and weak-signal monitoring.
- Introduces `ResearchBrief`, `CorpusManifest`, `EvidenceCard`, `AnalysisClaim`, and specialized output contracts.
- Removes internal `project_id`, API product codes, and billing steps from user-facing research workflows.
- Adds explicit clarification, stopping, partial-state, handoff, and artifact rules.
- Adds publication/application/family, applicant role, date basis, evidence-level, publication-lag, and sampling invariants.
- General subagent delegation remains off in the suite manifest. The original technical blocker — subagents applying every enabled skill's `allowed-tools` at build time — was fixed in commit `b7679504a` (move subagent tool policy to runtime via `SkillToolPolicyMiddleware`) and upstream `65afc9b1d`/#4098 (apply `allowed-tools` only to active skills). Skill-specific subagent profiles and run-scoped slash activation now exist. What still remains is run-scoped primary-skill state (the `skill_context` cross-turn union), which is the only reason the flag has not been flipped back on.

Release evidence is stored in `contracts/patent_skill_runtime/manifest.json`, the v2 JSON Schema, automated tests, and Git history.
