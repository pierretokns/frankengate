# Failure Mode (F4): Enterprise Kubernetes Launch

## Thesis

The dominant launch failure mode is not slow inference or a single provider outage. It is control-plane drift: local snapshots, async accounting, best-effort plugin hooks, MCP connection setup, privacy capture, Kubernetes probes, and Git/MR proposal automation each look acceptable in isolation, but their boundaries are not yet strong enough for enterprise multi-pod operation with Aurora, Okta-derived entitlements, controlled budget overdraft, and privacy-safe learning.

I treat the existing roadmap warnings as confirmed known risks. The findings below focus on where current code and open Beads still allow subtle cascades if those risks are not closed before launch. No benchmark numbers are invented here.

## Findings

### F4-01: Budget authority can drift faster than the intended overdraft envelope

**Severity:** P0 for enterprise budget enforcement; High availability risk only if fixed with synchronous per-request Aurora writes.
**Confidence:** High.

**Evidence:**

- `plugins/governance/main.go:926-1040`, `EvaluateGovernanceRequest`, reads the virtual key and evaluates budget/rate state from the local store before the provider call.
- `plugins/governance/main.go:1322-1385`, `PostLLMHook`, launches usage accounting asynchronously after the response, including streaming handling.
- `plugins/governance/tracker.go:65-70` sets `workerInterval = 10 * time.Second`; `tracker.go:91-214`, `UpdateUsage`, mutates process-local usage.
- `plugins/governance/tracker.go:217-260` periodically resets counters and calls store dump methods.
- `plugins/governance/store.go:2104-2168`, `DumpRateLimits`, and `store.go:2194-2240`, `DumpBudgets`, write absolute in-memory usage values back to the DB.
- `plugins/governance/store.go:2176-2187` and `store.go:2248-2258` tolerate deadlocks with comments that usage is synced through gossip.
- Roadmap requirement: `docs/roadmap/MODE_OUTPUT_B5_L5.md:109-124` calls for pod-local lease/reservation with Aurora settlement, controlled overdraft, alerts, and audited authority rows.
- Beads read-only confirmation: `bif-kyy.4.9` tracks fenced renewable reservations for long streams and agent trajectories.

**Reasoning chain:** In one pod, post-hook accounting can be acceptable. Across pods, the launch requirement is an explicit overdraft envelope, not eventual best effort. Current accounting is local, late, and periodically dumped as absolute usage. A long stream, fallback chain, or MCP agent trajectory can consume beyond the local decision point before any durable settlement is visible to other pods. If several pods dump absolute values, the last writer can also hide concurrent consumption unless an external reconciler corrects it. Tightening this by putting Aurora in the inference path would violate the availability thesis; leaving it as-is violates the budget thesis.

**Next-day action:** Specify the budget ledger contract: reservation, renewal, settlement, expiry, alert threshold, overdraft approval row, and deterministic failure behavior. Add a three-pod Aurora integration test that forces concurrent streams, pod death before post-hook flush, deadlock/retry, and fallback attempts. The test should assert an envelope, not exact timing.

### F4-02: Virtual-key and entitlement revocation can publish hybrid state across pods

**Severity:** P0 for revocation and Okta entitlement correctness.
**Confidence:** High.

**Evidence:**

- Roadmap requirement: `docs/roadmap/technical-decision-options.md:46-53` requires atomic mutation/publication, monotonic revisions, duplicate/missed/reordered recovery, fail-closed staleness, and lock-free local reads after atomic swap.
- Roadmap recommendation: `docs/roadmap/MODE_OUTPUT_B5_L5.md:75-91` calls for opaque random virtual keys, keyed digests, no plaintext logging, and fail-closed stale/malformed/revoked behavior.
- `plugins/governance/store.go:922-933`, `GetVirtualKey`, looks up process-local virtual keys by raw key value from a `sync.Map`.
- `plugins/governance/store.go:951-965`, `storeVirtualKey`, stores both raw key value and ID indexes.
- `plugins/governance/store.go:3012-3187`, `UpdateVirtualKeyInMemory`, mutates related virtual-key, budget, rate-limit, user, and model config maps through many separate stores/deletes before publishing the virtual key.
- `framework/configstore/tables/virtualkey.go:217-247` stores `Value` plus a `ValueHash`; `virtualkey.go:276-287`, `MarshalJSON`, emits the resolved key value; `virtualkey.go:299-315`, `BeforeSave`, computes an unkeyed SHA-256 hash.
- Beads read-only confirmation: `bif-kyy.6.7` covers stale-policy kill semantics; `bif-kyy.5.6` covers deprovisioning across sessions, keys, caches, MCP, and live connections.

**Reasoning chain:** The launch design wants immutable revisioned snapshots. Current hot state is a collection of process-local maps, and a virtual-key update mutates related entries independently. During an Okta entitlement change or key revocation, a request can observe a new key with old model configs, a deleted model config with old budgets, or a raw-key index that is ahead of dependent policy state. Across pods, missed notifications or reordered updates widen that window unless snapshot revisions are the unit of publication. Separately, plaintext virtual-key JSON output and raw-key hot indexes conflict with the desired keyed-digest/minimal-exposure posture.

**Next-day action:** Define a `GovernanceSnapshot` aggregate with a monotonic revision, checksum, staleness deadline, keyed virtual-key digest index, and atomic pointer publication. Add a hybrid-state test that repeatedly updates a virtual key, its budgets, its model config, and its Okta groups while issuing concurrent requests; any mixed revision should fail the test.

### F4-03: Routing failures degrade into default behavior instead of typed policy outcomes

**Severity:** High for deterministic routing, residency, canary safety, and cost containment; Medium for basic auth because `PreLLMHook` still performs governance checks.
**Confidence:** High.

**Evidence:**

- `core/schemas/plugin.go:280-297`, `PreRequestHook`, documents that errors do not block and cannot abort.
- `core/bifrost.go:7300-7338`, `RunPreRequestHooks`, logs pre-request hook errors and continues.
- `plugins/governance/main.go:500-561`, `PreRequestHook`, filters provider configs by model, budget, and rate limits; when no eligible providers remain, it logs a TODO and returns `nil`, continuing without modification.
- `plugins/governance/main.go:729-748`, `applyRoutingRules`, logs routing engine errors and returns `nil, nil`.
- `core/bifrost.go:4787-4816`, `shouldTryFallbacks`, defaults to allowing fallbacks unless `AllowFallbacks` is explicitly false.
- Roadmap requirement: `docs/roadmap/MODE_OUTPUT_B5_L5.md:126-140` calls for deterministic ordered routing policy at launch and omits learned/bandit routing.
- Roadmap guardrail: `docs/roadmap/technical-decision-options.md:314-324` says learned or semantic routing must run after hard filters and never weaken governance.
- Beads read-only confirmation: `bif-kyy.2.4` tracks mandatory request guards versus best-effort plugin hooks.

**Reasoning chain:** Best-effort pre-request routing is a reasonable extension point, but it is not a mandatory policy boundary. If route evaluation fails, if the model catalog is inconsistent, or if all configured providers are filtered out, the current behavior can continue into the default provider/fallback path. That can bypass routing intent: deterministic provider order, region class, cost ceiling, canary exclusion, or health quarantine. This is not the same as bypassing all authentication, because later governance checks still exist, but it is enough to violate the enterprise launch contract.

**Next-day action:** Introduce a typed route decision algebra: `allow(provider set, fallback policy)`, `deny(reason)`, `defer(reason)`, and `control-plane-stale(reason)`. Treat malformed policy, empty eligible set, and stale hard-filter snapshots as terminal decisions unless an explicit static fallback is configured and audited.

### F4-04: MCP governance can occur after target and connection preparation

**Severity:** P0 for privileged MCP tools; High for ordinary MCP tools in regulated deployments.
**Confidence:** High.

**Evidence:**

- `core/mcp/exec.go:52-66`, `executeToolWithHooks`, begins the tool execution path.
- `core/mcp/exec.go:85-91` calls `prepareToolExecution` and returns if connection preparation fails, before `RunWithPluginPipeline`.
- `core/mcp/exec.go:115-124` wraps `toolsManager.ExecuteTool` in the plugin pipeline only after the execution context is prepared.
- `core/mcp/exec.go:133-189`, `prepareToolExecution`, validates filters but also calls `AcquireClientConn`.
- `core/mcp/clientmanager.go:47-52`, `AcquireClientConn`, returns existing persistent connections without a connection plugin gate.
- `core/mcp/clientmanager.go:54-80` runs `PreConnectionHook` only for per-user ephemeral connections.
- `core/bifrost.go:7556-7615`, `RunMCPPreConnectionHooks`, skips plugins that do not implement `MCPConnectionPlugin`; connection hook errors are logged, with short-circuit only when a connection plugin returns one.
- Roadmap requirement: `docs/roadmap/MODE_OUTPUT_B5_L5.md:185-196` calls for identity-derived MCP narrowing and no wildcard privileged tools.
- Beads read-only confirmation: `bif-bpfk.19` requires normalize target -> mandatory policy -> attenuated credential -> connection -> wire call -> terminal receipt.

**Reasoning chain:** Existing filters remove many unavailable tools, but the stricter launch invariant is ordering: mandatory policy must run before credential selection, connection allocation, or any upstream packet. The current execute path prepares the target and connection before the main MCP plugin pipeline. For persistent clients, the connection is already live and no pre-connection gate runs. For per-user clients, credentials are resolved after the connection gate, but the gate still sits inside connection acquisition rather than before the mandatory execution policy. A denied call therefore may not leave the terminal receipt trail expected by the roadmap, and privileged tools may get too close to upstream state before denial.

**Next-day action:** Move MCP mandatory policy to the front of `executeToolWithHooks`, before `AcquireClientConn`. The unit test should prove that a denied call performs zero credential resolution, zero connection acquisition, zero upstream wire call, and emits a terminal denial receipt.

### F4-05: Privacy-safe traces and evals are not guaranteed by the current logging/trace substrate

**Severity:** P0 for privacy launch if learning/eval/proposal features are enabled; High otherwise because defaults can still over-capture.
**Confidence:** High.

**Evidence:**

- Privacy requirement: `docs/roadmap/privacy-redaction-and-learning-boundaries.md:3-9` says raw production content must not enter logs, replay, eval, skill improvement, training, analytics, or external observability by default.
- Privacy requirement: `docs/roadmap/privacy-redaction-and-learning-boundaries.md:18-32` requires classification before capture, deterministic recognizers before durable sinks/exporters, privacy receipts, and metadata-only behavior on detector failure.
- `framework/configstore/tables/clientconfig.go:20-22` defaults `EnableLogging` to true and `DisableContentLogging` to false.
- `transports/bifrost-http/lib/ctx.go:522-545` parses per-request raw storage and content logging headers into context.
- `core/bifrost.go:6357-6417` computes raw capture flags per attempt and writes `BifrostContextKeyShouldStoreRawInLogs`.
- `plugins/logging/main.go:772-784` captures passthrough JSON request bodies in log initial data.
- `plugins/logging/main.go:1075-1089` writes raw request/response on errors when raw storage is enabled.
- `plugins/logging/main.go:1102-1135` backfills raw streaming request/response data from the accumulator or errors.
- `plugins/logging/main.go:1520-1640`, `PostMCPHook`, logs MCP tool result content when content logging is enabled.
- `core/schemas/trace.go:107-127`, `ApplyRedactionReplacements`, redacts span content attributes but not arbitrary plugin logs or request headers; `trace.go:151-203`, `SnapshotForExport`, clones attributes, request headers, and plugin logs.
- `framework/tracing/tracer.go:699-755`, `CompleteAndFlushTrace`, snapshots the trace and asynchronously calls observability plugin `Inject`.
- Managed flywheel status: `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:190-209` says `EvidenceEnvelopeBuilder`, `EvidenceOutbox`, and related contracts are not implemented.
- Beads read-only confirmation: `bif-bpfk.18` covers the privacy-preserving evidence envelope/outbox; `bif-cks.14` covers stream accumulation and capture fanout.

**Reasoning chain:** The current logging and tracing code is useful observability infrastructure, but it is not yet the privacy evidence plane. Content logging defaults are permissive unless config disables them. Raw capture can be enabled by provider/request policy. Plugin logs and MCP result content can enter trace/log export paths outside a single mandatory privacy receipt model. If a proposal worker or eval service later consumes these logs as evidence, it can accidentally inherit raw prompts, tool outputs, headers, or error bodies before classification and retention policy are applied. That would violate the launch statement even if inference availability remains healthy.

**Next-day action:** Freeze launch config to metadata-only by default and block learning/eval/proposal consumers from reading existing log tables directly. Implement the evidence envelope as a separate async outbox with explicit `PrivacyTransformReceipt`, purpose, retention, region, owner, and deletion propagation before any skill proposal automation consumes production-derived data.

### F4-06: Current Kubernetes health checks can turn Aurora/log/vector impairment into pod churn

**Severity:** P0 for extreme availability if deployed as-is; Medium if chart values are overridden before launch.
**Confidence:** High.

**Evidence:**

- Reliability requirement: `docs/roadmap/extreme-reliability-and-day2-operations.md:37-47` says the inference path must not perform per-request Aurora, Okta, peer, or Redis checks.
- Reliability requirement: `docs/roadmap/extreme-reliability-and-day2-operations.md:78-98` says liveness cannot depend on Aurora/provider availability, readiness should reflect snapshot/capacity, and HPA should not use only CPU.
- `transports/bifrost-http/handlers/health.go:26-29` registers only `/health`.
- `transports/bifrost-http/handlers/health.go:31-37` returns OK only when DB pings are disabled.
- `transports/bifrost-http/handlers/health.go:38-89` pings config, log, and vector stores under a ten-second timeout and returns 503 on any error.
- `helm-charts/bifrost/values.yaml:133-149` uses `/health` for both liveness and readiness by default.
- `helm-charts/bifrost/values.yaml:151-171` disables autoscaling by default; when enabled, HPA is CPU/memory based.
- `helm-charts/bifrost/values.yaml:184-193` leaves rolling strategy as default unless the operator overrides it.
- `helm-charts/bifrost/templates/hpa.yaml:17-33` renders CPU/memory metrics only.
- `terraform/modules/bifrost/kubernetes/main.tf:158-178` also uses one health-check path for liveness and readiness; `main.tf:239-278` configures CPU/memory HPA.

**Reasoning chain:** The code substrate can keep serving from local snapshots during Aurora or auxiliary store impairment, but the deployment defaults can undo that by killing pods whose `/health` endpoint returns 503 because a config/log/vector store ping failed. A control-plane hiccup then becomes a data-plane churn event: pods restart, connection pools drain, warm snapshots may be lost, and rollout capacity drops. CPU/memory-only HPA also misses queue depth, provider throttling, stream concurrency, and in-flight request pressure, which are the scaling signals that matter for this gateway.

**Next-day action:** Split probes into `/livez`, `/readyz`, and `/startupz`. Liveness should be process/event-loop only. Readiness should require a fresh enough validated governance snapshot, provider worker capacity, and local queue health, not optional log/vector stores. Add PDB, topology spread, explicit rolling strategy, and HPA signals tied to queues, streams, and provider concurrency.

### F4-07: Git/MR skill proposals are safe only if evidence and credentials are split first

**Severity:** High if enabled at launch; Low if restricted to manual issue creation with no production evidence ingestion.
**Confidence:** Medium-high.

**Evidence:**

- Launch constraint: `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:5-18` says internal skills are promoted only through protected Git merge requests with mandatory human approval; the gateway may create issues, patches, or draft MRs but cannot merge, bypass protection, or publish.
- Promotion boundary: `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:151-166` permits automation to prepare evidence, tests, patches, issues, and draft MRs, but not merge or publish; some classes never auto-promote.
- Current status: `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:190-209` says managed Flywheel contracts and evidence builders are not implemented.
- Managed evidence boundary: `docs/roadmap/managed-agent-evidence-and-flywheel-services.md:21-41` requires ingest/index/proposals to stay out of the inference path and to downgrade/drop optional content under backpressure.
- Roadmap recommendation: `docs/roadmap/MODE_OUTPUT_B5_L5.md:170-183` recommends evidence-backed issue/draft MR only, no merge/protected-branch creds, and launch issues first.
- Beads read-only confirmation: `bif-bpfk.7` covers Git/MR-backed internal skill proposal workflow and requires no raw private traces/secrets, CI/CODEOWNERS approval, sandboxing, tests that gateway credentials cannot merge/publish, immutable SHAs, and revert.

**Reasoning chain:** Protected Git merge requests are a strong human-control boundary, but only after the proposal worker has safe evidence and safe credentials. Without the evidence envelope, proposals can smuggle raw traces into diffs, test fixtures, issue text, or MR descriptions. Without a credential split, the gateway or worker can become a confused deputy with repo write authority broader than intended. This is a post-launch automation hazard if disabled, but it becomes a launch blocker if positioned as part of the first enterprise release.

**Next-day action:** Make launch policy explicit: issue-only or draft-MR-only, backed by a separate Git App token that cannot merge, administer branches, publish packages, or bypass CODEOWNERS. Add a negative integration test that attempts merge/publish/protected-branch mutation with the gateway/proposal credentials and proves denial.

## Cascading Risks

- A budget overspend incident can cascade into routing failure if budget filters remove all eligible providers and routing then continues with default behavior.
- An Okta deprovision event can cascade into MCP exposure if stale snapshots still permit a tool and the MCP path acquires a persistent connection before mandatory policy receipts.
- Aurora impairment can be survivable at the data-plane design level but fatal at the deployment level if `/health` drives liveness restarts.
- Privacy capture can become a skill-promotion incident when observability logs are later treated as evidence without a privacy receipt.
- Attempting to close budget drift by adding synchronous Aurora checks to inference would solve one class of correctness bug by violating the availability invariant.

## Recommendations

**P0: Define mandatory pre-provider control gates. Effort: Medium.**
Unify virtual-key validation, Okta entitlement snapshot, hard route filters, budget reservation, and MCP mandatory policy as typed allow/deny decisions before provider writes or MCP connection acquisition.

**P0: Replace multi-map hot governance state with immutable revisioned snapshots. Effort: Large.**
Publish virtual keys, budgets, model configs, routing policy, MCP grants, and stale-policy deadlines as one atomic pointer with revision/checksum. Keep Aurora/outbox outside the hot path.

**P0: Implement budget reservations and settlement before enterprise launch. Effort: Large.**
Use fenced renewable reservations for long streams and agent loops, plus durable settlement, expiry, and alerting. Keep controlled overdraft as explicit policy, not accidental eventual consistency.

**P1: Split Kubernetes probes and scaling signals. Effort: Small-medium.**
Add `/livez`, `/readyz`, `/startupz`, PDB/topology spread, explicit rolling strategy, and HPA inputs for queue depth, in-flight streams, provider concurrency, and error saturation.

**P1: Build the privacy evidence envelope before evals or skill proposals. Effort: Large.**
Do not let proposal/eval workers read raw observability tables. Require privacy receipts, purpose, retention, region, owner, deletion propagation, and metadata-only fallback on classifier failure.

**P2: Make routing failures typed and auditable. Effort: Medium.**
Malformed routing policy, empty eligible provider sets, and stale hard filters should not silently continue. Provide an audited static fallback only where the enterprise policy explicitly allows it.

**P2: Harden virtual-key material handling. Effort: Medium.**
Move hot lookup to keyed digests, avoid plaintext virtual-key JSON except controlled one-time reveal semantics, and ensure logs/trace/export never receive plaintext key values.

**P3: Keep Git/MR proposal automation disabled or issue-only until evidence and credentials are split. Effort: Small for policy, Medium for tests.**
Use a no-merge/no-admin/no-publish Git App token, immutable SHAs, CODEOWNERS, and negative permission tests.

**P4: Defer learned routing and autonomous promotion. Effort: Small to defer, Large to later implement.**
Launch deterministic policy first. Later learning services can rank suggestions only after hard governance filters and never enter the availability path.

## Alternatives And New Ideas

- Use a two-lane control plane: a minimal P0 authority lane for revocation, budgets, routing, and MCP grants; a separate optional lane for observability/evals/proposals. The second lane may lag or drop data.
- Add a local `policy epoch` header to every trace/log/decision record. This makes mixed-revision incidents searchable without putting full policy content in logs.
- Treat MCP tool execution as a capability minting event: policy authorizes a narrow, short-lived capability, and only that capability can acquire credentials or a connection.
- Add a launch-time `metadata-only hard mode` flag that disables raw capture and content logging regardless of per-provider or per-request override until the privacy outbox is ready.
- Build a chaos test profile specifically for cascades: Aurora write outage, missed NOTIFY, Okta deprovision, budget threshold crossing, long stream, MCP denial, and rolling restart at the same time.

## Assumptions

- Aurora PostgreSQL is the durable control-plane authority, but inference must continue from validated local snapshots during transient Aurora impairment.
- Okta is not called synchronously per request; entitlements are reconciled into local authority tables and snapshots.
- Redis remains optional and cannot be a correctness dependency unless the architecture is explicitly changed.
- Internal skill promotion through protected Git remains mandatory human approval, with no gateway merge or publish authority.
- Heavy autonomous promotion is post-launch and should be disabled for the initial enterprise launch.

## Questions

- What is the maximum allowed budget overdraft envelope per scope: virtual key, team, customer, model, and provider?
- Which revocations must fail closed immediately on stale snapshots: virtual key revoke, Okta group removal, MCP grant removal, budget hard stop, route quarantine?
- Should plaintext virtual keys ever be retrievable after creation, or should the UI/API move to one-time reveal only?
- Which MCP tools are privileged enough to require per-call approval or just-in-time credential minting?
- Are logs already enabled in target enterprise environments with content logging on, and are any external observability exporters configured?
- Is the launch target multi-region or single-region Aurora? The failure envelope changes materially for regional write outage.

## Uncertainty

- I did not run benchmarks or chaos tests, so this analysis identifies plausible failure cascades from code and roadmap evidence, not measured frequencies.
- Some deployment defaults may be overridden in the private enterprise Helm/Terraform overlay. If so, the Kubernetes probe finding becomes a verification item rather than a direct launch blocker.
- Some raw logging paths are gated by provider/client/request configuration. The risk is highest where those toggles are enabled or where future evidence consumers treat logs as safe inputs.
- Beads are open work items, not implementation proof. I used them only to confirm known roadmap gaps and priorities.

## Tensions

- Stronger budget correctness wants durable coordination; extreme availability wants no synchronous control-plane dependency.
- Fast revocation wants small propagation windows; low overhead wants lock-free local reads and atomic snapshots.
- Rich evals and skill improvement want more evidence; privacy-safe launch wants less content capture and stricter purpose binding.
- MCP usability wants persistent connections and broad tool discovery; governance wants per-call capability narrowing and terminal receipts.
- Git automation wants fast proposal throughput; enterprise controls require human approval, least-privilege credentials, and immutable audit records.

## Final Confidence

Overall confidence: High that these are the major failure modes for the described launch shape. The most urgent next step is not adding more optional services; it is making the mandatory control decisions explicit, atomic, and testable while keeping Aurora, Okta, learning, and Git automation out of the inference availability path.
