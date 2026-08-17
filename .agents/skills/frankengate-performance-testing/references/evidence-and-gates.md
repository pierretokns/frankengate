# Evidence and release gates

## Required report fields

Every report should state:

1. exact command and harness revision;
2. image digest, source commit, config/schema epoch, and feature flags;
3. cluster/node/AZ topology and replica/HPA/PDB/rollout settings;
4. PostgreSQL version, instance class, max connections, pool settings,
   failover timing, and whether the run used SQLite, local PostgreSQL, or
   Aurora;
5. workload counts, admitted/rejected/canceled requests, stream and agent
   details, and provider behavior;
6. p50/p95/p99 latency, error classes, queue age/depth, active work, RSS,
   goroutines, GC, DB connections/locks/WAL/vacuum, and recovery time;
7. pass/fail/unknown for each SLO, with raw artifacts and dashboard queries.

## Three-nines arithmetic

For a 30-day month, 99.9% availability permits about 43m 12s of total
unavailability. State the measurement window and whether planned maintenance
is included. A rollout that keeps the service Ready but loses admitted streams
is not a successful availability result; count user-visible failures.

## Upgrade gate

Before a production upgrade, prove the migration Job succeeds with the exact
immutable image, serving pods are verify-only, N remains healthy while N+1
starts, and rollback compatibility is tested. During replacement, verify
readiness withdrawal, ALB target deregistration, active stream/agent behavior,
PostgreSQL pool headroom, event convergence, and no duplicate durable work.

## Failure gate

Run controlled pod replacement, node drain, provider brownout, PostgreSQL
connection pressure, notification disconnect/reconnect, and Aurora writer
promotion. Abort if the test would exceed the outage budget, violate the PDB,
exhaust database headroom, or leave work/leases/cursors unrecoverable.

## Interpretation

- A local pass is a contract/regression result, not AWS capacity evidence.
- A single high-RPS result is not a sustainable capacity claim.
- Missing custom-metric samples must not authorize scale-in.
- If the bottleneck is PostgreSQL, first tune pool budgets, indexes, query
  shape, retention, and vacuum; add a new stateful system only after a measured
  acceptance test shows PostgreSQL cannot meet the SLO.
- If a test is inconclusive, report it as inconclusive and name the missing
  instrumentation or environment; do not convert it into a green gate.
