# Eval and run control-plane architecture

Status: proposed architecture and Beads coverage review, 2026-07-18.

## Decision

Keep the Go gateway as the latency-critical inference data plane. Build new experiment, run, evaluation, report, and learning orchestration as a separately deployable Rust control plane with separately scalable worker classes. Keep the React dashboard in this repository, but make its deployment independent from the gateway and expose one browser origin through an ingress/BFF contract.

Do not add MLflow as a second source of truth. Implement the small canonical tracking contract FrankenGate needs in PostgreSQL and provide MLflow import/export or API compatibility only where it has measured user value. Large artifacts belong in an object store behind signed, short-lived access; PostgreSQL stores metadata, lineage, policy, state, and immutable manifests.

This is a staged extraction, not a rewrite:

1. Define versioned HTTP/event contracts and canonical PostgreSQL records while the existing Go binary can still serve the UI.
2. Deploy the static dashboard independently behind the same origin.
3. Add the Rust analytics control API and Rust worker supervisor.
4. Route `/api/analytics/*` to that service while existing administrative APIs remain in Go.
5. Split repositories only after ownership and release cadence prove the need.

## Why the current Beads are not yet sufficient

The roadmap already covers trace envelopes, replay jobs, evaluator revisions, learning datasets, training jobs, model artifacts, promotion, isolated workers, and operator dashboard quality. Those are strong primitives. The missing layer is an explicit product and execution model joining them:

- Experiment as the durable namespace and policy boundary.
- Run as the immutable requested configuration plus mutable lifecycle projection.
- RunAttempt for retries, leases, checkpoints, cancellation, and terminal outcome.
- EvaluationResult and per-example Assessment tied to exact trace, dataset, evaluator, model, prompt, code, and policy revisions.
- ArtifactManifest with digest, media type, size, provenance, retention, encryption, and object-store locator.
- Searchable lineage and comparison read models for the dashboard.
- An asynchronous admission API and workload-class routing contract.

Without this layer, the existing Beads could produce capable subsystems that do not compose into an MLflow-level user experience.

## Service boundaries

### Go inference gateway

Owns synchronous inference admission, provider routing, streaming, inference authentication, governance enforcement, and minimal trace/event emission. It may enqueue work and return job identifiers, but it must not execute evaluations, reports, index builds, training, or artifact transforms. Its reserved CPU, memory, PostgreSQL connections, and disruption budget cannot be borrowed by analytics workloads.

### Rust analytics control API

Owns experiments, runs, evaluations, lineage queries, job admission/cancellation, report requests, and dashboard projections. It reauthorizes every request using the same tenant and policy authority as the gateway; identity propagation is not authorization. It uses bounded request budgets and returns asynchronous job handles for unbounded work.

The Rust implementation should use structured concurrency and supervision: scoped tasks, explicit cancellation, typed outcomes, bounded queues, restart policy, and deterministic runtime tests. Rust is appropriate because this is greenfield orchestration code. It does not justify replacing the working Go inference loop.

### Worker pools

Use one protocol and separate Deployments for materially different resource and failure profiles:

| Workload class | Primary pressure | Scaling signal | Isolation requirement |
|---|---|---|---|
| Replay and deterministic eval | CPU, provider calls | eligible queue age and depth, active leases | no inference capacity; bounded provider quotas |
| LLM judges | provider quota and cost | oldest eligible job, quota headroom, active calls | budget and rate-limit admission; CPU is not sufficient |
| Embedding and index builds | CPU/GPU, memory, I/O | pending vectors/bytes, completion ETA, device utilization | separate build from query serving |
| Reports and skill mining | CPU, PostgreSQL reads | queue age/depth and query time | read role, statement timeout, replica preference |
| Training and arbitrary scorers | GPU or unsafe code | pending resource-class jobs | sandboxed external Python containers; never in the Rust API pod |
| Artifact transfer | network and object-store I/O | active transfers and throughput | preferably signed direct upload/download |

Rust orchestrates these jobs; it does not replace the Python ecosystem needed by arbitrary ML evaluators and training frameworks. Those run as pinned, signed, sandboxed job images with restricted secrets and egress.

### Dashboard and edge

The dashboard should become a separate static Deployment or CDN artifact because the current Vite build is copied into and embedded by `bifrost-http`. The browser must still see one coherent application and one origin:

- `/v1/*` and provider-compatible routes -> Go gateway.
- Existing `/api/*` administration routes -> Go control handlers during migration.
- `/api/analytics/*` -> Rust analytics API.
- Static assets and SPA fallback -> dashboard service/CDN.

Do not make the browser discover or authenticate independently to every backend. The edge terminates the session, while each backend validates the signed identity context and performs its own scope/tenant authorization. Generate TypeScript, Go, and Rust clients from versioned OpenAPI or protobuf contracts; do not share implementation structs across languages.

## MLflow compatibility boundary

MLflow demonstrates the right user concepts: experiments, runs, versioned datasets and scorers, evaluation results, traces, comparisons, and artifacts. Its production architecture also separates relational metadata from large artifact storage. That is a feature reference and interoperability target, not a reason to deploy its Python tracking server as FrankenGate's authority.

Reasons not to make MLflow the authority by default:

- It would add another server, dependency and security surface while PostgreSQL is already authoritative.
- FrankenGate needs tenant-, purpose-, and evidence-level authorization integrated with gateway governance.
- MLflow's classic ML evaluator and GenAI scorer systems are currently distinct, so copying its internal schema would import a boundary we do not need.
- Arbitrary code scorers still require execution isolation regardless of which tracking UI stores their results.

Support an adapter after the canonical contract is stable: ingest/export experiments, runs, parameters, metrics, tags, traces, artifacts, and evaluator provenance with explicit loss reporting. Never silently flatten FrankenGate authorization or promotion evidence into weaker MLflow fields.

## PostgreSQL and artifact storage

Use PostgreSQL for control-plane metadata and read models, with tenant RLS, explicit service roles, statement timeouts, bounded pools, and workload tagging. Use an outbox for worker admission and projections. Do not put model weights, large evaluation tables, screenshots, or report bundles in PostgreSQL; store content-addressed objects externally and keep immutable manifests in PostgreSQL.

One PostgreSQL cluster can remain the operational default, but inference and analytics need independently capped roles/pools. Autoscaling must be constrained by the database connection budget. Add a read replica or separate analytics database only after query/load evidence shows that workload management, indexes, partitions, projections, and timeouts cannot protect inference.

## Autoscaling contract

Each Deployment gets an independent HPA or event-driven scaler. CPU/memory are safety signals, not universal demand signals.

- Gateway: in-flight inference, queue age, admission rejects, streaming concurrency, and latency; CPU as a guardrail.
- Analytics API: request concurrency, latency, and saturation; never queue depth from worker jobs.
- Workers: eligible queue depth and oldest-job age, partitioned by workload/resource class; processing-time estimates prevent huge and tiny jobs looking identical.
- LLM-judge workers: quota and spend headroom must cap scale-out.
- GPU workers: pending jobs by GPU type plus device utilization; scale-to-zero only when startup latency fits the job SLO.
- FrankenSearch query service: query concurrency/latency and memory; index builders scale separately.
- Dashboard: normally two small replicas or CDN delivery, not workload-driven compute scaling.

With Kubernetes `autoscaling/v2`, multiple metrics produce separate replica recommendations and HPA chooses the maximum. Configure scale-up policy, readiness/startup behavior, and downscale stabilization per class. Missing custom metrics must alert: they can prevent safe scale-down. Queue consumers also require leases, idempotency keys, heartbeats, cancellation, retry budgets, dead-letter disposition, and graceful drain; autoscaling alone does not provide correctness.

The acceptance test is a combined-load test: peak streaming inference while replay, judges, report mining, re-embedding, index rebuild, artifact transfer, and dashboard polling burst concurrently. It must prove inference SLOs, reserved database connections, bounded queue age, budget enforcement, cancellation, drain, and recovery.

## Repository and Helm decision

Keep a monorepo during the extraction. Add a Rust workspace with small crates for contracts, authorization client, experiment/run domain, PostgreSQL store, job protocol, orchestration, analytics API, worker runtime, artifact manifests, and adapters. Keep deployable binaries thin. The existing repository already contains the UI, Helm chart, API schemas, migrations, and integration tests needed for atomic contract changes.

Helm composes independently enabled Deployments, Services, ServiceAccounts, HPAs/scalers, network policies, disruption budgets, and PostgreSQL pool budgets. Minimal installs retain the Go gateway and embedded UI initially; production profiles can select the external dashboard and analytics plane.

Split repositories only when at least two of these become true: distinct ownership, independent public lifecycle, materially different disclosure/security boundary, or repeated evidence that atomic releases are harmful. A desire to use Rust is not a repository boundary.

## Rejected alternatives

- Put eval execution in gateway pods: violates latency, failure, dependency, and capacity isolation.
- Deploy stock MLflow as the primary authority: adds operational and authorization duplication.
- Rewrite the gateway in Rust: high migration risk without solving the control-plane boundary.
- Give every worker type a bespoke API and queue: creates unnecessary operational surface; use one versioned job protocol with resource-class routing.
- Split repositories immediately: multiplies CI, releases, dependency updates, and contract coordination before ownership is stable.
- Let the dashboard call every backend directly: fragments authentication, authorization, errors, versioning, and user experience.

## Required proof before implementation is called complete

1. Versioned domain/API schema and forward/backward compatibility tests across Go, Rust, and TypeScript.
2. Tenant, scope, revocation, IDOR, artifact-URL, and worker-capability tests.
3. Deterministic cancellation, retry, lease-loss, duplicate-delivery, and supervisor-restart tests.
4. Combined-load and PostgreSQL connection-budget tests.
5. Dashboard tests for experiments, run comparison, evaluation drill-down, artifacts, live status, cancel/retry, and honest partial failure.
6. MLflow round-trip fixtures with explicit unsupported/lossy-field reports.
