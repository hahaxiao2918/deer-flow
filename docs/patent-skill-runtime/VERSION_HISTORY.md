# Patent Skill Runtime Version History

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
- Keeps general subagent delegation disabled in the suite manifest until Deerflow supports run-scoped primary skills and skill-specific subagent activation.

Release evidence is stored in `contracts/patent_skill_runtime/manifest.json`, the v2 JSON Schema, automated tests, and Git history.
