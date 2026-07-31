# Governed trace-query planner readiness gate

The frozen local policy evaluates the same four-query paired PostgreSQL
receipt before and after the recorded statistics refresh.

| phase | status | denied candidates | latency budgets | required plans |
| --- | --- | --- | --- | --- |
| before refresh | not_ready | True | False | True |
| after refresh | ready | True | True | True |

The release gate is **passed**:
fresh bulk-load receipts must fail readiness, while the post-refresh receipt
must pass all authorization, redacted-plan, and frozen latency checks.

This is local PostgreSQL readiness evidence only. It does not claim Aurora
failover, replication, PITR, RDS Proxy, storage scale, or production SLOs.

Machine-readable result: `experiments/results/planner-readiness-gate-2026-08-02.json`.
