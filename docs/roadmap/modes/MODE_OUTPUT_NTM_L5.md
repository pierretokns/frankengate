# NTM L5 Scope Control: Enterprise Launch Boundary

## Thesis

Launch Bifrost as a small enterprise control plane around the existing low-overhead Go gateway. The data plane should continue to use process-local provider queues, atomic runtime replacement, fast plugin/provider dispatch, and streaming accumulators. Enterprise policy state should converge through Aurora-backed versioned snapshots and local hot reads; no Okta, Git, evaluator, trainer, Redis, or peer pod dependency belongs on the request availability path.

The launch cut is strict: virtual keys, Okta-derived entitlements, budgets with controlled overdraft, deterministic routing, MCP governance, privacy-safe traces/evidence, Kubernetes availability hardening, and human-approved Git/MR skill proposal flow are launch scope. Learning services, autonomous promotion, semantic/bandit routing, raw replay/eval pipelines, and public marketplace behavior are optional or omitted unless they remain fully outside the inference path.

Existing roadmap warnings are treated here as confirmed known risks, not discoveries. The purpose of this L5 pass is to keep scope small enough to operate on day two.

## Classification

| Scope | Include |
| --- | --- |
| Launch | Aurora authority/outbox/snapshot, virtual-key lifecycle, Okta group reconciliation, local hard policy gate, bounded budget reservations and overdraft alerts, deterministic routing/fallback, MCP allow-list/firewall, metadata-first audit/evidence, split Kubernetes probes, Git issue/draft-MR skill proposal with mandatory human approval. |
| Optional | Redis counters if lease overshoot is unacceptable, `LISTEN/NOTIFY` wakeups above polling, deterministic canary/shadow, encrypted approved-content replay, external eval/RAG services, private recall, stateful MCP owner service. |
| Omit | Per-request Aurora/Okta/Redis lookup, gossip as authority, inline evaluator/trainer, online semantic/bandit router, autonomous skill merge/publish, gateway-held merge credentials, raw-log-by-default storage, arbitrary marketplace promotion inside gateway pods. |

## Beads Read-Only Signals

Read-only Beads inspection aligns with this cut. Launch-relevant P0 items include `bif-bpfk.7` for Git/MR-backed internal skill proposals with human gate, `bif-bpfk.19` for MCP policy before credential/connection acquisition, `bif-kyy.15.3` for the MCP invocation firewall, `bif-kyy.15.4` for per-call attenuated MCP credentials, and `bif-kyy.15.18` for stateful MCP ownership/failover ADR/prototype. Autonomous promotion and heavier flywheel items are post-launch scope.

## Findings

### L5-F01 - Mandatory gates cannot rely on best-effort plugin errors

**Classification:** Launch.

**Evidence:**

- `core/schemas/plugin.go:192-204` documents plugin errors as warnings and `AllowFallbacks=nil` as fallback-allowed.
- `core/schemas/plugin.go:283-294` defines `PreRequestHook` as the canonical routing phase but explicitly non-blocking and unable to abort.
- `core/bifrost.go:7275-7297` logs `PreLLMHook` errors and only stops provider execution through short-circuit.
- `core/bifrost.go:7311-7336` logs `PreRequestHook` errors and continues.
- `plugins/governance/main.go:398-405` keeps `HTTPTransportPreHook` as a no-op.
- `plugins/governance/main.go:1280-1307` enforces governance through `PreLLMHook` short-circuit.

**Reasoning chain:** The current substrate is fast because plugin failures usually do not stop execution. That is correct for logging, routing hints, and optional observability, but unsafe for enterprise auth, virtual-key revocation, entitlement denial, hard budget denial, and privacy gates. Those launch controls must be implemented as explicit short-circuits or a named reference-monitor boundary over local immutable snapshots. Returning an ordinary hook error is not a security control.

**Severity:** Critical for this deployment. A warn-and-continue policy bug can become an unauthorized provider call or MCP invocation.

**Confidence:** High.

**Next-day action:** Write a one-page gate matrix that maps every launch deny condition to `HTTPTransportPreHook`, `PreLLMHook` short-circuit, `PreMCPHook` short-circuit, or startup/readiness refusal. Mark ordinary plugin errors as non-authoritative.

### L5-F02 - Controlled overdraft needs a reservation ledger, not current local dumps

**Classification:** Launch.

**Evidence:**

- `framework/configstore/tables/budget.go:10-17` has `MaxLimit`, `ResetDuration`, `LastReset`, and `CurrentUsage`, but no reservation, overdraft grant, alert state, or settlement identity.
- `plugins/governance/store.go:421-457` increments budget usage with in-process CAS.
- `plugins/governance/tracker.go:91-140` applies usage after provider work by mutating in-memory provider/model counters.
- `plugins/governance/tracker.go:207-214` applies VK/team/customer budget usage after usage exists.
- `plugins/governance/tracker.go:65-70` sets a 10-second worker interval for background reset/dump work.
- `plugins/governance/store.go:2194-2248` dumps local in-memory budget values to the database.
- `plugins/governance/store.go:2254-2258` treats deadlock as non-fatal because usage will be synced later by gossip.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:109-124` already selects bounded pod-local reservation with Aurora settlement and controlled overdraft semantics.

**Reasoning chain:** The existing usage tracker is post-paid and process-local. In a multi-pod Kubernetes deployment, several pods can admit requests against the same remaining budget before any shared settlement occurs. That is acceptable only if the overshoot is explicitly bounded by reservations and any overdraft is policy-approved, alerted, and auditable. Redis remains optional; the launch requirement is the durable reservation/settlement contract and measured maximum overshoot.

**Severity:** Critical launch blocker for enterprise budgets.

**Confidence:** High.

**Next-day action:** Define Aurora tables for `budget_reservations`, `budget_ledger`, and `overdraft_grants`; specify admission, settlement, crash recovery, retry/fallback billing, alert thresholds, and maximum possible overshoot.

### L5-F03 - Control-plane convergence should publish one immutable snapshot

**Classification:** Launch.

**Evidence:**

- `core/bifrost.go:73-76` keeps providers/plugins behind atomic pointers and queues behind `sync.Map`.
- `core/bifrost.go:99-132` documents the low-overhead `ProviderQueue` lifecycle and why it avoids sender-side overhead.
- `plugins/governance/store.go:2474-2484` rebuilds governance state by replacing multiple `sync.Map` fields one by one.
- `framework/configstore/rdb.go:5588-5590` exposes transactional execution.
- `framework/configstore/rdb.go:5675-5697` exposes distributed lock acquisition.
- `docs/roadmap/extreme-reliability-and-day2-operations.md:51-52` requires Aurora mutations to commit with a transactional outbox row and treats `LISTEN/NOTIFY` as acceleration, not authority.

**Reasoning chain:** The existing code has the raw pieces for local hot reads and database transactions, but the launch contract requires every pod to observe a complete, monotonic governance view. Rebuilding independent maps is not the same as publishing one validated snapshot with a revision, checksum, schema version, and high-water mark. Use the proven data-plane pattern: build a complete object off-path, validate it, then atomically swap one pointer. Polling is the correctness mechanism; notification is only a wakeup.

**Severity:** High. Stale or partial policy state is a direct revocation and budget risk.

**Confidence:** High on the required shape; medium on current runtime exposure because call-site locking was not exhaustively audited in this read-only pass.

**Next-day action:** Specify `GovernanceSnapshot` as an immutable aggregate behind `atomic.Pointer`, with revision monotonicity, checksum, stale lease behavior, and old-snapshot retention on invalid updates.

### L5-F04 - Current health probing can turn optional store failures into pod churn

**Classification:** Launch.

**Evidence:**

- `transports/bifrost-http/handlers/health.go:26-29` registers only `/health`.
- `transports/bifrost-http/handlers/health.go:31-90` pings config, log, and vector stores under one health response and returns 503 on any failure unless DB pings are disabled.
- `terraform/modules/bifrost/kubernetes/main.tf:158-177` points both liveness and readiness probes at the same `var.health_check_path`.
- `terraform/modules/bifrost/aws/services/eks/main.tf:388-410` does the same for EKS.
- `docs/roadmap/extreme-reliability-and-day2-operations.md:87-89` requires startup, readiness, and liveness to mean different things; liveness must not depend on Aurora or provider reachability.

**Reasoning chain:** Launch availability depends on healthy pods continuing to serve from their last valid snapshot during control-plane or optional-store incidents. A single probe that pings log/vector/config stores and is reused as liveness can synchronize restarts across otherwise capable pods. This is a day-two operations hazard, not a feature gap.

**Severity:** High. It can amplify an Aurora/log/vector incident into gateway unavailability.

**Confidence:** High.

**Next-day action:** Define `/livez` as process-only, `/readyz` as serving readiness plus initialized providers and valid snapshot, and `/startupz` as boot/migration/snapshot acquisition. Update Terraform acceptance criteria before launch work proceeds.

### L5-F05 - Routing launch should be deterministic with explicit failure disposition

**Classification:** Launch, bounded.

**Evidence:**

- `framework/configstore/tables/virtualkey.go:25-40` models provider configs with `Weight`, allow/deny lists, keys, budgets, and rate limit, but no deterministic cohort seed or hard failure disposition.
- `plugins/governance/main.go:557-561` leaves no eligible provider configs as a TODO and continues without modification.
- `plugins/governance/main.go:580-599` selects weighted providers with `rand.Float64`.
- `plugins/governance/main.go:743-749` logs routing-rule evaluation errors and returns no decision.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:126-140` recommends deterministic ordered policy for launch and omits online semantic/bandit routing.

**Reasoning chain:** Weighted random routing is useful for canaries, but launch routing for internal enterprise traffic must be explainable, replayable, and auditable. If all eligible providers are filtered out by model, budget, rate, entitlement, or policy, the result must be an explicit fail-closed error or a documented fallback class. Routing-rule evaluator failures should not silently devolve into default provider behavior for restricted traffic.

**Severity:** High. Nondeterministic or silent routing fallback makes budget, compliance, and incident reconstruction weak.

**Confidence:** High.

**Next-day action:** Write deterministic route-policy semantics: ordered match inputs, stable cohort hash for canaries, hard-deny classes with `AllowFallbacks=false`, soft-provider-failure fallbacks, and golden replay vectors.

### L5-F06 - MCP has useful filtering, but policy still needs to precede credentials/connections

**Classification:** Launch for allow-list/firewall; optional for stateful owner service.

**Evidence:**

- `core/mcp/exec.go:85-91` states the upstream client is resolved and its connection acquired before the plugin gate runs; acquisition failure means the plugin gate is never invoked.
- `core/mcp/exec.go:161-184` repeats client and tool filters during direct execution, which is a good base to preserve.
- `core/mcp/exec.go:185-189` acquires the client connection after those filters and before the plugin pipeline.
- `plugins/governance/main.go:1403-1411` skips governance for non-execute and codemode tools.
- `plugins/governance/main.go:1429-1483` enforces VK and direct tool allow-list checks in `PreMCPHook`.

**Reasoning chain:** The current execution-side filters are valuable, and direct invocation cannot simply bypass discovery filters. The remaining launch risk is ordering and authority: mandatory policy should evaluate an immutable tool/client manifest before acquiring credentials or a transport connection, especially for consequential tools and per-user OAuth. Codemode skip may be valid for local sandbox execution, but it must be an explicit launch decision, not an accidental exemption.

**Severity:** High, potentially critical for privileged MCP tools.

**Confidence:** High, and Beads already tracks this as a P0 known risk.

**Next-day action:** Split MCP execution into manifest resolution, policy/firewall decision, attenuated credential issuance, connection acquisition, call, result tainting, and audit. Make codemode policy explicit.

### L5-F07 - Privacy-safe traces/evals must stay async and metadata-first at launch

**Classification:** Launch for privacy receipts and minimal audit; optional for eval/replay services.

**Evidence:**

- `plugins/logging/writer.go:281-301` drops log entries when the async queue is full to avoid Postgres slowness cascading into request handling.
- `plugins/logging/writer.go:310-327` applies the same queue-full drop behavior to MCP tool logs.
- `plugins/logging/operations.go:432-475` writes streaming content and raw request/response only when content logging and raw storage are enabled.
- `plugins/logging/operations.go:557-623` applies the same gating for non-streaming outputs and passthrough bodies.
- `core/schemas/redaction.go:19-23` defines request-scoped redaction data.
- `core/schemas/redaction.go:62-74` clones redaction maps for async log entries.
- `framework/streaming/accumulator.go:13-27` stores stream accumulation in a manager keyed by accumulator ID, not in `BifrostContext`.

**Reasoning chain:** The code already has the right availability instinct: logging is async and droppable under pressure, and stream-sized data lives outside context. Launch should keep that shape. Full-fidelity eval/replay/RAG/training capture can easily become a raw-content sink and an availability dependency. The launch line is metadata-first audit plus privacy receipt; approved-content replay and evaluator adapters are separate services fed by an explicit evidence envelope and durable outbox.

**Severity:** High for privacy and availability.

**Confidence:** High.

**Next-day action:** Define `EvidenceEnvelopeBuilder` with purpose, consent, redaction policy version, raw-content disposition, retention class, and sink allow-list. Default launch config should not store raw prompts, outputs, tool arguments, or passthrough bodies.

### L5-F08 - Existing skill APIs must not become launch promotion authority

**Classification:** Launch only as protected Git issue/draft-MR proposal; direct publication is omit.

**Evidence:**

- `transports/bifrost-http/handlers/skills.go:76-90` registers upload, version bump, CRUD, delete, and shift-version routes.
- `transports/bifrost-http/handlers/skills.go:122` says update can create a new version without switching serving, implying switching serving is normally supported.
- `transports/bifrost-http/handlers/skills.go:343-355` exposes `bumpAllSkillsVersion`.
- `transports/bifrost-http/handlers/skills.go:572-590` shifts a skill to a specified version.
- `transports/bifrost-http/handlers/skills.go:618-667` updates a skill and defaults `serve` to true.
- `framework/configstore/skills.go:775-873` creates a version and, when `serve` is true, atomically flips `LatestVersion` and bumps all-skills version.
- `framework/configstore/skills.go:1144-1194` shifts serving to a previous version and bumps all-skills version.
- `transports/bifrost-http/handlers/skills_serving.go:137-188` registers public unauthenticated marketplace/download/git serving routes.
- `transports/bifrost-http/handlers/skills_serving.go:200-263` builds marketplace JSON from stored skills and versions.

**Reasoning chain:** The codebase already contains a mutable skill repository and public serving surface. That may be useful for OSS or non-enterprise scenarios, but it conflicts with the stated enterprise launch rule if it is treated as the source of promotion authority. For launch, the gateway may create issues, patches, or draft MRs only. It cannot merge, publish, flip served skill versions, or hold protected-branch credentials. Existing serving endpoints should either be disabled in enterprise launch or read from immutable protected Git SHAs after human merge.

**Severity:** High, critical if exposed to production agents without a protected Git gate.

**Confidence:** High on code surface; medium on deployed auth exposure because middleware and deployment config were not exhaustively traced.

**Next-day action:** Add an enterprise launch decision record: skill mutation endpoints disabled or admin-only non-production; promotion authority is protected Git merge plus immutable revision import. The proposal worker gets no merge, publish, or production secret capability.

## Confirmed Known Risks

- Budget/rate multi-pod overspend and lost/double settlement are known launch risks, not new findings.
- Single `/health` reused for readiness/liveness is a known launch risk, not a new finding.
- Outbox, snapshot publication, `LISTEN/NOTIFY` loss, and polling convergence are known design risks, not discoveries.
- MCP policy-before-credential/connection is a known P0 risk.
- Skill autonomous promotion is intentionally post-launch; any direct publish path must be treated as a scope violation for this deployment.

## P0-P4 Recommendations

| Priority | Recommendation | Effort |
| --- | --- | --- |
| P0 | Freeze the launch boundary in an ADR and require every feature to be labeled launch, optional, or omit with a failure disposition. | Small |
| P0 | Specify the hard reference-monitor contract for virtual keys, Okta entitlements, budget denial, privacy denial, routing denial, and MCP denial. | Small |
| P0 | Design the Aurora reservation/settlement/overdraft ledger and its failure oracle before adding more budget UI or routing options. | Medium |
| P0 | Define immutable governance snapshot/outbox/polling semantics and a pod readiness contract. | Medium |
| P0 | Disable or scope direct skill mutation/publication for enterprise launch; proposal worker may create issues or draft MRs only. | Small to medium |
| P1 | Split `/livez`, `/readyz`, and `/startupz`; update Terraform/Kubernetes probes and failure drills. | Small |
| P1 | Replace launch routing semantics with deterministic ordered policy and explicit hard/soft failure classes. | Medium |
| P1 | Refactor MCP execution ordering so policy runs before credential and connection acquisition. | Medium |
| P2 | Build privacy-gated evidence envelopes and durable async outbox for audits/evals, with raw-content disabled by default. | Medium |
| P2 | Add multi-pod acceptance tests: create/use/revoke/rotate, delayed invalidation, DB failover, pod death with outstanding reservations, rolling upgrade, and direct MCP invocation. | Medium to large |
| P3 | Add Redis counter adapter only if measured lease overshoot is unacceptable and operations accepts Redis as a supported dependency. | Medium |
| P3 | Add deterministic canary/shadow and offline replay after baseline routing, budget, and privacy evidence pass. | Medium |
| P4 | Revisit autonomous promotion, semantic routing, training/distillation/RL, and richer flywheel automation only after launch SLOs and review trust are proven. | Large |

## Alternatives And New Ideas

- Emergency deny overlay: a signed local deny-list pushed through a narrow operator path for sub-second revocation during incident response, with Aurora reconciliation afterward.
- Signed offline snapshot bundle: allow new pods to become ready during Aurora outage only if the bundle is fresh, signed, and within the documented revocation exposure window.
- Route simulator: dry-run route decisions against snapshots and historical metadata without calling providers or exposing raw content.
- Skill provenance receipt: every draft MR includes source snapshot revision, evidence receipt IDs, redaction policy version, permission diff, and immutable base skill SHA.
- Budget "blast radius report": compute worst-case overshoot as outstanding leases plus in-flight retry/fallback attempts; make this an operator-facing launch gate.

## Assumptions

- Deployment is internal enterprise Kubernetes with Aurora PostgreSQL as launch authority.
- One to five second control-plane convergence is acceptable for normal revocation and entitlement changes.
- Redis is optional and should not be mandatory unless the budget overshoot oracle requires it.
- Okta is the source of group/user entitlement truth, reconciled into Aurora rather than queried per request.
- Internal skills are promoted only through protected Git merge requests with mandatory human approval.
- The gateway can create issues, patches, or draft MRs, but cannot merge, publish, or hold protected branch credentials.

## Questions

- What is the maximum acceptable dollar and time overdraft per tenant, team, user, and virtual key?
- What is the required exposure bound for Okta deactivation during Aurora or Okta interruption?
- Should enterprise launch disable public skill serving entirely, or serve only immutable protected-Git revisions after human merge?
- Which MCP tools are consequential enough to require human approval, per-call credentials, or result tainting at launch?
- Which traces are legally allowed to retain content, and for which purpose, retention period, and deletion workflow?

## Uncertainty

- This was read-only planning analysis. I did not run the gateway, multi-pod tests, or failure drills.
- I did not invent benchmark numbers; performance and convergence bounds need measurement.
- Some current risks are design-premortem risks because planned outbox/snapshot components are not implemented in the inspected Go code.
- Middleware deployment around skill APIs was not exhaustively traced, so the skill finding is about scope authority and code surface rather than a confirmed external exposure.

## Tensions

- Availability versus revocation: local snapshots keep inference available, but require explicit stale-lease and emergency-deny semantics.
- Budget accuracy versus low overhead: strict per-request shared counters simplify accounting but put Aurora/Redis in the path; bounded reservations preserve availability but require overdraft math.
- Privacy versus learning: useful evals want rich data; launch safety wants metadata, receipts, and approved-content flows only.
- Determinism versus optimization: deterministic routes are auditable; semantic/bandit routes need evidence, exploration controls, and poisoning defenses.
- Human approval versus improvement speed: protected MRs slow the loop, but they are the correct launch authority boundary.

## Final Confidence

Overall confidence: high for the launch/optional/omit boundary and the eight scope findings; medium for implementation effort estimates until the reservation ledger, snapshot contract, and MCP refactor are prototyped against real multi-pod failure tests.
