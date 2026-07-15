# Failure-Mode (F4) + Worst-Case (L3) Analysis

## Thesis

The launch architecture should not fail because it lacks gossip, Redis, or autonomous
skill-promotion security. Its largest plausible cascades sit at the seams between the
existing single-process governance implementation and the proposed multi-pod control
plane. In particular, the current accounting path is not merely eventually consistent:
independent pods overwrite shared database totals with absolute local values. The next
largest risks are admitting work before a durable quota reservation, coupling Kubernetes
health to every backing store, applying related policy objects non-atomically, and treating
routing-policy errors as permission to continue. These are survivability problems for an
internal service used continuously by developer agents, even though its attack surface and
skill-promotion risks are substantially reduced by mandatory human MR approval.

## Deployment and severity calibration

- Internal-only enterprise service on Kubernetes, initially in one U.S. control-plane
  region with Aurora PostgreSQL.
- Multiple stateless request pods; Redis, gossip, and shared filesystems are not mandatory.
- Revocation and restrictive-policy convergence may take 1-5 seconds. Temporary Aurora
  control-plane write unavailability is acceptable.
- Skills are internal Git artifacts. The gateway may propose a patch or draft MR but has no
  merge authority; protected branches and a human approver are the promotion authority.
- Controlled spend overdraft is acceptable only when pre-approved or explicitly approved
  and alerted.

Accordingly, no finding below is rated critical merely because an internal operator or
repository maintainer could behave maliciously. High severity means a realistic pod,
database, provider, or rollout failure can interrupt the internal gateway broadly or make
hard governance promises materially false.

## Top findings

### §F1 — Healthy pods can erase each other's budget and rate-limit usage

**Classification:** novel cascade, not just a restatement of the roadmap
**Severity:** high
**Confidence:** 0.98

**Evidence.** Each pod increments private in-memory counters
(`plugins/governance/tracker.go:124-214`). Every ten seconds, every tracker resets/dumps all
counters (`plugins/governance/tracker.go:65-70,217-260`). `DumpRateLimits` writes each pod's
absolute local totals with SQL `UPDATE` (`plugins/governance/store.go:2104-2168`), and
`DumpBudgets` does the same (`plugins/governance/store.go:2194-2240`). A deadlock is treated
as success on the assumption that gossip will synchronize usage
(`plugins/governance/store.go:2176-2187,2247-2258`), while the selected launch architecture
explicitly does not use gossip as counter authority
(`docs/roadmap/technical-decision-options.md:143-163,187-198`).

**Failure chain.** Pod A spends $8 and pod B spends $7 against the same $10 budget. A dumps
8, B later overwrites it with 7. Both local evaluators still see less than $10, admit more
traffic, and continue overwriting one another. Adding pods increases the error. Aurora,
alerts, dashboards, and reconciliation all consume a plausible but false total, so an
operator may approve a top-up or canary based on underreported spend.

**Simpler mitigation.** Do not adapt these dump methods for cluster authority. Introduce a
small `CounterAuthority` whose launch implementation performs atomic reservation deltas in
Aurora and records idempotent `(request_id, attempt)` settlement. Keep pod-local counters
only as telemetry. Delete the gossip-baseline assumption from the authoritative path.

**Executable oracle.** A PostgreSQL integration test starts three independent stores with
the same $10 budget, applies costs 4, 3, and 2 concurrently, runs dumps in all six orders,
and asserts the durable total is exactly 9 after every order and restart. A second phase
concurrently reserves 100 × $0.20 and proves accepted reservations plus configured
overdraft never exceed the limit.

**So what tomorrow?** Make this the first blocking technical spike; do not implement outbox
fanout or HPA around the existing dump algorithm.

### §F2 — Admission occurs before settlement, so a burst can overspend before any pod notices

**Classification:** confirmed known requirement, with an additional fallback cascade
**Severity:** high
**Confidence:** 0.96

**Evidence.** Governance checks current local state in `EvaluateGovernanceRequest`
(`plugins/governance/main.go:926-1040`) but does not reserve estimated cost or tokens. Usage
is calculated after the provider returns and launched in a new goroutine
(`plugins/governance/main.go:1322-1385,1656-1668`). The tracker then updates memory
(`plugins/governance/tracker.go:91-214`). Fallbacks execute another full attempt after a
failure (`core/bifrost.go:4931-5055`), while attempt billing remains asynchronous. The
roadmap already requires atomic reservation/reconciliation
(`docs/roadmap/enterprise-oss-program.md:164-181`); that requirement is owner-acknowledged.

**Failure chain.** A synchronized Claude Code burst reaches three pods while all observe
$9.90 of a $10 budget. Every request passes. Slow or failed primaries consume tokens,
fallbacks begin before primary settlement becomes visible, and successful fallbacks add a
second cost. The later accounting is accurate only locally and too late to enforce the
limit. HPA can amplify the burst by adding fresh pods with cold counters.

**Simpler mitigation.** Reserve a conservative estimate synchronously in one short Aurora
transaction before provider selection; bind it to request and attempt IDs. Reconcile actual
usage and refund the difference. When the authority is unavailable, hard tiers fail closed;
only an explicit overdraft policy receives a bounded escrow allocation.

**Executable oracle.** Barrier-start 1,000 requests across three pods at one remaining
request and $1 remaining. Assert at most the configured overdraft is admitted, including a
primary that reports partial usage followed by a successful fallback, cancellation, and a
pod kill between reserve and reconcile. After repair, ledger sum must equal provider-attempt
sum and no reservation may create credit.

**So what tomorrow?** Specify reservation state transitions before extending the current
tracker or building spend dashboards.

### §F3 — A policy event can expose a hybrid in-memory revision

**Classification:** non-obvious implementation seam; the roadmap's atomic-snapshot rule is known
**Severity:** medium-high
**Confidence:** 0.91

**Evidence.** `ReloadVirtualKey` deliberately fetches the VK and related model configs
before mutating memory (`transports/bifrost-http/server/server.go:384-422`), but then
publishes the VK, upserts each model config, and deletes stale configs as separate map
operations (`transports/bifrost-http/server/server.go:431-447`). `UpdateVirtualKeyInMemory`
also updates budget/rate maps before publishing the final VK pointer
(`plugins/governance/store.go:3012-3189`). Hot-path reads are independent lock-free map
loads (`plugins/governance/store.go:922-948`). The desired contract instead says a pod
fetches a versioned snapshot and atomically swaps it
(`docs/roadmap/technical-decision-options.md:46-52,189-193`).

**Failure chain.** A restrictive group/profile update removes model access and changes a
budget. During reload, a request can see the new VK with an old scoped model config, or new
standalone budget entries reachable from the old VK. Under a large profile update, this is
not merely a nanosecond map swap. A later stale event can repeat the hybrid unless one
monotonic aggregate revision gates the entire apply. Explain-access and invocation can
therefore disagree on the same pod.

**Simpler mitigation.** Build one immutable `GovernanceSnapshot` off-path, validate all
foreign keys and its aggregate revision, then publish one `atomic.Pointer`. Avoid trying to
make a sequence of `sync.Map` mutations transactional.

**Executable oracle.** Continuously invoke and explain access while alternating revisions
R1 (model allowed, budget A) and R2 (model denied, budget B), injecting delays after every
apply step and duplicate/reordered outbox events. Every observation must equal all-R1 or
all-R2; no mixed tuple is permitted.

**So what tomorrow?** Define the snapshot boundary and revision tuple before writing the
outbox consumer.

### §F4 — Database pressure can make Kubernetes remove every otherwise usable inference pod

**Classification:** novel cascade assembled from known individual concerns
**Severity:** high if `/health` is reused for liveness; medium otherwise
**Confidence:** 0.94

**Evidence.** The only registered health endpoint is `/health`
(`transports/bifrost-http/handlers/health.go:26-29`). Unless DB pings are disabled, every
probe concurrently pings the config, log, and vector stores with a ten-second timeout and
returns 503 if any one fails (`transports/bifrost-http/handlers/health.go:31-89`). The
roadmap itself requires readiness and liveness to have different meanings and warns against
restart storms (`docs/roadmap/enterprise-oss-program.md:215-226`). The chosen outbox design
also anticipates one listener plus polling per pod and explicitly calls out Aurora fanout
cost (`docs/roadmap/technical-decision-options.md:54-100,200-208`).

**Failure chain.** A control-plane burst or outbox catch-up saturates Aurora connections.
Health pings time out. If the same endpoint drives readiness and liveness, Kubernetes first
withdraws every pod and then restarts them. Every restarting pod opens migration/runtime
pools and reloads full governance state (`framework/configstore/postgres.go:36-69`), adding
more pressure. Inference that could safely continue from a fresh-enough snapshot disappears.

**Simpler mitigation.** Expose separate `/livez`, `/readyz`, and `/startupz`. Liveness checks
only process/event-loop health. Readiness evaluates explicit policy: loaded snapshot,
freshness lease, and required provider availability; optional log/vector stores cannot evict
the data plane. Add jitter and a shared per-pod probe result rather than opening work on
every kubelet probe.

**Executable oracle.** In a three-pod Kind test, block Aurora for 30 seconds while existing
snapshots remain inside their lease. Assert zero restarts and continued allowed inference;
control writes fail. Advance beyond the revocation lease and assert only protected traffic
fails closed. Restore Aurora and assert staggered recovery without a connection spike above
the configured budget.

**So what tomorrow?** Split the health contract before authoring Helm probes or chaos tests.

### §F5 — Routing failures silently fall back to caller/default behavior

**Classification:** novel reliability and cost-policy failure; entitlement bypass not proven
**Severity:** medium-high
**Confidence:** 0.93

**Evidence.** `PreRequestHook` returns routing and refinement errors
(`plugins/governance/main.go:1214-1248`), but the plugin contract declares those errors
non-blocking (`core/schemas/plugin.go:283-297`) and the pipeline logs and continues
(`core/bifrost.go:7300-7337`). Routing-rule evaluation goes further: it logs an engine error
and deliberately returns no error and no decision (`plugins/governance/main.go:743-751`). If
all eligible providers are excluded by budgets/rates, load balancing also returns success
without a route (`plugins/governance/main.go:534-561`).

**Failure chain.** A bad CEL rule, catalog-refinement regression, or all-provider budget
exhaustion occurs during a canary. Instead of producing a stable policy denial, the request
continues with its original provider/model or a later default resolver. PreLLM governance
likely still enforces model/provider entitlement, so this is not presented as a proven
authorization bypass. It can nevertheless bypass cost, locality, canary, or health intent,
send a surge to the wrong provider, trigger fallbacks, and compound §F2.

**Simpler mitigation.** Give routing results a typed outcome: `selected`, `no_match`,
`policy_denied`, or `engine_error`. Fail closed for restrictions and hard budgets; permit a
documented static fallback only for optional optimization errors. Do not use plain plugin
errors for policy outcomes.

**Executable oracle.** Table-test every routing stage with CEL error, missing model catalog,
zero eligible providers, stale health, and invalid pinned key. Assert the exact provider or
stable denial code, and assert no provider invocation occurs for `policy_denied`.

**So what tomorrow?** Add the outcome algebra to the routing ADR and bead acceptance tests.

### §F6 — Notification success can hide a permanently lagging pod

**Classification:** known transport limitation, missing operational stop condition
**Severity:** medium-high
**Confidence:** 0.88

**Evidence.** The selected design correctly states that `NOTIFY` is ephemeral and requires a
dedicated listener plus cursor polling repair
(`docs/roadmap/technical-decision-options.md:79-100`). It also requires per-pod cursors and
heartbeats (`docs/roadmap/technical-decision-options.md:54-59`) and a freshness lease
(`docs/roadmap/technical-decision-options.md:189-193`). Current hot-path authentication has
no database confirmation: it trusts the local key map (`plugins/governance/main.go:926-943`;
`plugins/governance/store.go:922-932`).

**Failure chain.** One pod loses its listener, while a cursor-write bug or poisoned event
causes polling to skip a sequence. Other pods converge and aggregate propagation metrics
look healthy. The isolated pod remains Kubernetes-ready and accepts a revoked key
indefinitely because traffic is sparse enough that the per-pod tail is invisible. An HPA
scale-down/up can repeatedly resurrect the bad cursor from durable consumer state.

**Simpler mitigation.** Readiness must compare each pod's applied watermark with a cheap
authoritative high-water mark and expire a local security lease. Persist cursors only after
an entire snapshot revision is validated and published. Alert on the maximum individual
pod lag, never only the fleet percentile.

**Executable oracle.** Drop notifications to exactly one pod, corrupt its next event, and
keep serving a revoked key through that pod. Polling must either converge within five
seconds or the pod must reject protected traffic and leave readiness. Restart it with the
old cursor and repeat.

**So what tomorrow?** Put `applied_revision`, `authority_revision`, lease age, and pod UID in
the first control-plane metrics schema.

### §F7 — Rolling upgrades can combine incompatible event semantics without a schema error

**Classification:** partially owner-acknowledged; the specific semantic-skew cascade is not specified
**Severity:** medium
**Confidence:** 0.82

**Evidence.** The program calls for a documented mixed-version window and multi-version
tests (`docs/roadmap/enterprise-oss-program.md:217-233`). PostgreSQL startup uses a separate
migration pool followed by a fresh runtime pool to avoid stale prepared plans
(`framework/configstore/postgres.go:14-69`), which solves SQL plan invalidation but not event
meaning. The proposed outbox message carries resource/revision and receivers fetch current
rows (`docs/roadmap/technical-decision-options.md:79-83`); no event-schema compatibility or
minimum-reader version is yet specified.

**Failure chain.** New code writes a field whose default changes deny/allow semantics. Old
pods can still decode the row, silently apply their old default, and advance the cursor.
The fleet reports full revision convergence while enforcing two meanings. A rollback of the
writer does not repair already-advanced consumers, so a nominally safe Kubernetes rollback
preserves policy divergence.

**Simpler mitigation.** Version the snapshot schema and policy semantics separately. Every
event declares minimum reader version and required capabilities. An incompatible pod must
stay unready before advancing its cursor. Use expand/migrate/contract releases; never make a
restrictive default change in the same rollout that first introduces its field.

**Executable oracle.** Run N-1 and N pods together against the same outbox while applying
every security-relevant mutation. Either both produce the same decision vector, or N-1
rejects the snapshot, does not advance its cursor, and leaves readiness. Then roll the
writer back and prove deterministic recovery.

**So what tomorrow?** Add semantic compatibility fields to the outbox/snapshot contract,
not merely a JSON/SQL schema version.

## Confirmed known risks versus discoveries

| Item | Status |
|---|---|
| `NOTIFY` loss/reconnect and Aurora listener behavior | Owner-acknowledged; §F6 adds the per-pod invisible-lag cascade and stop condition. |
| Need for atomic quota reservation and fallback reconciliation | Owner-acknowledged; §F2 confirms current admission is post-paid and shows HPA/fallback amplification. |
| Need for atomic snapshot swaps and mixed-version testing | Owner-acknowledged; §F3 and §F7 identify current piecemeal publication and semantic-version failure paths. |
| Separate Kubernetes liveness/readiness and avoid restart storms | Owner-acknowledged; §F4 ties the current single health endpoint to outbox/Aurora pressure. |
| Absolute local-counter overwrites from every pod | Discovery; current comments assume gossip will repair it, but gossip is not in the selected launch authority. |
| Routing-engine errors continuing with prior/default behavior | Discovery; no entitlement bypass is claimed, but cost/locality/reliability intent can be lost. |

## Priority recommendations

1. **P0, medium effort:** Replace absolute counter dumps with an idempotent Aurora
   reservation/settlement ledger. Expected benefit: makes budget claims true before scale.
2. **P0, low-medium effort:** Define separate liveness, readiness, startup, and security-
   freshness behavior before Helm work. Expected benefit: prevents a database incident from
   becoming a total restart storm.
3. **P0, medium effort:** Publish one immutable, versioned governance snapshot per pod.
   Expected benefit: eliminates hybrid authorization and explainability states.
4. **P1, low effort:** Make routing outcomes typed and define closed/open behavior by stage.
   Expected benefit: deterministic failure behavior and fewer cost/fallback cascades.
5. **P1, medium effort:** Add per-pod watermark/lease metrics and N-1/N semantic conformance.
   Expected benefit: detects the one bad pod that fleet averages hide.

## Assumptions ledger

- Aurora can sustain the measured reservation throughput after sharding; this must be
  falsified by benchmark rather than assumed.
- The gateway can estimate a conservative maximum charge before invocation. Requests with
  unknown upper bounds need an explicit cap or soft-budget classification.
- Kubernetes probes have not yet been fixed to `/health`; §F4 is conditional but should be
  resolved before charts encode it.
- Human MR approval substantially reduces malicious skill publication, but does not change
  runtime key, quota, routing, or database failure modes analyzed here.
- A five-second fail-closed lease is operationally acceptable for restrictive changes; the
  exact lease may differ inside the agreed 1-5 second range.

## Points of uncertainty

- Enterprise-only code may already provide gossip baselines or user-governance behavior not
  present in this OSS tree. The launch decision explicitly removes gossip as authority, so
  §F1 remains relevant unless a different atomic counter backend replaces these dumps.
- No outbox consumer exists yet in the inspected tree, so §F6 and §F7 are design-premortem
  findings rather than defects in committed product code.
- The health endpoint risk depends on Helm probe wiring. The code supplies no distinct
  endpoints, making accidental coupling likely but not yet proven.

## Verification performed

The focused command `go test ./...` was run from `plugins/governance`; it completed
successfully after the Go 1.26.4 toolchain and module dependencies were made available.
This verifies the current single-process governance suite, not the multi-pod or Aurora
properties above. None of the existing tests is evidence against §F1 or §F2 because they do
not place independent stores behind one concurrent database authority.

## Questions for the project owner

- Should the launch hard-budget oracle allow only the configured controlled overdraft, or
  also one maximum-size in-flight reservation per pod?
- When Aurora is unavailable but a snapshot is fresh, should ordinary model inference stay
  available while only new hard-budget work fails, or should all metered traffic fail closed?
- What is the maximum supported launch pod count and virtual-key count? Those values set the
  outbox polling, snapshot, connection, and high-water-mark benchmark matrix.

## Confidence: 0.93

Confidence is high because the two leading cascades follow directly from executable code
paths and absolute SQL update semantics. It would fall if an uninspected enterprise plugin
replaces—not supplements—the tracker and store for every launch request. Confidence in the
outbox and rolling-upgrade findings is lower because those components are planned rather
than implemented; their purpose is to constrain the implementation before those failure
modes become code.
