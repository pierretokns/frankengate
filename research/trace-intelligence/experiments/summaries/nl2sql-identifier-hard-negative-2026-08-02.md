# NL2SQL identifier-aware hard-negative benchmark (2026-08-02)

## Protocol

This study turns the earlier exact-morphology alias lower bound into a
collision-resolution benchmark. A positive is admitted only when a question
surface and a gold-SQL identifier agree under the existing conservative
normalizer. A hard negative is an identifier with the same normalized surface
in another database scope. This is intentionally not semantic alias truth.

The run used the pinned Defog PostgreSQL files (`questions_gen`,
`instruct_basic`, and `instruct_advanced`) outside the repository. The
committed receipt contains source hashes, counts, and aggregate metrics only:
[`nl2sql-identifier-hard-negative-2026-08-02.json`](../results/nl2sql-identifier-hard-negative-2026-08-02.json).

## Results

| Representation | MRR | Recall@1 | Recall@5 | Hard-negative-before-target |
| --- | ---: | ---: | ---: | ---: |
| surface exact, no scope filter | 0.4441 | 0.1992 | 0.8150 | 14.43% |
| surface exact + known database scope | 0.6867 | 0.4492 | 0.9980 | 0.20% |
| character/token similarity + scope | 0.4270 | 0.2276 | 0.7175 | 0.61% |
| `nomic-embed-text` + scope | 0.4151 | 0.2073 | 0.7236 | 0.61% |

The strongest measured improvement came from structured database scope, not
the generic embedding model. Character similarity and the embedding arm did
not beat the exact identifier channel on this task. The unfiltered arm shows
why same-surface cross-system collisions must be explicit hard negatives:
14.43% had a collision ahead of the target, versus 0.20% after scope filtering.

## Interpretation and boundary

This does not show that semantic aliases are easy, that a corporate embedding
model is unnecessary, or that these representations improve an agent. The
positive labels are conservative lexical links, there is no family-held-out
split, and database scope is supplied as known structured metadata. The next
valid gate is frontier/SME adjudication of alias, NIL, and wrong-system cases,
followed by held-out retrieval and changed-agent replay. It does establish a
concrete design rule: preserve exact identifiers and scope filters as a first
retrieval lane; do not replace them with generic dense search by default.
