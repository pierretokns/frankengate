# MODE_OUTPUT_NTM_F7

Mode: Systems Thinking (F7)
Date: 2026-07-15
Scope: read-only planning analysis for internal enterprise Kubernetes launch with Aurora PostgreSQL, optional Redis, 1-5 second control-plane convergence, protected Git merge requests with mandatory human approval, and optional learning services outside the inference availability path.

## Thesis

Bifrost's launch risk is not one missing subsystem. It is a set of feedback loops whose control points currently cross layers: local pod state, best-effort plugins, provider fallback, MCP connection acquisition, stream materialization, privacy capture, and roadmap-level Aurora authority. The leverage point is to make every safety-critical loop measurable and authoritative at one boundary: mandatory request guards before side effects, Aurora-backed budget reservations before spend, immutable policy snapshots before routing and MCP, and privacy receipts before any durable evidence sink. The existing low-overhead Go inference/provider/plugin substrate should remain the fast path; evaluators, skill learning, replay, and advanced routing should observe or propose asynchronously, never decide availability inline.

Existing roadmap warnings are treated here as confirmed known risks. Findings below add system-loop structure, code evidence, severity calibration for this deployment, and next-day actions.

## Findings

### F7-01 — Mandatory policy is still coupled to best-effort plugin semantics

Status: confirmed known risk with code evidence
Severity: P0 critical for enterprise launch
Confidence: high

Evidence:

- `core/bifrost.go:4936-4958` (`handleRequest`) creates and runs the PreRequest plugin pipeline. `core/bifrost.go:4951-4955` says PreRequest plugin errors are non-blocking and skipped.
- `core/bifrost.go:7260-7285` (`PluginPipeline.RunPreLLMHooks`) logs PreLLMHook errors as warnings and appends them to span data; it does not return them as request denials.
- `core/bifrost.go:7447-7485` (`PluginPipeline.RunMCPPreHooks`) applies the same warning-only behavior to MCP pre-hooks.
- `core/schemas/plugin.go:193-198` documents that plugin errors are not returned to callers and that only response/error transformations are part of the hook contract.
- `core/schemas/plugin.go:283-294` documents PreRequestHook as non-blocking and says denial must be expressed later via short-circuit rather than returned errors.
- `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:43-45` already flags that the current governance plugin cannot be the mandatory reference monitor.
- Beads read-only: `bif-kyy.2.4` tracks separating mandatory request guards from best-effort plugin hooks.

Reasoning chain:

1. Enterprise launch requires fail-closed decisions for Okta entitlements, virtual keys, budget exhaustion, privacy eligibility, route eligibility, and MCP tool authorization.
2. The plugin pipeline is intentionally availability-preserving: hook failures are warnings, not request failures.
3. A failed policy lookup, corrupt snapshot, panic, or timeout in a plugin can therefore become "continue with missing policy" unless every plugin manually converts every failure into a short-circuit.
4. That creates a positive feedback loop: policy-system degradation reduces the amount of policy applied, which can increase unsafe provider/tool traffic, which then creates more evidence and reconciliation work under degraded conditions.

Measurable loop:

- Inputs: local policy snapshot age, guard evaluation result, guard fault class.
- Control action: allow, deny, degrade to metadata-only, or route to safe fallback.
- Output: upstream provider/tool calls and durable evidence entries.
- Required invariant: a mandatory guard fault must have `upstream_calls_total == 0` unless an explicitly documented stale-read fail-open policy applies.

Next-day action:

Draft a `MandatoryRequestGuard` contract separate from plugins and define a conformance test that injects panic, timeout, corrupt snapshot, stale snapshot, and missing Okta entitlement cases while proving zero provider calls and zero MCP credential/connection acquisition on deny.

### F7-02 — Budget enforcement is a local periodic-settlement loop, not a controlled-overdraft loop

Status: confirmed known risk with code evidence
Severity: P0 critical for virtual keys across pods
Confidence: high

Evidence:

- `plugins/governance/store.go:24-39` (`LocalGovernanceStore`) stores virtual keys, budgets, rate limits, providers, and routing rules in local `sync.Map` instances.
- `plugins/governance/tracker.go:65-70` sets the usage worker interval to 10 seconds and billed request TTL to 5 minutes.
- `plugins/governance/tracker.go:180-214` (`UsageTracker.UpdateUsage`) updates rate limits and budgets in local memory after usage is known.
- `plugins/governance/tracker.go:240-260` (`UsageTracker.resetExpiredCounters`) periodically resets and dumps local rate-limit and budget state.
- `plugins/governance/tracker.go:266-283` uses a local billed-request map keyed by `RequestID:AttemptNumber`.
- `plugins/governance/store.go:430-457` (`LocalGovernanceStore.BumpBudgetUsage`) increments local budget usage with a local compare-and-swap loop.
- `plugins/governance/store.go:2195-2264` (`LocalGovernanceStore.DumpBudgets`) writes current usage to the database, but deadlock handling logs and returns nil so usage is retried next cycle.
- `framework/configstore/tables/budget.go:10-17` (`TableBudget`) contains `max_limit`, `reset_duration`, `last_reset`, and `current_usage`; it has no reservation, overdraft, alert, fence token, or ledger fields.
- `docs/roadmap/technical-decision-options.md:232-237` already recommends Aurora atomic reservations plus a durable ledger, with controlled overdraft as explicit policy state.

Reasoning chain:

1. Shared virtual keys across pods require a cross-pod admission decision before spend, not only local post-hoc settlement.
2. The current code can track local usage accurately inside one process, but every pod can admit based on its own local view.
3. A 10-second dump cadence plus retry-on-deadlock-next-cycle is acceptable for observability, but it is not a controlled-overdraft mechanism.
4. Controlled overdraft needs an explicit policy loop: reserve budget, renew for long streams/agent trajectories, settle actual usage, refund failures, emit alert transitions, and block or degrade after policy-defined limits.

Measurable loop:

- Inputs: reservation request, remaining authorized spend, overdraft policy, alert threshold, provider cost estimate.
- Control action: reserve, reserve-with-overdraft, deny, degrade model/provider, or require approval.
- Output: ledger row, alert event, settlement/refund event, and immutable request receipt.
- Required invariant: fleet-wide admitted spend cannot exceed `limit + approved_overdraft` except by documented estimator error, and estimator error must be reconciled.

Next-day action:

Write a `CounterAuthority` and `BudgetReservationLedger` design note with `reserve`, `renew`, `settle`, `refund`, and `alert_transition` operations. Add a multi-pod Aurora test plan that simulates concurrent reservations, long streams, fallback attempts, deadlocks, and controlled overdraft.

### F7-03 — MCP governance currently happens after credential and connection side effects

Status: confirmed known risk with code evidence
Severity: P0 critical for MCP governance
Confidence: high

Evidence:

- `core/mcp/exec.go:75-91` (`MCPManager.executeToolWithHooks`) populates tool metadata and then calls `prepareToolExecution`; the comment says the plugin pipeline wraps only the actual call and is not invoked if connection acquisition fails.
- `core/mcp/exec.go:115-124` runs `RunWithPluginPipeline` only after preparation has returned an `executeToolFn`.
- `core/mcp/exec.go:133-190` (`MCPManager.prepareToolExecution`) resolves the tool, applies include filters, and calls `AcquireClientConn` at `core/mcp/exec.go:185`.
- `core/mcp/clientmanager.go:24-40` (`MCPManager.AcquireClientConn`) defines shared connection reuse and per-user ephemeral connection behavior.
- `core/mcp/clientmanager.go:47-52` returns a persistent shared connection without a release hook.
- `core/mcp/clientmanager.go:80-83` resolves authentication headers before starting the temporary per-user client.
- `core/mcp/clientmanager.go:119-149` starts and initializes a temporary MCP client for per-user connections.
- `docs/roadmap/mcp-tool-skill-governance-and-research.md:75-89` requires a governance membrane that normalizes tool calls, classifies action type, applies parameter ABAC, and issues short-lived scope-bound credentials.
- Beads read-only: `bif-bpfk.19` tracks refactoring MCP invocation so mandatory policy precedes credential and connection acquisition.

Reasoning chain:

1. MCP tools can create side effects outside the LLM provider path.
2. Credential resolution and connection establishment are already side effects, especially for per-user OAuth-backed tool calls.
3. Current mandatory-looking checks include disabled tools and include filters, but the plugin-based MCP policy gate runs after `AcquireClientConn`.
4. A denied MCP call therefore cannot prove "zero credentials, zero connections, zero upstream packets" if denial depends on PreMCPHook policy.

Measurable loop:

- Inputs: normalized tool target, tenant/user entitlement, action class, parameter classification, approval receipt.
- Control action: deny, require human approval, issue attenuated credential, or reuse allowed connection.
- Output: credential lease, connection acquisition, tool call, result classification.
- Required invariant: denied calls must have `credential_requests_total == 0`, `connections_opened_total == 0`, and `tool_wire_calls_total == 0`.

Next-day action:

Specify a pre-credential MCP authorization sequence: immutable tool manifest lookup, parameter normalization, mandatory policy check, approval check, credential attenuation, connection acquisition, wire call. Add a fake credential resolver/client test plan that asserts denied calls do not request credentials or open connections.

### F7-04 — Routing decisions are not yet reproducible enough for deterministic and advanced routing

Status: confirmed known risk with additional loop structure
Severity: P1 high
Confidence: medium-high

Evidence:

- `plugins/governance/main.go:471-651` (`GovernancePlugin.loadBalanceProvider`) performs provider filtering, weighted selection, and fallback construction.
- `plugins/governance/main.go:500-547` filters providers by blacklists, model allowance, budget, and rate-limit state.
- `plugins/governance/main.go:557-560` has a TODO to return a proper error when all providers are excluded by budgets or rate limits.
- `plugins/governance/main.go:580-595` selects a provider using a random value over total weights.
- `plugins/governance/main.go:619-645` appends weighted fallbacks sorted by weight when no fallback list already exists.
- `plugins/governance/routing.go:131-150` (`RoutingEngine.EvaluateRoutingRules`) refreshes budget and rate-limit status at each routing-chain step.
- `plugins/governance/routing.go:300-336` (`selectWeightedTarget`) uses random selection, including uniform random behavior for zero-weight targets.
- `docs/roadmap/gateway-feature-landscape.md:153-163` frames constraint-first routing as a launch requirement.
- Beads read-only: `bif-kyy.7.11` tracks simulating and bounding fleet-wide adaptive-routing oscillation.

Reasoning chain:

1. Launch needs deterministic routing for audit, replay, and incident reconstruction, while also supporting advanced routing.
2. The current path can choose randomly after filtering and can append fallbacks based on current weights.
3. If health, cost, budget, latency, or learned-routing signals change quickly, multiple pods can converge on the same "best" fallback target and overload it.
4. Without a routing decision receipt containing candidate set, route graph revision, random seed, health/circuit revision, budget snapshot revision, and fallback cause, the system can log what happened but not reliably replay why it happened.

Measurable loop:

- Inputs: eligible provider set, route graph revision, budget/rate snapshot, health/circuit state, random assignment seed.
- Control action: primary route, fallback list, probe cohort, or deny.
- Output: provider attempt sequence, latency/error/cost observations, next health/routing snapshot.
- Required invariant: the same request receipt plus same snapshot revisions must reproduce the same route decision offline.

Next-day action:

Define a `RoutingDecisionReceipt` with candidate set after governance filters, random seed or deterministic assignment key, policy revisions, health/circuit revisions, fallback cause, and route chain trace. Add an offline fleet simulator plan that reuses current routing functions to test 100-pod oscillation scenarios without changing production code.

### F7-05 — Privacy-safe evidence needs one pre-sink transform receipt, not per-sink content toggles

Status: confirmed known risk with code evidence
Severity: P1 high
Confidence: high

Evidence:

- `plugins/logging/main.go:612-637` (`LoggerPlugin.PreLLMHook`) creates a stream accumulator for stream requests.
- `plugins/logging/main.go:650-785` captures input messages, parameters, tools, and selected request-body content when content logging is enabled.
- `plugins/logging/main.go:824-839` stores captured input data in pending log entries for later post-hook processing.
- `plugins/logging/main.go:1075-1089` stores raw request and response data from errors when raw storage and content logging are enabled.
- `plugins/logging/main.go:1117-1147` backfills raw request and response data for streaming errors under the same conditions.
- `plugins/logging/main.go:1167-1169` stores passthrough response body when content logging is enabled.
- `plugins/logging/main.go:1331-1383` (`storeOrEnqueueEntry` and `Inject`) connects completed traces to durable log writes.
- `core/schemas/trace.go:11-24` (`Trace`) includes request headers, plugin logs, and redaction replacement state.
- `docs/roadmap/privacy-redaction-and-learning-boundaries.md:5-9` requires default metadata-only behavior and forbids raw production content from reaching logs, replay, evals, training, analytics, or external observability merely because it passed through the gateway.
- `docs/roadmap/privacy-redaction-and-learning-boundaries.md:18-32` requires classification before capture and fail-closed or metadata-only behavior on detector failure.
- `docs/roadmap/privacy-redaction-and-learning-boundaries.md:67-70` defines the needed `PrivacyTransformReceipt` shape.
- Beads read-only: `bif-bpfk.18` tracks privacy-gated evidence envelope and bounded durable outbox.

Reasoning chain:

1. Current logging is a sink; planned replay, evals, traces, skill promotion evidence, and analytics are additional sinks.
2. Per-sink toggles cannot prove that every durable copy passed through the same classification, redaction, purpose, retention, region, and deletion policy.
3. Streaming errors, passthrough bodies, request headers, plugin logs, and MCP arguments/results are all separate capture surfaces.
4. The system needs a single pre-sink evidence loop: classify, transform, receipt, durable envelope, sink delivery. Without it, downstream evals can accidentally become a second raw-content logging system.

Measurable loop:

- Inputs: content class, tenant policy, purpose, retention, region, sink type, detector health.
- Control action: metadata-only, redacted content, reject capture, or fail request when policy requires.
- Output: evidence envelope with transform receipt and deletion lineage.
- Required invariant: every durable evidence row and every exported trace/eval record has exactly one `PrivacyTransformReceipt` or an explicit metadata-only receipt.

Next-day action:

Write the `PrivacyTransformReceipt` schema and a sink inventory covering logs, traces, plugin logs, provider errors, MCP args/results, stream accumulators, passthrough bodies, evals, replay, and skill-promotion evidence. Define detector-failure behavior for each sink before implementing more capture.

### F7-06 — Stream materialization is a shared leverage point and a shared failure amplifier

Status: confirmed known risk with code evidence
Severity: P1 high
Confidence: medium-high

Evidence:

- `framework/streaming/accumulator.go:22-41` (`Accumulator`) keeps per-stream accumulator state in a `sync.Map`.
- `framework/streaming/accumulator.go:137-168` (`createStreamAccumulator`) allocates per-stream chunk slices and maps.
- `framework/streaming/accumulator.go:220-244` and `framework/streaming/accumulator.go:333-351` append streaming chunks to accumulator slices.
- `framework/streaming/accumulator.go:399-456` (`CleanupStream`) returns pooled slices and deletes per-stream state.
- `framework/streaming/accumulator.go:580-595` cleans old accumulators by TTL.
- `framework/streaming/accumulator.go:611-657` (`NewAccumulator`) defaults to a 30-minute TTL and 1-minute cleanup interval.
- `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:53` warns that full-response reconstruction multiplied by replay, PII, eval, shadow, and skill-learning consumers increases memory and sensitive-copy risk.
- `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:83-86` already points to a streaming content evidence manager with bounded capture.
- Beads read-only: `bif-cks.14` tracks bounding stream accumulation, capture fanout, and cancellation cleanup.

Reasoning chain:

1. The accumulator correctly keeps stream-sized data outside `BifrostContext`, which preserves the context boundary.
2. The same accumulator is also the natural place every future consumer will want full response materialization.
3. Additional consumers that each buffer their own copy create a multiplicative memory and privacy surface.
4. Even one central accumulator needs explicit byte budgets, downgrade behavior, cancellation cleanup, retained-byte metrics, and per-purpose capture controls because TTL alone is not a backpressure policy.

Measurable loop:

- Inputs: stream bytes, consumer registrations, cancellation/finalization events, privacy policy.
- Control action: keep full content, keep prefix plus digest, metadata-only downgrade, or abort capture.
- Output: retained bytes, dropped bytes, evidence receipts, cleanup latency.
- Required invariant: total retained stream bytes per request and per pod remain bounded by configured policy independent of stream duration.

Next-day action:

Define stream capture budgets per purpose: logging, trace, eval, replay, shadow, and debugging. Add required metrics for retained bytes, downgrade reason, cleanup latency, and consumers per stream. Decide whether the existing accumulator becomes the single bounded capture manager or whether a separate evidence manager consumes bounded snapshots.

### F7-07 — Control-plane convergence exists as a roadmap contract, but not yet as a testable state machine

Status: confirmed known risk and implementation-evidence gap
Severity: P1 high
Confidence: medium

Evidence:

- `plugins/governance/store.go:215-247` (`NewLocalGovernanceStore`) initializes governance state from a config store when available, otherwise from static config.
- `plugins/governance/store.go:2268-2285` (`LocalGovernanceStore.loadFromDatabase`) bulk-loads governance data from the database into local memory.
- `plugins/governance/main.go:180-212` (`NewGovernancePlugin`) uses a startup distributed lock for reset work; lock acquisition or reset failure is logged and treated as non-critical.
- `docs/roadmap/extreme-reliability-and-day2-operations.md:51-62` requires Aurora authority, transactional outbox, LISTEN/NOTIFY wakeup, cursor polling, monotonic checksummed snapshots, freshness leases, and fail-closed reductions.
- `docs/roadmap/extreme-reliability-and-day2-operations.md:64-73` requires new pods to remain unready until they have a verified snapshot and Aurora connectivity.
- `docs/roadmap/technical-decision-options.md:188-198` recommends Aurora authority, transactional outbox, cursor polling, atomic snapshot swap, freshness leases, PostgreSQL reservations/ledger, and optional Redis only as an accelerator.
- Beads read-only: `bif-kyy.6.7` tracks disconnected-auth semantics; `bif-cks.15` tracks migration ownership and compatibility manifests.

Reasoning chain:

1. The deployment can tolerate 1-5 second convergence, but each resource class must define what stale means.
2. Current inspected code shows local in-memory state loaded from database and some distributed lock usage, not a complete monotonic snapshot/outbox/freshness state machine.
3. Privilege increases, privilege reductions, budget reductions, route changes, MCP kill switches, and privacy-policy updates should not share one generic stale-cache behavior.
4. Without a state machine and test oracle, "eventual convergence" can hide unsafe transitions, especially during Aurora failover, pod churn, or notification loss.

Measurable loop:

- Inputs: Aurora transaction commit, outbox sequence, notification wakeup, cursor poll, snapshot checksum, local freshness lease.
- Control action: accept stale read, fail closed, fail open for availability-only feature, mark pod unready, or degrade feature.
- Output: effective policy revision on each pod, propagation latency, stale-deny/stale-allow counts.
- Required invariant: policy reductions for privilege, spend, privacy, and MCP authorization never increase access because of stale local state.

Next-day action:

Write a control-plane state machine with resource classes, revision monotonicity, stale behavior, readiness rules, and test cases for notification loss, Aurora failover, brand-new pod startup, revocation, budget reduction, routing graph update, and MCP kill switch.

### F7-08 — Human-approved skill promotion is protected, but evidence generation can still become a shadow authority

Status: deployment-specific coupling risk
Severity: P2 medium
Confidence: medium-high

Evidence:

- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:7-18` defines launch-mode promotion through draft patches or merge requests with human approval, and forbids autonomous merge or publication.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:27` says no component may evaluate, promote, or rewrite itself.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:36-57` defines evidence trust, holdouts, and overfit controls.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:141-149` keeps shadow/canary and promotion separate from direct publication.
- `docs/roadmap/MODES_ANALYSIS_PROGRESS.md:16-19` states that learning and eval services must remain optional async consumers and never enter the inference availability path.

Reasoning chain:

1. The user constraint correctly blocks autonomous promotion at launch.
2. However, if evidence generation, eval selection, and issue/MR drafting use untracked raw traces or biased samples, they can become a shadow authority that pressures humans with incomplete or unsafe evidence.
3. The safety loop is therefore not only "human approves merge"; it is "human receives evidence with provenance, holdouts, privacy receipts, and blast-radius labels."
4. Keeping proposal generation outside the inference path is necessary but not sufficient; evidence quality must be governed too.

Measurable loop:

- Inputs: sanitized evidence envelopes, holdout evaluation, route/model cohort, failure labels, human review outcome.
- Control action: draft issue, draft patch, draft merge request, reject proposal, or require more evidence.
- Output: approved merge, rejected proposal, follow-up issue, eval corpus update.
- Required invariant: no promotion proposal lacks evidence provenance, privacy receipt IDs, holdout status, and human approval state.

Next-day action:

Define a `PromotionEvidenceBundle` manifest for generated issues, patches, and draft MRs. Include evidence receipt IDs, policy revisions, holdout coverage, affected tenants/features, privacy receipt IDs, and explicit "not auto-mergeable" metadata.

## Cross-Layer Cascading Risks

1. Policy-plane degradation can become data-plane permissiveness if mandatory checks remain plugin-shaped.
2. Budget overspend can cascade through fallback: a failed provider attempt may consume tokens, then fallback attempts can consume more unless reservations are attempt-aware and settled by terminal state.
3. MCP denial after credential acquisition can leak authority even when the eventual tool call is blocked.
4. Routing health feedback can overload the next-best provider if many pods observe the same failure and re-route without jitter, hysteresis, or assignment receipts.
5. Stream accumulation can turn long-running requests into retained memory and retained sensitive content, especially when logs, evals, replay, and traces all subscribe.
6. Aurora failover or notification loss can create asymmetric pod behavior unless snapshot freshness has per-resource stale semantics.
7. Human approval can be undermined by low-quality or privacy-unsafe evidence bundles even if merge permissions are protected.

## Recommendations

### P0

1. Build a mandatory reference-monitor design before adding more governance features.
   Effort: small design spike, medium implementation. Define fail-closed guard semantics, panic/timeout behavior, stale snapshot behavior, and conformance tests proving zero side effects on deny.

2. Design Aurora-backed budget reservations and controlled overdraft as a ledger, not as periodic counter sync.
   Effort: medium design, large implementation. Include reserve, renew, settle, refund, alert transition, overdraft approval, long-stream fencing, and fallback-attempt accounting.

3. Refactor MCP authorization order on paper first: normalize, mandatory policy, approval, attenuated credential, connection, wire call.
   Effort: small design, medium implementation. Add fake credential and fake client tests before changing real transports.

### P1

4. Turn control-plane convergence into a state machine and test oracle.
   Effort: medium. Define resource classes, revision numbers, freshness leases, readiness, and stale behavior for privilege, spend, privacy, routing, MCP, and availability-only features.

5. Introduce decision receipts for routing, privacy, budget, MCP, and promotion evidence.
   Effort: medium. Receipts should be small, structured, and joinable from logs/evals/replay without requiring raw content.

6. Add a single privacy transform boundary before durable sinks.
   Effort: medium-large. Start with schema and sink inventory; then route logs, traces, evals, replay, MCP results, and provider errors through the same receipt model.

### P2

7. Bound stream capture by bytes, time, consumers, and purpose.
   Effort: medium. Add downgrade modes such as metadata-only, prefix-plus-digest, and disabled capture. Instrument retained bytes and cleanup latency.

8. Build a routing oscillation simulator before enabling learned or adaptive routing.
   Effort: small-medium. Use existing route filtering and selection code with synthetic pod fleets, health delays, budget changes, and provider failures.

9. Define operator-facing alert transitions for budgets, privacy downgrades, stale snapshots, MCP kill switches, and route instability.
   Effort: small. Alerts should fire on state transitions, not only raw metric thresholds.

### P3

10. Keep Redis as an optional accelerator behind an interface with Aurora as authority.
    Effort: medium. Use Redis only for latency reduction or burst smoothing, not as the sole source of revocation, spend, or entitlement truth.

11. Add chaos scenarios for Aurora failover, notification loss, stale Okta groups, MCP server drain, long-stream cancellation, and provider brownout.
    Effort: medium-large. These tests should assert system invariants, not only uptime.

### P4

12. Defer autonomous skill promotion and learned routing until receipts, holdouts, and human approval manifests are routine.
    Effort: small policy now, larger post-launch implementation. Launch should generate issues, patches, and draft MRs only.

## Alternatives And New Ideas

1. Authority DAG: every request carries a compact set of authority revisions: policy snapshot, Okta entitlement epoch, budget reservation ID, route graph revision, privacy policy revision, MCP catalog digest, and promotion evidence bundle ID where applicable.

2. Staleness budget table: define stale behavior per resource class. For example, privilege reductions fail closed, privilege increases wait for fresh state, budget reductions fail closed above prior limit, routing changes can use last known good, and analytics configs can lag.

3. Decision receipts as join keys: make receipts the durable join path across logs, traces, evals, replay, and draft MRs. This reduces pressure to copy raw content between systems.

4. Shadow routers inside the eligible set only: learned or experimental routers should only rank candidates after mandatory governance filters have produced the eligible set.

5. Provider fallback as a bounded state machine: represent fallback attempts as a deterministic attempt plan with per-attempt budget reservation, terminal state, and no silent failover after bytes are streamed.

6. Evidence quality budget: treat evidence capture capacity as a budget with overload behavior. Under stress, degrade to metadata and sampled receipts before affecting inference.

## Assumptions

1. Aurora PostgreSQL is the launch control-plane authority.
2. Redis may be used later but is not mandatory for launch.
3. Okta is the enterprise identity and entitlement source.
4. Human approval through protected Git merge requests is required for internal skill promotion.
5. Existing low-overhead provider and inference paths are a core product constraint.
6. Optional learning, eval, replay, and promotion services may observe asynchronously but must not be required for serving requests.
7. Live provider benchmark numbers were not assumed or invented.

## Questions

1. What maximum controlled-overdraft amount is acceptable per virtual key, team, customer, model, and time window?
2. Which policy reductions must fail closed during Aurora outage: Okta revocation, virtual-key revoke, budget reduction, route deny, MCP kill switch, privacy policy change?
3. What is the required revocation propagation target within the allowed 1-5 second convergence window?
4. Are MCP shared connections allowed for tools with user-scoped authority, or should all user-authorized tools use fenced per-user/per-call leases?
5. Which content classes may ever enter eval/replay datasets, and who owns retention and deletion for each class?
6. Should deterministic routing mean identical replay for the same request and snapshot, or only auditable explanation of the original decision?
7. What Aurora write throughput and transaction latency targets should budget reservations be designed against?

## Uncertainty

1. I did not run tests or benchmarks; this is read-only planning analysis.
2. I inspected representative Go code paths for governance, routing, MCP, logging, traces, streaming, and config storage, but not every provider or transport path.
3. Some enterprise-specific implementation may exist outside the inspected files or planned future branches.
4. Beads were read read-only and used as planning context, not edited.
5. Severity assumes shared internal enterprise virtual keys across multiple Kubernetes pods with real spend, Okta entitlements, MCP tools, and privacy obligations.

## Tensions

1. Low latency vs synchronous spend authority: budget reservation must be fast enough not to damage the data plane, but local-only counters cannot enforce fleet-wide controlled overdraft.
2. Availability vs fail-closed policy: privilege and spend reductions need conservative stale behavior, while provider brownout routing should preserve service where policy allows.
3. Rich eval traces vs privacy: the best learning signal is often the most sensitive content; launch should privilege receipts, metadata, and explicit retention over raw capture.
4. Deterministic routing vs adaptive routing: replayable decisions need stable inputs and seeds, while advanced routing wants fresh feedback.
5. Plugin compatibility vs mandatory governance: existing plugins are deliberately resilient and best-effort; mandatory enforcement needs a different contract without breaking optional plugin behavior.
6. Optional Redis vs operational simplicity: Redis can smooth hot counters and pub/sub latency, but adding it before Aurora authority is crisp can create split-brain semantics.

## Final Confidence

Overall confidence: high on the system-loop structure and the main launch leverage points; medium-high on code-evidence alignment; medium on completeness because this was a read-only pass over representative paths, not a full implementation audit. The highest-confidence conclusion is that mandatory governance, budget authority, MCP authorization ordering, privacy receipts, and bounded stream capture should be resolved as control-loop boundaries before adding advanced learning or adaptive routing into the operational surface.
