# FrankenGate analytics control plane

This is the first isolated Rust vertical slice for the analytics plane. It is
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
scrapes this endpoint. When `DATABASE_URL` is configured, a tenant-scoped
projection is available as `/metrics?tenant=<tenant-id>` and reads the durable
queue view. Requests without a tenant parameter retain the local process
metrics, avoiding an unsafe cross-tenant aggregate query.
Workers can claim one durable job with
`/v1/jobs/lease?tenant=<tenant-id>&worker=<worker-id>&lease_seconds=30`.
Claims use PostgreSQL row locking and are therefore safe across independently
scaled replicas; the endpoint returns `204` when the tenant queue is empty.
The owner completes a claim with
`POST /v1/jobs/complete?tenant=<tenant-id>&worker=<worker-id>&job_id=<id>`;
non-owners receive `409` and cannot mutate another worker's lease.
Long-running workers renew it with
`POST /v1/jobs/renew?tenant=<tenant-id>&worker=<worker-id>&job_id=<id>&lease_seconds=30`.
Terminal worker errors are recorded with
`POST /v1/jobs/fail?tenant=<tenant-id>&worker=<worker-id>&job_id=<id>&error_code=<bounded-code>`.
Terminal jobs can be replayed with explicit lineage using
`POST /v1/jobs/replay?tenant=<tenant-id>&replay_id=<new-id>&source_job_id=<old-id>&kind=<kind>`.
Operators can cancel queued/leased work with
`POST /v1/jobs/cancel?tenant=<tenant-id>&job_id=<id>` and explicitly retry a
failed job with `POST /v1/jobs/retry?tenant=<tenant-id>&job_id=<id>`.
Workers persist bounded resumable state with
`POST /v1/jobs/checkpoint?tenant=<tenant-id>&worker=<worker-id>&job_id=<id>&checkpoint=<state>`;
the database rejects checkpoints over 64 KiB or writes by non-owners.
Kubernetes termination can release all leases for a worker with
`POST /v1/workers/drain?tenant=<tenant-id>&worker=<worker-id>` so replacement
replicas can claim them immediately.
Automation can create immutable experiment lineage with
`POST /v1/experiments?tenant=<tenant-id>&id=<id>&actor=<actor>&revision=<revision>`;
duplicate IDs are rejected idempotently.
Reproducible runs are created with
`POST /v1/runs?tenant=<tenant-id>&id=<id>&experiment_id=<experiment-id>&dataset_revision=<r>&evaluator_revision=<r>&model_revision=<r>&prompt_revision=<r>`.
Evaluation results are recorded with
`POST /v1/evaluations?tenant=<tenant-id>&run_id=<id>&example_id=<id>&evaluator_revision=<r>&score=<json>`;
the `(run, example, evaluator revision)` key is idempotent.
Artifact lineage is recorded without copying artifact bytes into Postgres via
`POST /v1/artifacts?tenant=<tenant-id>&run_id=<id>&digest=<digest>&media_type=<type>&object_uri=s3://...`.
Runs are terminalized once with
`POST /v1/runs/finish?tenant=<tenant-id>&run_id=<id>&outcome=<json-or-status>`;
subsequent terminalization attempts are rejected.

The control-plane contract also has a standalone image build, which is kept
separate from the Go gateway image:

```bash
docker build -f analytics-rs/Dockerfile -t frankengate-analytics-control:dev analytics-rs
```
