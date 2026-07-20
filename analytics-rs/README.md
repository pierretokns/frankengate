# FrankenGate analytics control plane

This is an isolated Rust control plane for the analytics plane. The in-memory
`JobStore` remains the protocol reference, while the SQLx/PostgreSQL boundary
in `src/database.rs` provides the first durable projections and worker queue
operations. It is deliberately separate from Go inference workers.

## Adoption gates

Potential FrankenSuite/Dicklesworthstone/Doodlestein components are not runtime
dependencies yet. Each candidate must provide:

1. a pinned upstream release and compatible license/NOTICE entry;
2. a measured improvement over the current slice (latency, recovery, memory,
   or owned lifecycle code);
3. deterministic duplicate-delivery, cancellation, shutdown, and worker-death
   tests; and
4. an explicit stop decision if the candidate does not close a named gap.

The production direction is a separately deployed Rust control plane with
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

The protocol tests are complemented by durable SQLx methods for experiments,
runs, evaluations, artifact manifests, replay lineage, job submission/leasing,
renewal, checkpoints, completion/failure, cancellation, worker draining, and
bounded listings/statistics. An HTTP API and gateway event adapter remain
separate implementation gates.

PostgreSQL transactions set `app.tenant_id` with `set_config(..., true)` before
queries. The migration uses forced row-level security, so missing tenant
context fails closed. Set `DATABASE_URL` for the service deployment; the
Helm chart can inject it from `analyticsControlPlane.databaseUrl.existingSecret`.
Set `ANALYTICS_WORKER_TOKEN` to require `Bearer` authentication for governed
worker endpoints; the Helm chart injects it from
`analyticsControlPlane.workerTokenSecret`. An unset token intentionally leaves
local contract mode open, but production deployments should configure it.

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
traffic, then exposes `/healthz`, `/readyz`, and `/version` (the protocol
version). When `DATABASE_URL` is set, `/readyz` fails closed until the
PostgreSQL endpoint is reachable; without it, dependency-free local contract
mode remains available.

The control-plane contract also has a standalone image build, which is kept
separate from the Go gateway image:

```bash
docker build -f analytics-rs/Dockerfile -t frankengate-analytics-control:dev analytics-rs
```
