# MODE_OUTPUT_NTM_I4 - Perspective Taking

## Thesis

For this internal Kubernetes/Aurora launch, the primary product risk is not the Go inference substrate. It is whether each stakeholder can trust the same control-plane fact at the moment they need it: operators need accurate pod state, platform needs bounded convergence, security needs fail-closed authority, finance needs reserved spend rather than retrospective accounting, reviewers need privacy-safe evidence, researchers need useful but non-production-path data, and internal users need understandable access. Preserve the low-overhead provider/plugin path, but move launch authority into explicit snapshots, reservations, receipts, and operator-facing diagnostics. Optional learning and skill promotion should remain async and outside the gateway availability path.

## Confirmed Known Risks Used As Context

The existing roadmap already confirms multi-pod budget/rate-limit loss, admission-before-settlement overspend, hybrid policy revisions, health/readiness restart storms, silent routing continuation, notification lag, rolling semantic skew, MCP policy-before-credential gaps, privacy/evidence boundaries, and missing Flywheel implementation. I treat those as established risks. The findings below are I4 stakeholder consequences and next-day planning actions, not fresh rediscoveries.

## Findings

### I4-01 - Operators Need Probe Semantics That Separate Process Life, Traffic Readiness, And Optional Store Health

**Stakeholders:** operators, platform, internal users.

**Evidence:**
- `transports/bifrost-http/handlers/health.go` `HealthHandler.RegisterRoutes`, lines 26-29, registers only `/health`.
- `transports/bifrost-http/handlers/health.go` `HealthHandler.getHealth`, lines 31-89, returns 503 when config, log, or vector store ping fails unless DB pings are disabled.
- `terraform/modules/bifrost/kubernetes/main.tf`, lines 158-178, uses the same `var.health_check_path` for liveness and readiness probes.
- `helm-charts/bifrost/values.yaml`, lines 133-149, defaults both liveness and readiness to `/health`.
- `helm-charts/bifrost/values.yaml`, lines 276-283, defaults `disableDbPingsInHealth: false`.

**Reasoning chain:** A log/vector/config-store impairment can make `/health` fail. Because liveness and readiness use the same path, Kubernetes can treat an otherwise serving process as dead and restart it. Operators then see churn instead of a clear control-plane impairment. For this deployment, where active agents depend on the gateway, the pod should stay alive when optional sinks fail, leave service only when it cannot safely admit traffic, and expose freshness/control-plane degradation separately.

**Severity:** High for launch availability.

**Confidence:** High.

**Next-day action:** Define `/livez`, `/readyz`, and `/startupz` contracts. Make liveness process-local, readiness depend on provider admission plus policy-snapshot freshness, and expose store/policy lag as structured health details and metrics. Update Helm/Terraform defaults and add one K8s fault test for Aurora/log/vector impairment.

### I4-02 - Finance And Platform Cannot Rely On Controlled Overdraft Until Budget Admission Is A Durable Reservation

**Stakeholders:** finance, platform, operators.

**Evidence:**
- `plugins/governance/main.go` `GovernancePlugin.PostLLMHook`, lines 1373-1385, launches async `postHookWorker` usage settlement after response handling.
- `plugins/governance/tracker.go` `UsageTracker.UpdateUsage`, lines 91-215, mutates in-memory usage counters after a request has consumed tokens/cost.
- `plugins/governance/tracker.go` `UsageTracker.resetExpiredCounters`, lines 254-260, periodically dumps all rate limits and budgets to the database.
- `plugins/governance/store.go` `LocalGovernanceStore.DumpRateLimits`, lines 2153-2168, writes absolute current usage values.
- `plugins/governance/store.go` `LocalGovernanceStore.DumpRateLimits`, lines 2176-2187, treats deadlocks as benign because usage is expected to sync later.
- `plugins/governance/store.go` `LocalGovernanceStore.DumpBudgets`, lines 2231-2240, writes `current_usage` from local memory.
- `plugins/governance/store.go` `LocalGovernanceStore.DumpBudgets`, lines 2247-2259, makes the same deadlock/gossip assumption.

**Reasoning chain:** Controlled overdraft is a finance policy, not an accounting afterthought. The current path admits first, bills later, and relies on local in-memory state plus periodic absolute dumps. That can be useful telemetry, but it cannot prove that a request was admitted under a specific spend lease, overdraft rule, approver, and alert state across pods. Finance needs a reservation receipt before spend, then reconciliation after usage is known.

**Severity:** High for launch governance and cost controls.

**Confidence:** High.

**Next-day action:** Specify the Aurora reservation ledger: reservation id, actor, VK/team/customer scopes, model/provider attempt, policy revision, overdraft policy id, expiry, renewal for streams/tool trajectories, settlement, cancellation, and alert receipt. Use local counters only as cache/telemetry until a multi-pod reservation oracle test passes.

### I4-03 - Security Reviewers Need A Reference Monitor, Not Best-Effort Plugin Error Semantics

**Stakeholders:** security, reviewers, platform, operators.

**Evidence:**
- `core/schemas/plugin.go` `LLMPlugin.PreRequestHook`, lines 283-297, documents that non-nil errors are non-blocking and cannot abort a request.
- `core/bifrost.go` `PluginPipeline.RunPreRequestHooks`, lines 7300-7311, repeats that there is no short-circuit and errors are non-blocking.
- `core/bifrost.go` `PluginPipeline.RunPreRequestHooks`, lines 7331-7337, logs pre-request errors and continues.
- `core/bifrost.go` `PluginPipeline.RunMCPPreHooks`, lines 7477-7494, records MCP pre-hook errors but continues unless a short circuit is returned.
- `plugins/governance/main.go` `GovernancePlugin.PreLLMHook`, lines 1271-1309, does provide an LLM short-circuit when `EvaluateGovernanceRequest` returns a `BifrostError`.
- `plugins/governance/main.go` `loadBalanceProvider`, lines 557-561, continues without modification when no eligible provider configs remain.
- `plugins/governance/main.go` `GovernancePlugin.evaluateRoutingRules`, lines 743-749, logs routing-rule evaluation errors and returns no decision/no error.

**Reasoning chain:** The governance plugin has a correct-looking LLM short-circuit path, but the generic plugin substrate is intentionally fail-open for several phases. Security reviewers need to know which decisions are mandatory and what happens under timeout, panic, corrupt snapshot, or rule-engine failure. If mandatory authorization, entitlement, quota, privacy, or routing-deny logic is implemented as ordinary plugin behavior, reviewers must audit every continuation path rather than a single fail-closed authority boundary.

**Severity:** High for enterprise security approval.

**Confidence:** High.

**Next-day action:** Add a design artifact for a typed reference monitor outcome: `allow`, `deny`, `stale-fail-closed`, `unknown-fail-closed`, `degraded-allow-by-policy`, and `observe-only`. Require fault-injection tests proving mandatory guard failure causes zero provider write, zero MCP credential acquisition, and an auditable denial receipt.

### I4-04 - MCP Governance Has Tool Filters, But Denied Calls Can Still Reach Connection/Credential Preparation Before The Plugin Gate

**Stakeholders:** security, MCP platform owners, internal tool users.

**Evidence:**
- `core/mcp/exec.go` `MCPManager.executeToolWithHooks`, lines 85-91, resolves the upstream client and acquires its connection before the plugin gate runs.
- `core/mcp/exec.go` `MCPManager.executeToolWithHooks`, lines 115-124, wraps only `ToolsManager.ExecuteTool` in the plugin pipeline.
- `core/mcp/exec.go` `MCPManager.prepareToolExecution`, lines 161-184, enforces client/tool filters before acquisition.
- `core/mcp/exec.go` `MCPManager.prepareToolExecution`, line 185, calls `AcquireClientConn` before returning to the plugin gate.
- `core/mcp/clientmanager.go` `MCPManager.AcquireClientConn`, lines 24-41, may open fresh per-user connections and surface credential errors from that method.
- `core/mcp/clientmanager.go` `MCPManager.createHTTPConnection`, lines 1660-1679, resolves auth headers on direct fallback paths.
- `plugins/governance/main.go` `GovernancePlugin.PreMCPConnectionHook`, lines 1570-1587, explicitly states it only populates identity and does not short-circuit unknown VKs or check tool policy.

**Reasoning chain:** Discovery and direct-execution filters are valuable, but they are not the full enterprise governance membrane. For privileged MCP tools, security wants denied calls to acquire no credentials, open no connection, and send no upstream packet. The current sequencing can do useful allow-list filtering first, but budget, rate, VK, team/customer, and action-governance checks in `PreMCPHook` occur after connection preparation. That is the wrong mental model for security reviewers and MCP service owners.

**Severity:** High where tools are privileged or destructive; Medium-High for read-only internal tools.

**Confidence:** High.

**Next-day action:** Promote `bif-bpfk.19` / MCP policy-before-credential work to launch gating. Add one conformance test that a denied tool call issues zero credential-store lookup, zero connection acquisition, and zero upstream network attempt.

### I4-05 - Researchers Need Evidence, But Privacy Reviewers Need A Receipt Boundary Before Logs/Traces/Evals Become Training Inputs

**Stakeholders:** researchers, privacy/security reviewers, legal/compliance, internal users.

**Evidence:**
- `docs/roadmap/privacy-redaction-and-learning-boundaries.md`, lines 3-32, defines the invariant that raw production content must not enter logs, replay, eval, skill, model, training, cross-team analytics, or external observability merely because it passed through the gateway.
- `plugins/logging/main.go` `LoggingPlugin.buildInitialLogData` / content logging path, lines 650-785, records input history, params, tools, payload inputs, and passthrough request body when content logging is enabled.
- `framework/logstore/payload.go` `payloadFields`, lines 14-53, includes raw request/response, input history, passthrough body, routing logs, and related payload fields.
- `framework/logstore/hybrid_test.go` `TestHybrid_ExcludeFields_RawRequestStaysInDB`, lines 844-879, verifies excluded raw fields can remain in DB.
- `framework/logstore/hybrid_test.go` `TestHybrid_ExcludeFields_InputHistoryStaysFullInDB`, lines 881-922, verifies excluded input history can remain full in DB.
- `core/schemas/trace.go` `Trace.SnapshotForExport`, lines 166-202, copies request headers, plugin logs, spans, and attributes for export.
- `core/schemas/redaction.go`, lines 19-99, provides redaction-data structures and context helpers, but not a durable purpose/tenant privacy receipt.

**Reasoning chain:** The codebase has useful logging, tracing, redaction, and offload mechanics. Researchers will want those artifacts for evals and routing improvement. Privacy reviewers need a stronger boundary: every evidence artifact should declare purpose, tenant/team scope, raw/derived status, transform version, detector failures, retention, and export eligibility. Without a receipt boundary, a configuration that is reasonable for operational debugging can silently become too broad for evals or skill proposals.

**Severity:** High for privacy-safe launch; Medium for availability because the learning path can remain async.

**Confidence:** High.

**Next-day action:** Implement or spec `PrivacyTransformReceipt` and `EvidenceEnvelopeBuilder` before any eval/replay/skill pipeline consumes production traces. Default evidence to metadata-only, fail closed to no-capture on detector/transform failure, and add canary tests for credentials/secrets in logs and proposed MRs.

### I4-06 - Internal Users And Okta Admins Need Explainable Access From The Same Snapshot Used For Invocation

**Stakeholders:** internal users, Okta admins, support, reviewers.

**Evidence:**
- `docs/roadmap/enterprise-oss-program.md`, lines 183-206, requires Okta/OIDC/SCIM/import mapping, removal within a measured bound, and explainable access.
- `core/bifrost.go` `Bifrost.ListModelsRequest`, lines 402-443, sets `BifrostContextKeySkipBudgetAndRateLimits=true` and routes list-models through `handleRequest`.
- `core/bifrost.go` `Bifrost.ListAllModels`, lines 445-620, fans out to configured providers and tolerates expected provider-blocked/no-key/not-supported errors.
- `core/bifrost.go` `filterProvidersByContext`, lines 625-650, returns all provider keys when no available-provider context is present.
- `plugins/governance/main.go` `GovernancePlugin.PostLLMHook`, lines 1336-1338, filters list-models responses for a virtual key after provider responses are available.
- `plugins/governance/resolver.go` `EvaluateVirtualKeyRequest`, lines 281-298, enforces provider and model allowance during invocation.
- `plugins/governance/store.go` `LocalGovernanceStore.UpdateVirtualKeyInMemory`, lines 3012-3189, updates budgets, rate limits, provider configs, and the virtual key across several mutable maps before storing the key clone.

**Reasoning chain:** Internal users will ask, "Why can I see this model?" and "Why was I denied?" Okta admins will ask, "When did this group change take effect?" The invocation path and list-model path are close but not yet an explicit single evaluator with an immutable decision snapshot and explanation receipt. During the accepted 1-5 second convergence window, piecemeal in-memory updates and post-response filtering can produce confusing answers unless every decision reports the applied policy revision, entitlement sources, staleness, and reason codes.

**Severity:** Medium-High for enterprise usability and support load.

**Confidence:** Medium-High.

**Next-day action:** Define an immutable `GovernanceSnapshot` plus `ExplainAccess` response shape shared by `/v1/models`, invocation admission, and operator/admin UI. Include policy revision, Okta group/profile inputs, model/provider candidates removed, budget/quota state, freshness age, and denial reason.

### I4-07 - Skill Authors And Reviewers Are Protected By Human MR Gates Only If Proposal Artifacts Are Privacy-Safe And Non-Promoting By Construction

**Stakeholders:** skill authors, human reviewers, security, researchers.

**Evidence:**
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md`, lines 5-18, defines the launch boundary: protected Git merge requests with mandatory human approval; the gateway may create issues, patches, and draft MRs but cannot merge or publish.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md`, lines 151-166, states there is no organization-scoped auto-promotion at launch.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md`, lines 190-209, says Flywheel is not implemented and key Go definitions such as evidence envelopes, operational contracts, promotion receipts, and durable outbox do not exist.
- Beads `bif-bpfk.7` describes the Git/MR-backed internal skill proposal workflow with provenance, diffs, no raw traces, branch protection, no merge/publish authority, immutable SHA pinning, and revert receipt acceptance criteria.
- Beads `bif-bpfk.18` makes privacy-gated evidence envelopes and bounded durable outbox a prerequisite for proposal generation.

**Reasoning chain:** Mandatory human approval removes the most dangerous autonomous promotion path, but it does not automatically sanitize evidence, test fixtures, diffs, or generated rationale. Reviewers need proposal packets that are already privacy-filtered, provenance-linked, sandbox-tested without production credentials, and reversible. Otherwise launch risk shifts from autonomous merge to reviewer overload and accidental raw-data disclosure.

**Severity:** Medium-High for launch trust; lower than runtime admission because auto-merge is explicitly out of scope.

**Confidence:** High.

**Next-day action:** Launch skill automation as issue-only or draft-MR-only until `EvidenceEnvelopeBuilder`, privacy receipts, sandbox CI, immutable SHA pinning, and revert receipts exist. Reject any proposal artifact without a privacy receipt and source trace lineage.

## Risks

- **Availability risk:** A control-plane or observability outage can still be misclassified as pod death if probe semantics stay collapsed.
- **Cost risk:** Retrospective usage accounting cannot satisfy controlled overdraft without durable pre-admission reservations.
- **Security risk:** Fail-open plugin phases and MCP connection-before-policy sequencing can undermine mandatory governance claims.
- **Privacy risk:** Logs/traces can be operationally useful but unsafe as eval/training/proposal inputs without receipt-bound transforms.
- **User trust risk:** Model visibility, entitlement denials, and Okta deprovisioning will be hard to explain without one snapshot-backed evaluator.
- **Reviewer risk:** Human MR gates may become a bottleneck or privacy leak if proposal packets are not already sanitized and provenance-bound.

## Recommendations

### P0

- **Split health endpoints and deployment probes.** Effort: Low-Medium. Add `/livez`, `/readyz`, `/startupz`, Helm/Terraform defaults, and one store-impairment K8s test.
- **Define and enforce the mandatory reference monitor.** Effort: Medium-High. Move auth, entitlement, quota/reservation, privacy, and MCP invocation authority behind typed fail-closed outcomes with receipt logging.
- **Replace launch-budget authority with Aurora reservations.** Effort: Medium-High. Keep in-memory counters as cache/telemetry, but gate spend on durable reservations and settlements.
- **Create immutable policy snapshots with freshness leases.** Effort: Medium. Use the same snapshot for list-models, invocation, MCP governance, and explain-access.

### P1

- **Reorder MCP execution to policy-before-credential/connection.** Effort: Medium. Add zero-credential/zero-connection denial tests.
- **Add privacy receipts and bounded evidence outbox.** Effort: Medium. Default to metadata-only and require transform receipts before eval/replay/skill consumers.
- **Build an operator doctor bundle.** Effort: Low-Medium. Include applied policy revision, outbox lag, reservation DB state, probe state, provider circuit state, and last deny/overdraft receipts.

### P2

- **Make routing decisions receipt-based.** Effort: Medium. Emit deterministic candidate-set and route-decision receipts before adding adaptive or learned routing.
- **Launch skill automation as issue-only/draft-MR-only.** Effort: Medium. Require privacy-safe evidence, sandbox CI, immutable SHA pins, and revert receipts before reviewer assignment.

### P3

- **Add offline evals and replay after privacy controls.** Effort: Medium. Keep eval workers outside gateway availability and publish only aggregate safe metrics by default.

### P4

- **Defer learned routing, distillation, and autonomous promotion.** Effort: High when resumed. Treat them as post-launch services that consume receipts, never as request-path dependencies.

## Alternatives And New Ideas

- **Authority receipt bundle:** Attach a compact internal receipt id set to every request: policy revision, reservation id, route decision id, privacy receipt id, and evidence envelope id when applicable.
- **Staleness banner:** Show operators and admins the applied revision, durable authority revision, freshness lease age, and next poll/notify state per pod.
- **Explain-access CLI and API:** Let support answer access questions with the same evaluator used by invocation, but without provider calls.
- **Evidence escrow:** Keep raw production content out of default evidence. Permit exceptional raw capture only through a separate vault-backed approval receipt and retention policy.
- **Issue-first Flywheel:** Before draft MRs, generate only privacy-safe issues with failing/passing evidence references so reviewers can decide whether a patch should exist.

## Assumptions

- Deployment target is internal enterprise Kubernetes with Aurora PostgreSQL as durable control-plane authority.
- Redis/memberlist/gossip may be useful later but is not mandatory for launch.
- One to five seconds of control-plane convergence is acceptable when surfaced and bounded.
- Human approval through protected Git merge requests is mandatory for internal skill promotion.
- The gateway may create issues, patches, and draft MRs, but cannot merge or publish.
- Optional learning, eval, replay, and skill services must never enter the inference availability path.

## Questions

- What exact freshness lease should fail closed inside the accepted 1-5 second convergence window?
- During Aurora write outage, which request classes may continue under existing reservations, and which must deny?
- Which MCP tools are destructive or privileged enough to require stronger per-call human approval or just-in-time entitlement?
- What launch purposes permit content logging, if any, and which teams may access transformed evidence?
- What is the minimum operator UI/CLI surface needed before the first three-pod production exercise?

## Uncertainty

- I did not run benchmark or fault-injection tests, so this analysis does not claim latency, throughput, or convergence measurements.
- Some enterprise-only controls may exist outside the inspected OSS fork and roadmap files.
- Beads were inspected read-only; their dependency graph and acceptance criteria may evolve before implementation starts.
- Exact Okta group/profile shape and internal MCP tool risk tiers were not available in code.

## Tensions

- **Availability vs. fail-closed security:** stale policy can preserve uptime or enforce revocation, but not both without explicit lease policy.
- **Finance exactness vs. hot-path overhead:** durable reservations add authority; they must be batched/cached carefully to preserve provider-path performance.
- **Research value vs. privacy:** better evals want richer traces; launch privacy wants metadata-only by default.
- **Reviewer throughput vs. mandatory human approval:** safety requires humans; proposal quality must be high enough to avoid review queue collapse.
- **Deterministic routing vs. adaptive optimization:** hard filters and receipts must precede any learned or exploratory routing.
- **Simple Go substrate vs. enterprise control plane:** keep inference simple, but make authority state explicit and testable outside the provider call path.

## Final Confidence

High. The stakeholder implications are well supported by roadmap decisions, Beads acceptance criteria, and inspected code paths. Confidence is strongest for health/probes, budget reservations, plugin authority semantics, MCP sequencing, and privacy receipts; it is slightly lower for Okta/user-experience details because the final identity mapping model is still design-stage.
