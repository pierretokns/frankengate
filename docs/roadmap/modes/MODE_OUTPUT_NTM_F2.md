# Dependency Mapping F2 - Enterprise Kubernetes/Aurora Launch

Date: 2026-07-15
Mode: Dependency Mapping (F2)
Scope: read-only planning analysis; product code, Beads, and shared roadmap documents were not edited.

## Thesis

The launch-critical dependency spine is not "add enterprise features to the existing plugin surface." It is:

```text
mandatory reference-monitor seam
  -> versioned principal/entitlement/key/grant schemas
  -> Aurora mutation authority plus outbox/snapshot freshness
  -> fenced budget reservations and overdraft receipts
  -> deterministic eligibility sets for routing, fallbacks and MCP invocation
  -> privacy-gated evidence export and human Git/MR skill proposals
```

The existing Go substrate should remain the low-overhead inference/provider/plugin data plane. Mandatory controls cannot inherit best-effort plugin failure semantics, and optional learning/evaluation/skill services must stay async consumers outside the serving availability path.

Existing roadmap warnings are treated as confirmed known risks. This report flags true prerequisites, hidden coupling and Beads graph defects relative to the stated internal Kubernetes/Aurora deployment.

## Findings

### F2-01 - Mandatory controls currently sit on a best-effort plugin seam

Evidence:
- `core/schemas/plugin.go:172-188` documents `PreRequestHook` once per request and `PreLLMHook`/`PostLLMHook` once per provider attempt.
- `core/schemas/plugin.go:192-204` documents that plugin errors are not returned to callers, and `AllowFallbacks = nil` allows fallbacks by default.
- `core/schemas/plugin.go:283-294` states `PreRequestHook` errors are non-blocking and cannot abort a request.
- `core/bifrost.go:7253-7297` logs `PreLLMHook` errors as warnings and continues unless the plugin returns a short circuit.
- `core/bifrost.go:7300-7340` logs `PreRequestHook` errors as warnings and continues to later plugins.
- `plugins/governance/main.go:1184-1269` implements routing/MCP include-tool stamping in governance `PreRequestHook`; invalid or expired VKs at `1203-1209` return `nil`, deferring denial to later phases.
- `plugins/governance/main.go:1271-1310` performs governance denial via `PreLLMHook` short circuit.
- Roadmap baseline: `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:41-45` already identifies generic plugin errors as fail-open and unsuitable for auth, entitlement, quota, privacy and invocation authorization.

Reasoning chain:
1. Launch requirements include virtual keys across pods, Okta entitlements, budgets, MCP governance and privacy eligibility.
2. These are mandatory controls: on error or ambiguous freshness they must deny, degrade to metadata-only, or use a typed safe state.
3. Current plugin error semantics are correct for telemetry and optional enrichers but unsafe as the only admission membrane.
4. `PreLLMHook` short-circuit can deny, but it is per-attempt and wrapped by fallback semantics; `PreRequestHook` is the correct once-per-logical-request routing phase but cannot deny by error.
5. Therefore `bif-kyy.2.4` is a true launch gate for enterprise control behavior, not a cleanup task.

Severity: Critical for this deployment. A revoked principal, stale entitlement or unavailable policy source must not degrade into a provider call.

Confidence: High.

Next-day action: Write the reference-monitor contract and call-site sketch before provider queueing and before MCP credential/connection acquisition. Include typed dispositions: `allow`, `deny`, `metadata_only`, `defer_unavailable`, `fail_stale`. Convert mandatory plugin responsibilities into adapters behind that seam.

### F2-02 - Controlled overdraft depends on fenced Aurora reservations, not post-hook accounting

Evidence:
- `plugins/governance/tracker.go:91-123` updates usage after the provider attempt, with terminal idempotency keyed by request ID and attempt number.
- `plugins/governance/tracker.go:124-215` mutates provider/model/user/VK counters in memory after usage is known.
- `plugins/governance/main.go:1322-1388` launches usage tracking asynchronously in a goroutine from `PostLLMHook`.
- `plugins/governance/tracker.go:240-264` periodically resets and dumps counters.
- `plugins/governance/store.go:2104-2192` dumps rate-limit usage by direct database updates from local in-memory state.
- `plugins/governance/store.go:2194-2264` dumps budget usage by direct database updates from local in-memory state.
- `plugins/governance/store.go:24-40` defines the local store as `sync.Map` caches for VKs, budgets, rate limits, providers and routing rules.
- `docs/roadmap/technical-decision-options.md:210-236` selects Aurora PostgreSQL atomic reservations plus durable ledger for launch, with Redis only as an optional accelerator.
- Beads: `bif-kyy.4.1` says reserve estimates before upstream work; `bif-kyy.4.9` covers fenced renewable reservations for long streams and agent trajectories.

Reasoning chain:
1. Controlled overdraft is allowed only by explicit approval or preconfigured policy, with audit and alerts.
2. Current accounting is settlement-after-the-fact and local-first. It can explain usage, but it is not an admission-time spend fence across pods.
3. Routing can only use budget state safely after a reservation authority has returned an idempotent reservation or denial.
4. Long streams and agent trajectories need renewable leases and settlement epochs; a single post-hook settlement cannot prove bounded overspend during pod loss or tool-loop fanout.
5. The launch dependency is a `CounterAuthority`/reservation ledger before provider I/O, routing rankers, fallback fanout and overdraft UI.

Severity: Critical. Budget breaches are accepted only when they are policy states, not race margins.

Confidence: High.

Next-day action: Define reservation API shape: estimate, reserve, renew, settle, refund, overdraft receipt, alert event, idempotency key and attempt epoch. Add invariants for primary/fallback/shadow/tool/replay accounting. Make routing consume reservation receipts, not mutable local usage.

### F2-03 - Cross-pod convergence needs mutation/outbox/snapshot freshness before key, entitlement, routing and MCP grant work

Evidence:
- `plugins/governance/store.go:218-248` loads governance data from database or config memory at store initialization.
- `framework/configstore/postgres.go:21-72` opens a migration pool, runs migrations, then swaps to a runtime pool; this is database access infrastructure, not a mutation publication protocol.
- `plugins/governance/store.go:2968-3155` (read during analysis) implements in-memory VK create/update paths that preserve local usage.
- `docs/roadmap/technical-decision-options.md:42-54` states the requirements: atomic mutation/publication, monotonic revisions, bounded revocation, durable recovery and fail-closed freshness.
- `docs/roadmap/technical-decision-options.md:54-78` selects Aurora transactional outbox plus polling as the default for configuration, key lifecycle, entitlements, route policy and capability revisions.
- `docs/roadmap/technical-decision-options.md:187-198` summarizes the proposed hybrid: Aurora authority, same-transaction outbox, optional `LISTEN/NOTIFY`, immutable local snapshot swaps and freshness leases.
- `docs/roadmap/mcp-tool-skill-governance-and-research.md:95-101` applies the same outbox/cursor/snapshot pattern to MCP registry and grants.
- Beads: `bif-kyy.6.4` selects cross-pod propagation; `bif-kyy.6.7` defines disconnected/stale-policy semantics; `bif-kyy.6.8` defines outbox cursor lifecycle.

Reasoning chain:
1. The deployment accepts 1-5 second convergence, not synchronous global reads on every request.
2. That requires every ready pod to prove which authority revision it is serving.
3. Initial database load plus local mutation helpers do not prove monotonic catch-up, poison-event recovery, cold-start readiness or revocation freshness.
4. VK lifecycle, Okta entitlement changes, route-policy edits and MCP grants all consume the same substrate.
5. Therefore outbox/snapshot/freshness semantics are prerequisites, not implementation details under each feature.

Severity: High to Critical. The exact severity depends on stale-policy disposition, but revocation and restrictive policy changes are Critical until `bif-kyy.6.7` is decided.

Confidence: High.

Next-day action: Write a launch ADR for resource revisions, tenant snapshot manifests, cursor leases, poison events, cold-start readiness and stale-policy kill behavior. Then add explicit graph edges from this substrate to VK mutations, Okta entitlement compiler output, routing-policy mutations, MCP grants and revocation tests.

### F2-04 - Routing must split hard eligibility from ranking; current load balancing can silently continue on empty eligibility

Evidence:
- `plugins/governance/main.go:520-548` filters provider configs by model allowance, provider budget and provider rate limit.
- `plugins/governance/main.go:557-561` logs "No eligible providers remaining" but returns `nil`, continuing without modification.
- `plugins/governance/main.go:571-645` does weighted selection and auto-populates fallback providers from weighted configs.
- `core/bifrost.go:4951-4958` runs `PreRequestHook` once, then all downstream provider attempts observe the mutated provider/model/fallbacks.
- `core/bifrost.go:5000-5057` iterates configured fallbacks after primary failure.
- `docs/roadmap/technical-decision-options.md:314-318` requires hard filters to run before learned/semantic scorers.
- Tests read: `plugins/governance/routing_test.go` covers scope, priority, pinned-key and routing-rule behavior; it does not replace the need for cross-pod hard-policy monotonicity around fallbacks and reservations.

Reasoning chain:
1. Routing has two roles: enforce "may use" and optimize "best to use".
2. Learned, semantic, adaptive and health-aware routing can only rank candidates already allowed by identity, capability, privacy, residency, budget reservation and kill-switch policy.
3. Current load balancing blends eligibility filtering and selection, and the empty-eligible case is explicitly TODO/fail-open to the original request shape.
4. Fallbacks are constructed from weighted configs and later executed by core. Without a durable `EligibleCandidateSet` receipt, later fallback/adaptive layers can reintroduce a denied candidate.
5. Deterministic routing, canaries, shadows and advanced ranking must depend on the hard eligibility set, not vice versa.

Severity: High. Misrouting can be unauthorized model/provider use, not just bad quality or cost.

Confidence: Medium-High.

Next-day action: Split `EligibilitySet` from `Ranker`. Make empty eligible set a fail-closed denial with reasons. Attach policy revision, pricing revision, reservation ID and allowed provider/model/key set to a decision receipt. Add tests that fallback, shadow and adaptive routes are monotonic subsets of the eligible set.

### F2-05 - MCP mandatory policy currently runs after credential/connection acquisition

Evidence:
- `core/mcp/exec.go:52-62` describes `executeToolWithHooks`.
- `core/mcp/exec.go:85-91` explicitly says the upstream client is resolved and its connection acquired before the plugin gate runs; if acquisition fails, the plugin gate is never invoked.
- `core/mcp/exec.go:133-190` filters client/tool request context and then calls `AcquireClientConn` at `185`.
- `plugins/governance/main.go:1400-1487` performs MCP execution governance in `PreMCPHook`, including VK validation and tool allow-list checks.
- `plugins/governance/main.go:1570-1587` says `PreMCPConnectionHook` only populates identity; budget, rate limit and tool allow-list checks stay on `PreMCPHook` for `CallTool`.
- Beads: `bif-bpfk.19` acceptance criteria require policy before attenuated credential, connection and wire call; it currently depends on `bif-kyy.15.18` and `bif-kyy.2.4`.

Reasoning chain:
1. MCP tools can carry stronger side effects than LLM provider calls.
2. For denied or ambiguous executions, the system must prove zero credentials issued, zero connection acquired and zero upstream packets sent.
3. Current execution order cannot prove that property because credential/connection acquisition happens before the governance plugin gate.
4. Stateful connection ownership/failover (`bif-kyy.15.18`) is important, but the policy-before-credential invariant must be extracted as a prerequisite to all MCP execution paths and evidence consumers.

Severity: Critical for MCP-enabled internal agents.

Confidence: High.

Next-day action: Refactor the MCP path into: normalize immutable target, load signed catalog/tool digest, mandatory policy, attenuated credential, connection, wire call, terminal receipt. Add a zero-side-effect denial test around credential resolver, connection acquisition and transport call.

### F2-06 - Privacy-safe traces/evals require sanitized copies and a bounded evidence outbox before learning consumers

Evidence:
- `core/schemas/trace.go:11-24` trace objects hold attributes, request headers and plugin logs.
- `core/schemas/trace.go:81-86` stores captured request headers on the trace.
- `core/schemas/trace.go:151-202` `SnapshotForExport` clones maps for race safety but copies attribute values by reference and requires read-only treatment at `165`.
- `framework/tracing/tracer.go:259-307` copies input message content onto the LLM/root span for observability.
- `plugins/logging/main.go:39-63` `UpdateLogData` can carry `RawRequest` and `RawResponse`.
- `plugins/logging/main.go:650-785` records input histories, params, tools and passthrough JSON body when content logging is enabled.
- `plugins/logging/main.go:1426-1488` logs MCP tool name and arguments metadata path for MCP tool execution.
- `plugins/logging/operations.go:288-301`, `349-355`, `457-473` and `557-570` persist raw request/response fields when enabled.
- `framework/logstore/tables.go:165-205` log rows include input/output histories, params, tools, raw request/response, passthrough bodies, routing logs and plugin logs.
- `framework/logstore/hybrid_test.go:795-830` confirms summaries can retain content even when payload fields are offloaded; `844-878` confirms raw fields can remain in DB when excluded from object storage.
- Beads: `bif-bpfk.18` defines `EvidenceEnvelopeBuilder` plus bounded outbox; `bif-kyy.16.5` defines sanitized-copy boundaries.

Reasoning chain:
1. The existing trace/logging surfaces are appropriate observability substrates, but they are not automatically safe evidence or eval substrates.
2. Snapshotting for exporter race safety is not privacy transformation.
3. Logs may include raw bodies, input histories, summaries, params, tools, MCP arguments and plugin logs depending on settings.
4. Learning services, replay, evals and skill proposals must consume transformed, purpose-scoped copies with receipts, not the mutable trace/log objects directly.
5. The bounded outbox is also an availability dependency: inference must not wait on evidence persistence or downstream consumers.

Severity: High. It is a launch blocker for privacy-safe evals/proposals, but not for serving if evidence consumers are disabled.

Confidence: High.

Next-day action: Define `EvidenceEnvelopeBuilder` as the only bridge from trace/log/MCP data to eval/proposal services. It should deep-copy, allowlist, redact/pseudonymize, produce `PrivacyTransformReceipt`, enforce byte/event budgets and choose metadata-only/drop/quarantine without blocking inference.

### F2-07 - Beads graph has no structural cycles, but it still encodes wrong launch priorities and missing gates

Evidence:
- `br dep cycles --json` returned zero cycles.
- `bv --robot-insights` reported cycle count zero, but its longest path runs through skill marketplace/flywheel tasks: `bif-kyy.1.1 -> ... -> bif-kyy.15.10 -> bif-kyy.15.13 -> bif-kyy.15.15 -> bif-kyy.15.16`.
- `bv --robot-insights` ranks `bif-kyy.8.1`, `bif-kyy.16.5`, `bif-kyy.2.1`, `bif-kyy.7.1` and `bif-kyy.4.1` as top bottlenecks; it also marks `bif-kyy.2.4`, `bif-kyy.6.7`, `bif-kyy.6.8`, `bif-kyy.4.9` and `bif-kyy.15.18` as important authority/keystone/orphan-like nodes.
- `docs/roadmap/modes/MODE_OUTPUT_F2_H4.md:106-166` already records confirmed graph edits, including removing `bif-kyy.5.3 -> bif-kyy.5.2`, removing `bif-kyy.5.4 -> bif-kyy.3.2`, removing `bif-kyy.6.1 -> bif-kyy.3.2` and `bif-kyy.6.1 -> bif-kyy.4.1`, removing `bif-kyy.4.6 -> bif-kyy.5.4`, splitting `bif-kyy.7.1`, removing `bif-kyy.7.3 -> bif-kyy.7.2`, adding outbox/snapshot/reservation/eligibility prerequisites, and reframing `bif-kyy.15.10`.
- `docs/roadmap/MODES_ANALYSIS_PROGRESS.md:46` says not to expand launch scope back into autonomous marketplace promotion.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:7-18` says Git/MR plus human approval is the launch promotion authority; autonomous promotion, bandits, recall and employee analytics are post-launch.
- Beads read-only checks: `bif-kyy.4.6` still depends on `bif-kyy.5.4`; `bif-bpfk.19` depends on stateful MCP failover though the policy-before-credential invariant is a smaller earlier gate; `bif-bpfk.7` correctly depends on `bif-bpfk.18` but should not pull autonomous promotion controls into launch.

Reasoning chain:
1. The graph is a DAG, so the issue is semantic dependency accuracy, not cycle breaking.
2. Confirmed wrong edges still matter because they can put substrate work behind consumers or keep post-launch controls on the launch path.
3. New launch gates from this pass are: reference monitor before consumers, reservation ledger before budgets/routing, outbox/snapshot freshness before cross-pod policy consumers, and MCP policy-before-credential before MCP evidence/skill proposal work.
4. Heavy autonomous Flywheel controls should remain optional until the human Git/MR path is insufficient.

Severity: Medium-High. The graph will not break builds, but it can mis-sequence the launch plan and waste the scarce early critical path.

Confidence: High.

Next-day action: Apply graph edits only after human approval: remove confirmed inverted edges, add missing gates, split overbroad tasks, and mark autonomous promotion/recall/analytics as post-launch unless a concrete internal threat requires them.

## Risks

- Fail-open control risk: mandatory enterprise controls inherit plugin warning/continue behavior.
- Overspend risk: local post-hook accounting cannot bound cross-pod budget races or long-running streams without reservations.
- Stale-authority risk: pod-local snapshots without freshness leases can serve revoked keys, reduced entitlements or killed MCP tools.
- Routing blast radius: fallback/adaptive logic can select candidates outside the intended hard policy set unless eligibility is a first-class receipt.
- MCP side-effect risk: denied calls can still acquire credentials/connections before policy unless execution order changes.
- Privacy propagation risk: traces/logs/summaries/raw fields can feed evals or skill proposals without a distinct privacy receipt.
- Scope risk: autonomous Flywheel work can consume launch path despite the human Git/MR promotion constraint.

## Recommendations

P0:
- Build the mandatory reference-monitor seam and typed dispositions. Effort: 2-4 engineer-days for ADR, call-site sketch and first conformance tests; more to migrate all consumers.
- Define and prototype Aurora fenced reservation ledger for spend/RPM/TPM/concurrency. Effort: 1-2 engineer-weeks for minimal SQL authority, receipt model and failure tests.
- Define cross-pod mutation/outbox/snapshot freshness contract. Effort: 3-5 engineer-days for ADR and schema; 1-2 engineer-weeks for a first working consumer.
- Refactor MCP invocation ordering so mandatory policy precedes credential and connection acquisition. Effort: 3-5 engineer-days plus sequence-conformance tests.

P1:
- Split routing into `EligibilitySet` and `Ranker`, and fail closed on empty eligibility. Effort: 3-5 engineer-days.
- Implement `EvidenceEnvelopeBuilder` and bounded durable outbox as the only eval/proposal bridge. Effort: 1-2 engineer-weeks, depending on privacy scanner depth.
- Specify canonical principal/linking and entitlement compiler semantics for Okta/OIDC/SCIM. Effort: 3-5 engineer-days for contract; implementation depends on Okta integration scope.

P2:
- Add cross-pod revocation, reservation, fallback monotonicity and stale-policy conformance tests. Effort: 1 engineer-week for a minimal three-pod harness after P0 contracts.
- Unify migration ownership/compatibility manifests across config, log, evidence and governance tables. Effort: 3-5 engineer-days for plan plus incremental implementation.

P3:
- Add optional Redis `CounterAuthority` adapter only after Aurora contention measurements justify it. Effort: unknown until launch load shape is measured.
- Build health/adaptive routing simulations after deterministic eligibility and reservation receipts exist. Effort: 3-5 engineer-days for simulator scaffolding.

P4:
- Keep autonomous skill promotion, distributed recall, large-scale fuzz campaigns, contextual bandits and employee analytics post-launch. Effort: intentionally deferred.

## Wrong or Missing Beads Dependencies

Do not apply automatically; these are dependency recommendations for human review.

- Confirmed wrong edge: remove `bif-kyy.4.6 -> bif-kyy.5.4`. Controlled overdraft needs principal/approval policy plus budget algebra/reservation, not full Okta group-to-model mapping.
- Confirmed wrong edge: remove `bif-kyy.5.3 -> bif-kyy.5.2`. Directory importer and inbound SCIM both depend on canonical identity/linking, not on each other.
- Confirmed wrong edge: remove `bif-kyy.5.4 -> bif-kyy.3.2` as a blanket dependency. Managed key issuance depends on entitlement compilation; generic key lifecycle should not.
- Confirmed wrong edge: remove `bif-kyy.6.1 -> bif-kyy.3.2` and `bif-kyy.6.1 -> bif-kyy.4.1`. Cluster propagation is substrate; key and quota products should depend on its contracts.
- Confirmed wrong edge: remove `bif-kyy.7.3 -> bif-kyy.7.2` for deterministic canary assignment. Adaptive circuits are not required for basic deterministic rollout.
- Missing edge: make `bif-kyy.2.4` block VK lifecycle enforcement, Okta entitlement enforcement, budget admission, routing policy pipeline, MCP invocation policy and privacy eligibility sinks.
- Missing edge: make `bif-kyy.6.7` stale/disconnected semantics precede acceptance of revocation tests, restrictive entitlement changes, MCP kill-switch behavior and route-policy reductions.
- Missing edge: make outbox/snapshot freshness (`bif-kyy.6.4`, `bif-kyy.6.8`, plus snapshot compiler/readiness gate) block key mutations, entitlement compiler publication, routing-policy mutations and MCP grant publication.
- Missing edge: make fenced reservation primitives (`bif-kyy.4.1`, `bif-kyy.4.4`, `bif-kyy.4.5`, `bif-kyy.4.7`, `bif-kyy.4.9`) block controlled overdraft, routing admission and cross-pod budget tests.
- Missing/split edge: extract the policy-before-credential invariant from `bif-bpfk.19` so it blocks MCP evidence/proposal consumers and stateful connection failover work; `bif-kyy.15.18` should not be required before proving denied MCP calls issue no credentials.
- Scope correction: keep `bif-bpfk.14/.15/.16/.17/.21/.22/.23/.25/.26` out of the launch critical path unless human Git/MR controls are explicitly deemed insufficient.
- Scope correction: reframe `bif-kyy.15.10` as pre-merge validation and post-merge SHA pin/revert, not gateway-owned promotion authority.

## Alternatives and New Ideas

- Treat the reference monitor as a small local decision engine fed by immutable snapshots, not as a remote service on the hot path.
- Use a `DecisionReceipt` envelope shared by LLM routing, MCP invocation and evidence export. It should carry policy revision, candidate set, denial reasons, reservation ID and privacy eligibility.
- Use `CounterAuthority` as an interface with Aurora launch implementation and Redis as an optional later adapter.
- Represent MCP tools with signed catalog snapshots containing client ID, tool name, schema digest, risk class and grant revision. Tool execution policy should bind to this digest.
- Keep evidence as an append-only sanitized event stream with rebuildable indexes. Search/vector/eval stores are derived products, not authority.
- Add a "no upstream effect" conformance harness for denied controls: no provider request, no MCP credential, no MCP connection, no evidence with raw content.

## Assumptions

- The deployment remains internal Kubernetes backed by Aurora PostgreSQL.
- Redis is optional and cannot be required for launch correctness.
- 1-5 second control-plane convergence is acceptable if stale-policy behavior is explicit and tested.
- Human-protected Git merge requests remain the only launch promotion authority for internal skills.
- Enterprise-only code not present in this workspace may add mechanisms, but the visible OSS/plugin seams remain relevant because they define the shared substrate and integration points.
- This pass was read-only except for this output file; no product code, Beads or shared roadmap files were edited.

## Questions

- For stale restrictive updates, should pods fail closed immediately after freshness lease expiry, or allow a bounded grace window for availability?
- Which budgets are hard launch blockers: dollar spend only, RPM/TPM, concurrent in-flight requests, or all of them?
- Are MCP tools classified by side-effect level at launch, or is every tool treated as high-risk until proven otherwise?
- Should controlled overdraft approval be synchronous in-product only, or can preconfigured team/user policy grant automatic overdraft within a cap?
- What is the minimum privacy transform acceptable for internal research traces: metadata-only by default, pseudonymized content, or content only for explicit opt-in cohorts?

## Uncertainty

- I did not run runtime tests; this is a planning/dependency pass.
- Aurora contention and propagation behavior require measurement. This report does not invent throughput or latency numbers.
- Some enterprise functionality may live outside the visible repo. Findings are based on shared Go substrate and roadmap/Beads state available in this workspace.
- Exact implementation effort depends on whether current governance/plugin code is adapted behind new interfaces or replaced in enterprise modules.

## Tensions

- Availability versus revocation: fail-closed stale policy protects security but can amplify Aurora/control-plane incidents.
- Low overhead versus strong counters: a durable reservation ledger adds writes; the design must keep inference reads local and make the write path bounded and measured.
- Determinism versus optimization: advanced routing should not enter until hard eligibility is monotonic and auditable.
- Evidence quality versus privacy: useful evals want rich content, but launch safety requires purpose-scoped transformed copies and deletion lineage.
- Fast internal skill improvement versus human authority: proposal automation is acceptable; merge/publish automation is intentionally post-launch.

## Final Confidence

Overall confidence: High.

The strongest conclusions are the ordering constraints around the reference monitor, reservations, outbox/snapshots, MCP policy-before-credential and privacy-gated evidence. The lower-confidence area is implementation effort, because enterprise-only modules may already contain partial substrate not visible in this workspace.
