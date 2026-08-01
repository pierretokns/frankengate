# MATM embedding/frontier cascade cost replay

**Status:** independently verified cost/latency extension of the existing
same-corpus cascade benchmark

## Protocol

The nine MATM leave-one-model-out queries, candidate pool, pinned parquet, and
embedding cache were held constant. The frontier arm was rerun with
`gpt-5.6-luna`; lexical and cached-embedding rankings were recomputed over the
same candidates. Wall-clock timing was recorded around each frontier call. The
Codex CLI `tokens used` line is retained as a diagnostic only; it is not a
provider billing or dollar-cost measurement.

## Result

| Arm | MRR | Recall@1 | Recall@3 | Recall@5 | Top-3 success |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 1.000 | 1.000 | 1.000 | 1.000 | .703704 |
| Frontier Luna | 1.000 | 1.000 | 1.000 | 1.000 | .703704 |
| Cached embedding | .674074 | .555556 | .777778 | 1.000 | .666667 |

All nine frontier calls completed. The frontier-call wall-clock total was
`104.118s`, mean `11.569s`, median `11.226s`, and maximum `15.692s`. The CLI
diagnostic usage total was `140,598` tokens (mean `15,622`); this must not be
interpreted as API billing.

## Interpretation

The timing extension strengthens the operational decision but does not change
the quality result: frontier reranking added no quality over lexical ranking on
this silver same-work candidate pool while adding roughly eleven seconds per
query. Embeddings were weaker on this pool but remain useful as a candidate
recall lane in the separate leave-one-model-out study.

This does not prove frontier models are unhelpful for real enterprise insight
mining. The candidate pool was deliberately rich, labels were normalized
task/goal signatures rather than human insight judgments, and no downstream
artifact or skill replay was performed. The safe cascade remains exact and
structured retrieval first, dense recall second, frontier review only for
ambiguous/high-value cases.

Receipts:

- [`deduplicated timing result`](../results/matm-frontier-reranker-luna-9q-cost-2026-08-04-deduped.json)
- [`source timing result`](../results/matm-frontier-reranker-luna-9q-cost-2026-08-04.json)
- [`existing quality receipt`](../results/matm-frontier-reranker-luna-9q-2026-08-02.json)
- [`independent verifier`](../verify_matm_frontier_cost_receipt.py)
