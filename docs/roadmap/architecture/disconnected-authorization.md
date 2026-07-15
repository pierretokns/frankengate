# ADR: Disconnected Authorization Semantics And Stale-Policy Kill Behavior

Status: Accepted for Aurora-backed Kubernetes launch planning

Date: 2026-07-15

Scope: Internal enterprise Bifrost deployment on Kubernetes with Aurora PostgreSQL as the durable control-plane authority.

## Decision

Use signed, versioned, immutable local authorization snapshots plus narrow signed capabilities for budget/pricing reservations. Do not use global fail-open and do not use global fail-closed.

The launch default is class-based:

- Additive changes may lag safely. Until a pod receives the new grant, it denies the newly allowed action.
- Restrictive changes, revocations, routing denials, MCP tool kill-switches, and privacy hardening fail stale-closed after a short signed security lease.
- Pricing and budget admission use signed reservations/capabilities rather than trusting stale price or counter state.
- Aurora unavailability freezes new authority mutations and reservation issuance, but does not stop already-authorized traffic while the relevant local lease remains valid.

The selected launch security lease for restrictive/revocation/tool-kill/privacy-hardening classes is 5 seconds maximum from Aurora commit to last stale authorization of a new protected action. This matches the accepted 1-5 second control-plane convergence target. If a pod cannot prove freshness inside that lease, it must stop starting protected provider attempts, MCP tool calls, and raw evidence capture until it refreshes or receives a higher-version rollback.

## Context

Bifrost's current serving shape is optimized for low overhead: hot-path governance reads are local and lock-free, provider calls are isolated behind queues, and plugin failures are generally best-effort. That is the right substrate for inference, but enterprise launch adds hard controls that must remain authoritative while pods are disconnected from Aurora, Okta, or peer notifications.

The launch problem is therefore not "should every request query Aurora." It should not. The problem is: when a pod has a stale local snapshot, which mutations can safely lag, which must fail closed, which can be represented as a bounded signed lease, and what exact window of unauthorized use or outage is accepted?

## Current Source Evidence

- Governance hot state is local: `LocalGovernanceStore` stores virtual keys, budgets, rate limits, providers, model configs, and routing rules in `sync.Map` fields (`plugins/governance/store.go:24-66`).
- Virtual-key validation reads local state: `GetVirtualKey` is a local map lookup (`plugins/governance/store.go:922-932`), and `EvaluateGovernanceRequest` trusts that store for key existence/revocation checks (`plugins/governance/main.go:927-943`).
- Process-local reloads mutate current in-memory state: `ReloadVirtualKey` loads from `ConfigStore` and then updates the governance store and MCP server in the current process (`transports/bifrost-http/server/server.go:384-449`); removal deletes from the current process store and MCP server (`transports/bifrost-http/server/server.go:452-470`).
- The `ConfigStore` interface owns governance CRUD, budgets, routing rules, pricing, and transactions (`framework/configstore/store.go:288-436`), but this interface is CRUD-oriented and does not by itself define a versioned pod snapshot, outbox cursor, or stale-lease contract.
- Generic plugin errors are not hard denials: plugin docs state errors are logged and not returned to callers (`core/schemas/plugin.go:192-198`), and `PreRequestHook` errors cannot abort a request (`core/schemas/plugin.go:283-297`). The runtime logs `PreLLMHook` and `PreRequestHook` errors and continues (`core/bifrost.go:7253-7297`, `core/bifrost.go:7300-7345`).
- Governance hard denial currently depends on explicit short-circuit behavior: `PreLLMHook` converts `EvaluateGovernanceRequest` denials into `LLMPluginShortCircuit` (`plugins/governance/main.go:1271-1310`).
- Routing errors currently degrade to no routing decision: `applyRoutingRules` logs an engine error and returns `nil, nil` (`plugins/governance/main.go:743-749`), while successful decisions mutate provider, model, fallbacks, and key pinning (`plugins/governance/main.go:756-793`).
- Pricing is response/usage driven: cost calculation resolves pricing after usage is available (`framework/modelcatalog/datasheet/cost.go:13-68`, `framework/modelcatalog/datasheet/cost.go:169-214`), and governance usage updates apply costs asynchronously after provider attempts (`plugins/governance/main.go:1322-1389`, `plugins/governance/tracker.go:91-214`).
- MCP execution acquires an upstream connection before the plugin gate: `executeToolWithHooks` calls `prepareToolExecution` before `RunWithPluginPipeline` (`core/mcp/exec.go:85-124`), and nested code-mode tool execution mirrors this ordering (`core/mcp/codemode/starlark/executecode.go:471-488`).
- Privacy/logging can capture sensitive data when enabled: logging headers and `x-bf-lh-*` metadata are copied from request context (`plugins/logging/main.go:547-595`), content logging can capture inputs, tools, params, and passthrough bodies (`plugins/logging/main.go:650-786`), and stream accumulation retains per-request chunks in manager state (`framework/streaming/accumulator.go:135-210`, `framework/streaming/accumulator.go:212-252`, `framework/streaming/accumulator.go:333-364`).
- Launch roadmap already selects Aurora authority, local immutable snapshots, notification hints plus polling, and no per-request Aurora/Okta/Git dependency (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:3-10`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:52-73`).

## Terms

- Authority revision: a monotonically increasing Aurora-committed revision for one tenant/control-plane partition.
- Security lease: a signed freshness claim for a local snapshot and mutation class. It expires quickly for hard-deny classes.
- Capability: a signed narrow grant for one purpose, such as a budget reservation, emergency deny overlay, or approved overdraft allowance.
- New protected action: a new provider attempt, fallback attempt, MCP connection/tool invocation, raw evidence capture, or skill/proposal side effect. An already-started provider call may need separate cancellation semantics.
- Stale-closed: if the pod cannot prove the class-specific lease is fresh, it denies or degrades to the safe mode.

## Options Considered

### Option A - Fail Open On Last Known Snapshot

Behavior: keep using the last validated snapshot indefinitely when Aurora, Okta, or notification delivery is unavailable.

Benefits:

- Highest inference availability.
- Preserves the current hot-path shape.
- Simple operational story during brief Aurora outages.

Costs:

- Revoked virtual keys, removed Okta entitlements, MCP tool kills, privacy hardening, and restrictive routing can remain ineffective indefinitely on a disconnected pod.
- A single lagging pod can violate policy while fleet-level metrics look healthy.
- It cannot provide a decision-grade unauthorized-use bound.

Use at launch:

- Only for additive lag where the old state is more restrictive than the new state.
- Never for revocation, restrictive entitlement, MCP tool kill, privacy hardening, or hard budget/routing denial.

### Option B - Fail Closed On Any Control-Plane Disconnection

Behavior: deny protected traffic whenever the pod cannot contact Aurora or validate latest authority state.

Benefits:

- Minimizes stale authorization.
- Easy to explain to security reviewers.
- Avoids subtle per-class policy mistakes.

Costs:

- Turns transient Aurora/network/Okta problems into inference outages.
- Violates the launch goal that Aurora unavailability freezes admin changes rather than the data plane.
- Creates restart and retry amplification if paired with aggressive Kubernetes probes.

Use at launch:

- As a local fallback after a class-specific security lease expires.
- Not as the global disconnected behavior.

### Option C - Signed Leases And Capabilities Over Immutable Snapshots

Behavior: pods serve from the last validated signed snapshot while its class-specific leases are valid. High-risk classes have short security leases. Budget/pricing admission uses narrow reservations. Notifications are hints; polling/high-water checks are the correctness backstop.

Benefits:

- Preserves local hot-path reads.
- Gives explicit unauthorized-use and outage windows.
- Lets additive changes lag without exposing unauthorized access.
- Avoids per-request Aurora lookups.
- Supports emergency deny overlays and audited rollbacks.

Costs:

- Requires versioned snapshot build/swap, lease validation, cursor/high-water metrics, and conformance tests.
- Requires a separate reservation/capability path for budgets/pricing.
- Requires careful long-running stream/tool/agent kill checkpoints.

Use at launch:

- Selected default.

## Mutation Classification

| Mutation class | Examples | Stale risk | Selected disconnected behavior | Unauthorized-use window | Outage/false-deny window |
|---|---|---|---|---|---|
| Additive | New group grant, new model allow, new provider allow, new MCP tool allow, budget increase, raw evidence approval | Old state denies something now allowed | Safe to lag. Continue using old restrictive snapshot until a higher signed revision applies. | 0 for unauthorized use; stale state is more restrictive. | Until convergence; target p99 <= 5 seconds. If Aurora remains unavailable, the new grant is unavailable until refresh. |
| Restrictive | Remove model/provider/group/team/customer access, lower budget, lower rate limit, disable fallback, remove API key pin | Old state allows something now denied or narrowed | Stale-closed after security lease. Before lease expiry, old snapshot may start new actions. | <= 5 seconds for new protected actions after Aurora commit. | After lease expiry during outage, affected protected traffic is denied until refresh or rollback. |
| Revocation | Revoke virtual key, deactivate user, disable team/customer, burn temp token, emergency deny subject | Old state authenticates a dead identity | Stale-closed after security lease; emergency deny overlay can be an independently signed higher-priority capability. | <= 5 seconds for new protected actions; already-started provider attempts run only to the next configured kill checkpoint or operation deadline. | Revoked subjects denied. If rollback is needed, issue a new higher-version grant or key rather than reusing stale authority. |
| Pricing | Model price increase/decrease, pricing override, cost multiplier, billing tier, data-residency multiplier | Stale price can under-reserve, over-admit, or over-deny | Use signed reservation capabilities with price_version and max_cost/max_tokens. No new hard-budget admission without reservation authority except explicit overdraft capability. | Financial exposure, not access exposure: bounded by sum(outstanding reservation caps) + approved overdraft + already-started attempts that cannot be preempted. | If Aurora reservation authority is unavailable and local reservation bucket is exhausted, hard-budget traffic is denied until authority returns or an overdraft capability is issued. |
| Routing | Provider/model route change, fallback list, region/locality rule, canary cohort, key pin | Old route can violate locality, cost, provider health, or canary intent | Treat restrictive routing and no-eligible-provider as hard policy. Additive route improvements may lag. Routing engine errors are typed, not "no decision." | <= 5 seconds when old route is now forbidden; 0 when new route is purely additive. | Restrictive-route lease expiry can deny traffic until refresh. Additive route improvement lag only delays the new path. |
| Tool kill | Disable MCP client, remove MCP tool grant, kill server, disable wildcard, revoke per-user OAuth grant | Old state can expose or invoke a killed tool | Same as revocation, but authorization must occur before MCP connection acquisition. Discovery narrowing is not sufficient. | <= 5 seconds for new tool invocations and zero connection acquisition after local kill applies. Existing tool calls run only to timeout/cancellation semantics. | Killed tools remain unavailable until higher-version rollback/regrant. |
| Privacy | Disable raw logging, tighten redaction, remove dataset approval, delete/retention hold, prohibit evidence sink | Old state may persist raw or derived sensitive content | Privacy hardening stale-closes to metadata-only. Additive raw-capture approvals may lag. Any uncertain privacy revision degrades to metadata-only/drop. | <= 5 seconds for new raw/derived capture after Aurora commit; already-persisted raw content requires deletion lineage, not rollback. | Raw/eval/proposal capture may be unavailable until refresh; inference continues with metadata-only/drop. |

## Window Definitions

For a committed mutation at Aurora time `T0`:

- `T_detect`: time until a pod observes a newer authority revision by notification, polling, or high-water check.
- `T_apply`: time to fetch, validate, and publish a complete immutable snapshot.
- `T_security`: class-specific maximum age of a stale snapshot for hard-deny classes. Launch default: 5 seconds.
- `T_kill_check`: the next boundary where a long-running operation rechecks authority, such as before provider I/O, before fallback, before MCP acquisition, before tool call, before raw capture, at stream chunk interception, or at agent turn boundary.
- `T_operation`: remaining duration of an already-started provider/tool operation that cannot be preempted cleanly.

For new protected actions:

```text
unauthorized_new_action_window = min(T_detect + T_apply, T_security)
launch maximum for hard-deny classes = 5 seconds
```

For already-started operations:

```text
residual_exposure = min(T_operation, time_to_next_kill_check + cancellation_latency)
```

If a request class has no configured operation deadline or kill checkpoint, its residual exposure is unbounded. That is not acceptable for revocation, tool-kill, or privacy-hardening launch paths. Long-running streams and agent loops must therefore have kill checkpoints before fallback, before each MCP acquisition/tool call, and at stream chunk boundaries where practical.

For pricing/budget:

```text
financial_exposure = sum(unsettled_reservation_caps)
                   + approved_overdraft_cap
                   + cost_of_started_attempts_that_cannot_be_preempted
```

This is a cap-based exposure, not a time-only exposure. A pricing or budget design is not launch-ready unless this expression is computable from durable reservation rows and alerts.

## SLOs

### Initialization

- A pod serves zero protected requests before it has loaded and validated an initial signed authority snapshot.
- A pod without an initial snapshot is not ready.

### Convergence

- Additive mutation convergence: p99 pod apply time <= 5 seconds. Failure mode is false-deny of the new grant.
- Restrictive, revocation, routing-deny, tool-kill, and privacy-hardening convergence: p99 pod apply time <= 5 seconds, with a hard local stale-closed lease of <= 5 seconds.
- Per-pod lag is measured and alerted by maximum pod lag, not only fleet percentile.

### Disconnected Serving

- With a fresh signed snapshot, Aurora write/read outage must not stop already-authorized inference.
- After the class-specific security lease expires, protected traffic for that class fails closed until refresh.
- Optional sinks, evals, proposal generation, and logging backends never extend the serving lease and never block inference.

### Budget And Pricing

- Hard-budget admission requires an unexpired reservation capability or a configured overdraft capability.
- No new hard-budget reservation is issued from stale pricing/counter state.
- Duplicate settlements are idempotent by request/attempt identity.
- Overdraft alerting fires on first use of an overdraft capability and on exhaustion of reservation authority.

### MCP

- A denied or stale-killed MCP tool invocation performs zero upstream connection acquisition, zero credential refresh, zero packets, and zero tool calls after local kill applies.
- Discovery filtering and execution filtering must agree, but execution-time authorization is the authority.

### Privacy

- Unknown, stale, or failed privacy policy degrades to metadata-only/drop, not raw capture.
- Raw or derived evidence has a privacy revision, purpose, retention/deletion lineage, and sink identifier.

## Failure Oracles

These are acceptance tests for the ADR, not implementation suggestions.

1. Additive grant oracle: start two pods, grant a new model or tool, block notifications to one pod. The lagging pod may continue denying the new access, but must never allow anything not previously allowed. It converges within 5 seconds when polling is available.
2. Restrictive mutation oracle: remove a model/provider/group grant. Block notification to one pod. The isolated pod must stop starting new now-denied provider attempts within 5 seconds of Aurora commit or fail protected traffic stale-closed.
3. Virtual-key revocation oracle: revoke a virtual key while one pod misses notifications. Within 5 seconds, every pod either denies that key or marks the protected class stale-closed. A restarted pod with an old cursor must not resurrect the key.
4. Pricing reservation oracle: increase a model price and exhaust a hard budget while Aurora reservation issuance is unavailable. Existing unexpired reservations may settle, but no new hard-budget admission occurs without a signed overdraft capability. Durable exposure must equal the reservation formula above.
5. Routing oracle: inject invalid CEL/routing rule, missing model-catalog entry, no eligible provider, and invalid key pin. The result must be an explicit typed denial or deterministic degraded route. It must not silently continue as "no decision" for restrictive policies.
6. Tool-kill oracle: kill an MCP client/tool grant and invoke it by direct name and by nested code-mode call. After local kill applies, acquisition, credential refresh, outbound packets, and `CallTool` count are all zero.
7. Privacy oracle: commit a policy that disables raw logging/evidence for a tenant. After at most 5 seconds, new requests from that tenant produce only metadata-only/drop envelopes. Existing raw rows must be covered by deletion lineage, not hidden by rollback.
8. Aurora outage oracle: with fresh snapshots, block Aurora and assert already-authorized inference continues. After the restrictive security lease expires, protected new actions fail closed. Restore Aurora and assert snapshots advance monotonically without manual pod restart.
9. Rollback oracle: apply restrictive revision `N`, then rollback with higher revision `N+1`. Pods must not accept older revision `N-1`; rollback is a new signed event, not a clock rewind.

## Rollback Semantics

Rollback always moves authority forward. Pods reject lower or duplicate revisions after they have applied a higher one.

- Additive rollback is restrictive: removing the newly granted permission uses the restrictive class and stale-closes after the security lease.
- Restrictive rollback is additive: restoring access may lag; false-deny is acceptable until the higher revision applies.
- Virtual-key revocation rollback should issue a new key or new higher-version grant. Do not rely on old revoked tokens becoming valid again on stale pods.
- Pricing rollback creates a new `price_version`. Existing reservations settle against the version they were issued with; future reservations use the higher rollback version.
- Routing rollback creates a new routing-policy revision. Requests carry the route revision used for audit and cost attribution.
- Tool-kill rollback creates a new grant revision. Until applied, the tool remains killed.
- Privacy rollback cannot undo already-persisted raw content. It creates a new privacy revision for future capture and must preserve deletion/retention lineage for prior rows.

## Required Architecture Shape

1. Authority rows are committed in Aurora inside a transaction with an authority revision and outbox event.
2. Notifications carry only invalidation metadata, such as tenant, kind, and revision.
3. Pods poll or listen, fetch committed state, build a complete immutable snapshot off-path, validate signatures/foreign keys/revision monotonicity, and publish with one atomic swap.
4. The request path reads only the current local snapshot/capability set.
5. Mandatory decisions return typed results. Ordinary plugin errors and "no decision" cannot authorize hard controls.
6. Budget/pricing capabilities are narrow: tenant, actor/key, model/provider/request type, reservation cap, price_version, request/attempt id, expiry, and overdraft policy.
7. Emergency deny overlays are signed, higher-priority capabilities with the same monotonic revision discipline.
8. Long-running operations check kill state at explicit boundaries.

## Consequences

Positive:

- Preserves low-overhead Go serving and avoids per-request Aurora/Okta lookups.
- Provides bounded, reviewable unauthorized-use windows.
- Keeps optional learning/eval/proposal services out of the availability path.
- Gives operators concrete lag, lease, and rollback metrics.

Negative:

- Requires a real snapshot/outbox/capability implementation before enterprise launch.
- Requires test harnesses that simulate lagging pods, missed notifications, stale cursors, and Aurora outage.
- Requires refactoring MCP execution order so hard denials happen before upstream acquisition.
- Requires routing and privacy decisions to become typed mandatory outcomes rather than best-effort plugin behavior.

## Selected Default Summary

Default launch posture:

- Additive: fail closed to the old state until applied.
- Restrictive/revocation/routing-deny/tool-kill/privacy-hardening: allow stale only inside a signed lease, maximum 5 seconds, then fail closed.
- Pricing/budget: require signed reservation capability; stale pricing cannot issue new hard-budget admission.
- Privacy uncertainty: metadata-only/drop.
- Aurora outage: freeze admin changes, continue fresh-snapshot serving, stale-close protected classes at lease expiry.
- Rollback: always a higher signed revision.

This ADR intentionally accepts a small bounded stale window to avoid making Aurora part of every inference request. It rejects unbounded fail-open behavior and rejects global fail-closed behavior that would turn every control-plane interruption into a data-plane outage.
