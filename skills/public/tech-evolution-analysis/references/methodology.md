# Patent document trajectory methodology

## Date semantics

Choose exactly one primary clock per view:

- application date: when the application was filed, subject to missing/format limitations;
- publication date: when the document became publicly observable.

Never call either the true first invention date. State the cutoff and right-censoring risk: recent applications may not yet be public, and publication lag can shift apparent change.

## Time slices and change claims

Use fixed slices or event-aligned slices declared before comparison. For every slice calculate only frozen-corpus measures: route members, evidence density, applicant participation, mechanism/claim emphasis, entries, exits, persistence, and hybrids.

Classify a change as `observed` only with document/evidence support; `interpreted` when synthesizing multiple observations; `uncertain` when coverage/date bias could explain it. Cite before/after evidence_ids and retain counterexamples.

Do not infer causal technology evolution, product launch, adoption, commercial maturity, market share, or priority. The correct user-facing object is “专利公开文献轨迹”. Missing slices generate search_gap_request; this Skill never searches.
