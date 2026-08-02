# Local-only cross-user dense candidate generation

## Question

Do lexical and embedding retrieval identify the same candidate cross-user work,
or are they selecting materially different sessions? This is a candidate
generation study; it intentionally does not ask an external model to infer
private user intent or skill.

## Protocol

The licensed public DataClaw exports contain 549 sessions for Peter and 38 for
Vaynelee. For every Peter session, the study ranked all 38 Vaynelee sessions
using:

1. cleaned lexical term cosine; and
2. local `nomic-embed-text:latest` cosine over the cleaned summaries.

The summaries never left the machine. The receipt stores only session/pair
hashes, scores, tool-name Jaccards, and aggregate counts. There is no semantic
ground-truth label and no frontier adjudication.

## Result

- Lexical and dense top-1 candidates agreed on only `6.01%` of queries.
- Mean top-5 candidate-set Jaccard was `0.238796`.
- Dense top-1 cosine was `.589646`; lexical term cosine was `.063941`.
- Mean tool-name Jaccard for the selected pair was `.257594` dense versus
  `.270708` lexical.
- The top candidate was tool-disjoint in 38 dense cases and 43 lexical cases.
- Candidate concentration was low for both generators: the most frequent top
  pair represented only `.3643%` of queries.

## Interpretation

The two generators are not interchangeable: embeddings produce a very
different cross-user candidate graph from lexical overlap, but neither gives
us evidence that a pair represents the same work. Tool overlap is weak and
often zero, so it cannot serve as a semantic label. This supports a cascade in
which lexical and dense retrieval generate a diverse review queue, followed by
explicit task-equivalence adjudication and opt-in/outcome gates.

The result does **not** establish who is doing the same work, missing skills,
collaboration value, or cross-user transfer. The prior 8-pair Luna pilot is a
silver adjudication only; expanding external adjudication requires explicit
approval to transmit derived user summaries. The next safe experiment is a
locally or enterprise-authorized labelled cohort with blinded reviewers and
prospective recommendation outcomes.

Receipts:

- [content-free result](../results/dataclaw-cross-user-dense-candidates-2026-08-09.json)
- [independent verification](../results/dataclaw-cross-user-dense-candidates-verification-2026-08-09.json)
- [`dataclaw_cross_user_dense_candidates.py`](../../dataclaw_cross_user_dense_candidates.py)
