# Extreme Reliability and Low Day-Two Operations

Status: architecture acceptance criteria
Date: 2026-07-14

## Reliability contract

The gateway is production infrastructure for interactive developer agents. A gateway
failure interrupts every active session and damages confidence beyond the duration of
the incident. Availability, predictable degradation, and repairability are product
features. No dashboard, evaluator, trainer, replay worker, identity sync, or control-
plane mutation path may be a synchronous dependency of inference.

## Ownership and graph integration

E17 is a cross-domain acceptance program, not a second implementation program. E5 owns
Kubernetes, cluster and snapshot-distribution implementation; E6 owns routing and
provider-circuit implementation; E10 owns build and artifact production. E17 defines
SLOs, shared failure semantics, invariant suites, chaos/performance evidence, operator
acceptance, and release gates over those implementations. The production/private
release rehearsal is incomplete until its relevant E17 runtime gates pass. Development-
tooling tasks `bif-cks.12-.13` improve the build process but are not runtime dependencies.

Initial numeric SLOs remain owner decisions, but every release must publish and test:

- availability and successful-stream-start SLOs;
- gateway-added time-to-first-token and p99 latency budgets;
- revocation and policy-reduction propagation, currently bounded at 1-5 seconds;
- recovery time and data-loss objectives for each state class;
- overload behavior, including the exact requests rejected before saturation;
- error-budget ownership and an automatic release freeze/rollback threshold.

## Failure-domain architecture

### Request path

The request path uses immutable, locally readable policy and routing snapshots. A pod
must not query Aurora, Okta, a peer, Redis, the dashboard, or an evaluator per token or
per request. Each outbound provider, region, tenant, and optional policy plugin has a
separate concurrency budget and failover handling so one dependency cannot consume the
gateway's entire connection, goroutine, memory, or retry budget.

Every request carries one end-to-end deadline. Retries and hedges spend that same
budget, are bounded, and are disabled when they would duplicate a non-idempotent tool
action. After response bytes have been exposed, failover never silently restarts a
generation as though it were the same response. Streaming disconnect, partial usage,
and billing reconciliation are explicit terminal states.

### Control-plane impairment

Aurora is the launch authority. Mutations commit with a transactional outbox row;
`LISTEN/NOTIFY` accelerates discovery and cursor polling repairs every missed signal.
Pods atomically install monotonic, checksummed snapshots. A transient database or
notification outage does not evict a known-good configuration.

Each resource class declares a freshness lease and stale behavior:

- security reductions, revocations, and deny rules fail closed after their short lease;
- stable provider/routing configuration may remain usable for a longer bounded window;
- control-plane writes may be unavailable during an Aurora regional failure;
- increases in privilege or spend never arise from stale or ambiguous state;
- freshness, revision, source, and expiry are observable without exposing secrets.

A brand-new pod with no verified snapshot remains unready during an Aurora outage. A
restarting pod may use a locally persisted encrypted snapshot only when its signature,
threat-model rules and resource freshness leases permit it; otherwise it also remains
unready. Snapshot rollback and revision downgrade are rejected.

Aurora verification must name writer/reader endpoints, pool and DNS failover behavior,
retryable transaction classes, outbox publisher leasing/fencing, notification reconnect,
durable cursor recovery, backup verification and PITR. Regional failure freezes control-
plane writes at launch. Measured recovery/data-loss objectives, rather than a successful
SDK reconnect alone, are the oracle.

This design has no mandatory Redis, gossip, shared filesystem, or peer availability.
Those may be replaceable adapters only after evidence shows a material benefit.

## Kubernetes launch requirements

- At least three replicas across availability zones where capacity permits, plus
  capacity-based N+1 and zone-loss math. A disruption budget constrains voluntary
  disruption only; it does not protect node/zone loss or prove displaced long-stream
  capacity. Topology, readiness, surge and a tested maintenance procedure complete it.
- Rolling updates use surge capacity, no planned unavailable pod, readiness gates, and
  endpoint removal before graceful connection drain. Termination must bound new
  admission, finish or explicitly terminate streams, and flush only bounded telemetry.
- Startup, readiness, and liveness have different meanings. Liveness cannot depend on
  Aurora/provider reachability and must not turn a dependency outage into a restart
  storm. Readiness proves the pod has a valid snapshot and local serving capacity.
- HPA signals include admitted concurrency, queue delay, CPU, memory headroom, and
  stream duration. Provider throttling must not trigger unlimited gateway scaling.
- HPA tests cover floors/ceilings, stabilization windows, long-stream scale-down,
  cold-start/readiness delay, provider-throttle suppression, and simultaneous rollout.
- Resource requests, hard memory limits, bounded queues/caches, and graceful overload
  are validated with the actual request-size and stream-duration distributions.
- Node drain, zone loss, DNS failure, certificate rotation, API-server partition, and
  simultaneous rollout plus HPA behavior are exercised before release.

## Overload and dependency failure

Admission control happens before expensive parsing or provider connection creation.
Queues are bounded and fair by tenant; overload returns an actionable retry response
instead of accumulating unbounded memory. Controlled spend overdraft requires an
approved or preconfigured policy and emits user/operator alerts plus an audit receipt.

failover handlings use slow-call and failure signals, half-open probes, jitter, and
provider-specific classification. Retry storms are prevented through shared budgets,
backoff, load shedding, and bulkheads. Route selection accounts for capacity and
health but cannot flap based on a tiny sample. All emergency behavior has a safe,
audited expiry rather than a permanent hidden toggle.

The failover taxonomy distinguishes transport failure before first byte, provider
capacity/429, semantic/provider rejection, partial stream, tool side effect, and
batch/file mutation. Each class declares retry/hedge legality, idempotency key behavior,
quota/usage reconciliation, and destination-region evidence. Bedrock runtime, inference
profile, provisioned-capacity and cross-region routes are not treated as interchangeable.

## Safe evolution and rollback

- Database and snapshot schemas use expand/contract migrations. Adjacent versions must
  coexist during rolling deployment and downgrade behavior is specified.
- Heavy PostgreSQL indexes, table rewrites, validation, and backfills never block pod
  boot. They use concurrent/background, resumable, observable workflows.
- Configuration is parsed and validated before publication; a bad revision is rejected
  without replacing the last-known-good snapshot.
- Releases progress through replay, shadow, sticky canary, and automated rollback.
  Rollback criteria cover correctness, latency tails, memory, provider errors, and
  policy divergence, not merely HTTP 5xx.
- Build artifacts are reproducible, signed, include an SBOM and provenance, and retain
  enough prior versions for immediate rollback.
- Every release evidence manifest binds artifact digests, schema compatibility range,
  scenario IDs/seeds, performance comparison, unresolved flakes, rollback target,
  license/SBOM/signature verification and retention expiry. Periodic drills retrieve the
  old artifact and rotate certificates, JWKS, provider credentials and signing keys.

## Verification program

Testing is evidence-producing and scenario-specific:

1. Conformance freezes observable Bifrost/provider behavior and streaming edge cases.
2. Mock-free provider and Aurora integration tests exercise real protocol semantics.
3. Deterministic concurrency tests, race detection, lock-order audits, and stress at
   ten times the reproducing load guard shared state.
4. Fuzzing covers parsers, streaming frames, provider adapters, policy documents,
   snapshot decoding, and malformed tool/MCP traffic.
5. Metamorphic tests assert invariants across equivalent request encodings, retry and
   replay transformations, pod counts, event duplication/reordering, and route sets.
6. Fault injection covers notification loss, stale snapshots, slow/dead providers,
   partial streams, Aurora failover, DNS/TLS faults, pod/node/zone loss, disk pressure,
   clock skew, and telemetry backpressure.
7. Soak tests detect goroutine, connection, file-descriptor, heap, cache-cardinality,
   and credential-refresh leaks over realistic long streams.
8. Performance work begins with reproducible workload fingerprints and p50/p95/p99/
   p99.9 baselines. Optimizations require a ranked profile, not intuition.

Artifacts, seeds, environment fingerprints, and failure timelines are retained so a
release result can be reproduced. Flaky tests are defects with owners, not retry loops.

## Day-two operator surface

The gateway exposes a read-only `doctor`/diagnostic bundle that explains snapshot age,
revision convergence, provider health, circuit state, capacity, migration state,
certificate/key expiry, and recent configuration rejection without printing secrets.
Its checks are deterministic, machine-readable, time-bounded, independently runnable,
and safe during an incident.

Runbooks cover overload, provider outage, Aurora impairment, stale/revoked policy,
certificate rotation, stuck rollout, bad migration, and rollback. Alerts are symptom-
and-SLO based, deduplicated, routed to a named owner, and paired with the relevant
dashboard and runbook. Telemetry cardinality and retention are budgeted. Operators can
answer which tenants are affected without inspecting raw prompts.

Alert acceptance includes synthetic firing, delivery, acknowledgement/escalation,
runbook execution, affected-tenant correlation, cardinality budgets, and stale/missing
telemetry detection. Every emergency mutation records owner, reason, scope, TTL,
precondition and audit receipt, automatically reverts, and requires two people when it
widens security or spend. `doctor` remains read-only; remediation is separate and
authenticated.

## Tooling safety for the development flywheel

Agentic Flywheel tooling should run inside Codex's workspace sandbox with interactive
approval for escapes and state-changing orchestration. Narrow command-prefix rules may
allow specific read-only discovery, status, verification, and test commands. Blanket
allow rules for `ntm`, `jsm`, shells, language runtimes, cloud CLIs, Kubernetes, Docker,
or Git are prohibited because any of them can transitively execute arbitrary actions.

DCG adds command-pattern defense and should enable project-relevant Git, filesystem,
database, Kubernetes, container, cloud, infrastructure, and secret packs after their
rules are tested against this workflow. It is not the only safety boundary: its own
documented timeout/budget behavior is fail-open. Codex sandboxing, approval policy,
narrow rules, cloud/Kubernetes RBAC, short-lived credentials, branch protection, and
two-person release controls remain independent layers.

## Release gate

A release is blocked by an unexplained conformance difference, reliability regression,
unbounded resource path, unsafe boot migration, missing rollback, unresolved critical
security finding, or failed failure-injection scenario. Passing unit tests alone is not
permission to ship infrastructure on which every developer session depends.
