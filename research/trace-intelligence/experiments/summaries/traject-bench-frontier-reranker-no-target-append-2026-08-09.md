# TRAJECT-Bench no-target-append control (2026-08-09)

This is the fairer companion to the oracle-covered reranking probe. It uses
the same eight public cases and the same domain-scoped lexical top-16
shortlist, but does **not** append the benchmark's target tool names. Luna
sees only the query and candidate metadata; target labels, tool outputs, and
outcomes remain hidden.

## Result

| Arm | Candidate target coverage | MRR | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|---:|
| Domain lexical top-16 | 0.458333 | 0.360417 | 0.041667 | 0.270833 | 0.385417 |
| Luna reranker | 0.458333 | **0.886364** | **0.270833** | **0.427083** | **0.427083** |

The model improved ordering **only among artifacts that the lexical shortlist
already covered**. Candidate coverage stayed at 0.458333 for both arms, so
the model could not recover the missing target tools. This is the key boundary:
semantic reranking helps after retrieval, but it is not a substitute for
identifier-aware, alias-aware, or embedding-based candidate generation.

## Architectural implication

The minimum useful cascade is now empirically clearer:

1. Scope/domain filter.
2. Cheap lexical and identifier retrieval.
3. A second candidate-generation lane (validated aliases, structured fields,
   or a domain embedding) to improve coverage.
4. Frontier reranking only after the candidate pool is sufficiently complete.

Adding a larger model before step 3 improves rank metrics while leaving the
fundamental recall ceiling unchanged. It also remains unsuitable for automatic
artifact acceptance without execution checks and human/outcome labels.

## Receipts

- Result: [`traject-bench-frontier-reranker-no-target-append-2026-08-09.json`](../results/traject-bench-frontier-reranker-no-target-append-2026-08-09.json)
- Independent verification: [`traject-bench-frontier-reranker-no-target-append-verification-2026-08-09.json`](../results/traject-bench-frontier-reranker-no-target-append-verification-2026-08-09.json)
- Runner/verifier: [`traject_bench_frontier_reranker.py`](../../traject_bench_frontier_reranker.py), [`verify_traject_bench_frontier_reranker.py`](../../verify_traject_bench_frontier_reranker.py)

All eight external raw-output hashes verified. This remains a public-tool
benchmark, not an enterprise skill-improvement or cross-user outcome test.
