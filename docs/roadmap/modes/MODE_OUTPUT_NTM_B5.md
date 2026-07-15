# NTM B5 Option Generation: Enterprise Kubernetes/Aurora Launch

## Thesis

Launch should keep Bifrost's Go inference/provider/plugin substrate as the hot path, and add a narrow enterprise control plane around it: Aurora as durable authority, immutable per-pod snapshots for request-time reads, explicit mandatory gates for entitlement/budget/MCP authorization, and asynchronous privacy-filtered evidence. Redis, learning services, evaluators, semantic routers, skill improvement workers, and Git proposal generators can exist only behind adapters that never enter inference availability.

The simplest credible launch architecture is not a rewrite or a distributed-service expansion. It is a versioned authority/snapshot layer plus a small set of hard reference-monitor decisions that ordinary best-effort plugins cannot safely represent.

Existing roadmap warnings are treated here as confirmed known risks, not discoveries. Beads read-only cross-check agrees that the active launch blockers are already tracked around mandatory guards (`bif-kyy.2.4`), stale-policy/outbox (`bif-kyy.6.7`, `bif-kyy.6.8`), reservations (`bif-kyy.4.9`), MCP ordering (`bif-bpfk.19`), privacy evidence (`bif-bpfk.18`), deprovisioning (`bif-kyy.5.6`), stream capture bounds (`bif-cks.14`), routing oscillation (`bif-kyy.7.11`), and cross-module migrations (`bif-cks.15`).

## Confirmed Known Risk Baseline

- Roadmap owner constraints already accept 1-5 second revocation/policy convergence, controlled overdraft only through approval or preconfigured policy plus alerts/audit, Aurora-not-Redis as launch authority, Kubernetes-only launch, and no shared filesystem requirement (`docs/roadmap/technical-decision-options.md:6-26`).
- Roadmap requires immutable local request-path snapshots and no per-request Aurora, Okta, peer, Redis, dashboard, or evaluator dependency (`docs/roadmap/extreme-reliability-and-day2-operations.md:35-45`).
- Roadmap already selects Aurora transactional outbox plus `LISTEN/NOTIFY` as a candidate, with polling repair and measured failover/convergence evidence still required (`docs/roadmap/technical-decision-options.md:79-99`, `docs/roadmap/technical-decision-options.md:200-208`).
- Roadmap already says generic plugin errors fail open and enterprise reference-monitor functions cannot inherit that contract (`docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:41-46`).
- Roadmap already prohibits raw-production-content-by-default learning, replay, eval, logging, external observability, and cross-team analytics (`docs/roadmap/privacy-redaction-and-learning-boundaries.md:3-31`).

## Findings

### B5-F01 Mandatory Enterprise Gates Need A Separate Contract

Evidence:
- `PluginPipeline.RunLLMPreHooks` records plugin errors, logs warnings, and continues unless the plugin returns a short-circuit (`core/bifrost.go:7253-7297`).
- `PluginPipeline.RunPreRequestHooks` explicitly has no short-circuit and treats errors as non-blocking (`core/bifrost.go:7300-7338`).
- Governance authorization currently lives in `GovernancePlugin.PreLLMHook`, which can short-circuit denials but still sits inside the ordinary plugin path (`plugins/governance/main.go:1271-1309`).

Reasoning chain: Internal enterprise launch requires Okta entitlements, virtual-key revocation, spend denial, and MCP invocation authorization to fail closed on indeterminate state. The current plugin substrate is intentionally tolerant for observability/enrichment. Hardening every plugin would damage extensibility; leaving mandatory gates as regular plugins makes plugin registration/order/misconfiguration part of the reference monitor.

Options and decision tests:
- Option A: Add a typed mandatory guard phase before provider/MCP I/O, with dispositions `allow`, `deny`, `metadata_only`, `stale_fail_closed`, and `stale_allow_bounded`. Decision test: a deliberately panicking optional plugin cannot turn an authorization denial into a provider call.
- Option B: Keep governance as the only mandatory plugin but add boot-time validation, non-skippable registration, and conformance tests around short-circuit behavior. Decision test: every HTTP, SDK, streaming, fallback, and MCP path must prove the governance plugin ran exactly where expected.
- Option C: Enforce at HTTP transport only and disable direct SDK paths for enterprise deployment. Decision test: no in-process caller can bypass HTTP transport in production.

Severity: P0 launch-blocking for this deployment because it controls entitlements, revocation, and budget denial.

Confidence: High.

Next-day action: Draft the minimal guard interface and path matrix, then write failing conformance tests that force all inference, stream, fallback, and MCP execution paths through it before any provider/tool side effect.

### B5-F02 Shared Budgets Need Reservations, Not Periodic Per-Pod Dumps

Evidence:
- `UsageTracker` keeps terminal idempotency in a process-local `billed` map (`plugins/governance/tracker.go:42-70`) and updates usage asynchronously from `PostLLMHook` goroutines (`plugins/governance/main.go:1322-1388`).
- Budget/rate increments are CAS-safe only inside one process-local store (`plugins/governance/store.go:411-520`).
- The reset worker periodically dumps in-memory counters to the database every worker tick, logging persistence failures (`plugins/governance/tracker.go:217-264`).
- `DumpBudgets` and `DumpRateLimits` directly overwrite usage fields from current local memory and treat deadlocks as retry-next-cycle conditions (`plugins/governance/store.go:2104-2264`).
- Launch acceptance requires simultaneous requests not exceeding a hard shared budget beyond the documented reservation bound (`docs/roadmap/enterprise-oss-program.md:382-389`).

Reasoning chain: Current accounting is good for local bookkeeping and eventual persistence, but it is not a hard cross-pod admission control. Controlled overdraft is acceptable, but only if the bound is designed, audited, alerted, and tested. Periodic dumps also do not provide a durable reservation receipt before provider spend occurs.

Options and decision tests:
- Option A: Aurora-backed reservation ledger with idempotent reservation IDs, short leases, hierarchical/time-bucket sharding, and post-attempt settlement. Decision test: under concurrent pods and injected crashes, accepted spend never exceeds configured limit beyond the calculated outstanding reservations.
- Option B: Pod-local escrow allocations replenished from Aurora. Decision test: maximum overrun equals sum of active escrows plus in-flight reservations, and emergency reductions shrink future allocations within the convergence SLO.
- Option C: Optional Redis atomic counters behind a `CounterAuthority` adapter. Decision test: only choose if Aurora reservations fail measured contention/failover tests and Redis is accepted as an operational dependency, which is not launch default.

Severity: P0 launch-blocking for hard budgets; P1 for soft telemetry-only budgets.

Confidence: High.

Next-day action: Specify `budget_reservations` and `budget_ledger` semantics, including idempotency key, lease expiry, reconciliation, overdraft policy ID, alert receipt, and fail-open/closed behavior per budget class.

### B5-F03 Control-Plane Convergence Should Extend Current Local Reloads Into Versioned Snapshots

Evidence:
- HTTP governance handlers mutate Aurora through `ExecuteTransaction` for virtual-key create/update (`transports/bifrost-http/handlers/governance.go:1322-1459`, `transports/bifrost-http/handlers/governance.go:1562-1620`) and then call the local `GovernanceManager.ReloadVirtualKey` callback (`transports/bifrost-http/handlers/governance.go:1459-1463`, `transports/bifrost-http/handlers/governance.go:1923-1930`).
- Routing-rule create/update/delete similarly write the database and then reload or remove only through the local manager callback (`transports/bifrost-http/handlers/governance.go:4065-4074`, `transports/bifrost-http/handlers/governance.go:4174-4183`, `transports/bifrost-http/handlers/governance.go:4196-4209`).
- The roadmap requires mutation and publication to be atomic, pods to observe monotonic revisions, and request-time reads to be lock-free local snapshots (`docs/roadmap/technical-decision-options.md:42-53`).
- A tight source search found no implemented PostgreSQL `LISTEN`, `NOTIFY`, `pg_notify`, or domain `outbox` in `framework/configstore`, `transports/bifrost-http`, `plugins/governance`, or `core`.

Reasoning chain: The code already has the right in-pod shape, but multi-pod launch cannot rely on “admin request hit this pod.” The next step should not add database reads to inference; it should turn DB mutations into versioned, replayable snapshot invalidations consumed by every pod.

Options and decision tests:
- Option A: Transactional outbox plus polling only. Decision test: revocation/policy reductions converge within the accepted 1-5 second target at expected pod count and control-change rate.
- Option B: Transactional outbox plus `LISTEN/NOTIFY` wakeup and polling repair. Decision test: Aurora failover, listener reconnect, notification loss, and long partition catch-up all preserve monotonic revisions.
- Option C: Redis Streams/gossip/file snapshots as adapters only. Decision test: reject for launch unless Aurora-native propagation is proven insufficient and the operational owner accepts the new dependency/failure mode.

Severity: P0 for cross-pod virtual keys, revocation, Okta group removal, and routing policy; P1 for dashboard freshness.

Confidence: High.

Next-day action: Write the domain outbox ADR and first migration sketch: resource type, resource ID, tenant/scope, monotonic revision, checksum, tombstone, producer transaction pattern, consumer cursor, readiness/freshness lease, and rollback rejection.

### B5-F04 Routing Should Start Deterministic; Probabilistic/Adaptive Routing Needs Guardrails

Evidence:
- Routing rules implement scope precedence and chained reevaluation with a max depth (`plugins/governance/routing.go:79-150`).
- Routing-rule compile/eval errors are logged and the rule is skipped (`plugins/governance/routing.go:202-218`).
- Matched routing rules select weighted targets (`plugins/governance/routing.go:229-240`), and governance load balancing uses `rand.Float64` for weighted provider selection (`plugins/governance/main.go:580-599`).
- If no eligible weighted provider remains, load balancing currently logs and returns without a hard denial (`plugins/governance/main.go:557-577`).
- Routing targets are modeled as weighted probabilities (`framework/configstore/tables/routingrules.go:97-108`).

Reasoning chain: Weighted routing is useful for canarying and traffic distribution, but deterministic authorization/cost/residency decisions must be explainable and reproducible. Random primary selection also complicates replay, budget reservation, Bedrock destination evidence, and incident analysis unless the chosen route and policy revision are captured.

Options and decision tests:
- Option A: Deterministic ordered policy for launch: scope, entitlement, model alias, provider health, cost ceiling, region/profile, then existing fallback list. Decision test: identical request plus same snapshot revision produces identical primary/fallback decision.
- Option B: Stable-hash weighted cohorts for canary/shadow after P0 gates. Decision test: cohort assignment is deterministic by tenant/request key and cannot cross entitlement/budget boundaries.
- Option C: Online adaptive/semantic/bandit routing as an asynchronous recommendation service only. Decision test: it may propose route-policy changes or draft MRs, but the gateway never waits on it and it cannot change live routing without protected human approval.

Severity: P1 for launch correctness and auditability; P0 if routing is used for data residency, model entitlement, or hard spend controls.

Confidence: Medium-high.

Next-day action: Define a route-decision receipt schema with request class, policy revision, selected provider/model/key, fallback order, budget reservation ID, health input revision, Bedrock inference-profile/destination evidence, and deterministic seed/cohort only when weighted routing is enabled.

### B5-F05 MCP Execution Governance Must Move Before Upstream Connection Acquisition

Evidence:
- `MCPManager.executeToolWithHooks` resolves the upstream client and acquires its connection before the execute-tool plugin gate; the comment states the plugin gate is never invoked when `AcquireClientConn` fails (`core/mcp/exec.go:85-103`).
- `prepareToolExecution` performs discovery/filter checks and then calls `AcquireClientConn` (`core/mcp/exec.go:144-190`).
- `AcquireClientConn` may create a fresh per-call ephemeral upstream connection, with credential headers resolved after the connect-plugin gate (`core/mcp/clientmanager.go:24-105`).
- Governance's `PreMCPHook` performs the execution-time VK/tool allow-list check, but it runs after the pre-acquisition path above (`plugins/governance/main.go:1400-1488`).
- The roadmap already lists MCP ordering and stateful in-process ownership as known risks (`docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:67-73`).

Reasoning chain: Even though current code protects bearer-token visibility from plugins, enterprise MCP governance wants policy to precede credential/connection acquisition. A denied or deprovisioned user should not cause a fresh upstream connection, auth challenge, or ambiguous side-effect window before the mandatory gate has run.

Options and decision tests:
- Option A: Split MCP prepare into `resolveToolIdentityAndPolicyInputs` before the mandatory gate, then `AcquireClientConn` only after allow. Decision test: denied tool calls never open per-user MCP connections and never resolve user credentials.
- Option B: Launch MCP with static shared clients and explicit allow-lists only, while deferring per-user OAuth execution. Decision test: no per-user credential path exists in launch traffic.
- Option C: Separate stateful MCP connection-owner service with sticky ownership and explicit ambiguous-completion ledger. Decision test: choose only if launch tools require durable sessions that cannot tolerate reconnect/duplicate ambiguity.

Severity: P0 for MCP tools that can mutate internal systems or expose privileged data; P1 for read-only discovery-only tools.

Confidence: High.

Next-day action: Create the pre-acquisition MCP policy test: inactive VK, removed Okta group, and disallowed tool all fail before `AcquireClientConn` can be called.

### B5-F06 Privacy-Safe Traces/Evals Need A New Evidence Envelope, Not Direct Log/Trace Reuse

Evidence:
- Trace spans can store tool-call arguments and full tool-call results (`core/mcp/pluginpipeline.go:64-99`).
- Trace redaction is replacement-map based over classified content attributes (`core/schemas/trace.go:88-127`, `core/schemas/trace.go:238-277`).
- Streaming finalization can carry output messages, token usage, raw response, and raw request into an accumulator result (`framework/tracing/tracer.go:620-666`).
- Observability export happens asynchronously after applying replacements and snapshotting the trace (`framework/tracing/tracer.go:699-756`).
- The log table model includes structured histories, tool calls, raw request/response, passthrough bodies, summaries, plugin logs, and redaction mapping fields (`framework/logstore/tables.go:165-213`).
- The logging plugin has content-logging gates and error raw-byte sanitization, but content logging is enabled unless disabled by config (`plugins/logging/main.go:122-157`).
- Roadmap invariant says raw production content must not enter logs, replay, evals, skill improvement, training, cross-team analytics, or external observability merely because it traversed the gateway (`docs/roadmap/privacy-redaction-and-learning-boundaries.md:3-31`).

Reasoning chain: Current logging/tracing surfaces are useful operational internals, not privacy-reviewed learning inputs. Reusing them directly for evals or skill proposals risks accidental raw-content propagation, especially through tool arguments/results and streaming accumulation. The enterprise seam should emit an explicit privacy receipt and sanitized envelope, with raw vault access as a separate approved workflow.

Options and decision tests:
- Option A: New `AgentEvidenceEnvelope` built from sanitized trace/log snapshots after policy classification, with metadata-only default and bounded queues. Decision test: sink backpressure degrades to metadata/drop and never retains request pools or stream buffers.
- Option B: Enterprise logstore wrapper as the only evidence source. Decision test: accepted only if every content field, summary, embedding, tool result, and error detail carries a privacy transform receipt and deletion lineage.
- Option C: Encrypted raw replay vault for named investigations/evals. Decision test: raw access requires purpose, retention, region, owner, access receipt, and independent output re-scan.

Severity: P0 for privacy/compliance and skill-promotion safety; P1 for ordinary ops traces if metadata-only by default.

Confidence: High.

Next-day action: Define `PrivacyTransformReceipt` and `AgentEvidenceEnvelope` fields, plus a sink failure policy: `metadata_only`, `drop`, or `fail_closed_for_capture` without blocking inference.

### B5-F07 Okta Entitlements Need An Enterprise Identity Snapshot, Because User-Level Store Methods Are No-Ops Here

Evidence:
- `PreLLMHook` and `PreMCPHook` read `BifrostContextKeyUserID` and pass it into governance evaluation (`plugins/governance/main.go:1286-1301`, `plugins/governance/main.go:1418-1431`).
- Community `LocalGovernanceStore.CheckUserBudget` and `CheckUserRateLimit` return allow with comments that they are enterprise-only no-ops (`plugins/governance/store.go:1587-1591`, `plugins/governance/store.go:1660-1664`).
- Community `UpdateUserBudgetUsageInMemory` and `UpdateUserRateLimitUsageInMemory` also no-op (`plugins/governance/store.go:1732-1736`, `plugins/governance/store.go:1830-1834`).
- Launch acceptance requires group removal to remove model visibility and invocation rights consistently (`docs/roadmap/enterprise-oss-program.md:382-389`).

Reasoning chain: Okta identity can be a request-authentication source, but per-request Okta lookups violate the availability model. The missing enterprise piece is a reconciled identity/entitlement snapshot: users, groups, deprovisioning epoch, policy mapping, and freshness leases, all locally readable by the mandatory guard.

Options and decision tests:
- Option A: SCIM/Okta API reconciler writes identity and membership authority rows; pods consume them through the same outbox/snapshot channel. Decision test: group removal changes `/v1/models`, inference, and MCP execution decisions under the convergence SLO without querying Okta per request.
- Option B: OIDC token claims as request input plus local policy snapshot. Decision test: accepted only if token TTL and claim completeness satisfy deprovisioning policy; otherwise it is authentication context, not authority.
- Option C: Live Okta group lookup per request. Decision test: reject for launch because Okta outage/throttling would enter inference availability.

Severity: P0 for entitlement correctness and deprovisioning.

Confidence: High.

Next-day action: Draft identity snapshot schema: subject ID, Okta user ID, group IDs, access profile IDs, deprovisioned-at epoch, policy revision, source cursor, freshness lease, and emergency deny overlay.

## Risks

- A hard gate bolted into the wrong layer could duplicate provider/MCP routing logic and increase bypass risk. Keep it narrow: evaluate authority, return disposition, and leave provider execution to existing core paths.
- Aurora outbox can become a second under-tested subsystem. Treat `NOTIFY` as a wakeup only, require cursor replay, and run failover/partition tests before approval.
- Budget reservation design can understate overdraft if streaming, retries, fallbacks, cancellation races, and MCP tools are not modeled as physical attempts.
- Deterministic routing can become too rigid if health signals are ignored. Health should be an input snapshot with hysteresis, not an online learner in the path.
- Privacy wrappers can create a false sense of safety if summaries, embeddings, evaluator rationales, and skill patches are not treated as derived sensitive content.
- Protected Git human approval is a launch invariant; any shortcut for skill publishing creates a governance and audit breach.

## P0-P4 Recommendations With Effort

- P0, L: Implement the mandatory guard phase for virtual-key auth, Okta entitlement, hard budget reservation, privacy eligibility, and MCP invocation authorization. Start with conformance tests before code paths are changed.
- P0, L: Add Aurora domain outbox, snapshot revisions, consumer cursors, freshness leases, and readiness gates for virtual keys, routing rules, identity/entitlements, MCP grants, and emergency deny overlays.
- P0, L: Design and implement budget/rate reservation ledger with controlled overdraft policy, alert/audit receipt, settlement, reconciliation, and crash recovery.
- P0, M: Move MCP execution policy ahead of credential and connection acquisition; add tests proving denied calls do not open per-user connections.
- P0, M: Define privacy receipts and `AgentEvidenceEnvelope`; route flywheel/eval/skill proposal consumers through bounded async sinks only.
- P1, M: Replace launch routing randomness for authority-bearing routes with deterministic ordered policy; preserve weighted/stable-hash canary as an explicit non-default mode.
- P1, M: Implement Okta identity reconciler and deprovisioning epoch snapshots; keep OIDC claims as input, not sole authority.
- P2, M: Add route-decision, budget-reservation, privacy, and snapshot-revision receipts to ops/audit surfaces.
- P2, S: Add a source-search/CI guard that prevents new gateway code from importing learning/eval workers into request-path packages.
- P3, M: Add optional Redis `CounterAuthority` and optional lexical MCP tool search adapters after Aurora-native launch tests fail a stated requirement.
- P4, S: Build draft-MR/issue creation for skills as an offline worker with no merge/publish credentials; keep autonomous promotion out of launch.

## Alternatives And New Ideas

- Emergency deny overlay: a small signed, TTL-bound local deny list loaded by pods can reduce exposure while Aurora propagation catches up. It must be audited and expire automatically; it is not a second durable authority.
- Policy dry-run shadow: before enforcing new entitlement/routing policies, evaluate them asynchronously against metadata-only traffic and emit divergence reports. It must never alter live decisions.
- Snapshot diff receipts: every installed snapshot records previous revision, new revision, checksum, resource counts, policy reductions/increases, and stale-fail-closed deadline. This makes convergence debuggable without exposing secrets.
- Budget preflight modes: separate `estimate`, `reserve`, `settle`, and `reconcile` APIs behind a `CounterAuthority` interface so Aurora and Redis implementations can be tested with the same conformance suite.
- MCP risk tiers: classify tools as read-only, idempotent mutation, non-idempotent mutation, credential-bearing, and external-egress. Retry, replay, evidence, and failover rules should key off the tier.

## Assumptions

- Internal Kubernetes and Aurora PostgreSQL are fixed launch constraints.
- Redis is allowed only as optional future infrastructure, not mandatory launch infrastructure.
- Gateway pods may create issues, patches, and draft merge requests but cannot merge, publish, or bypass protected human approval.
- Direct Go SDK/in-process gateway usage either remains supported and must pass mandatory guards, or enterprise deployment explicitly disables it.
- Initial enterprise launch favors correctness, auditability, and availability over online learning or autonomous optimization.

## Questions

- What is the exact maximum stale window for security reductions versus non-security routing/provider config?
- Which budget classes are hard-deny, soft-alert, preapproved overdraft, or manual-approval overdraft?
- Will Okta provide SCIM push, incremental API polling, or only OIDC claims for group data?
- Which MCP tools must launch, and which of them are non-idempotent or credential-bearing?
- Are any teams allowed to approve raw replay/eval datasets, and what retention/deletion authority governs them?
- Are direct SDK callers in scope for enterprise production, or can the HTTP transport be the only supported entrypoint?

## Uncertainty

- No benchmark numbers are claimed here. Aurora outbox/listener behavior, reservation contention, route-decision overhead, privacy sink backpressure, and snapshot sizes require measurements under representative pod counts and control-plane change rates.
- Exact enterprise-only code may exist outside this fork; this analysis is limited to the visible repository, roadmap, tests, and read-only Beads state.
- Existing governance/plugin tests were not fully run because this was a read-only planning analysis, not an implementation verification pass.

## Tensions

- Fail-closed security versus extreme availability: revocations and spend reductions must fail closed after a short lease, while stable provider/routing config can stay usable longer.
- Determinism versus experimentation: launch needs reproducible routing receipts; canary/shadow traffic should use stable cohorts and explicit spend/privacy caps.
- Privacy versus eval quality: raw content improves debugging and model evaluation, but the launch invariant is metadata-only by default with purpose-bound approved capture.
- Low overhead versus enterprise authority: do not put Aurora/Okta/eval calls into inference, but do add a small mandatory local guard that reads immutable snapshots.
- Human approval versus learning speed: protected merge requests slow skill promotion, but they are the launch safety boundary.

## Final Confidence

Overall confidence: High that the launch path should be Aurora-authoritative snapshots plus mandatory local guards, with asynchronous privacy-safe evidence and no learning service in the availability path. Medium confidence on the exact reservation and routing mechanisms until Aurora contention, failover, and convergence tests produce evidence.
