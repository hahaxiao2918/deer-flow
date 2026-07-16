---
name: technology-insight-analysis
description: Analyze a bounded patent evidence set into technical routes, problems, solutions, differentiators, and gaps. Use when the user asks for an evidence-grounded technology landscape or insight analysis from patents.
allowed-tools:
  - patent-data_data_capabilities
  - patent-data_data_cost_estimate
  - patent-data_patent_search
  - patent-data_patent_get_records
---

# Technology Insight Analysis

Convert patent evidence into a route map while separating facts from interpretation.

## Workflow

1. Require a technology question, `project_id`, and either patent numbers or a bounded retrieval scope. Define the unit of analysis: patent, publication, or selected candidate set.
2. Discover only when necessary with one or more documented P002 searches. Before selecting text, call `patent-data_data_cost_estimate` and keep each D114 request to 100 numbers or fewer.
3. Retrieve the selected records. Extract a structured evidence card for each: problem, technical means, claimed effect, key components, constraints, and source field.
4. Cluster cards into competing routes. For each route, state supporting patent numbers, common technical mechanism, differentiators, and evidence gaps.
5. Produce: executive finding, route comparison matrix, evidence register, uncertainties, and a bounded next-search recommendation.

## Guardrails

- Treat model-generated technical decomposition as interpretation; cite the supporting patent fields and patent numbers.
- Never infer performance, commercial adoption, legal freedom-to-operate, or novelty from text alone.
- Do not call disabled capability families or external literature. If literature would change the answer, state it as an unperformed feature-flagged extension.
- Do not retrieve full texts merely to make a chart; begin with the smallest representative set that can answer the question.
