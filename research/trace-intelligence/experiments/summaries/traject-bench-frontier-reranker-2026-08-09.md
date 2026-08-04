# TRAJECT-Bench frontier reranking probe (2026-08-09)

This is a bounded reranking probe on eight deterministic public
TRAJECT-Bench cases. It is deliberately narrower than full tool retrieval:
the local stage built a domain-scoped lexical shortlist of up to 16 tools and
then appended the benchmark's target tool names when they were absent. Luna
was asked to rank that shortlist. It saw the public query and candidate
metadata, but not the target labels, tool outputs, or success outcomes.

## Result

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Domain lexical shortlist | 0.360417 | 0.041667 | 0.270833 | 0.385417 |
| Luna reranker | **1.000000** | 0.302083 | **0.822917** | **0.968750** |

The frontier model substantially improved ordering inside this already
covered shortlist. This is evidence for a **selective semantic reranking
lane** after deterministic scope filtering, not evidence that a model can
discover missing tools or validated corporate artifacts from raw traces.

## What this adds to the architecture

1. Keep domain/scope filtering and cheap identifier/name retrieval first.
2. Use a frontier model only on a small, candidate-complete shortlist when
   ambiguity remains.
3. Do not let the reranker accept, publish, or authorize an artifact. The
   benchmark has no enterprise outcome labels, no human utility labels, and no
   same-surface/different-system hard-negative cohort.
4. The appended target names make this an oracle-coverage reranking test. A
   fair next experiment must remove that append step and evaluate recall and
   reranking separately on a held-out candidate pool.

## Verification and reproducibility

- Content-minimized result: [`traject-bench-frontier-reranker-2026-08-09.json`](../results/traject-bench-frontier-reranker-2026-08-09.json)
- Independent receipt verification: [`traject-bench-frontier-reranker-verification-2026-08-09.json`](../results/traject-bench-frontier-reranker-verification-2026-08-09.json)
- Runner: [`traject_bench_frontier_reranker.py`](../../traject_bench_frontier_reranker.py)
- Verifier: [`verify_traject_bench_frontier_reranker.py`](../../verify_traject_bench_frontier_reranker.py)
- Raw model outputs remain external under `/private/tmp`; only SHA-256
  receipts are committed.

The verifier passed for all eight cases, with outcomes hidden from the
frontier prompt. This probe does not measure agent intervention, trace replay,
skill improvement, enterprise transfer, or production authorization.
