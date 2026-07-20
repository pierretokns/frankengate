# Analytics control-plane contract v1

Status: contract proposal (2026-07-20)

The analytics plane is asynchronous and separately deployable. The Go gateway
may emit an accepted job envelope, but never executes analytics work in an
inference worker.

## Identity and lineage

Every experiment, run, attempt, evaluation result, and artifact manifest has
`tenant_id`, `actor_id`, `policy_epoch`, and an immutable revision tuple:
`dataset_revision`, `evaluator_revision`, `model_revision`,
`prompt_revision`, and `code_revision` where applicable. Run intent is
immutable; retries create `run_attempt` rows and cannot overwrite the intent.

Large bytes live in an encrypted, content-addressed object store. PostgreSQL
stores only the manifest, digest, media type, size, retention/deletion epoch,
and authorization metadata.

## Leased job protocol

`POST /v1/jobs` is idempotent on `(tenant_id, idempotency_key)` and returns a
queued job. Workers claim with a lease and heartbeat. `POST /v1/jobs/{id}/cancel`
is owner/policy checked and terminally records cancellation. Lease expiry
returns a non-terminal job to the queue; duplicate delivery is safe because
completion requires the current lease owner and attempt. Shutdown drains leases
without silently dropping checkpoints. All terminal transitions emit one
outcome receipt with a stable protocol version and error category.

## Query boundaries

List and compare endpoints require bounded pagination and an authorization
snapshot. Results are filtered by tenant, principal/team scope, policy epoch,
deletion epoch, and purpose before serialization. An MLflow import/export
adapter is compatibility-only and must report every lossy or unsupported field;
MLflow is not a second authority.

## Readiness and scaling

The control API is not ready until migrations and the PostgreSQL connectivity
fence pass. API, replay/evaluation workers, embedding/index workers, report
workers, and sandbox workers are separate Deployments with separate service
accounts, queues, database pools, and resource budgets. HPA signals are
component-specific; no analytics queue may consume reserved gateway capacity.

## Promotion gates

The contract is not production-ready until SQLx/PostgreSQL integration tests
cover outage, duplicate delivery, lease expiry, worker death, cancellation,
RLS isolation, and N/N+1 compatibility. Generated Go/Rust/TypeScript fixtures,
SBOM/license evidence, and a combined-load test are required before enabling
the control plane by default.
