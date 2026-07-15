# NTM A1 - Deductive Reasoning Analysis

## Thesis

The launch invariants do not yet deductively follow from the mechanisms visible in this repository. The current codebase has a strong low-overhead inference/provider/plugin substrate, useful governance hooks, and local accounting protections, but the enterprise Kubernetes/Aurora launch requires several invariants that must be proven by new mandatory mechanisms: cross-pod fenced budget reservations, immutable policy snapshots with bounded stale behavior, fail-closed reference monitoring, deterministic routing outcomes, MCP credential/invocation governance, and privacy transforms before trace/eval persistence.

This is not a rediscovery of the roadmap warnings. The roadmap and Beads already identify these risks. A1's result is narrower: when the launch premises are tested against current code paths and deployment defaults, the premises remain unproven unless the planned P0/P1 work lands and is verified.

## Findings

### A1-F1 - Shared budget and controlled overdraft do not follow from current local accounting

Severity: Critical for this deployment
Confidence: High
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `plugins/governance/tracker.go:42-63` (`UsageTracker`) stores idempotency state in an in-process `map[string]time.Time`.
- `plugins/governance/tracker.go:91-123` (`UpdateUsage`) deduplicates terminal settlement by `requestID:attempt` in the local tracker.
- `plugins/governance/tracker.go:124-214` (`UpdateUsage`) applies usage to in-memory provider, model, user, virtual-key, and hierarchy counters.
- `plugins/governance/store.go:411-457` (`BumpBudgetUsage`) atomically increments budget usage with `sync.Map.CompareAndSwap`, which is process-local.
- `plugins/governance/store.go:1054-1082` (`CheckBudget`) admits based on local `CurrentUsage` plus optional baselines.
- `plugins/governance/store.go:2195-2263` (`DumpBudgets`) periodically writes in-memory budget usage to the config store; deadlocks are treated as benign because usage is expected to sync later.
- `plugins/governance/storeconcurrency_test.go:27-56` proves local concurrent increments are not dropped inside one process.
- `plugins/governance/accounting_test.go:83-188` proves local cumulative cost, streaming settlement, retry-attempt billing, and duplicate final-response dedupe.

Reasoning chain:

1. The launch invariant requires virtual-key budgets across pods with controlled overdraft and alerting.
2. Current admission checks local values, then usage is settled after responses and periodically dumped.
3. Local CAS and local tests prove per-process accounting correctness, not cross-pod hard admission.
4. Periodic dumps plus benign deadlock handling can be acceptable for telemetry-style usage, but they do not prove a shared hard budget bound without a durable reservation ledger.
5. The invariant follows only if the planned Aurora fenced reserve/commit/cancel/expire mechanism exists and all provider/tool attempts acquire a reservation before side effects.

Next-day action:

Define and test the Aurora reservation state machine with idempotency keys, renewable leases for long streams, controlled-overdraft math, alert thresholds, and a three-pod concurrency harness. Do not rely on the existing in-memory counters as the cross-pod authority.

### A1-F2 - Mandatory admission cannot be implemented as ordinary best-effort plugin behavior

Severity: Critical for this deployment
Confidence: High
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `core/bifrost.go:4471-4479` (`RunPreRequestHooks`) documents that plugin errors are non-blocking and the pipeline continues.
- `core/bifrost.go:7254-7297` (`PluginPipeline.RunLLMPreHooks`) logs `PreLLMHook` errors as warnings and continues unless a short-circuit response is returned.
- `core/bifrost.go:7300-7311` (`PluginPipeline.RunPreRequestHooks`) documents that pre-request errors are non-blocking.
- `core/bifrost.go:7327-7336` (`PluginPipeline.RunPreRequestHooks`) logs `PreRequestHook` errors and continues to the next plugin.
- `plugins/governance/main.go:1192-1268` (`GovernancePlugin.PreRequestHook`) returns errors for routing/load-balancing failures, but the core pre-request pipeline treats those errors as warnings.
- `plugins/governance/main.go:1280-1309` (`GovernancePlugin.PreLLMHook`) can hard-deny by returning an `LLMPluginShortCircuit` after governance evaluation.

Reasoning chain:

1. The launch invariant requires authentication, entitlement, quota reservation, privacy gating, and MCP invocation policy to be mandatory fail-closed checks.
2. Generic plugin error semantics are explicitly best-effort in multiple core hook runners.
3. Governance can deny in `PreLLMHook` only if that hook is reached and returns a short-circuit.
4. Any mandatory launch guard implemented only as a normal `PreRequestHook` error, post-hook, or observability hook can fail open.
5. Therefore, a launch-grade reference monitor must sit outside best-effort plugin error semantics or use typed mandatory outcomes that core treats as terminal.

Next-day action:

Add a mandatory admission layer before provider I/O with explicit outcomes such as `allow`, `deny`, `reserve_failed`, `snapshot_stale`, `policy_error`, and `privacy_error`. Add failure-injection tests proving plugin errors, panics, and stale snapshots cannot silently continue to upstream provider calls.

### A1-F3 - Deterministic and advanced routing do not follow from current weighted random routing

Severity: High
Confidence: High
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `plugins/governance/main.go:469-480` (`loadBalanceProvider`) skips load balancing when the request already has a provider.
- `plugins/governance/main.go:485-490` (`loadBalanceProvider`) logs and continues without modification when there are no provider configs.
- `plugins/governance/main.go:500-548` (`loadBalanceProvider`) filters provider configs by blacklist, allowlist, budgets, and rate limits.
- `plugins/governance/main.go:557-562` (`loadBalanceProvider`) logs when no eligible providers remain and returns nil; the TODO says a proper error should be sent when budgets or rates caused exclusion.
- `plugins/governance/main.go:580-599` (`loadBalanceProvider`) selects a provider using `rand.Float64()` over weights.
- `plugins/governance/main.go:619-645` (`loadBalanceProvider`) builds fallback providers by weight order after the random primary selection.
- `plugins/governance/main.go:743-747` (`applyRoutingRules`) returns routing-rule evaluation errors, but the core pre-request pipeline logs pre-request errors and continues.

Reasoning chain:

1. The launch invariant requires deterministic and advanced routing after entitlement and budget filters.
2. Current provider selection is intentionally probabilistic for load balancing.
3. Several "no config" or "no eligible provider" states are soft skips, not typed denials.
4. Routing errors returned from pre-request hooks are non-blocking at the core pipeline layer.
5. The invariant can hold only if launch routing is redefined as a typed policy engine whose hard-filtered candidate set and terminal errors cannot be bypassed by fallback, canary, shadow, or random selection.

Next-day action:

Create a routing outcome algebra and golden tests: `selected`, `no_candidate`, `policy_denied`, `budget_denied`, `capacity_denied`, `engine_error`, and `shadow_only`. Weighted and adaptive strategies should run only after hard filters and must emit deterministic receipts for audit.

### A1-F4 - 1-5 second Aurora convergence does not follow from the inspected OSS control-plane mechanisms

Severity: High
Confidence: Medium-high
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `docs/roadmap/extreme-reliability-and-day2-operations.md:49-63` specifies Aurora as launch authority with transactional outbox, polling repair, monotonic snapshots, checksums, and stale-security fail-closed behavior.
- `docs/roadmap/extreme-reliability-and-day2-operations.md:64-76` states there is no mandatory Redis, gossip, shared filesystem, or peer availability requirement.
- `transports/config.schema.json:4948-5016` defines cluster mode using memberlist gossip and a gRPC counter-sync layer.
- `transports/bifrost-http/lib/config.go:548-552` wires feature flags to an optional sync delegate for cluster-wide gossip.
- `transports/bifrost-http/server/server.go:412-416` broadcasts virtual-key-scoped model config changes to peers through cluster gossip.
- `plugins/governance/store.go:2176-2187` (`DumpRateLimits`) treats deadlocks as benign because usage data is expected to be synced via gossip and written next cycle.
- `plugins/governance/store.go:2248-2258` (`DumpBudgets`) uses the same gossip-based assumption for budget dumps.

Reasoning chain:

1. The deployment premise allows 1-5 second convergence but says Redis is optional and peer/gossip availability must not be required.
2. The roadmap describes the desired Aurora outbox/snapshot authority.
3. Inspected OSS mechanisms still include gossip assumptions for configuration and counter convergence.
4. If gossip is disabled, missed, partitioned, or not part of the internal launch profile, those mechanisms do not prove the desired convergence bound.
5. The convergence invariant follows only from an implemented Aurora snapshot/outbox protocol with per-pod cursors, leases, monotonic revision checks, startup readiness gates, and stale-policy kill semantics.

Next-day action:

Write the concrete convergence contract and a pod lifecycle test matrix: lost `NOTIFY`, outbox cursor lag, Aurora failover, pod restart with empty cache, stale security-reduction lease expiry, and checksum mismatch. Mark gossip and Redis as accelerators only if the Aurora path passes alone.

### A1-F5 - Extreme availability is contradicted by current default health probe wiring

Severity: High
Confidence: High
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `transports/bifrost-http/handlers/health.go:26-29` (`HealthHandler.RegisterRoutes`) exposes only `GET /health`.
- `transports/bifrost-http/handlers/health.go:32-37` (`HealthHandler.handleHealth`) returns OK only when DB pings are disabled.
- `transports/bifrost-http/handlers/health.go:38-89` (`HealthHandler.handleHealth`) pings config, log, and vector stores with a timeout and returns 503 on failure.
- `helm-charts/bifrost/values.yaml:133-145` configures both liveness and readiness probes to hit `/health`.
- `helm-charts/bifrost/values.yaml:275-284` defaults `disableDbPingsInHealth` to `false`.
- `helm-charts/bifrost/templates/deployment.yaml:270-273` wires the configured liveness and readiness probes into the pod.
- `terraform/modules/bifrost/kubernetes/main.tf:158-178` and `terraform/modules/bifrost/aws/services/eks/main.tf:388-412` also use `/health` for liveness and readiness.

Reasoning chain:

1. The launch invariant says inference availability should not depend synchronously on Aurora, log storage, vector storage, evaluators, dashboards, or control-plane mutation paths.
2. Current defaults make liveness fail when backing stores fail.
3. Kubernetes liveness failure restarts an otherwise healthy gateway process.
4. In an Aurora or auxiliary-store incident, this can create restart storms and reduce data-plane availability.
5. Therefore, current deployment defaults do not prove the extreme availability invariant.

Next-day action:

Split probes into process-only `/livez`, data-plane `/readyz`, and diagnostic `/healthz` or `/health`. Liveness must not ping stores. Readiness should prove a valid local snapshot, provider worker capacity, and policy lease status.

### A1-F6 - Privacy-safe traces and evals do not follow from default trace/log content capture

Severity: High
Confidence: High
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `framework/tracing/tracer.go:259-307` (`PopulateLLMRequestAttributes`) copies request attributes into spans and propagates input messages to the root span.
- `framework/tracing/llmspan.go:227-275` (`PopulateChatRequestAttributes`) marshals input messages into trace attributes.
- `framework/tracing/llmspan.go:277-303` (`PopulateChatResponseAttributes`) marshals output messages into trace attributes.
- `plugins/otel/main.go:86-89` (`Config`) exposes `DisableContentLogging`; when false, content is exportable.
- `plugins/otel/main.go:98-104` (`Config`) exposes `DisableRootSpanContent`, which only strips root-span duplicate content.
- `plugins/otel/converter.go:216-254` (`convertAttributesToKeyValues`) drops content attributes only when `disableContentLogging` is true.
- `plugins/logging/main.go:145-157` (`LoggerPlugin.NewLoggerPlugin`) defaults content logging to enabled unless `disableContentLogging` is set.
- `plugins/logging/main.go:650-785` (`LoggerPlugin.createLogEntry`) stores request content, tools, params, and raw passthrough JSON when content logging is enabled.
- `plugins/logging/operations.go:230-286` (`processChatOrTextCompletion`) stores output content when content logging is enabled.

Reasoning chain:

1. The launch invariant requires privacy-safe traces and evals.
2. Current tracing and logging code can capture raw prompts, outputs, tool definitions, and arguments.
3. There are configuration flags to suppress content, but flags are not the same as a privacy transform proof.
4. Optional eval/flywheel services that consume traces would inherit raw-content risk unless a transform/receipt boundary exists before persistence or export.
5. Therefore, privacy safety does not deductively follow from the current defaults or from OTEL/logging flags alone.

Next-day action:

Insert a privacy transform envelope before logging, OTEL export, eval capture, and evidence generation. Require a redaction/allowlist receipt on each stored artifact, default raw content off in enterprise profiles, and add canary tests proving sensitive tokens cannot reach logs, spans, eval queues, or draft MR evidence.

### A1-F7 - MCP governance is partially enforced at execution, but not proven before credential acquisition and all side effects

Severity: High
Confidence: High
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `plugins/governance/main.go:1391-1488` (`GovernancePlugin.PreMCPHook`) validates MCP tool execution requests and denies inactive, expired, or unauthorized virtual keys.
- `plugins/governance/main.go:1408-1411` (`GovernancePlugin.PreMCPHook`) skips codemode tools.
- `plugins/governance/main.go:1490-1568` (`GovernancePlugin.PostMCPHook`) records MCP tool usage and cost only after execution, and returns without tracking when there is no virtual key.
- `plugins/governance/main.go:1570-1587` (`GovernancePlugin.PreMCPConnectionHook`) explicitly states that connection-time policy checks remain in `PreMCPHook` and this hook only populates identity for credential-store resolution.
- `plugins/governance/main.go:1592-1613` (`GovernancePlugin.PreMCPConnectionHook`) stamps identity when a virtual key is recognized, but leaves identity unset for unknown virtual keys instead of producing a terminal denial there.
- `transports/bifrost-http/handlers/mcpserver.go:531-582` (`MCPHandler.fetchToolsForVK`) builds per-virtual-key tool exposure lists and uses an empty include list as deny-all.
- `transports/bifrost-http/handlers/mcpserver.go:619-629` (`MCPHandler.getMCPServerForRequest`) supports JWT, virtual-key, OAuth, and unauthenticated routing depending on configuration.
- `transports/bifrost-http/handlers/mcpserver.go:780-784` (`MCPHandler.getMCPServerForRequest`) routes unauthenticated requests to the global MCP server when auth enforcement is disabled.
- `transports/bifrost-http/handlers/mcpserver.go:846-881` (`MCPHandler.ensureVKMCPServer`) lazily creates per-virtual-key MCP servers after checking that the virtual key exists and is active.

Reasoning chain:

1. The launch invariant requires MCP governance, especially for credentials and stateful side effects.
2. Tool execution allowlisting exists and is meaningful.
3. The connection hook is intentionally not the final policy gate and may be used before credential resolution.
4. If credential acquisition or connection setup has side effects or grants broad capabilities, execution-time denial is too late for a strict reference-monitor invariant.
5. Production also depends on auth enforcement configuration; an auth-disabled global server is not compatible with enterprise MCP governance.

Next-day action:

Define MCP phases as `target_resolve_without_secret`, `policy_authorize`, `credential_attentuate`, `connect`, `invoke`, and `settle`. Add tests that unauthorized virtual keys, stale snapshots, codemode tools, and anonymous requests cannot obtain credentials or execute side effects.

### A1-F8 - Okta entitlement invariants are specified, but not proven by current OSS user-governance paths

Severity: High
Confidence: Medium
Risk status: Confirmed known risk, not a new discovery

Evidence:

- `docs/roadmap/enterprise-oss-program.md:183-201` requires OIDC/SCIM/Okta reconciliation, group-to-profile mapping, deprovisioning, and bounded group-removal revocation.
- `plugins/governance/main.go:996-1040` (`GovernancePlugin.EvaluateGovernanceRequest`) calls user, team, customer, and virtual-key checks.
- `plugins/governance/store.go:1660-1664` (`CheckUserRateLimit`) is a no-op in the inspected community store.
- `plugins/governance/store.go:1732-1735` (`UpdateUserBudgetUsageInMemory`) is a no-op in the inspected community store.
- `plugins/governance/store.go:3536-3556` (`GetUser`, `GetUserByEmail`, `UpdateUser`, `ListUsers`) are no-op or not-supported implementations in the inspected community store.
- `transports/bifrost-http/handlers/mcpserver.go:646-656` (`MCPHandler.getMCPServerForRequest`) can resolve a user identity to a representative virtual key when an identity resolver is configured.
- `transports/bifrost-http/handlers/mcpserver.go:822-827` (`MCPHandler.getMCPServerForRequest`) checks user active status and resolves a user virtual key for user-mode requests.

Reasoning chain:

1. The launch invariant requires Okta entitlements across pods with bounded deprovisioning.
2. The roadmap specifies the desired identity domain.
3. The inspected OSS store leaves user governance mostly as no-op placeholders, and user-mode MCP depends on an identity resolver being configured.
4. Enterprise code may implement these paths, but the invariant does not follow from this repository alone.
5. The proof obligation is an immutable principal/access-profile snapshot with a principal epoch that every request, virtual key, and MCP invocation checks locally.

Next-day action:

Produce the identity proof harness: SCIM deactivate, group removal, OIDC token with stale groups, concurrent pod snapshots, and MCP user-mode access. The expected result is revocation within the launch bound without live Okta calls on the request path.

## Risks

- A budget system that settles after the fact can pass normal tests while allowing unbounded or poorly bounded cross-pod overspend during bursts.
- Best-effort plugin semantics are useful for observability and optional behavior, but dangerous if reused for auth, quota, privacy, or MCP authorization.
- Probabilistic routing and soft-skip routing states can obscure policy failures and make post-incident reconstruction difficult.
- Store-backed liveness probes can convert an Aurora or auxiliary-store incident into a data-plane outage.
- Raw trace/log content can leak into evals, evidence packets, or draft MRs unless privacy is enforced before persistence.
- MCP connection and credential phases can violate the intended governance model even if final tool execution is denied.
- Enterprise-only implementations may satisfy some invariants, but they still need repository-visible contracts and regression tests before launch.

## Recommendations

### P0

- Build the mandatory admission/reference-monitor path. Effort: M. It must run before provider/tool side effects and convert auth, entitlement, quota reservation, privacy, routing, stale snapshot, and MCP authorization failures into terminal outcomes.
- Implement Aurora fenced budget reservations. Effort: L. Required states: reserve, commit, cancel, expire, renew, controlled overdraft, alert emitted, and reconciliation. Use idempotency keys that include request, attempt, turn, provider, model, and tool identity.
- Implement the Aurora outbox/snapshot convergence proof. Effort: L. Include monotonic revisions, checksums, per-pod cursors, NOTIFY plus polling, startup readiness without peer dependency, and stale-security fail-closed leases.
- Lock down enterprise privacy defaults. Effort: M. Raw content must be disabled by default and any persisted trace/eval/evidence artifact must carry a transform receipt.

### P1

- Split `/livez`, `/readyz`, and diagnostic health endpoints; update Helm and Terraform defaults. Effort: S-M.
- Replace launch routing with typed deterministic outcomes and audit receipts before applying weighted, adaptive, canary, or shadow behavior. Effort: M.
- Refactor MCP governance around target resolution, authorization, attenuated credential acquisition, invocation, and settlement. Effort: M.
- Add Okta entitlement snapshot tests with group removal, deprovisioning, stale token, and multi-pod convergence cases. Effort: M.

### P2

- Add a route/policy proof receipt to request logs after privacy transformation. Effort: M. It should record hard-filtered candidates, removal reasons, selected route, snapshot revision, and fallback eligibility without raw prompt content.
- Add a cross-pod budget and routing chaos suite against ephemeral PostgreSQL/Aurora-compatible storage. Effort: M-L.
- Define an explicit degraded-mode matrix for Aurora down, Okta down, provider down, policy stale, budget ledger lagging, OTEL down, and eval down. Effort: S-M.

### P3

- Introduce optional Redis only as a measured accelerator for read-heavy snapshots or advisory leases. Effort: M. Redis must not become required for correctness unless the launch contract changes.
- Add an offline auditor that recomputes admission, routing, and budget outcomes from the durable ledger to detect snapshot or implementation drift. Effort: M.

### P4

- Keep adaptive learning, eval optimization, and autonomous skill promotion out of the inference availability path until after launch. Effort: ongoing governance.
- Later, use sanitized evidence to propose issues, patches, and draft MRs, but keep protected Git merge requests and human approval as the only promotion path.

## Alternatives And New Ideas

- Aurora-only first: prove correctness with Aurora outbox and reservation tables before adding Redis, gossip, or gRPC counter sync. This best matches the stated deployment premise.
- Capability lease token: mint a local, signed per-request admission receipt from the current snapshot and reservation. Providers and MCP tools consume the receipt instead of re-reading mutable policy.
- Shadow auditor: asynchronously recompute every admission and budget decision from the durable ledger and emit high-severity alerts on divergence.
- Routing proof receipt: store a sanitized record of candidate expansion, hard-filter removals, selected provider, fallback order, and snapshot revision for each request.
- MCP attenuated credential broker: issue short-lived, tool-scoped credentials only after policy authorization, rather than resolving broad credentials before the final invocation gate.
- Privacy quarantine queue: send raw candidate evidence only to a tightly controlled in-memory transformer, and persist only transformed artifacts with receipts.

## Assumptions

- The inspected repository is the current shared basis for the internal fork; enterprise-private code may exist but was not available in this read-only pass.
- The target deployment is multi-pod Kubernetes with Aurora PostgreSQL as durable authority and no mandatory Redis or peer-gossip dependency.
- The 1-5 second convergence bound applies to security reductions such as revocation, entitlement removal, and policy tightening.
- Human-approved protected Git merge requests are the only promotion path at launch.
- Existing roadmap warnings and open Beads are owner-acknowledged known risks.
- No benchmark numbers are inferred here.

## Questions

- Will the launch profile enable existing gossip/gRPC cluster sync, or must the Aurora path work with those disabled?
- What is the exact permitted overdraft bound per tenant, virtual key, model, and tool, including long streams and retries?
- Which requests lack reliable pre-call max-token or cost estimates, and how should reservations handle them?
- What is the intended fail-closed behavior when a pod's security snapshot is stale and Aurora is temporarily unavailable?
- Is SCIM push, Okta polling, OIDC token introspection, or a combination the authoritative identity update source?
- Is `/mcp` auth enforcement mandatory in every production profile, and are codemode tools in launch scope?
- Which trace, log, eval, and MR-evidence sinks are allowed to store sanitized content, and for how long?

## Uncertainty

- Enterprise-specific governance, identity, and persistence implementations may satisfy some of these invariants outside the inspected tree.
- Line numbers are exact for the repository state inspected during this pass and may drift after edits.
- This pass did not run product tests because the user requested read-only planning analysis and no product code changes.
- The analysis used targeted roadmap and code evidence rather than a full exhaustive read of every document and provider.
- The exact Aurora schema and protected-MR workflow may be in private planning artifacts not visible here.

## Tensions

- Low-overhead inference vs synchronous correctness: hard budget reservations add a control point, so the design must keep it cheap and offload only noncritical learning work.
- Availability vs fail-closed security: stale policy cannot increase privilege or spend, but overly aggressive fail-closed leases can reduce readiness during Aurora incidents.
- Privacy vs observability: the system needs enough evidence for debugging and evals, but raw prompts and tool arguments cannot leak into durable traces or draft MRs.
- Determinism vs adaptive routing: launch needs reproducible policy decisions; learning-based routing should operate only after deterministic hard filters and outside the availability path.
- Human approval vs flywheel speed: the gateway can propose issues, patches, and draft MRs, but protected Git approval must remain the only production promotion mechanism at launch.

## Final Confidence

Overall confidence: High that the listed invariants do not yet follow from the inspected mechanisms alone. Medium confidence on Okta-specific gaps because enterprise identity code may live outside the visible OSS paths. The recommended next step is not further abstract planning; it is proof-oriented implementation and failure testing of the P0 admission, reservation, snapshot, and privacy boundaries.
