# E2 same-candidate PostgreSQL joint retrieval

**Status:** completed local same-candidate quality + forced-RLS gate
**Dataset documents:** 145
**Eligible silver-label queries:** 99
**Result SHA-256:** `e26cc9992a1c04df3af8638339d326d4b70cd8c6ab7ae2379c049f6fc0961854`

The same 145 documents and pinned 1024-dimensional Qwen query/document vectors
were loaded into a rollback-only disposable PostgreSQL transaction. All rankings
ran as the non-owner, non-bypass `trace_research_app` role under forced RLS.

## Native PostgreSQL quality

| Channel | R@1 | R@5 | R@20 | nDCG@20 | MRR |
|---|---:|---:|---:|---:|---:|
| postgres_fts | 0.061 | 0.177 | 0.444 | 0.236 | 0.213 |
| postgres_trigram | 0.040 | 0.172 | 0.384 | 0.199 | 0.185 |
| postgres_exact_pgvector | 0.338 | 0.561 | 0.667 | 0.597 | 0.666 |
| postgres_hybrid_rrf | 0.212 | 0.480 | 0.672 | 0.494 | 0.510 |

## Sequential local latency

| Operation | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|
| postgres_fts | 28.502 | 38.647 | 39.757 | 52.551 |
| postgres_trigram | 223.595 | 261.010 | 266.387 | 267.492 |
| postgres_exact_pgvector | 3.017 | 3.428 | 4.130 | 4.682 |
| postgres_hybrid_rrf_end_to_end | 256.843 | 291.111 | 306.610 | 310.413 |
| hybrid_fusion_only | 0.108 | 0.131 | 0.341 | 0.393 |

The denied candidate matrix is entirely zero. Withdrawn and soft-deleted rows
both disappeared before ranking. The transaction was rolled back and the
post-rollback visible row count was
0.

Loaded-state storage was
17809408 total bytes,
including 12296192 index bytes.
Raw trace text, source identities, labels, rankings, and vectors are absent from
this result.

## Claim limits

- task identity is a publisher-provided silver positive, not blinded human adjudication
- the 145-document cohort is a correctness and small-query benchmark, not a scale test
- latency is sequential client-observed local PostgreSQL latency without concurrency
- the disposable single-node PostgreSQL fixture is not Aurora and does not test failover, replicas, RDS Proxy, or reader lag
- FTS and trigram query projections are fixed bounded approximations, not learned query rewriting
- all corpus documents share one synthetic private authority; this proves fail-closed mechanics, not enterprise sharing policy quality
- withdrawal and deletion are tested as visibility transitions inside the same rollback-only transaction
- same benchmark task does not establish that two enterprise users should collaborate
- no user skill-gap, productivity, longitudinal memory, or causal improvement claim is supported
