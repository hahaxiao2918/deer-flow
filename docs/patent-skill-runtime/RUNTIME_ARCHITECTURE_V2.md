# Patent Skill Runtime Architecture v2

## Outcome

The six patent skills form a composable evidence pipeline rather than six independent end-to-end prompts:

```text
ResearchBrief
  -> QueryPlan
  -> CorpusManifest
  -> EvidenceCard[]
  -> LabelDecision[] | RouteMap | EvolutionMap | WeakSignalRegister
  -> AnalysisClaim[] + limitations + handoff
```

The lead agent chooses one primary skill from the user's requested deliverable. It may reuse upstream artifacts, but it must not silently restart corpus construction or load several broad skills to answer the same stage.

## Routing

| Primary deliverable | Primary skill |
| --- | --- |
| Search-query expressions (检索式) for a later corpus search | `patent-query-composition` |
| Candidate list or auditable corpus | `applicant-tech-patent-retrieval` |
| Per-document inclusion, relevance, or route labels | `evidence-based-labeling` |
| Technical mechanisms and route comparison | `technology-insight-analysis` |
| Time slices, phases, and transitions | `tech-evolution-analysis` |
| Falsifiable weak signals and monitoring triggers | `black-swan-tech-radar` |

Composite requests run as a DAG. For example, “find an applicant's patents and explain route changes” produces a `CorpusManifest` first and passes it to evolution analysis. The second stage must reuse the first-stage artifact.

## Runtime-owned versus user-owned inputs

The runtime owns run IDs, project identity, tool availability, authentication, and data-access policy. A skill must not ask the user for these internal fields. The user owns the research question, intended deliverable, entity/technology boundary, and any decision rule that materially changes the answer.

Each skill asks at most one consolidated clarification for blocking ambiguity. Non-blocking omissions use explicit defaults and are recorded in `ResearchBrief.defaults_applied`.

## Patent-method invariants

- Default to a publication document as the analysis unit. Keep publication, application, grant-publication, and family identifiers separate.
- Treat family counts only under an explicitly named family definition. EPO distinguishes DOCDB simple families from INPADOC extended families and warns that database definitions differ.
- Treat the named entity as applicant as published unless an ownership source supports a different role.
- Use one primary date basis per timeline. Priority, application, publication, grant, and commercial dates are not interchangeable.
- Mark recent publication periods as potentially incomplete. WIPO notes that applications are generally published about 18 months after filing or priority.
- Separate independent-claim support, dependent-claim/embodiment support, general description, model interpretation, and missing evidence.
- Treat a patent's stated effect as an applicant assertion, not independently verified performance.

Primary references:

- [EPO: Patent families](https://www.epo.org/en/searching-for-patents/helpful-resources/first-time-here/patent-families)
- [WIPO: Frequently Asked Questions—Patents](https://www.wipo.int/en/web/patents/faq_patents)
- [EPO: Claims define the matter for which protection is sought](https://www.epo.org/en/legal/guidelines-pct/2026/f_iv_1.html)

## Evidence scale

| Level | Meaning |
| --- | --- |
| E3 | Independent claim directly limits the feature |
| E2 | Dependent claim or explicit embodiment directly supports it |
| E1 | Abstract, background, or general description only |
| I | Model interpretation derived from identified evidence |
| U | Missing, conflicting, or insufficient evidence |

Confidence and evidence level are separate. A confident interpretation remains `I`; missing evidence remains `U` rather than becoming a negative fact.

## State and recovery

Artifacts use the shared statuses `needs_input`, `scope_ambiguous`, `ready`, `no_results`, `partial_data`, `insufficient_evidence`, `unsupported_request`, and `completed`. A partial artifact is resumable and records upstream artifact IDs, assumptions, limitations, and the next missing condition.

For multi-stage or multi-turn work, store artifacts under `workspace/patent-analysis/<analysis_id>/`. Small single-stage answers may return the same structure inline.

## Current runtime limitation

Deerflow's current `skill_context` treats previously read skills as active across later turns and unions their tool permissions. As of commit `b7679504a` (move subagent tool policy to runtime via `SkillToolPolicyMiddleware`) and upstream `65afc9b1d`/#4098 (apply `allowed-tools` only to active skills), general-purpose subagents no longer apply every enabled skill's `allowed-tools` at build time — they filter tools by active-skill state at runtime, the same as the lead agent. The residual blocker is therefore the `skill_context` cross-turn union itself, not the earlier preload behaviour. v2 still does not instruct these skills to use general subagents. Reliable delegation requires one later runtime change: run-scoped primary skill state (skill-specific subagent profiles already exist).

## Release gates

1. All six directories are under `skills/public/` and appear in the production skill registry.
2. Frontmatter parses and `allowed-tools` is enforced by the lead-agent middleware.
3. Routing descriptions are mutually distinguishable on near-neighbor prompts.
4. Each skill emits or consumes the v2 artifact contract.
5. Patent-method invariants pass scenario tests, including applicant ambiguity, duplicate publications, description-versus-claim evidence, recent-period lag, and isolated weak signals.
