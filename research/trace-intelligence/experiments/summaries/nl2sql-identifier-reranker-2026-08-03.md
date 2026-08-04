# Held-out identifier-aware hard-negative reranker

## Question

Can a small identifier-aware ranker, trained on other databases, reduce
same-scope collision errors without requiring a frontier model or a custom
embedding model?

## Protocol

The experiment reused the 17-case public Defog same-scope collision cohort.
It used leave-one-database-out splits and trained a deterministic logistic
ranker on query/candidate surface features: database scope, identifier and
table surface matches, token overlap, lexical score, and collision metadata.
The hard-negative arm upweighted same-scope same-normalized-identifier
siblings by 4x. Positives are deterministic gold-SQL focus proxies, not SME
semantic-alias labels. Raw questions and candidates remain external.

Receipt: [`../results/nl2sql-identifier-reranker-2026-08-03.json`](../results/nl2sql-identifier-reranker-2026-08-03.json)

Independent verification: [`../results/nl2sql-identifier-reranker-verification-2026-08-03.json`](../results/nl2sql-identifier-reranker-verification-2026-08-03.json)

## Result

| Arm | MRR | Recall@1 | Recall@5 | Collision before target |
| --- | ---: | ---: | ---: | ---: |
| Identifier-aware ranker | .737 | .647 | .882 | 0.0 |
| Hard-negative-weighted ranker | .737 | .647 | .882 | 0.0 |
| Exact baseline | .573 | .353 | 1.000 | 0.0 |
| Dense baseline | .586 | .471 | .765 | .235 |
| Luna baseline | .947 | .941 | .941 | 0.0 |

## Interpretation

Identifier-aware features materially improved Recall@1 over exact and dense
retrieval while eliminating observed collision-before-target errors. The
4x hard-negative weighting produced no incremental gain over the unweighted
ranker on this small cohort, so it is not evidence that hard-negative training
alone is sufficient. Luna remained stronger, but at substantially higher
latency/cost and with a gold-proxy candidate pool.

This supports a cheap learned reranking lane between lexical retrieval and
frontier adjudication. It does not justify a custom embedding promotion or
claim semantic alias discovery. The next test should use SME labels, more
databases, temporal schema changes, and a fixed cost/latency budget.
