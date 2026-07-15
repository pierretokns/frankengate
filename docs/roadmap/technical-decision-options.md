# Technical Decision Options

Status: owner constraints recorded; mechanisms still require evidence
Date: 2026-07-14

## Owner constraints recorded 2026-07-14

- Revocation and policy-reduction propagation SLO: **1-5 seconds is acceptable**.
- Spend limits: **controlled overdraft is acceptable**, but only through either an
  explicit approval or a preconfigured user/team policy. Every overdraft requires
  significant user/operator alerting and an audit trail.
- Aurora regional control-plane write availability is **not a launch requirement**.
  Regional failure may temporarily make control-plane mutations unavailable while the
  data plane operates from bounded-fresh last-known-good state.
- Redis is **not acceptable as a mandatory dependency**.
- Launch deployment is **Kubernetes only**.
- Launch scope is **internal systems and internal research**, not a multi-customer
  public SaaS offering.
- Bedrock routing may use **U.S. geographic inference profiles**. Global profiles are
  not required at launch.
- A shared filesystem is **not a launch requirement**.

These constraints favor a PostgreSQL-native launch architecture and remove several
premature portability/multi-region requirements. Interfaces should remain replaceable,
but the first implementation should optimize for the actual internal Kubernetes/Aurora
environment rather than hypothetical deployment modes.

## How to use this document

Each section separates the correctness requirement from the transport or storage
mechanism. Choose per domain. A system that is excellent for membership can be unsafe
for revocation or monetary counters. Every decision must include failure behavior,
an operating-cost estimate, a benchmark, a migration path, and a way to replace the
mechanism without rewriting the inference hot path.

The current Bifrost code already favors immutable snapshots swapped through
`atomic.Pointer`, PostgreSQL-backed configuration, durable database-claimed background
jobs (`framework/sidekiq`), and in-process stores. New distribution mechanisms should
feed versioned snapshots into those seams rather than introduce distributed reads on
every request.

## Decision 1: cross-pod configuration and revocation propagation

### Requirements

- Database mutation and publication cannot disagree.
- Every ready pod observes monotonic resource revisions.
- Key revocation and policy reduction meet a bounded propagation SLO.
- Duplicate, missing, delayed, and reordered signals are recoverable.
- A pod can prove cache freshness or fail closed after the safe-staleness window.
- Large snapshots do not travel through a notification channel.
- Inference performs lock-free local reads after an atomic snapshot swap.

### Option A: Aurora PostgreSQL transactional outbox plus polling

Write the resource mutation and a compact outbox row in the same transaction. Each pod
polls by monotonically increasing outbox sequence, fetches authoritative rows/snapshots,
applies them, and persists its cursor/heartbeat. Old events are retained until every
live consumer or a retention horizon has passed.

Advantages:

- Strongest fit with Aurora PostgreSQL already required by the program.
- Mutation and event are atomic; no dual-write gap.
- Durable catch-up after pod restarts or long partitions.
- Easy to inspect, replay, audit, and test.
- Avoids another required production service.

Costs and risks:

- Polling adds database reads and a latency floor.
- Poor queries or too many consumers can amplify Aurora I/O.
- Needs compaction, cursor leases, tombstones, and cleanup.
- Hot global counters do not belong in the outbox.

Good default for: configuration, key lifecycle, entitlements, route policy, audit
work dispatch, and capability revisions.

### Option B: transactional outbox plus PostgreSQL `LISTEN/NOTIFY` wakeups

Keep Option A's durable outbox as authority. After commit, notify a channel with only
tenant/resource/revision or simply a wakeup. Consumers immediately drain the outbox;
periodic polling remains the repair path.

Advantages:

- Low normal-case propagation latency without giving up durable recovery.
- Simple payload and no need to fit configuration in notification limits.
- Natural extension of PostgreSQL/Aurora operations.

Costs and risks:

- `NOTIFY` is ephemeral, connection-bound, and not a queue; reconnect gaps are normal.
- Aurora failover and pool/proxy behavior must be tested rather than assumed.
- Long transactions delay notification delivery.
- Dedicated listener connections and reconnect/resubscribe logic are required.

Selected launch candidate: preferred starting architecture for low/medium-rate control-
plane changes, provided an Aurora failover experiment proves the listener recovers and
the polling repair loop meets the revocation SLO during notification loss.

### Option C: PostgreSQL logical replication / CDC

Consume WAL changes through logical decoding or a managed CDC pipeline, project them
to resource events, and apply versioned snapshots.

Advantages:

- Durable ordered database change stream at high change volume.
- Captures changes made by more than one application path.

Costs and risks:

- Considerably more operational machinery, replication-slot lifecycle, schema coupling,
  failover behavior, and backpressure management.
- Raw row changes are not always the correct domain event.
- Aurora version/parameter/slot constraints must be managed.

Use when: outbox throughput or number of independent consumers demonstrably exceeds
the simpler design. Do not start here.

### Option D: Redis Streams plus database outbox relay

Commit database mutation and outbox row, relay to Redis Streams, and let pods consume
with resumable IDs. PostgreSQL remains authoritative.

Advantages:

- Low latency, consumer replay, backpressure, and natural reuse if Redis is already
  required for atomic quotas.
- Separates event fanout load from Aurora.

Costs and risks:

- Adds relay lag and a second durability/operations surface.
- Requires idempotency because the relay is at-least-once.
- Multi-region Redis topology and failover are nontrivial.

Not selected for launch because Redis cannot be mandatory. Retain as an optional future
adapter only if measured Aurora fanout cost/latency justifies it. Prefer streams over
ephemeral Redis Pub/Sub for security events.

### Option E: memberlist gossip plus gRPC state synchronization

Use gossip for node membership and compact versions/health; use authenticated gRPC to
fetch deltas or snapshots from peers/leaders.

Advantages:

- Fast decentralized membership and health propagation.
- Can operate while the database notification path is unavailable.
- Matches Bifrost Enterprise's documented cluster shape.

Costs and risks:

- Eventual convergence, conflict/version design, peer authentication, port/network
  complexity, cross-region chatter, and difficult partition behavior.
- Unsafe as sole authority for revocation or hard monetary limits.
- Duplicates capabilities already provided by Kubernetes/Aurora for many deployments.

Not selected for Kubernetes launch. Kubernetes already supplies membership; gossip may
remain a later portability adapter. It is a poor sole authority for revocation, policy,
or budgets.

### Option F: shared config file on FSx/EFS

A writer publishes versioned immutable snapshots with checksums and atomically changes
a manifest/pointer. Pods watch or poll the shared mount and atomically load verified
snapshots.

Advantages:

- Operationally legible snapshots and simple air-gapped/static deployment mode.
- Efficient for large read-mostly configuration bundles.

Costs and risks:

- Filesystem notification semantics on network mounts are unreliable/implementation-
  specific; polling is still necessary.
- Writer election, partial writes, cache coherence, mount outage and rollback matter.
- Poor fit for high-rate revocation, identity changes, quotas, or multi-region writes.
- A compromised writer changes every pod.

Not selected for launch. Possible future use is import/export, disaster bootstrap,
offline bundles, or an explicit read-only mode—not the primary live control plane.

### Proposed hybrid to benchmark

1. Aurora PostgreSQL is durable authority.
2. Every mutation writes a domain outbox row in the same transaction.
3. `LISTEN/NOTIFY` is only a low-latency wakeup; periodic cursor polling repairs gaps.
4. Pods fetch authoritative deltas/snapshots and atomically swap local immutable state.
5. Freshness leases and revision watermarks govern fail-closed behavior.
6. PostgreSQL supplies launch quota/rate reservations through atomic SQL, advisory or
   row locks where needed, and a durable reservation ledger. The implementation must
   shard hot rows and benchmark contention before acceptance.
7. Kubernetes EndpointSlice/watch supplies launch membership.
8. Redis, memberlist and versioned file snapshots are non-launch adapters.

### Evidence required before approval

- Aurora PostgreSQL failover while listeners and outbox consumers are active.
- RDS Proxy/direct connection comparison for listener behavior.
- 1, 10, 100, and 1,000 control changes/second with 3, 30, and 300 consumers.
- Notification loss and 10-minute partition catch-up.
- Revocation p50/p95/p99 propagation and fail-closed transition.
- Aurora I/O/CPU/connection cost versus Redis Streams and gossip alternatives.
- Snapshot sizes from realistic 10K/100K/1M virtual-key tenants.

## Decision 2: globally shared quotas and budgets

### Option A: Aurora row locks/atomic SQL

Strong durable semantics and one service, but write contention, latency, and hot rows
can damage inference throughput. Suitable for low-rate budget top-ups and the durable
ledger, not high-rate TPM/RPM admission without proof.

### Option B: Redis Lua/functions with durable reconciliation

Atomically reserve across multiple dimensions in one operation, expire time windows,
and reconcile an append-only durable PostgreSQL ledger. This is the leading option for
the hot path. It requires cluster-slot-aware key design, failover tests, reservation
leases, and a clear closed/open policy when Redis is unavailable.

### Option C: regional counters with asynchronous global settlement

Lowest latency and highest regional availability, but can overspend during partitions.
Only acceptable for explicitly soft limits with bounded per-region allocations/escrow.
Hard enterprise budgets require centrally allocated tokens or a globally authoritative
reservation service.

Launch recommendation: Aurora PostgreSQL atomic reservations plus a durable ledger,
because Redis cannot be mandatory. Use hierarchical/time-bucket sharding, short
transactions, idempotent reservation rows and reconciliation. Benchmark realistic peak
contention and preserve a `CounterAuthority` interface so Redis can be an optional
accelerator later. Controlled overdraft is a policy state, not a race-condition margin:
it requires a pre-approved rule or an explicit approval workflow plus alerts.

## Decision 3: membership and health propagation

- Kubernetes EndpointSlice/watch: simplest and authoritative inside Kubernetes.
- AWS Cloud Map/Route 53: useful across ECS/VM deployments, slower for fine health.
- Memberlist gossip: portable, fast decentralized membership; additional ports and
  partition/security complexity.
- Database heartbeats: simplest fallback and operator-visible, but slow and adds DB load.

Launch recommendation: Kubernetes EndpointSlice/watch plus readiness. Database
heartbeats may support operator visibility and job fencing, but are not primary
membership. Defer memberlist and non-Kubernetes discovery. Never couple policy
consistency to discovery.

## Decision 4: large configuration snapshots

- PostgreSQL normalized rows: best mutation/query authority.
- PostgreSQL JSONB immutable version: easy atomic snapshot and rollback; can duplicate
  normalized data and produce large WAL.
- S3 versioned object plus signed manifest: cheap large snapshots and multi-region
  distribution; higher propagation latency and separate consistency workflow.
- FSx/EFS immutable file: local operational convenience, poor global control plane.
- Peer gRPC snapshot transfer: fast catch-up but requires trusted healthy seed and
  integrity verification.

Preliminary recommendation: normalized PostgreSQL authority; deterministic signed
snapshot artifact in S3 for bootstrap/DR; direct DB delta for ordinary changes. Peer
transfer is an optimization only after checksum/version verification.

## Decision 5: multi-region control plane

### Active/passive writer

One Aurora writer region, read replicas/global database, regional data planes, and a
tested promotion runbook. Simplest conflict model; control mutations may be unavailable
during failover. Good first production target.

### Home-region sharding

Each tenant has one writer region and globally visible versioned state. Scales writes
and preserves single-writer semantics, but tenant movement and cross-region operations
are complex.

### Active/active writes

Lowest local write latency but requires conflict-free semantics for every entity,
global uniqueness, and careful revocation ordering. Not justified until requirements
prove active/passive or home-region sharding inadequate.

Launch recommendation: one U.S. Aurora control-plane writer and Kubernetes data plane.
Control mutations may be unavailable during a regional database failure. Inference may
continue only while the local snapshot is within its bounded freshness lease and the
operation does not require an unavailable hard reservation. Preserve an active/passive
DR path without building active/active writes.

## Decision 6: provider and region failover

Retries are allowed only when the request is safe and no response bytes have been
delivered. After streaming begins, a hidden retry can duplicate work or splice outputs.
Route attempts carry deadlines and idempotency classification.

- Native Bedrock geographic/global CRIS: maximum simplicity and capacity, opaque AWS
  destination selection. Record actual `inferenceRegion` from CloudTrail/log correlation.
- Gateway-controlled Bedrock regional targets: deterministic priority/weights, locality,
  cache affinity and circuit logic; higher maintenance and quota discovery burden.
- Hybrid provisioned/on-demand/CRIS: prefer reserved capacity, overflow only when tenant
  residency and cost policy permits. Provisioned Throughput and inference profiles are
  separate target types.
- Cross-provider fallback: protects from provider-wide failure but changes model behavior,
  tokenizer, tools, logprobs, safety, pricing and data-processing jurisdiction.

Launch recommendation: default to U.S. geographic CRIS, with gateway-controlled mode for
explicit region order, side-by-side/canary evaluation, cross-provider ladders, capacity
overflow, or route evidence AWS does not expose. Global CRIS is disabled by launch
policy.

## Decision 7: learned and semantic routing

Hard filters always run first: identity entitlement, capabilities, context length,
modality/tools/JSON/logprobs, residency/data policy, health, quota and capacity. A
learned scorer can rank only remaining candidates.

Implement a `RouterScorer` contract returning score, confidence, explanation, feature
version and model revision. Candidate scorers include rules/complexity, embeddings,
small classifier, bandit/feedback router and offline-trained quality/cost/latency router.
Run new scorers in shadow, calibrate thresholds on versioned datasets, and require
canary promotion. Never let a learned router weaken a hard governance constraint.

## Sanitized architecture-duel prompt

This prompt contains no private source and can be sent to external models after the
owner explicitly approves that workflow:

> Design cross-pod state propagation for a Go AI gateway on Kubernetes using Aurora
> PostgreSQL and optionally Redis. Compare: transactional outbox plus polling;
> outbox plus LISTEN/NOTIFY wakeup; logical replication/CDC; Redis Streams relay;
> memberlist gossip plus authenticated gRPC; versioned FSx/EFS files; and hybrids.
> Evaluate configuration, virtual-key revocation, policy reductions, hard budget/RPM/TPM
> counters, membership, regional provider health and large snapshots separately.
> Score correctness under partitions/failover, p99 propagation, hot-path overhead,
> Aurora connections/I/O, operational burden, multi-region evolution, security and
> testability. Recommend the simplest design that gives durable catch-up and bounded
> revocation while keeping inference reads lock-free. State what evidence could falsify
> the recommendation.

## Resolved owner decisions

1. Revocation bound: 1-5 seconds.
2. Budgets: controlled overdraft with approval or preconfigured policy and alerts.
3. Aurora regional failure: temporary control-plane write outage acceptable.
4. Redis: not mandatory.
5. Deployment: Kubernetes only at launch.
6. Bedrock: U.S. geographic profiles.
7. Shared filesystem: not required at launch.

## Remaining decisions after benchmarks

1. Exact propagation target inside the 1-5 second window and fail-closed lease length.
2. Maximum automatic overdraft by user/team and which events require synchronous versus
   asynchronous human approval.
3. PostgreSQL quota reservation throughput target and acceptable contention budget.
4. Whether a hard-limit request is denied during Aurora unavailability or may consume a
   preallocated bounded local escrow.
5. Retention and access policy for raw traces, logprobs and distillation datasets.
