---
name: frankengate-postgres-capacity-testing
description: Measure FrankenGate PostgreSQL control-plane connection, lock, WAL, failover, reload, and maintenance behavior. Use when sizing Aurora/RDS PostgreSQL, validating LISTEN/NOTIFY, testing migration overlap, or deciding whether another stateful service is justified.
---

# FrankenGate PostgreSQL capacity testing

## Capacity model

Before a run, calculate the peak rather than only steady state:

```text
(serving pods + rollout surge) * (config pool + logs pool + LISTEN/NOTIFY)
+ refresh/verification overlap + migration pool + operator/failover headroom
```

Compare it with `max_connections` and observe actual `pg_stat_activity`; do
not assume the Helm/Terraform check proves Aurora capacity.

## Test sequence

1. Run normal reads/writes and config reloads with representative tenant,
   provider, key, log, outbox, and agent populations.
2. Add rollout surge, concurrent reloads, long streams, durable-worker leases,
   compaction, and admin writes.
3. Inject connection exhaustion, writer failover, transient network errors,
   lock contention, slow queries, WAL growth, and vacuum lag.
4. Verify committed writes have RPO 0, consumers replay after restart, stale
   authority fails closed, and recovery is within the SLO contract.

## Observe

Record connection counts by application/pod, pool wait time, query p50/p95/p99,
locks/deadlocks, transaction age, WAL/replication lag, vacuum progress, CPU,
IOPS, and outbox age. Verify every retry is bounded and idempotent.

Use local PostgreSQL for deterministic contract tests, then repeat against
Aurora/RDS in multiple AZs. A local SQLite result cannot validate this path.
RDS Proxy is a hypothesis to test only after direct pool pressure is measured.
