# Retrieval methodology

## Scope and query design

Represent scope as `{applicant identities, technical concepts, exclusions, jurisdiction, date field/cutoff}`. Keep original applicant and current assignee separate. Record aliases as `confirmed`, `candidate`, or `rejected`; never merge candidates without evidence.

Use a staged query ledger: broad technical discovery, applicant-constrained recall, synonym/classification expansion, then explicit exclusions. Each `query_run` records expression, syntax version, limit/offset, returned/total counts, timestamp, cost, and purpose. P002 is a candidate generator, not an exhaustiveness proof.

## Freeze and identifiers

Canonicalize the freeze payload as UTF-8 JSON with sorted keys and compact separators:

```json
{"cutoff":"...","ordered_pns":["..."],"query_runs":[...],"scope":{...}}
```

`corpus_id = "sha256:" + SHA256(canonical_payload)`.

The PN list order is deterministic: publication date, then normalized PN. Preserve all query-run and pagination boundaries so the corpus can be reproduced.

## D114 batching and checkpoints

D114 is priced per call for up to 100 records. Pack full batches where practical; quote 101 as two complete calls (100+1). A manifest must preserve requested, returned, missing, batch_id, cache hits, charged cost, and provider status. Partial is never complete success.

Consume cached passages in 10–20-record working sets. After each set, persist processed PNs and any unresolved gap. A passage locator and text hash are the evidence boundary; do not copy 100 full texts into model context.

## Search-gap request

A downstream gap request should state: originating artifact, missing proposition, desired evidence fields, affected PNs or scope, priority, and why existing evidence cannot answer it. The Retriever decides whether a new paid query is justified.
