# Database-family-held-out embedding adaptation

## Question

Can hard-negative supervision from corporate-like same-scope collisions improve
dense schema-object retrieval when the evaluation database family is held out?

## Protocol

The 17-case same-scope collision cohort was split by database family across
three folds (`car_dealership`, `derm_treatment`, and `ewallet`; the cohort had
no broker collision cases). Each fold trained a regularized pair scorer on two
families and evaluated on the third. The positive was the deterministic
gold-SQL focus proxy; same-table and same-normalized-name candidates were hard
negatives. We compared identifier-only Nomic embeddings, table-aware Nomic
embeddings, deterministic structured scores, and a learned pair adapter over
table-aware embedding product/difference features.

## Result

| Arm | MRR | Recall@1 | Recall@5 | Collision before target |
| --- | ---: | ---: | ---: | ---: |
| Identifier-only embedding | .352 | .198 | .635 | 0.0% |
| Table-aware embedding | .511 | .373 | .738 | 29.8% |
| Structured score | .518 | .337 | .889 | 5.6% |
| Hard-negative pair adapter | .499 | .302 | .738 | 51.2% |

## Interpretation

This is a negative adaptation result. Table context improves Recall@1 over
identifier-only vectors, but dense retrieval still confuses same-name objects.
The small learned adapter does not generalize across database families and is
worse than deterministic structured retrieval on MRR, Recall@1, Recall@5, and
collision safety. It is not promotion-eligible and does not justify claiming a
corporate embedding model.

The result does not disprove domain-specific embedding research: the cohort is
small, labels are gold-SQL focus proxies, and there are only three held-out
families. It does establish the correct next gate: larger SME-labelled
hard-negative data, entity/project/time holdouts, and an absolute-lift plus
collision-safety threshold before any adapter is deployed.

Receipts: [`../results/nl2sql-collision-embedding-adaptation-2026-08-03.json`](../results/nl2sql-collision-embedding-adaptation-2026-08-03.json) and
[`../results/nl2sql-collision-embedding-adaptation-2026-08-03-verification.json`](../results/nl2sql-collision-embedding-adaptation-2026-08-03-verification.json).
