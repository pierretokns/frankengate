# WMH-BIRD fold-local embedding adapter

## Question

Can a small domain-adaptive representation improve a frozen embedding model
when it is trained only from replay-confirmed table labels on task-disjoint
traces, rather than from raw repeated-work frequency?

## Protocol

The same 44 odd-half evaluation tasks and eleven database families used by the
dense/frontier study were frozen. The even half supplied 77 training tasks and
13,040 positive/negative table pairs. Positive labels were recorded SQL tables
plus independently replay-confirmed result-preserving substitutions.

The adapter is deliberately modest: a pairwise hinge ranker over absolute
embedding differences and elementwise query/table interactions. It trains only
on the even half and is evaluated on the odd half. The frozen baseline is local
`nomic-embed-text:latest`; lexical retrieval is included as a lower bound.

## Result

| Arm | Strict MRR | Recall@1 | Recall@5 | Compatible selected rate | Mean invalid selected |
|---|---:|---:|---:|---:|---:|
| Lexical | `.796266` | `.704545` | `.886364` | `.391153` | `3.727` |
| Frozen Nomic | `.940152` | `.909091` | `1.000000` | `.408198` | `3.591` |
| Fold-local adapter | `.947917` | `.931818` | `.977273` | `.408198` | `3.591` |

The adapter improved frozen Nomic MRR by `.007765` and Recall@1 by
`.022727`, but reduced Recall@5 by `.022727` and did not reduce incompatible
shortlist selections. The pooled gain is narrow: Formula 1 improved from
`.708/.500` MRR/Recall@1 to `.812/.750`, Student Club slipped slightly, and the
other families were mostly at or near ceiling.

## Interpretation

This is a bounded positive for **task-disjoint supervised adaptation**, not a
promotion result for a custom corporate embedding. Replay-confirmed labels can
teach a small reranker to improve rank-one selection on a hard family, but they
did not solve candidate precision or wrong-table rejection. The next enterprise
experiment must add reviewed undocumented aliases, same-surface wrong-system
negatives, temporal replacements, and NILs; otherwise the adapter can improve a
proxy rank without improving safe artifact reuse.

The current evidence therefore supports:

```text
structured scope/identifiers
  -> frozen dense candidate recall
  -> fold-local supervised adapter only when labels exist
  -> frontier compression
  -> replay and authority gate
```

It does not support training on raw trace frequency, universal embedding
promotion, or replacing deterministic compatibility checks with a learned
score.

Receipts:

- [content-free result](../results/wmh-bird-sql-embedding-adapter-cohort-2026-08-09.json)
- [independent verification](../results/wmh-bird-sql-embedding-adapter-cohort-verification-2026-08-09.json)
- [`wmh_bird_sql_embedding_adapter_cohort.py`](../../wmh_bird_sql_embedding_adapter_cohort.py)
