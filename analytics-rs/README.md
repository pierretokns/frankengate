# FrankenGate analytics control plane

This is the first isolated Rust vertical slice for the analytics plane. It is
deliberately dependency-free: the `JobStore` proves the lifecycle invariants
before an HTTP server, PostgreSQL persistence, or worker runtime is selected.

## Adoption gates

Potential FrankenSuite/Dicklesworthstone/Doodlestein components are not runtime
dependencies yet. Each candidate must provide:

1. a pinned upstream release and compatible license/NOTICE entry;
2. a measured improvement over the current slice (latency, recovery, memory,
   or owned lifecycle code);
3. deterministic duplicate-delivery, cancellation, shutdown, and worker-death
   tests; and
4. an explicit stop decision if the candidate does not close a named gap.

The production direction remains a separately deployed Rust control plane with
PostgreSQL as the authoritative contract store. It must never execute analytics
jobs inside gateway inference workers.

The current in-memory contract already covers:

- monotonic delivery attempts across lease expiry and explicit retry;
- optional hard queue capacity with typed admission rejection;
- atomic tenant-scoped claiming, bounded listings, and queue statistics;
- owner-only heartbeats, checkpoints, completion, and failure transitions;
- graceful worker draining and duplicate-delivery idempotency; and
- tenant-scoped cancellation/retry plus reproducible experiment lineage; and
- terminal, same-tenant replay jobs with explicit `replay_of` lineage.

Replay ingestion now has an explicit normalized boundary for the gateway's
observability output. `ReplayTrace` carries the stable trace/request IDs,
tenant, model/provider, and bounded input/output payloads; `ReplaySource`
requires an explicitly configured OTLP HTTP or log-store HTTP endpoint. This
keeps source-specific OTEL schemas and credentials outside the Rust job
protocol. A deployment must select the adapter matching its configured OTLP
collector or log destination before enabling live replay; the current process
does not guess a collector endpoint or pretend that an arbitrary exporter is
queryable.

These are protocol and test guarantees, not a claim of durable persistence or
production API availability. The PostgreSQL service, supervision runtime, and
independent Helm deployments remain separate implementation gates.

`migrations/001_analytics_contract.sql` is the first durable schema contract.
It enables tenant RLS across experiments, runs, run attempts, evaluations,
artifacts, and jobs, and stores only artifact manifests in PostgreSQL; artifact
bytes remain in the configured object store. Run-attempt policies also verify
that referenced runs and worker jobs belong to the same tenant. The migration is safe to rerun
during rolling upgrades, including upgrades of an existing `jobs` table to add
replay lineage.

Run the current contract tests with:

```bash
cargo test --manifest-path analytics-rs/Cargo.toml
```

The dependency-free operator smoke check exercises submit → lease → complete
and verifies the typed terminal outcome:

```bash
cargo run --manifest-path analytics-rs/Cargo.toml -- --check
```

For a minimal independently deployable process, run `--serve` (default port
8081). It runs the contract self-check as a boot fence before accepting
traffic, then exposes `/healthz`, `/readyz`, `/version` (the protocol
version), `/stats?tenant=<tenant>` and `/jobs?tenant=<tenant>` as bounded,
tenant-scoped JSON inspection APIs, and `/metrics`. The metrics endpoint emits Prometheus gauges named
`frankengate_analytics_jobs` with `state` labels for `queued`, `leased`,
`cancelled`, `completed`, and `failed`; the optional Helm `ServiceMonitor`
scrapes this endpoint. This is still only a process/readiness contract: the production
queue/database service remains a subsequent implementation gate.

The control-plane contract also has a standalone image build, which is kept
separate from the Go gateway image:

```bash
docker build -f analytics-rs/Dockerfile -t frankengate-analytics-control:dev analytics-rs
```
