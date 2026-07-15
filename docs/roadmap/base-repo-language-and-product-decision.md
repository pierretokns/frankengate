# Base Repository, Language, and Product Decision

**Status:** proposed experiment; no irreversible fork or rewrite decision yet
**Recommendation:** distinct downstream compatibility distribution, Bifrost/Go data
plane initially, fork-owned enterprise contracts, and replaceable engines behind a
conformance envelope

## Decision in one sentence

Start with Bifrost because its valuable substrate is provider, streaming, MCP, plugin,
SDK, deployment, and test compatibility—not because Go is sacred—then make that engine
replaceable only after its observable behavior has been frozen and a candidate proves a
material, scoped advantage.

## Identity test

Removing Go would change the implementation. Removing the provider/API compatibility,
streaming semantics, plugin ordering, failover behavior, and operational surface would
change what the product is. Those semantics are the initial core substrate.

Bifrost is therefore the right bootstrap engine, but the project being defined is
larger than a feature fork. It is a managed AI control, evidence, evaluation, learning,
and knowledge-governance system whose online gateway is one execution engine.

## Options

| Start | Main advantage | Dominant risk | Verdict now |
|---|---|---|---|
| Permanent Bifrost hard fork | fastest feature delivery | upstream/module/release merge debt becomes architecture | do not commit yet |
| Downstream compatibility distribution | preserves mature engine and an exit path | seams may prove too porous | run this experiment |
| Plugin/sidecar without fork | minimal upstream burden | cannot enforce deep quota, replay, stream, and policy invariants | insufficient |
| Archived Rust gateway | possible reusable code | unidentified, stale, incomplete, unknown license/tests | reject until identified and audited |
| Clean-room Rust gateway | maximum design freedom | second-system trap and years of protocol-tail work | reject now |
| Hybrid with two authoritative gateways | language flexibility | split policy, quota, keys, audit, and incident truth | prohibited |
| Go authority plus bounded Rust workers | preserves correctness and enables specialization | RPC/operations overhead | allowed when measured |

## Why not rewrite now

The current repository has hundreds of Go tests and mature implementations across 20+
providers, native and OpenAI-compatible APIs, streaming, MCP, integration adapters,
plugins, UI, Helm, Terraform, and releases. The hard gateway work is long-tail protocol
semantics and continual provider change, not raw HTTP dispatch.

Rust would not inherently solve distributed quota algebra, key revocation, Okta group
semantics, replay privacy, policy monotonicity, or knowledge promotion. A line-for-line
port would also discard useful Go runtime choices such as immutable atomic snapshots,
provider queues, pools, and carefully documented streaming lifecycle behavior.

## Architecture

Use selective hexagonal architecture. Deep interfaces belong at seams with real
alternatives or future engine replacement:

- `IdentityDirectory`: Okta/SCIM and future directories.
- `PolicySource`, `PolicyCompiler`, `PolicySnapshotPublisher`: durable policy to an
  immutable online decision snapshot.
- `QuotaReservationLedger`: PostgreSQL launch implementation and optional future
  authority.
- `AuditSink`, `TraceStore`, `ReplayStore`: buffered evidence exports.
- `EvaluationBackend`, `TrainingBackend`, `ModelRegistry`: MLflow, Phoenix, NVIDIA,
  Prime, Hugging Face, and other adapters.
- `GatewayEngine`: the narrow compatibility envelope that Bifrost satisfies first and a
  future engine may satisfy later.

Do not wrap every package in generic ports. The Go data plane should consume concrete,
versioned compiled snapshots and use atomic swaps. One adapter is a hypothetical seam;
build an interface when two real adapters or an engine-exit requirement justify it.

## Rust adoption rule

Rust runs out of process, never through request-path FFI, and only for a bounded workload
such as bulk trace redaction/compression, local learned-router inference/tokenization,
ANN search, replay/evaluation, or training workers. Calls are batched, deadline-bound,
cancel-propagating, and degrade to a safe Go path.

Asupersync is considered only for a native Rust component that benefits from structured
cancellation, capability narrowing, supervision, and deterministic concurrency tests.
It is not an executor swap or a reason to create a Rust component.

A candidate must:

1. Match 100% of the scoped conformance contract, including errors, cancellation,
   streaming, retries, and policy behavior.
2. Improve a measured binding constraint materially; an initial bakeoff threshold is at
   least 20% better p99, CPU, or RSS on the declared workload.
3. Preserve safe degradation and operational simplicity after RPC, deployment, and
   observability costs.
4. Pass license, dependency, security, fuzz, fault, and release review.

## Compatibility and ecosystem contracts

- HTTP: OpenAI Responses/Chat/Embeddings and supported provider-native APIs, with exact
  stream, error, idempotency, retry, and cancellation behavior.
- Telemetry: OTLP/OpenInference with stable identity, route, policy, quota, retrieval,
  and evaluation attributes; content capture is explicitly governed.
- Evaluation: normalized internal results plus native artifacts. MLflow GenAI trace
  datasets and classic ML evaluation remain distinct adapters.
- Catalog: opaque external coordinates such as MLflow model alias, Bedrock inference
  profile, Hugging Face revision, or signed local artifact resolve to immutable route
  candidates.
- Jobs: provider-neutral evaluation/training records; arbitrary Python and GPU runtimes
  never execute in gateway pods.
- Policy: subject, model, tool, region, budget, and decision receipts do not depend on
  Bifrost handler structs.

## Five-stage start

### 0. Release archaeology

Reproduce builds and tests from a clean checkout; enumerate module tags, registries,
images, charts, source archives, secrets, signing, SBOM, NOTICE/attribution, and third-
party obligations. Current release paths and module names are Maxim-coupled, so a fork
release is not a workflow toggle.

### 1. Compatibility envelope

Create a black-box differential harness against a pinned upstream binary for unary and
streaming requests, tools, cancellation, errors, fallback, routing, and governance.
Record a coverage matrix and every intentional discrepancy. This is the future
`GatewayEngine` acceptance suite.

### 2. Enterprise vertical slice

Prove virtual-key create/use/revoke across three Kubernetes pods, PostgreSQL atomic
quota reservation/reconciliation, and Okta-group-derived model access. Measure the
1–5-second revocation SLO, controlled-overdraft bounds/alerts, p95 overhead, and network
partition behavior before building broad UI.

### 3. Portable evidence loop

Export OTLP/OpenInference to both MLflow and Phoenix, curate a trace-backed evaluation
dataset, run offline evaluation, and resolve an external model alias to a route. The
gateway must not execute arbitrary MLflow Python models or recursively evaluate its own
latency pool.

### 4. Merge and release drill

Merge the newest upstream, count conflicts and changed upstream files, rerun conformance
and the three-pod suite, then build signed private prerelease binary/image/chart/source
artifacts with SBOM, licenses, install, upgrade, and rollback evidence.

Keep a downstream distribution if merge effort stays bounded and the enterprise slice
mostly lives behind fork-owned interfaces. If core edits remain broad or semantic merge
failures repeat, retain the public contracts and incrementally replace the engine. Never
perform a big-bang rewrite.

## Benchmarks required before a language claim

Use unary and streaming mocked-provider/loopback cases at concurrency 1/100/5000;
0/1/10 plugins; 0/10/100 policy rules; 1K/1M keys; varied chunk cadence; and PostgreSQL
quota contention. Capture queue delay, TTFT, p50/p99, throughput, allocs/bytes, goroutine
count, CPU, mutex/block profiles, race and pool-debug results. Provider latency and the
claimed microsecond gateway overhead must be shown separately.

## Agentic flywheel

The flywheel is a development process, not a Rust dependency: exhaustive research and
planning, self-contained beads, graph prioritization, fungible agents, coordination,
conformance, adversarial review, performance evidence, release rehearsal, and honest
negative ledgers. Use Rust-specific gauntlets only for Rust components.

Verified useful local capabilities include codebase archaeology, beads/br/bv, agent
fungibility, NTM where platform policy permits it, conformance/golden/metamorphic/fuzz
testing, performance profiling, Asupersync, RCH, UBS, DSR, and release preparation.
`SuperSink` was not found in the local skills or the relevant primary GitHub profile and
must be treated as an unverified name, not an architectural dependency.

## Product and name

Use a distinct internal codename now and clear GitHub, package registries, container
registries, domains, and trademarks before public release. Keep “Bifrost-compatible” as
factual compatibility prose only after the conformance suite supports it. Preserve the
Apache-2.0 license, applicable notices, modification notices, and attribution without
implying endorsement; citation alone is insufficient.

`Frankengate` is memorable but generic and potentially crowded; `FrankenGateway` is
descriptive but long. A Ghostbusters-inspired public name adds trademark risk. A safer
working codename is **Containment Gate**: it fits routing, governance, and the containment
unit metaphor without claiming the Ghostbusters mark. Naming must not drive the engine
decision.
