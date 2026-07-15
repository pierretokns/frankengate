# Horizontal Scaling Bead Coverage

Date: 2026-07-15

Scope: `bif-kyy.6.9` coverage audit for internal enterprise Kubernetes launch with Aurora PostgreSQL authority. This document maps launch horizontal-scaling requirements to existing Beads, identifies remaining gaps, and records new child Beads created for narrowly scoped executable failure oracles.

This is not an implementation status claim. Closed ADR/prototype Beads are treated as design evidence only unless the Bead notes say production integration is complete. Existing roadmap warnings remain confirmed known risks.

## Source Material Inspected

- Beads under `bif-kyy.6`, plus adjacent governance, quota, MCP, release, and cross-cutting conformance Beads.
- `docs/roadmap/architecture/disconnected-authorization.md`, which selects signed local snapshots, bounded stale-closed leases, budget capabilities, Aurora as durable authority, and failure oracles for revocation, pricing, MCP tool kill, privacy, outage, and rollback.
- `docs/roadmap/architecture/outbox-cursor-lifecycle.md`, which designs Aurora outbox tables, consumer leases, signed snapshot watermarks, poison/resnapshot flows, compaction, metrics, LISTEN/NOTIFY as an optimization, and failure oracles for notification loss, Aurora failover, dead consumers, mixed versions, clock skew, and partitions.
- `docs/roadmap/architecture/migration-compatibility-manifest.md`, which defines migration IDs, predeploy Kubernetes migration jobs, mixed-version compatibility, rollback oracles, schema epochs, and manifest/linter expectations.
- `docs/roadmap/architecture/mcp-connection-ownership.md`, which selects sticky fenced MCP ownership without mandatory Redis and covers OAuth callback routing, stateful sessions, pod loss, ambiguous completion, and idempotent reconnect.
- `docs/roadmap/architecture/principal-deprovisioning.md`, which binds derived sessions, keys, caches, MCP grants, and live connections to immutable principal identity plus monotonically increasing authorization epoch and describes Aurora/outbox integration.
- `docs/roadmap/architecture/virtual-key-fingerprint-rotation.md`, for virtual-key secret authority and rotation context.

## Coverage Legend

- Covered design: accepted ADR/prototype coverage exists, but production code may still be open.
- Open implementation: an implementation/test Bead already exists and should not be duplicated.
- Gap now covered by new child Bead: this audit created a narrow executable oracle Bead.
- Tension: coverage exists but has conflicting defaults or acceptance language that must be reconciled before launch.

## New Child Beads Created

| Bead | Title | Why it was created | Dependencies added |
| --- | --- | --- | --- |
| `bif-kyy.6.10` | Prove RDS Proxy and direct PostgreSQL listener topology | Existing ADRs state LISTEN/NOTIFY is only a wakeup and mention RDS Proxy/direct listener behavior, but there was no narrow launch oracle proving the selected topology through failover, reconnect gaps, and unsupported pooled listener paths. | Depends on `bif-kyy.6.4` and `bif-kyy.6.8`. |
| `bif-kyy.6.11` | Prove optional Redis acceleration cannot become authority | Redis is optional in the roadmap, but no Bead explicitly proves Redis enabled/disabled/flushed/partitioned behavior cannot extend stale auth, budgets, routing, MCP grants, or snapshots. | Depends on `bif-kyy.6.4`, `bif-kyy.6.7`, and `bif-kyy.6.8`. |
| `bif-kyy.6.12` | Prove authority leases under clock skew | Clock skew is mentioned in existing chaos/outbox docs, but no narrow primitive test ties pod skew to authorization epochs, reservation renewal, outbox ordering, readiness, and fail-closed behavior. | Depends on `bif-kyy.6.7`, `bif-kyy.6.8`, `bif-kyy.5.6`, and `bif-kyy.4.9`. |
| `bif-kyy.6.13` | Prove 100-pod bootstrap backpressure and notification storms | Existing Beads cover three-pod conformance and general chaos, but there was no explicit 100-pod cold bootstrap, notification storm, DB backpressure, and no-mandatory-Redis oracle. | Depends on `bif-kyy.6.2`, `bif-kyy.6.3`, `bif-kyy.6.5`, and `bif-kyy.6.8`. |

`br dep cycles --json` reported zero active dependency cycles after these additions.

## Requirement-To-Bead Matrix

| Requirement | Existing Bead coverage | Status | Gap or action |
| --- | --- | --- | --- |
| Aurora/PostgreSQL durable control-plane authority | `bif-kyy.6.4`, `bif-kyy.6.8`, `bif-cks.2`, `bif-9w0.4`; ADR source in outbox cursor lifecycle and disconnected authorization. | Covered design; implementation open. | Keep authority out of per-request inference hot path. Do not close `6.1`, `6.4`, or `cks.2` until durable snapshot/cursor tests pass. |
| Transactional outbox for authority changes | `bif-kyy.6.8` accepted ADR; `bif-kyy.6.4` propagation ADR; `bif-kyy.6.1` runtime implementation. | Covered design; implementation open. | Production rows, cursor consumers, atomic snapshot swaps, and stale-closed validation remain implementation evidence for `6.1`/`6.4`. |
| LISTEN/NOTIFY as wakeup only | `bif-kyy.6.8`, `bif-kyy.6.4`, `bif-9w0.4`, `bif-cks.7`. | Covered design. | `bif-kyy.6.10` now requires the executable listener topology oracle and proves polling catches missed wakeups. |
| RDS Proxy vs direct listener topology | Mentioned by `bif-kyy.6.4` and `bif-9w0.4`. | Gap now covered by new child Bead. | `bif-kyy.6.10` must prove direct listener reconnect gaps, RDS Proxy interruptions, and unsupported pooled listener paths cannot affect correctness. |
| Optional Redis accelerator | `bif-kyy.6.4` says Redis/gossip/shared files are future comparisons, not launch dependencies; migration ADR says Redis must not be required for convergence or rollback safety. | Gap now covered by new child Bead. | `bif-kyy.6.11` must prove Redis can be disabled and that Redis values are hints guarded by durable revision/epoch checks. |
| Redis loss, flush, restart, and partition | Partially implied by no-mandatory-Redis launch design and `bif-kyy.6.4`. | Gap now covered by new child Bead. | `bif-kyy.6.11` owns the loss oracle across governance/config/MCP/quota freshness. |
| Stateless request pods | Parent `bif-kyy.6`, runtime `bif-kyy.6.1`, Kubernetes `bif-kyy.6.2`, membership/bootstrap ADR `bif-kyy.6.5`. | Open implementation. | Pods must be replaceable from signed snapshots plus durable cursor state; no pod-local authority. |
| Initial bootstrap before serving protected requests | `bif-kyy.6.5`, `bif-kyy.6.8`, `bif-cks.2`. | Covered design; scale gap now covered. | `bif-kyy.6.13` adds the 100-pod cold bootstrap oracle. |
| Local cache freshness and stale-closed semantics | `bif-kyy.6.7`, `bif-cks.2`, `bif-kyy.3.3`, `bif-kyy.5.6`, `bif-kyy.15.5`. | Covered design; implementation open in several Beads. | Matrix treats key, principal, MCP, routing, privacy, and budget cache freshness as separate failure surfaces, not one generic cache. |
| Virtual key coherence and bounded revocation | `bif-kyy.3.3`, `bif-kyy.6.7`, `bif-cks.2`. | Open implementation. | Must prove create/use/revoke across pods, duplicate/reordered events, disconnection, rotation, and stale-closed behavior. |
| Principal deprovisioning across sessions, keys, caches, MCP grants, live connections | `bif-kyy.5.6` ADR/prototype; `bif-kyy.14.3`; `bif-kyy.15.5`. | Covered primitive; production integration open. | `bif-kyy.6.12` adds skew/lease interaction; `5.6` remains open for actual gateway integration. |
| MCP catalog/grant/health/kill-switch snapshots | `bif-kyy.15.5`, `bif-kyy.15.18`, `bif-kyy.6.7`, `bif-kyy.5.6`. | Open implementation. | Must prove zero upstream connection/credential/tool packets after local kill applies. |
| Stateful MCP connection ownership | `bif-kyy.15.18` accepted ADR/prototype; `bif-kyy.15.5` distribution. | Covered design/prototype. | Do not treat as wired into runtime until MCP integration Beads close with evidence. |
| Budget/quota reservations | `bif-kyy.4.1`, `bif-kyy.4.5`, `bif-kyy.4.9`, `bif-kyy.4.2`, `bif-kyy.4.3`. | Open implementation. | Must prove atomic reserve-before-upstream, idempotent request/attempt keys, fenced renewal, settlement, refunds, controlled overdraft, and alerting. |
| Reservation behavior during DB outage | `bif-kyy.6.7`, `bif-kyy.6.6`, `bif-kyy.4.9`, `bif-kyy.4.2`. | Covered design; implementation open. | No new hard-budget admission without unexpired reservation or overdraft capability. |
| Budget owner/reviewer alert surfaces for overdraft | `bif-kyy.4.3`, `bif-kyy.6.7`, `bif-kyy.14.3`. | Open implementation. | Ensure overdraft use and reservation-authority exhaustion produce operator-visible alerts, not silent local allowances. |
| Migrations and schema epochs | `bif-cks.15`, `bif-cks.9`, migration compatibility ADR. | Covered design; implementation open. | Predeploy migration Job, manifest linter, mixed-version harness, and rollback smoke are still required. |
| Startup migration locks and leases | `bif-cks.15`, `bif-cks.9`, migration compatibility ADR. | Covered design; implementation open. | Move required heavy DDL out of ordinary pod startup; pods should verify schema epoch before readiness. |
| Consumer leases and dead-consumer retirement | `bif-kyy.6.8`, `bif-kyy.6.1`, `bif-cks.7`. | Covered design; implementation open. | Lease authority must use DB time and fencing; dead pods cannot block compaction. |
| Kubernetes discovery/membership | `bif-kyy.6.5`, `bif-kyy.6.1`. | Covered design; implementation open. | EndpointSlice/watch/readiness are launch membership sources; database heartbeat is operator visibility/fencing, not ordinary discovery. |
| Readiness/startup/liveness | `bif-kyy.6.2`, `bif-cks.4`, `bif-9w0.7`, `bif-kyy.6.8`. | Open implementation. | Readiness must withhold protected serving before signed snapshot and required schema epoch. |
| Graceful drain and SIGTERM long-stream behavior | `bif-kyy.6.2`, `bif-cks.4`, `bif-9w0.7`, `bif-kyy.6.7`. | Open implementation. | Drains need stream/agent kill checkpoints so revocation/privacy/MCP tool-kill exposure is bounded. |
| HPA metrics and overload | `bif-kyy.6.2`, `bif-9w0.7`, `bif-cks.4`. | Open implementation. | HPA must include CPU plus concurrency/queue/latency metrics; backpressure is separately tested by `6.13`. |
| PDB, topology spread, anti-affinity, resource sizing | `bif-kyy.6.2`, `bif-cks.4`, `bif-9w0.7`. | Open implementation. | Verify N+1 and zone-loss math; do not infer availability from Helm values alone. |
| Network policy and internal pod forwarding | `bif-kyy.6.2`, `bif-kyy.15.18`, `bif-cks.4`. | Open implementation. | MCP owner forwarding must be internal-only and fenced; network policies must still permit required control-plane and owner routes. |
| Pod loss | `bif-kyy.6.3`, `bif-kyy.6.8`, `bif-kyy.15.18`, `bif-cks.7`. | Covered by open tests/design. | Prove leases expire, ambiguous MCP calls are surfaced, snapshots/cursors recover, and no stale owner writes land. |
| Node loss | `bif-kyy.6.2`, `bif-kyy.6.3`, `bif-cks.4`, `bif-cks.7`. | Open implementation/evidence. | Must show PDB/topology/anti-affinity and HPA capacity keep data plane available for allowed traffic. |
| Zone loss | `bif-kyy.6.2`, `bif-kyy.6.3`, `bif-kyy.6.6`, `bif-cks.4`, `bif-cks.7`. | Open implementation/evidence. | Regional control-plane writer remains single-writer; mutation outage may be acceptable, data-plane stale rules still apply. |
| Aurora writer failover | `bif-kyy.6.4`, `bif-kyy.6.8`, `bif-kyy.6.6`, `bif-9w0.4`, `bif-cks.7`. | Covered design; oracle narrowed by new Bead. | `bif-kyy.6.10` covers listener/polling topology through failover; existing chaos Beads cover broader failover evidence. |
| Mixed-version rolling upgrade | `bif-cks.15`, `bif-cks.9`, `bif-kyy.6.3`, migration compatibility ADR. | Covered design; implementation open. | Must prove N/N+1 snapshots, durable events, MCP records, budget records, and privacy/eval envelopes. |
| Notification loss | `bif-kyy.6.8`, `bif-kyy.6.1`, `bif-kyy.6.4`, `bif-9w0.4`, `bif-cks.7`. | Covered design; scale gap now covered. | Polling by durable IDs is correctness path; `6.13` adds large-fleet loss/storm behavior. |
| Notification reordering and duplicates | `bif-kyy.6.1`, `bif-kyy.6.8`, `bif-kyy.3.3`, `bif-cks.5`. | Covered by open implementation/testing Beads. | Apply only monotonic revisions/watermarks; stale epochs must not revive. |
| Notification storms | `bif-9w0.4`, `bif-cks.7`, `bif-kyy.6.8`. | Gap now covered by new child Bead. | `bif-kyy.6.13` must prove no DB thundering herd, cursor regression, duplicate application, or stale policy revival. |
| Clock skew | `bif-kyy.6.8`, `bif-9w0.4`, `bif-cks.7`. | Gap now covered by new child Bead. | `bif-kyy.6.12` owns deterministic skew tests for leases, readiness, epochs, reservations, and outbox order. |
| Bootstrap from no local snapshot | `bif-kyy.6.5`, `bif-kyy.6.8`, `bif-cks.2`. | Covered design; scale gap now covered. | `bif-kyy.6.13` adds 100-pod cold start and recovery. |
| Backpressure during bootstrap/catch-up/recovery | `bif-kyy.6.8`, `bif-kyy.6.5`, `bif-9w0.4`, `bif-9w0.7`. | Gap now covered by new child Bead. | `bif-kyy.6.13` must bound bootstrap readers, LISTEN reconnects, snapshot downloads, and per-tenant catch-up. |
| Recovery after compaction, poison, or snapshot failure | `bif-kyy.6.8`, `bif-cks.7`. | Covered design; implementation open. | Keep poison/resnapshot/compaction oracles in `6.8`/`cks.7`; do not duplicate. |
| Privacy-safe traces/evals under stale policy | `bif-kyy.6.7`, `bif-cks.9`, migration ADR, adjacent privacy Beads. | Covered design; implementation open outside E5. | Stale or unknown privacy policy must degrade to metadata-only/drop; mixed-version records must carry schema/producer versions. |
| Three-pod horizontal conformance | `bif-kyy.6.3`, `bif-kyy.14.3`. | Open implementation/evidence. | Three-pod suite remains the first launch gate for pod death, delayed invalidation, counters, DB failover, fencing, partitions, and mixed versions. |
| 100-pod horizontal conformance | No existing narrow Bead before this audit. | Gap now covered by new child Bead. | `bif-kyy.6.13` owns the 100-pod bootstrap/backpressure/notification storm oracle. |

## Dependency Rationale

- `bif-kyy.6.10` depends on `6.4` because the propagation ADR selects the cross-pod control-plane transport, and on `6.8` because the oracle relies on durable cursor/polling semantics.
- `bif-kyy.6.11` depends on `6.4`, `6.7`, and `6.8` because Redis loss can only be judged against selected propagation, freshness leases, and durable outbox replay.
- `bif-kyy.6.12` depends on `6.7`, `6.8`, `5.6`, and `4.9` because clock skew crosses authorization leases, outbox DB-time leases, principal epochs, and fenced reservation renewal.
- `bif-kyy.6.13` depends on `6.2`, `6.3`, `6.5`, and `6.8` because 100-pod testing should build on Kubernetes runtime semantics, the smaller three-pod suite, membership/bootstrap design, and outbox lifecycle semantics.

No new dependencies were added from these new Beads into optional Redis launch paths, because Redis is explicitly non-mandatory. No implementation Beads were closed.

## Tensions To Reconcile

1. Freshness lease default: disconnected authorization selects a maximum 5 second launch security lease for restrictive/revocation/tool-kill/privacy-hardening classes, while the outbox cursor lifecycle document lists an initial 15 second security-reduction freshness lease to validate. The launch matrix treats 5 seconds as the accepted target and requires `bif-kyy.6.4`, `bif-kyy.6.10`, `bif-kyy.6.12`, and `bif-kyy.6.13` to reconcile measured defaults before production closure.
2. Closed design/prototype Beads are not production proof. `bif-kyy.5.6`, `bif-kyy.6.7`, `bif-kyy.6.8`, and `bif-kyy.15.18` contain important accepted design/prototype work, but the implementation Beads that integrate those designs remain open.
3. Aurora must be authoritative without entering the inference availability path. The matrix deliberately separates local snapshot reads from outbox/listener/polling/control-plane machinery.
4. Three-pod and 100-pod tests should not use invented benchmark thresholds. The new 100-pod Bead requires measured lag, queue depth, retry, WAL/autovacuum, CPU, and memory data before setting numeric launch thresholds.

## Current Launch Coverage Summary

Covered by existing design:
- Aurora/PostgreSQL authority, outbox/watermarks/cursors, local immutable snapshots, stale-closed leases, no mandatory Redis, disconnected authorization, MCP fenced ownership, principal authorization epoch primitive, and migration compatibility model.

Covered by open implementation/evidence Beads:
- Runtime invalidation transport, Kubernetes hardening, three-pod chaos/conformance, quota reservations/reconciliation, cross-pod key revocation, MCP snapshot distribution, migration manifest implementation, and cross-cutting chaos/soak.

Newly covered by child Beads from this audit:
- RDS Proxy/direct listener topology oracle (`bif-kyy.6.10`).
- Optional Redis accelerator and Redis-loss oracle (`bif-kyy.6.11`).
- Clock-skew authority lease oracle (`bif-kyy.6.12`).
- 100-pod bootstrap/backpressure/notification storm oracle (`bif-kyy.6.13`).

## Questions Left Open

- Which exact Aurora/RDS Proxy topology will launch use for app traffic, listener traffic, and migration jobs?
- What environment will run the 100-pod oracle if CI cannot realistically reproduce Aurora failover, RDS Proxy, and Kubernetes zone-loss behavior?
- Which release artifact will own the machine-readable migration compatibility manifest?
- Which Bead will set measured launch thresholds after the first RDS/Aurora/Kubernetes experiments produce real lag and resource data?
