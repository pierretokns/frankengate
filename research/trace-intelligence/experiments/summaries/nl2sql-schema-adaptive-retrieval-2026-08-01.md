# Schema-grounded domain-adaptation retrieval benchmark

## Protocol

This is a retrieval-only test on 601 gold-SQL focus-object cases from the
pinned Defog cohort. It uses four leave-one-database-family-out folds. Training
positives are schema-generated table/column queries; negatives are mined from
same-surface, same-table, high-cosine, and granularity-conflict objects. The
adapted scorer is a regularized logistic pair model over frozen Nomic
embedding product/difference features. No enterprise labels or agent replay
outcomes are used.

## Aggregate result

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 | Same-scope collision before target |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical | .1688 | .0801 | .2269 | .3065 | .1311 |
| frozen Nomic embedding | .1824 | .0933 | .2499 | .3760 | .1013 |
| schema-adaptive pair scorer | .1573 | .0761 | .2317 | .3214 | .1094 |

The schema-adaptive scorer underperformed the frozen embedding on MRR,
Recall@1, and Recall@10, and underperformed lexical retrieval on MRR and
Recall@1. It did slightly exceed lexical Recall@5, but not enough to offset
the overall regression. The result is independently receipt-checked.

## Interpretation

Schema-grounded hard negatives and a small adapter did not automatically make
the representation more useful, even when the training positives were
schema-generated and the split was family-held-out. This is a stronger null
than the earlier tiny collision adapter, but it still does not disprove
custom corporate embeddings: the labels are generated proxies, the corpus is
public, and no downstream SQL/tool artifact utility was measured.

The next embedding gate needs SME-labelled undocumented aliases, true NIL and
wrong-system cases, user/project/time holdouts, and a downstream changed-system
replay requirement. Keep exact identifiers and structured scope authoritative.

Receipt: [`../results/nl2sql-schema-adaptive-retrieval-2026-08-01.json`](../results/nl2sql-schema-adaptive-retrieval-2026-08-01.json); [verification](../results/nl2sql-schema-adaptive-retrieval-2026-08-01-verification.json).
