# Analytics control-plane status

## Verified in this beta track

- Replay reads the gateway OTEL plugin's tenant-partitioned JSONL sink when
  `FRANKENGATE_REPLAY_DIR` is configured.
- Job submission, listing, leasing, renewal, checkpoints, completion,
  cancellation, failed-job retry, tenant statistics, and Prometheus metrics
  are exposed by the standalone Rust process.
- PostgreSQL migration contracts cover experiments, runs, evaluations,
  artifacts, jobs, replay lineage, RLS, and `NOTIFY` worker wake-ups.
- The Rust test suite and dependency-free operator smoke check pass locally.

## Explicit remaining gates

- The current process uses the in-memory `JobStore`; `GET /persistence` and
  `GET /contract` report `postgres_runtime: false` deliberately. The
  parameterized SQL boundary and migration are ready for a client/runtime
  implementation, but no PostgreSQL driver is bundled in this dependency-free
  beta yet.
- OTLP collectors remain export-only in the gateway. Replay uses the concrete
  JSONL sink because it is the only existing read-capable OTEL destination;
  enabling OTLP replay requires a deployment-specific query adapter.
- The latest beta workflow run is externally stalled during setup/build and
  has not produced a terminal publication result. This is a CI state, not a
  local Rust test failure.

Do not interpret readiness as durable persistence until the persistence mode
reports a PostgreSQL runtime and a deployment-level migration/connectivity
check has passed.
