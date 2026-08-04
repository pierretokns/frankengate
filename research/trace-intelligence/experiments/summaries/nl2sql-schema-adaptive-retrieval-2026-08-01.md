# Schema-adaptive NL2SQL retrieval benchmark (2026-08-01)

## Question

Does schema-grounded adaptation—schema-generated positives plus
granularity-aware hard negatives—improve retrieval over exact/scope, lexical,
or frozen dense retrieval on held-out database families?

## Protocol

- 304 table/column documents from four pinned Defog/BIRD PostgreSQL schemas.
- 601 target-object cases from the frozen 96-task public cohort.
- Training positives were deterministic question-like templates generated from
  in-fold table/column metadata.
- Hard negatives were high-cosine wrong objects, same-surface identifiers,
  same-table siblings, and granularity conflicts.
- Four leave-one-database-family-out folds.
- Candidate modes: known database scope and all four databases pooled.
- Embedding: cached `nomic-embed-text:latest`.
- Adapter: regularized logistic pair scorer over query/document product and
  absolute-difference features.
- Raw questions, SQL, vectors, and model output remain external; only hashes
  and aggregates are committed.

## Results

### Known database scope

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 | Same-scope collision before target |
|---|---:|---:|---:|---:|---:|
| Exact + scope | .212903 | .112351 | .279807 | .411319 | .131148 |
| Lexical | .212903 | .112351 | .279807 | .411319 | .131148 |
| Frozen Nomic | **.217356** | .105583 | **.305847** | **.447275** | **.101321** |
| Schema-adaptive pair scorer | .201527 | .093609 | .296131 | .425539 | .109423 |

### All databases pooled

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 | Wrong-scope collision before target |
|---|---:|---:|---:|---:|---:|
| Exact + scope | .177071 | .086127 | .240039 | .319787 | .001760 |
| Lexical | .168784 | .080066 | .226936 | .306544 | .001760 |
| Frozen Nomic | **.182393** | **.093345** | **.249854** | **.376003** | .003416 |
| Schema-adaptive pair scorer | .157347 | .076090 | .231716 | .321425 | .008698 |

The independent verifier passed all hash, source, split, document-count,
case-count, mode/arm, and metric-bound checks.

## Interpretation

1. Frozen Nomic is slightly better than the deterministic baselines on this
   public schema/focus-object proxy, especially Recall@10.
2. The lightweight adapter is not promotable: it loses to frozen Nomic in both
   scope modes and has worse pooled wrong-scope collisions.
3. This does **not** test the full 305M-parameter corpus-adaptive recipe from
   the July 2026 schema-retrieval paper. It does establish that “add a simple
   hard-negative pair scorer” is not enough.
4. The cohort uses gold-SQL focus objects, not independent SME alias labels;
   it does not establish semantic alias truth, agent utility, or changed-system
   artifact value.

## Next gate

Reproduce the stronger schema recipe: generate paraphrases with a frozen
frontier/local model, train a true contrastive adapter or compatible 305M
encoder, add independent SME/NIL labels, and compare against the frozen Nomic
and identifier-aware ranker on the same splits. Promote only if the retrieval
gain survives changed-system artifact replay.

Receipts: [`result`](../results/nl2sql-schema-adaptive-retrieval-2026-08-01-v2.json), [`independent verification`](../results/nl2sql-schema-adaptive-retrieval-2026-08-01-v2-verification.json).
