# Evidence-labeling methodology

## Evidence unit

An EvidenceRecord is a bounded D114 passage. Compute:

`evidence_id = "sha256:" + SHA256(PN + "\n" + field + "\n" + locator + "\n" + text_hash)`.

Preserve the source text hash, locator, truncation flag, and corpus_id. Direct evidence quotes or paraphrases what the passage says; interpretation explains why it bears on a label.

## Multi-dimensional decisions

Define each dimension before labeling: value vocabulary, positive rule, negative rule, minimum evidence, and ambiguity rule. Use:

- `supported`: direct evidence meets the positive rule.
- `not_supported`: reviewed evidence affirmatively conflicts with the proposition.
- `unknown`: missing/insufficient evidence; never treated as negative.
- `mixed`: material supporting and conflicting evidence coexist.
- `not_applicable`: the dimension does not apply to the record.

Confidence is `high`, `medium`, or `low` with a reason; it is not a probability. Record label conflicts across abstract, claims, and description rather than voting them away. Claims usually support claimed scope; description may support embodiments; abstracts are screening evidence.

## Quality gates

Every supported/not-supported/mixed decision cites evidence_ids. Unknown may cite missing fields. Check inter-label consistency, prohibited inferences, unresolved conflicts, and whether truncated passages could change the decision. Issue a search_gap_request only for corpus coverage, never to bypass missing evidence by searching directly.
