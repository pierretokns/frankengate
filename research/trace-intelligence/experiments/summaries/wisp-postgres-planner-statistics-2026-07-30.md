# Governed Wisp PostgreSQL planner-statistics experiment

**Date:** 2026-07-30
**Status:** paired local PostgreSQL experiment complete
**Result SHA-256:** `f0a69ed9c7b03bdaf29bb2df96508a0f3734992741539b97157ffd07c9ab1bda`

## Question

Does a freshly bulk-loaded governed trace corpus produce a stable query plan
before PostgreSQL planner statistics are refreshed?

## Design

The same disposable PostgreSQL 16.12 database with pgvector 0.8.1 was measured
twice. It contained:

- 104 Wisp trajectories;
- 17,505 canonical events;
- 122 proposal-only derived artifacts; and
- identical tenant, subject, purpose, classification, and authorization-epoch
  settings.

Each phase ran 250 warm invocations of personal-history, structural-tool-event,
proposal-queue, and controlled-FTS queries. Between phases the only intended
intervention was `ANALYZE` on the three `trace_research` data tables. All five
wrong-tenant, wrong-subject, stale-epoch, wrong-purpose, and
insufficient-clearance scenarios returned zero candidates before ranking in
both phases.

## Result

| Query | Before p50 | After `ANALYZE` p50 | Ratio | Plan changed |
|---|---:|---:|---:|---|
| Controlled FTS | 57.188 ms | 2.167 ms | 26.39x | Yes |
| Proposal queue | 10.973 ms | 0.952 ms | 11.53x | Not captured |
| Personal history page | 1.182 ms | 1.089 ms | 1.09x | Yes |
| Structural tool events | 24.111 ms | 21.861 ms | 1.10x | Yes |

Before statistics refresh, the controlled-FTS plan drove from 104
`trajectories` rows and repeatedly scanned `derived_artifacts`. After
`ANALYZE`, it drove from the 122 artifact rows and used primary-key lookups
into authorized trajectories. The p95 ratio was 23.64x.

## Architecture consequence

This is evidence for an ingestion-readiness gate, not for a new database:

1. bulk trace and derived-artifact ingestion must refresh or otherwise ensure
   sufficiently current planner statistics before latency certification;
2. readiness should assert cardinality estimates and a bounded plan signature
   for the small number of product-critical queries;
3. benchmark reports must distinguish pre-statistics and post-statistics
   phases; and
4. Aurora testing must repeat the same bulk-load/statistics/failover sequence
   instead of assuming a steady-state plan.

The result also weakens any argument that the 57 ms observation justifies
adding a search sidecar: a standard PostgreSQL maintenance operation recovered
the expected plan and approximately 2 ms median controlled-FTS latency.

## Claim boundary

This is one paired observation on local, single-node PostgreSQL. It does not
establish Aurora latency, autovacuum timing, replica planning, failover,
concurrency, storage scaling, or production workload behavior. It does prove
that planner-statistics state is a load-bearing experimental variable for the
Frankengate trace workload and must be frozen or reported.

Machine-readable result:
[`wisp-postgres-planner-statistics-2026-07-30.json`](../results/wisp-postgres-planner-statistics-2026-07-30.json).
