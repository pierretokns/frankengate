# Worst-Case Mode (L3): Internal Enterprise Kubernetes Launch

## Thesis

The worst plausible launch failures are not provider-call latency regressions. They are control-plane correctness failures that leave the fast Go data plane running while mandatory enterprise controls become advisory, stale, or locally inconsistent. The dangerous shape is a pod that is healthy enough to serve inference but is using stale virtual-key, Okta, budget, routing, MCP, or privacy state.

For this deployment, the target architecture should keep the low-overhead provider/plugin substrate, but move mandatory control decisions into a fail-closed reference-monitor path with bounded local snapshots, executable convergence oracles, and no dependency on optional learning/eval services.

Existing roadmap warnings are treated here as confirmed known risks, not discoveries. This analysis adds L3 worst-case framing, code-line evidence, and executable oracles.

## Findings

### L3-01 - Mandatory controls can fail open when expressed as ordinary plugin errors

Status: Confirmed known risk.

Severity: High for launch. This is not a public internet exploit by itself, but it can make Okta entitlement, budget, routing, privacy, or MCP denial controls non-authoritative inside the enterprise gateway.

Confidence: High.

Evidence:

- `core/schemas/plugin.go` (`LLMPlugin` contract), lines 192-198: plugin errors are logged as warnings and are not returned to callers.
- `core/schemas/plugin.go` (`PreRequestHook` contract), lines 283-297: pre-request errors are explicitly non-blocking and the request continues.
- `core/bifrost.go` (`PluginPipeline.RunLLMPreHooks`), lines 7253-7297: `PreLLMHook` errors are appended/logged and execution continues unless a short-circuit is returned.
- `core/bifrost.go` (`PluginPipeline.RunPreRequestHooks`), lines 7300-7338: `PreRequestHook` errors are logged and ignored.
- `plugins/governance/main.go` (`GovernancePlugin.PreLLMHook`), lines 1271-1310: governance denials are currently effective only when converted into an `LLMPluginShortCircuit`.
- `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md`, lines 41-45 and 77-86: mandatory governance/privacy controls must not inherit generic plugin fail-open behavior.

Reasoning chain:

1. The current generic plugin contract is intentionally best-effort.
2. Enterprise launch controls include mandatory decisions: virtual-key auth, Okta entitlement, quota/budget reservation, privacy eligibility, and MCP invocation authorization.
3. If any mandatory control is implemented as "return an error from a hook" rather than a typed fail-closed decision or short-circuit, the core pipeline can continue to provider I/O.
4. A reachable failure is a transient resolver, parser, DB, policy, or privacy classifier error that becomes an allow-by-default path for an internal agent or service account.

Executable oracle:

- Add guard-failure tests that inject errors from each mandatory control path and assert: zero provider calls, zero fallbacks, zero MCP connection acquisition, and a typed denial/degraded response.
- Run the same oracle for streaming and non-streaming requests because streaming can otherwise hide partial side effects.

Next-day action:

- Define a small `MandatoryDecision` surface for launch controls: `allow`, `deny`, `degrade`, `stale_allow_within_bound`, and `indeterminate_fail_closed`.
- Add a regression test that proves ordinary plugin errors cannot authorize protected traffic.

### L3-02 - Budget and rate-limit enforcement is post-paid and pod-local without a bounded reservation ledger

Status: Confirmed known risk.

Severity: High for launch. It can violate controlled overdraft guarantees across pods even when each individual pod appears locally correct.

Confidence: High.

Evidence:

- `plugins/governance/main.go` (`GovernancePlugin.PostLLMHook`), lines 1322-1389: usage tracking is launched asynchronously after the provider response path.
- `plugins/governance/tracker.go` (`UsageTracker.UpdateUsage`), lines 91-214: usage is deduplicated/charged and then applied to in-memory provider, model, virtual-key, team/customer, and user counters.
- `plugins/governance/store.go` (`LocalGovernanceStore.CheckBudget`), lines 1052-1083: admission checks current local usage plus optional baselines.
- `plugins/governance/store.go` (`LocalGovernanceStore.BumpBudgetUsage`), lines 411-460: budget increments are applied to local in-memory budget objects.
- `plugins/governance/store.go` (`LocalGovernanceStore.DumpBudgets`), lines 2194-2240: database persistence writes each in-memory absolute usage value plus baseline.
- `plugins/governance/store.go` (`LocalGovernanceStore.DumpRateLimits`), lines 2104-2168: rate-limit persistence follows the same local snapshot plus baseline pattern.
- `plugins/governance/store.go` (`DumpBudgets`/`DumpRateLimits`), lines 2176-2187 and 2247-2258: deadlocks are treated as retryable/safe because another node is assumed to update and gossip will sync later.
- `plugins/governance/accounting_test.go`, lines 122-157: streaming failures with usage and retry attempts are billable.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md`, lines 109-124: launch plan already requires pod-local reservation with Aurora settlement and bounded overdraft.
- `docs/roadmap/modes/MODE_OUTPUT_F4_L3.md`, lines 35-104: multi-pod usage erasure and admission-before-settlement are already recorded as confirmed risks.

Reasoning chain:

1. Admission currently checks local counters, not a durable reservation or lease.
2. Usage is applied after the provider call, and database writes are periodic absolute snapshots from each pod.
3. Multiple pods can admit the same virtual key or budget window concurrently while each sees remaining local capacity.
4. Retry/fallback attempts can legitimately bill more than one physical provider call for one logical request.
5. The launch promise is not "eventual accounting"; it is controlled overdraft with alerting.

Executable oracle:

- Start multiple gateway pods against Aurora with the same virtual key and budget.
- Synchronize a burst at the admission boundary, include at least one streaming request and one fallback/retry.
- Assert accepted reservations plus configured overdraft never exceed the configured bound, including when one pod crashes before post-hook settlement.

Next-day action:

- Sketch and test an Aurora-backed reservation ledger: request/attempt idempotency key, reservation amount, expiry, final settlement, cancellation, and overdraft policy.
- Do not rely on periodic absolute dumps for launch budget admission.

### L3-03 - Revoked or changed authority can remain live on one pod without versioned per-pod convergence

Status: Confirmed known risk.

Severity: High for virtual-key revocation and Okta deprovisioning; Medium-High for routing/model-policy drift.

Confidence: High.

Evidence:

- `plugins/governance/store.go` (`LocalGovernanceStore`), lines 24-66: virtual keys, teams, customers, budgets, rate limits, providers, model configs, and routing rules are held in local `sync.Map` state.
- `plugins/governance/store.go` (`LocalGovernanceStore.GetVirtualKey`), lines 922-932: virtual-key lookup is a local map read.
- `plugins/governance/main.go` (`GovernancePlugin.EvaluateGovernanceRequest`), lines 927-943: governance admission trusts the local virtual-key entry.
- `transports/bifrost-http/server/server.go` (`Server.ReloadVirtualKey`), lines 384-449: a virtual-key reload mutates the current process store and associated model configs.
- `transports/bifrost-http/server/server.go` (`Server.RemoveVirtualKey`), lines 452-470: virtual-key removal deletes from the current process store and MCP server.
- `framework/configstore/store.go` (`ConfigStore` governance methods), lines 288-436: the public persistence interface exposes CRUD/config operations, but no versioned cross-pod outbox or snapshot API in this interface.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md`, lines 52-73 and 75-91: the intended launch design is Aurora authority with versioned outbox/snapshot, bounded stale age, and fail-closed unknown/revoked keys.
- `docs/roadmap/modes/MODE_OUTPUT_F4_L3.md`, lines 106-139 and 208-239: hybrid in-memory revision and missed notification scenarios are already confirmed known risks.

Reasoning chain:

1. The serving path intentionally reads local in-memory state for speed.
2. Admin changes are process-local unless every pod observes and applies the same ordered change set.
3. A pod that misses a delete/update can stay ready and continue admitting a revoked virtual key or stale Okta-derived entitlement.
4. Sparse traffic can hide the problem because fleet-level success metrics still look good.
5. A 1-5 second convergence target is acceptable, but it must be measured per pod and per protected decision.

Executable oracle:

- Run at least two pods with the same Aurora control plane.
- Revoke a virtual key or Okta-derived entitlement while deliberately dropping notification delivery to one pod.
- Assert the isolated pod either converges from polling within the configured bound or fails closed for protected traffic after the stale-snapshot bound.

Next-day action:

- Define the snapshot contract: monotonic version, applied cursor, max stale age, readiness/degraded state, and emergency deny overlay.
- Add a convergence test harness before implementing additional policy features.

### L3-04 - MCP denial currently happens after client/connection acquisition in important paths

Status: Confirmed known risk (`bif-bpfk.19` tracks the same owner-acknowledged issue).

Severity: High for privileged MCP servers with user or service credentials; Medium-High for ordinary read-only tools.

Confidence: High.

Evidence:

- `core/mcp/exec.go` (`ToolExecutor.executeToolWithHooks`), lines 85-104: the upstream client is resolved and a client connection is acquired before the plugin pipeline is invoked.
- `core/mcp/exec.go` (`ToolExecutor.executeToolWithHooks`), lines 115-124: the plugin pipeline wraps the actual `ExecuteTool` call after acquisition.
- `core/mcp/exec.go` (`ToolExecutor.prepareToolExecution`), lines 156-190: request/client/tool filters run before acquisition, but mandatory virtual-key governance is not the final pre-acquire reference monitor.
- `plugins/governance/main.go` (`GovernancePlugin.PreMCPHook`), lines 1400-1488: governance performs execution-time virtual-key and tool allow-list checks in the MCP plugin hook.
- `core/mcp/codemode/starlark/executecode.go` (`callMCPTool` path), lines 471-488: nested code-mode MCP invocation also acquires a connection before the plugin gate.
- `core/mcp/codemode/starlark/executecode.go`, lines 521-531: the upstream `CallTool` happens after that gate.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md`, lines 185-197: launch MCP governance requires identity-derived narrowing and no wildcard auto-execution for privileged tools.

Reasoning chain:

1. Discovery filters reduce the visible tool set, but invocation authorization is the mandatory boundary.
2. Current execution acquires an MCP connection before the governance `PreMCPHook` can deny.
3. Acquiring a connection can be observable or stateful for servers with OAuth/session refresh, per-user leases, audit side effects, or scarce connection pools.
4. The worst plausible outcome is not necessarily an unauthorized `CallTool`; it is unauthorized credential/session/connection side effect before policy denial.

Executable oracle:

- Build a fake MCP client that counts connection acquisition, token refresh, outbound packets, and tool calls.
- Invoke a denied tool through direct execution and code-mode nested execution.
- Assert denied calls produce zero acquisition, zero refresh, zero packets, and zero tool calls.

Next-day action:

- Move mandatory MCP authorization before `AcquireClientConn`.
- Keep connection acquisition inside the already-authorized closure and preserve discovery filters as narrowing, not authority.

### L3-05 - Privacy-safe traces/evals can become raw-content persistence plus stream memory pressure

Status: Confirmed known risk.

Severity: High for privacy and internal data handling; Medium-High for availability when full stream capture is enabled without bounds.

Confidence: High on the risk shape; Medium on exact blast radius because deployment logging defaults and enterprise privacy controls may differ.

Evidence:

- `plugins/logging/main.go` (`captureLoggingHeaders`), lines 547-595: configured logging headers, wildcard headers, dimensions, and `x-bf-lh-*` headers are copied into metadata.
- `plugins/logging/main.go` (`LoggingPlugin.PreLLMHook`), lines 650-786: when content logging is enabled, input histories, tools, params, speech/transcription/image fields, and passthrough JSON bodies can be captured.
- `plugins/logging/main.go` (`LoggingPlugin.PostLLMHook`), lines 1054-1099 and 1102-1158: error and stream paths can attach accumulated output plus raw request/response when configured.
- `plugins/logging/main.go` (`LoggingPlugin.Inject`), lines 1353-1384: plugin logs from traces are serialized into log entries.
- `framework/streaming/accumulator.go` (`Accumulator.CreateStreamAccumulator`/`GetStreamAccumulator`), lines 135-210: per-stream accumulated chunks live in manager state keyed by request ID.
- `framework/streaming/accumulator.go` (`AddChatChunk`/`AddResponsesChunk`), lines 212-252 and 333-364: chunks are appended and retained for accumulation; no launch-policy byte cap is visible in this path.
- `framework/streaming/accumulator.go` (`NewAccumulator`), lines 611-658: default cleanup uses TTL/ticker cleanup.
- `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md`, lines 51-57 and 90-99: full stream materialization and raw/derived content capture are already identified as privacy and memory risks.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md`, lines 155-168: launch telemetry should be metadata-first with raw content only under explicit approval.

Reasoning chain:

1. Launch asks for privacy-safe traces/evals, not a raw prompt/tool/result warehouse.
2. Logging and trace paths can persist headers, plugin logs, request bodies, responses, and accumulated stream output when configured.
3. Evals, skill proposals, or incident workflows often want the same evidence, so the easiest integration path can accidentally reuse raw logging surfaces.
4. Long streams or fanout capture can retain content in memory until completion or cleanup.
5. The worst plausible outcome is internal sensitive prompts, code, HR/legal content, tool outputs, or secrets becoming durable evidence or proposal text.

Executable oracle:

- Create a privacy canary suite with secrets in headers, body, tool args, tool results, provider errors, plugin logs, and stream chunks split across boundaries.
- Assert durable logs, eval inputs, issue bodies, patches, and draft MRs contain only approved metadata or privacy receipts.
- Run a long-stream soak with capture enabled and assert configured memory and queue bounds are enforced by drop/degrade behavior, not unbounded accumulation.

Next-day action:

- Define an `EvidenceEnvelope` allowlist before wiring eval/proposal consumers.
- Add hard-deny fields for credentials/secrets and require a privacy receipt for any raw or derived content leaving the request path.

### L3-06 - Shared health checks can turn Aurora/log/vector outage into a pod restart storm

Status: Confirmed known risk.

Severity: High when Kubernetes liveness and readiness both point at the same dependency-pinging endpoint.

Confidence: High for the checked Terraform module; Medium if production Helm diverges.

Evidence:

- `transports/bifrost-http/handlers/health.go` (`HealthHandler.RegisterRoutes`), lines 26-29: only `/health` is registered.
- `transports/bifrost-http/handlers/health.go` (`HealthHandler.handleHealthCheck`), lines 31-89: if store ping checks are enabled, config, log, and vector store ping errors return HTTP 503.
- `terraform/modules/bifrost/kubernetes/main.tf`, lines 158-178: liveness and readiness probes both use `var.health_check_path`.
- `framework/configstore/postgres.go` (`NewPostgresConfigStore`), lines 36-69: startup opens migration and runtime database pools.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md`, lines 142-153: launch guidance requires process-only liveness and snapshot-aware readiness.
- `docs/roadmap/modes/MODE_OUTPUT_F4_L3.md`, lines 141-174: DB pressure plus Kubernetes health removing pods is already a confirmed known risk.

Reasoning chain:

1. The gateway can serve inference from a valid local snapshot while Aurora or a log/vector store is temporarily impaired.
2. A health endpoint that returns 503 for those dependencies is valid for readiness/degraded admin state, but not for process liveness.
3. If liveness uses the same dependency-pinging path, Kubernetes kills pods exactly when the control plane is stressed.
4. Restarts reopen DB pools and can amplify the outage while also dropping warm serving state.

Executable oracle:

- In a Kubernetes test environment, hold valid snapshots in serving pods and then make Aurora/log/vector pings fail.
- Assert liveness stays green, readiness/admin-write capability reflects degraded state, and inference for already-authorized traffic continues.
- Assert a pod without an initial valid snapshot never becomes ready.

Next-day action:

- Split endpoints: `/livez` process-only, `/readyz` snapshot/provider readiness, `/healthz/dependencies` for operator diagnostics.
- Update Terraform/Helm defaults so liveness never depends on Aurora/log/vector stores.

### L3-07 - Routing errors can silently fall back to caller/default routing

Status: Confirmed known risk.

Severity: Medium-High. The likely failure is wrong provider/model/region/cost lane rather than broad data exfiltration, but it undermines deterministic enterprise routing.

Confidence: High.

Evidence:

- `plugins/governance/main.go` (`GovernancePlugin.applyRoutingRules`), lines 743-749: routing-rule evaluation errors are logged and converted to "no decision" by returning `nil, nil`.
- `plugins/governance/main.go` (`applyRoutingRules`), lines 756-783: successful routing decisions mutate provider, model, and fallbacks.
- `plugins/governance/main.go` (`applyRoutingRules`), lines 786-793: successful routing can pin an API key via context.
- `core/schemas/plugin.go` (`PreRequestHook`), lines 283-297: even returned pre-request errors are non-blocking.
- `core/bifrost.go` (`PluginPipeline.RunPreRequestHooks`), lines 7300-7338: pre-request errors are logged and ignored.
- `core/bifrost.go` (`Bifrost.shouldTryFallbacks`), lines 4787-4816: fallbacks proceed unless `AllowFallbacks` is explicitly false.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md`, lines 126-140 and 251-259: launch routing should be deterministic, with online/semantic/bandit routing omitted from the availability path.
- `docs/roadmap/modes/MODE_OUTPUT_F4_L3.md`, lines 176-206: routing failures silently falling back is already a confirmed known risk.

Reasoning chain:

1. Enterprise routing is a policy control: provider locality, approved models, cost class, key pinning, and fallback eligibility.
2. A routing-engine error currently behaves like no routing rule matched.
3. The core request can then proceed using caller/default provider, model, key selection, and fallback behavior.
4. If an advanced or learning router is later placed inline, its outage can become either an availability outage or a silent policy bypass unless it is shadow-only or compiled into deterministic rules.

Executable oracle:

- Add table tests for invalid rule expression, missing model catalog entry, no eligible provider, stale health, and bad key pin.
- For each case, assert the exact typed result: deny, use explicit deterministic degraded route, or continue only when the policy says continue.
- Assert no provider call occurs for `policy_denied` and no fallback occurs when fallback is disallowed.

Next-day action:

- Make routing evaluation return a mandatory decision enum, not "error means no decision."
- Keep advanced routing services shadow-only until their output is compiled into deterministic rules with static validation.

## Cross-Cutting Risks

- Partial pod correctness: a single stale pod can violate revocation, budget, routing, or MCP controls while fleet metrics remain healthy.
- Attempt versus request ambiguity: one logical user request can create multiple physical provider attempts through retries, fallbacks, streams, and tool loops.
- Fail-open vocabulary: "plugin error", "no decision", "missing signal", and "optional service unavailable" must not all mean "continue."
- Privacy/evidence coupling: the data needed for evals and skill proposals is often the data least safe to persist.
- Human approval boundary drift: protected Git merge requests are safe only if proposal workers lack merge/publish/admin credentials and cannot smuggle raw evidence into issue/MR text.

## Recommendations

### P0 - Launch blockers, next day to one week

Effort: Small design surface, high test value.

- Define mandatory decision types for auth, entitlement, quota, privacy, routing, and MCP.
- Add fail-closed oracles for guard errors, stale snapshots, denied MCP tools, and routing failures.
- Split liveness/readiness/dependency health endpoints and update deployment defaults.
- Freeze any inline learning/eval/proposal dependency from the inference availability path.

### P1 - Core launch controls, one to three weeks

Effort: Medium to large; requires cross-module ownership.

- Implement Aurora-backed control-plane snapshots with monotonic version, outbox cursor, stale-age policy, and per-pod convergence metrics.
- Implement reservation-based budget/rate admission with idempotent attempt settlement, cancellation, expiry, controlled overdraft, and alert hooks.
- Move MCP mandatory authorization before client/connection acquisition.
- Add Okta reconciler semantics to the same snapshot/convergence model; do not live-call Okta per request.

### P2 - Privacy and deterministic routing, two to four weeks

Effort: Medium.

- Build privacy-gated `EvidenceEnvelope` output with field allowlists, hard-deny fields, and deletion/retention receipts.
- Bound stream capture by policy: max retained bytes/chunks, terminal cleanup, drop/degrade behavior, and metrics.
- Compile deterministic routing rules with static validation; make runtime failures typed and observable.

### P3 - Availability hardening, post-MVP launch window

Effort: Medium to large.

- Add chaos drills for Aurora outage, missed outbox events, pod crash before settlement, provider fallback storms, and MCP server partial outages.
- Consider Redis only as an optional lease/cache accelerator; Aurora remains source of truth.
- Add emergency deny overlay for revocation incidents that cannot wait for normal admin workflows.

### P4 - Post-launch autonomy and learning

Effort: Large; defer until controls are proven.

- Keep autonomous skill promotion limited to issue/patch/draft MR generation until human-gated workflows have privacy and credential oracles.
- Run learning routers, eval loops, and proposal generation in shadow/offline services.
- Promote a learned route or skill only through protected Git merge requests with human approval and reproducible evidence.

## Alternatives And New Ideas

- Use an "authority receipt" on every admitted request: snapshot version, policy version, budget reservation id, routing rule id, MCP grant version, and privacy envelope id.
- Treat controlled overdraft as a policy object, not an accounting accident: explicit amount/window/approver/alert target.
- Add a per-pod "stale authority mode" that allows only predeclared safe traffic when the snapshot is too old.
- Require every draft MR produced by the gateway to include a machine-readable evidence manifest and a redaction manifest.
- Keep advanced routing as a recommendation service whose outputs are periodically compiled into static routing config after review.

## Assumptions

- Deployment is internal enterprise Kubernetes with Aurora PostgreSQL as authoritative control-plane storage.
- Redis is optional and must not become the only source of budget or authorization truth.
- 1-5 second control-plane convergence is acceptable if stale behavior is explicit and tested.
- Internal skills are promoted only through protected Git merge requests with mandatory human approval.
- The gateway may create issues, patches, and draft MRs, but cannot merge, publish, or directly modify protected production state.
- Optional learning, eval, proposal, and analytics services must not enter the inference availability path.

## Questions

- What is the exact stale-snapshot cutoff for emergency virtual-key and Okta deprovisioning: closer to 1 second, 5 seconds, or different by policy class?
- Are MCP servers using per-user OAuth/session credentials, shared service credentials, or both?
- Which request classes may continue during Aurora outage: all previously authorized traffic, only low-risk models, or none?
- What raw-content logging, if any, is required at launch for audit or incident response?
- Is budget overdraft a hard financial boundary, a soft operational alert, or tenant-specific?
- Which repository/branch protections and credentials will proposal workers actually have in production?

## Uncertainty

- Some enterprise-only integrations are represented by interfaces or build-gated no-ops in the inspected tree, so exact Okta and external quota behavior may differ from the open code paths.
- I did not run destructive multi-pod, Aurora, or Kubernetes fault tests in this read-only pass.
- Production Helm may differ from the inspected Terraform module, but the shared health-path pattern is risky enough to require an oracle.
- Exact privacy blast radius depends on deployment defaults for content logging, raw request/response capture, trace plugins, and future eval/proposal consumers.

## Tensions

- Low-overhead serving versus mandatory pre-provider decisions: solve with local immutable snapshots and typed decisions, not live per-request DB calls.
- Availability versus revocation speed: stale serving can be allowed only inside a measured, bounded policy window.
- Privacy versus eval/proposal usefulness: evidence should be minimized, receipted, and purpose-bound.
- Deterministic routing versus advanced routing: advanced routers can advise, but launch routing must be compiled and explainable.
- Human approval versus autonomous improvement speed: keep protected Git as the promotion boundary until post-launch controls are proven.

## Final Confidence

Overall confidence is high that these are the dominant worst-case launch paths for the stated deployment. Confidence is medium on exact production blast radius because several enterprise integrations and deployment defaults may differ from the inspected repository. The next useful step is not more brainstorming; it is implementing the oracles above and refusing launch readiness until they pass.
