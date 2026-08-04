# FinanceBench governed pgvector replay

The revision-pinned FinanceBench corpus was loaded into a disposable forced-RLS PostgreSQL/pgvector table using the 768-dimensional finance-specialized embedding.

| metric | value |
| --- | ---: |
| Recall@20 | 1.0000 |
| MRR | 0.8021 |
| authorized candidates | 189 |
| latency p50 (ms) | 2.023 |
| latency p95 (ms) | 2.960 |

All denial scenarios zero: `True`.
Deletion filtered before ranking: `True`.
Rows after rollback: `0`; table cleanup: `True`.

This proves a local governed RLS/deletion path, not Aurora availability, failover, or production promotion.
