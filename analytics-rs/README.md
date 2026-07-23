# FrankenGate analytics control plane

This is the first isolated Rust vertical slice for the analytics plane. It
keeps the `JobStore` protocol and its durable PostgreSQL boundary separate from
the Go gateway hot path. SQLx is used only by the independently deployed
control-plane process.

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

These are protocol and test guarantees. The SQLx migration and tenant-scoped
database operations now provide the first durable persistence gate; the HTTP
job API, supervision runtime, and independent Helm deployments remain separate
implementation gates.

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

The operator smoke check exercises submit → lease → complete
and verifies the typed terminal outcome:

```bash
cargo run --manifest-path analytics-rs/Cargo.toml -- --check
```

For a minimal independently deployable process, run `--serve` (default port
8081). It runs the contract self-check as a boot fence before accepting
traffic, then exposes `/healthz`, `/readyz`, `/version` (the protocol
version), and `/metrics`. The metrics endpoint emits Prometheus gauges named
`frankengate_analytics_jobs` with `state` labels for `queued`, `leased`,
`cancelled`, `completed`, and `failed`; the optional Helm `ServiceMonitor`
scrapes this endpoint. This is still only a process/readiness contract: the production
queue/database service remains a subsequent implementation gate.

The control-plane contract also has a standalone image build, which is kept
separate from the Go gateway image:

```bash
docker build -f analytics-rs/Dockerfile -t frankengate-analytics-control:dev analytics-rs
```

The current HTTP surface is an internal worker/control-plane contract, not a
public unauthenticated API. Put it behind cluster network policy and an
identity-aware service boundary before exposing it outside the namespace; the
tenant and worker query parameters are partitioning inputs, not credentials.
