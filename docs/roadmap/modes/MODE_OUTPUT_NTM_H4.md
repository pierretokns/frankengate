# H4 Mechanism Design: Enterprise Gateway Launch

Date: 2026-07-15

Mode: Mechanism Design. Scope: authority, incentives, and review boundaries for overdrafts, budget ownership, route policy, MCP governance, privacy-safe evidence, skill proposal review, and incident response.

## Thesis

The launch system should treat spending, routing, MCP invocation, trace capture, skill promotion, and emergency denial as separate authorities with explicit receipts. The current Go gateway substrate can remain the low-overhead inference path if it consumes immutable local snapshots and small admission receipts. The missing launch mechanisms are not more optimizers or evaluators; they are durable authority records, separation of duty, and tests proving that optional learning services, proposal workers, and policy evaluators cannot spend money, widen access, acquire credentials, capture raw content, or publish skills without the named authority.

Existing roadmap warnings are accepted here as confirmed premises, not new findings. The confirmed premises include: generic plugin errors fail open for ordinary plugins, hard governance needs a non-optional pre-provider boundary, Aurora is the durable authority with local snapshots, budget overdraft must be controlled and auditable, raw traces are off by default, protected Git merge is the sole launch skill-promotion authority, and optional learning services must never enter the inference availability path.

## Confirmed Premises

- The launch profile is internal Kubernetes with Aurora authority, 1-5 second control-plane convergence, optional Redis, protected Git merge requests, and learning services outside the availability path (`docs/roadmap/MODES_ANALYSIS_PROGRESS.md:9`, `docs/roadmap/MODES_ANALYSIS_PROGRESS.md:10`, `docs/roadmap/MODES_ANALYSIS_PROGRESS.md:11`, `docs/roadmap/MODES_ANALYSIS_PROGRESS.md:13`).
- The recommended architecture deliberately keeps a small control plane around the existing Go data plane and excludes autonomous publishing, training, or evaluation from gateway launch scope (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:5`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:7`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:9`).
- Aurora outage should freeze admin writes, not inference from a bounded-age validated snapshot; initial snapshots are required before readiness; emergency local deny is a planned mitigation, not a second durable authority (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:52`).
- Ordinary plugin errors are warnings and continue, so authentication, entitlement, hard quota, privacy eligibility, and invocation authorization cannot inherit generic plugin failure semantics (`docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:41`, `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:43`, `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:45`).
- Controlled overdraft is explicitly required as amount, duration, alert recipients, preapproval state, and audited authority-row mutation (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:111`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:113`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:124`).
- Skill publication at launch is protected Git merge by an authorized human; the gateway may create issues, patches, or draft MRs, but has no merge, branch-protection-bypass, deploy, or publication authority (`docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:7`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:11`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:16`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:153`).
- Privacy-safe evidence defaults to metadata-only; raw content capture needs purpose, retention class, region, owner, and policy, and detector failure is metadata-only or fail-closed for capture, never silent raw capture (`docs/roadmap/privacy-redaction-and-learning-boundaries.md:5`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:8`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:29`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:31`).
- Read-only Beads context confirms these launch concerns are already tracked as known work, especially mandatory request guards (`bif-kyy.2.4`), fenced stream/agent reservations (`bif-kyy.4.9`), stale-policy kill behavior (`bif-kyy.6.7`), MCP stateful ownership (`bif-kyy.15.18`), bounded stream capture (`bif-cks.14`), routing oscillation (`bif-kyy.7.11`), Git/MR skill proposal authority (`bif-bpfk.7`), evidence privacy outbox (`bif-bpfk.18`), and MCP policy-before-credential (`bif-bpfk.19`).

## Findings

### H4-01: Controlled overdraft is not yet an admission-time authority receipt.

Severity: P0 launch blocker

Confidence: High

Evidence:

- The roadmap requires pod-local reservation with Aurora settlement and says overdraft is explicit policy: amount, duration, alert recipients, and preapproval state (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:111`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:124`).
- `TableBudget` stores max limit, reset duration, current usage, and one owning entity FK, but no grant, approver, overdraft window, alert audience, or terminal settlement state (`framework/configstore/tables/budget.go:10`, `framework/configstore/tables/budget.go:13`, `framework/configstore/tables/budget.go:16`, `framework/configstore/tables/budget.go:18`).
- `BeforeSave` validates only owner cardinality, reset duration, and non-negative max limit (`framework/configstore/tables/budget.go:49`, `framework/configstore/tables/budget.go:68`, `framework/configstore/tables/budget.go:72`, `framework/configstore/tables/budget.go:78`).
- `CheckBudget` compares in-memory `CurrentUsage` plus optional baselines against `MaxLimit`; nil baselines default to an empty map (`plugins/governance/store.go:1054`, `plugins/governance/store.go:1068`, `plugins/governance/store.go:1075`, `plugins/governance/store.go:1091`).
- Usage is settled after provider execution from `PostLLMHook` via a goroutine and `postHookWorker`, not as a synchronous pre-provider reservation (`plugins/governance/main.go:1373`, `plugins/governance/main.go:1384`, `plugins/governance/main.go:1639`, `plugins/governance/main.go:1725`).
- Accounting tests intentionally bill every token-consuming physical attempt, including failed retries, which means retries and streams can consume real spend after a prior admission check (`plugins/governance/accounting_test.go:142`, `plugins/governance/accounting_test.go:154`, `plugins/governance/accounting_test.go:159`, `plugins/governance/accounting_test.go:170`).

Reasoning chain:

1. Mechanism design needs three visibly different states: within budget, authorized overdraft, and unauthorized overspend.
2. Current admission can deny after a local limit comparison, but it cannot attach an overdraft grant ID or prove that spend beyond limit was approved before provider I/O.
3. Post-attempt accounting is appropriate for low overhead and provider billing reconciliation, but it is not a fleet-wide authority for "may spend now" when pods, retries, streams, and fallbacks can all create additional physical attempts.
4. The incentive failure is asymmetric: callers receive value immediately, while budget owners and responders discover the spend later unless a pre-provider receipt names the budget, reservation fence, overdraft grant, owner, and alert path.

Next-day action:

Define `BudgetReservation` and `OverdraftGrant` contracts before implementation fan-out. Minimum fields: budget ID, tenant/principal scope, amount or token cap, max duration, reservation fence, pod lease ID, policy revision, requester, owner, approver, approval quorum, alert recipients, terminal state, settlement deltas, and expiry. Require either a live reservation or a valid overdraft grant before provider I/O for governed requests, and write a failure test proving no upstream provider call happens when the receipt cannot be created or renewed.

### H4-02: Budget ownership is represented as parentage, not accountability.

Severity: P1 high

Confidence: High

Evidence:

- Budget owner fields are structural FKs to team, virtual key, provider config, model config, or customer, with no accountable person, group, backup, approver, or notification fields (`framework/configstore/tables/budget.go:18`, `framework/configstore/tables/budget.go:19`, `framework/configstore/tables/budget.go:23`).
- Create/update budget API shape accepts only `id`, `max_limit`, and `reset_duration` or updates to max/reset duration (`transports/bifrost-http/handlers/governance.go:255`, `transports/bifrost-http/handlers/governance.go:258`, `transports/bifrost-http/handlers/governance.go:262`, `transports/bifrost-http/handlers/governance.go:264`).
- Virtual key create/update embeds budgets but no budget owner, finance approver, alert recipients, or overdraft approver (`transports/bifrost-http/handlers/governance.go:167`, `transports/bifrost-http/handlers/governance.go:186`, `transports/bifrost-http/handlers/governance.go:193`, `transports/bifrost-http/handlers/governance.go:214`).
- `TableVirtualKey` has `CreatedByUserID`, but no approver, steward, or budget-owner separation (`framework/configstore/tables/virtualkey.go:217`, `framework/configstore/tables/virtualkey.go:228`, `framework/configstore/tables/virtualkey.go:248`).
- `TableTeam` and `TableCustomer` carry budgets and rate limits but no owner/approver fields (`framework/configstore/tables/team.go:11`, `framework/configstore/tables/team.go:21`, `framework/configstore/tables/customer.go:9`, `framework/configstore/tables/customer.go:19`).

Reasoning chain:

1. A budget's attached entity is not the same as an accountable budget owner. A team can consume a budget without the team object encoding who is allowed to raise limits, approve overdraft, receive alerts, or answer incident questions.
2. Okta group entitlement can determine who may call models, but that should not automatically determine who may approve cost overrun. Access owner, budget owner, and reviewer are separate roles.
3. Without first-class owner and approver records, limit increases become generic admin writes or self-service API mutations. The incentive is to raise the limit for the requesting group instead of proving business approval or accepting denial.
4. Responders cannot route alerts to a human decision maker if the only owner is a team/customer FK and a mutable current-usage number.

Next-day action:

Create a `BudgetAuthorityPolicy` design tied to local principal/group IDs reconciled from Okta. It should name primary owner, backup owner, finance/security approval groups where applicable, requester/approver separation rules, emergency approver roles, alert destinations, cost center, and escalation TTL. Make it mandatory for hard budgets and overdraft grants before launch.

### H4-03: Routing rules have production spend and key-pin authority without reviewer separation.

Severity: P1 high

Confidence: High

Evidence:

- Routing rule create/update requests include name, enabled flag, CEL expression, targets, fallbacks, scope, query, and priority, but no author, reviewer, approval state, rollout lease, rollback pointer, or blast-radius record (`transports/bifrost-http/handlers/governance.go:278`, `transports/bifrost-http/handlers/governance.go:284`, `transports/bifrost-http/handlers/governance.go:285`, `transports/bifrost-http/handlers/governance.go:293`).
- `TableRoutingRule` persists scope, expression, targets, fallbacks, chain behavior, priority, and timestamps, but no review or approval metadata (`framework/configstore/tables/routingrules.go:12`, `framework/configstore/tables/routingrules.go:19`, `framework/configstore/tables/routingrules.go:30`, `framework/configstore/tables/routingrules.go:37`).
- Routing targets can set provider, model, key ID, and weight, which is direct control over spend path and selected provider credential (`framework/configstore/tables/routingrules.go:97`, `framework/configstore/tables/routingrules.go:103`, `framework/configstore/tables/routingrules.go:105`, `framework/configstore/tables/routingrules.go:107`).
- `applyRoutingRules` mutates provider, model, fallbacks, and the routing-pinned API key (`plugins/governance/main.go:754`, `plugins/governance/main.go:756`, `plugins/governance/main.go:766`, `plugins/governance/main.go:786`).
- Core commits a routing key pin into the canonical selected API key ID after restricted writes are unblocked, and routing pin overrides a caller-supplied pin (`core/bifrost.go:7342`, `core/bifrost.go:7346`, `core/bifrost.go:7347`, `core/bifrost.go:7351`).
- Tests verify that routing pins are committed and override caller pins (`core/bifrost_test.go:2838`, `core/bifrost_test.go:2854`, `core/bifrost_test.go:2859`, `core/bifrost_test.go:2860`).

Reasoning chain:

1. A routing rule is not just configuration. It can redirect cost, latency, data residency, vendor exposure, key selection, and fallback behavior.
2. Deterministic priority and CEL evaluation make route execution testable, but they do not answer who is allowed to author a global/customer/team rule or pin a production key.
3. If route authors and approvers are the same actor, local incentives can dominate enterprise constraints: one team can optimize its own success/cost profile while shifting spend, risk, or outage exposure to shared budgets and responders.
4. Key pins make route policy especially sensitive: they can override caller intent and select a specific provider credential, so reviewer separation and rollback need to be explicit.

Next-day action:

Define a `RoutePolicyChange` approval mechanism before exposing enterprise routing broadly. Require author, independent reviewer, affected scope, target/fallback diff, key-pin diff, residency/provider class, expected budget authority, dry-run result, rollback rule ID/version, expiry for temporary rules, and emergency disable semantics. Enforce reviewer-not-author for global, customer, key-pin, fallback, and residency-changing rules.

### H4-04: Advanced routing must be constrained by an admitted candidate set, or optimizer incentives will erode entitlements and budget controls.

Severity: P1 high for online optimization; P2 for deterministic launch routing

Confidence: High

Evidence:

- Governance publishes a provider allowlist so later routing layers cannot select a provider the VK forbids; an empty allowlist means no provider is permitted (`plugins/governance/main.go:651`, `plugins/governance/main.go:655`, `plugins/governance/main.go:656`, `plugins/governance/main.go:674`).
- The model-catalog resolver intersects catalog candidates with the governance allowlist and logs excluded candidates (`plugins/modelcatalogresolver/main.go:135`, `plugins/modelcatalogresolver/main.go:166`, `plugins/modelcatalogresolver/main.go:172`, `plugins/modelcatalogresolver/main.go:204`).
- E2E cases prove VK allowlists block explicit disallowed providers and prune off-allowlist fallbacks (`tests/e2e/api/runners/build-routing-wiring.mjs:820`, `tests/e2e/api/runners/build-routing-wiring.mjs:828`, `tests/e2e/api/runners/build-routing-wiring.mjs:870`, `tests/e2e/api/runners/build-routing-wiring.mjs:877`).
- Launch routing guidance selects deterministic ordered policy and explicitly omits online semantic/bandit routing at launch (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:126`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:128`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:138`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:245`).
- Weighted load balancing already chooses among eligible VK provider configs and can auto-attach the remaining weighted providers as fallbacks (`plugins/governance/main.go:508`, `plugins/governance/main.go:535`, `plugins/governance/main.go:580`, `plugins/governance/main.go:619`).

Reasoning chain:

1. Deterministic launch routing already has the right monotonic shape: start from the VK/provider/model permissions and narrow, never widen.
2. A future semantic, bandit, shadow, or canary router will be rewarded for quality, cost, latency, or learning signal. Those rewards naturally create pressure to explore candidates that were not originally admitted or to duplicate traffic outside the primary budget path.
3. The mechanism that aligns incentives is an explicit `EligibleCandidateSet` generated after entitlement, budget reservation, privacy eligibility, and route-scope checks. Optimizers may rank or sample only within that set, and every decision should carry a `RoutingDecisionReceipt`.
4. Shadow and canary traffic need separate spend caps and privacy receipts; otherwise the optimizer can turn "evidence gathering" into unapproved cost and content duplication.

Next-day action:

Specify `EligibleCandidateSet` and `RoutingDecisionReceipt` schemas. Include allowed providers, models, key IDs, fallback list, budget reservation IDs, privacy disposition, policy revision, and route rule IDs. Add property tests that any downstream router, fallback expansion, canary, or shadow path produces a subset of the admitted candidates and cannot add a provider, model, key, or tool outside the set.

### H4-05: MCP execution has useful allow-lists, but policy-before-credential is not yet a universal invariant.

Severity: P0 for privileged MCP clients; P1 for narrow read-only MCP clients

Confidence: Medium-high

Evidence:

- `PreMCPHook` performs execution-time governance and short-circuits missing headers, invalid virtual keys, inactive/expired keys, and disallowed tools (`plugins/governance/main.go:1391`, `plugins/governance/main.go:1413`, `plugins/governance/main.go:1439`, `plugins/governance/main.go:1474`).
- VK-specific MCP configs take precedence over `AllowOnAllVirtualKeys`, and caller include-tools can only narrow the VK grant (`plugins/governance/main.go:799`, `plugins/governance/main.go:820`, `plugins/governance/main.go:854`, `plugins/governance/main.go:906`).
- Direct MCP execution repeats lifecycle, client include-list, client tool allow-list, and request tool narrowing before acquiring a client connection (`core/mcp/exec.go:161`, `core/mcp/exec.go:176`, `core/mcp/exec.go:179`, `core/mcp/exec.go:185`).
- `MCPCredentialStore.ConnectionHeaders` can return admin-level headers for shared connection auth types when called with a synthetic context with no identity (`core/schemas/mcp.go:126`, `core/schemas/mcp.go:129`, `core/schemas/mcp.go:132`, `core/schemas/mcp.go:143`).
- `createHTTPConnection` has a direct fallback path that composes static config headers with credential-store auth when no plugin-supplied overrides are present (`core/mcp/clientmanager.go:1660`, `core/mcp/clientmanager.go:1668`, `core/mcp/clientmanager.go:1669`, `core/mcp/clientmanager.go:1673`).
- `PreMCPConnectionHook` explicitly says connect is transport setup, not the gated operation; policy checks stay on `PreMCPHook` for the actual `CallTool` (`plugins/governance/main.go:1570`, `plugins/governance/main.go:1578`, `plugins/governance/main.go:1580`, `plugins/governance/main.go:1581`).
- Starlark code-mode nested MCP calls acquire a connection before delegating to the canonical plugin gate (`core/mcp/codemode/starlark/executecode.go:471`, `core/mcp/codemode/starlark/executecode.go:475`, `core/mcp/codemode/starlark/executecode.go:483`, `core/mcp/codemode/starlark/executecode.go:488`).

Reasoning chain:

1. The existing allow-list hierarchy is directionally correct: discovery and direct invocation are both narrowed.
2. Mechanism design for enterprise MCP must distinguish connection setup authority, credential resolution authority, and tool invocation authority. Shared admin-level connections may be acceptable for trusted clients, but that is a different authority model than per-user credentials.
3. The critical invariant is not merely "a denied tool call returns 403." It is: a denied call cannot acquire a per-user credential, cannot open a new privileged transport, cannot send `CallTool`, and produces a responder-readable receipt explaining whether completion is denied, failed before wire, sent with ambiguous outcome, or completed.
4. The Starlark nested path is the clearest pressure point because it obtains the connection before running the plugin gate. Even if the gate prevents the wire call, credential/connection acquisition has already happened.

Next-day action:

Write a policy-before-credential sequence spec and tests. For denied MCP calls, assert zero per-user credential lookup, zero new transport acquisition, and zero upstream `CallTool` packets. For shared admin connections, document the attenuated service credential boundary and prove every wire `CallTool` is gated. Move Starlark nested calls to run the policy gate before `AcquireClientConn`, or formally restrict that path to already-authorized, attenuated connections. Add `MCPInvocationReceipt` with principal, VK, client, tool digest, argument hash, policy revision, credential mode, connection mode, outcome, ambiguity flag, and responder owner.

### H4-06: The Git-human skill promotion boundary is correct, but proposal incentives still need reviewer and privacy controls.

Severity: P1 high

Confidence: High

Evidence:

- Launch skill changes go through existing Git MR workflow with mandatory human approval; the gateway may collect privacy-eligible evidence, create issues, prepare patches, or open draft MRs, but receives no merge or publication authority (`docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:5`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:7`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:11`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:16`).
- Auto-promotion is explicitly disallowed at launch, and governance/meta skills, evaluators, routers, policies, evidence rules, identity, authorization, credentials, privacy, and employee analytics never auto-promote (`docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:151`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:153`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:155`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:157`).
- The current skill table records `CreatedBy` on skills and versions but does not encode reviewer, approver, evaluator owner, permission approval, or rollout authority (`framework/configstore/tables/skills.go:82`, `framework/configstore/tables/skills.go:94`, `framework/configstore/tables/skills.go:117`, `framework/configstore/tables/skills.go:125`).
- The skill operational contract calls for approval points and separation-of-duty policy, and promotion receipts name approvals and rollback (`docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:75`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:87`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:113`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:115`).
- Core promotion invariants require candidate authors not to supply the decisive vote and high-risk organization promotion to separate proposer, evaluator owner, approver, and rollout authority (`docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:174`, `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:184`).

Reasoning chain:

1. Protected Git is the right launch authority. The Bifrost DB can cache skills and versions, but it should not become a second promotion state machine.
2. A proposal worker or skill author can still create harm before merge by attaching raw private traces, generating noisy patch volume, widening permissions, or exhausting reviewer attention.
3. If proposal metrics reward MR count or acceptance rate, authors and automation will optimize for plausibility and throughput rather than verified defect reduction, reviewer effort reduction, privacy compliance, and rollback safety.
4. Reviewers need a machine-generated but human-owned packet: provenance, privacy transform receipts, permission diff, dependency diff, validation output, rollback, and known non-goals.

Next-day action:

Define a `SkillChangeProposal` manifest that lives with the draft MR. Required fields: proposer, non-author reviewer requirement, evidence receipt IDs, privacy transform IDs, raw-content absence proof, permission/dependency diff, skill operational contract diff, deterministic validator output, sandbox credential profile, rollback SHA, and reviewer checklist. Track proposal quality by verified defect reduction, deterministic-test improvement, reviewer effort, rollback rate, and privacy violations, not proposal count.

### H4-07: Privacy-safe traces and evals need destination-specific capture authority, not inherited log settings.

Severity: P1 high

Confidence: High

Evidence:

- The privacy roadmap says raw production content must not enter logs, replay, evaluation, skill improvement, training, cross-team analytics, or external observability merely because it passed through the gateway (`docs/roadmap/privacy-redaction-and-learning-boundaries.md:5`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:6`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:7`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:8`).
- Every `PrivacyTransformReceipt` must record detector/rule/model versions, policy, purpose, transformations, destination eligibility, retention, and deletion time without raw entity values (`docs/roadmap/privacy-redaction-and-learning-boundaries.md:67`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:68`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:69`, `docs/roadmap/privacy-redaction-and-learning-boundaries.md:70`).
- The logging plugin derives whether raw storage is allowed from context/global flags and writes raw request/response on an error path when `shouldStoreRaw` and content logging are enabled (`plugins/logging/main.go:899`, `plugins/logging/main.go:900`, `plugins/logging/main.go:1075`, `plugins/logging/main.go:1084`).
- Traces stamp governance identifiers and names, including selected key, VK, team, customer, business unit, user ID, and user name (`core/bifrost.go:5978`, `core/bifrost.go:5983`, `core/bifrost.go:5991`, `core/bifrost.go:6039`).
- Observability plugins receive completed traces asynchronously after response write and must copy data before returning because the trace pointer is released to a pool (`core/schemas/plugin.go:405`, `core/schemas/plugin.go:408`, `core/schemas/plugin.go:419`, `core/schemas/plugin.go:422`).
- Architecture invariants already require any raw or derived content entering a new sink to have a privacy receipt and deletion lineage (`docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:90`, `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:92`, `docs/roadmap/flywheel-gauntlet-codebase-archaeology.md:98`).

Reasoning chain:

1. Logging, tracing, replay, evals, and skill improvement have different purposes and risk profiles. A flag that permits raw logging for incident response cannot imply permission to reuse the same content for evaluation or proposal generation.
2. Evaluators and skill authors have an incentive to ask for richer examples. Privacy owners and responders have the opposite incentive: minimize durable copies while preserving enough metadata to operate.
3. Existing trace/log code can carry useful governance metadata and optionally raw payloads, but a privacy-safe learning plane needs destination eligibility, transform receipt, retention, and deletion lineage at the point each sink is created.
4. Because observability injection is async and trace objects are pooled, learning/eval consumers must copy only approved, transformed data and must not retain gateway objects or streams.

Next-day action:

Define `EvidenceEnvelope` plus `PrivacyTransformReceipt` as the only path from gateway observations to replay, eval, or skill proposal. Gate each destination independently: logs, incident replay, offline eval, MR attachment, aggregate dashboard, and privacy adjudication. Default every content sink to metadata-only; allow raw or reversible encrypted content only with named purpose, owner, retention, deletion path, and access receipt. Add tests for no raw content in MR proposals and no employee-scoring aggregates.

### H4-08: Incident responders need bounded break-glass authority independent of budget owners, route authors, and Aurora writes.

Severity: P1 high

Confidence: Medium-high

Evidence:

- The roadmap permits an emergency local deny overlay for sub-second mitigation but keeps Aurora as durable authority (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:52`).
- Premortem gates require stale revocation, partial snapshot, Aurora outage, budget overshoot, plugin failure ambiguity, Okta deactivation, MCP bypass, skill proposal escape, and bad rollout drills (`docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:266`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:267`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:268`, `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:273`).
- Plugin error semantics are non-blocking unless a hook returns an explicit short-circuit; `PreRequestHook` cannot abort by returning an error (`core/schemas/plugin.go:192`, `core/schemas/plugin.go:197`, `core/schemas/plugin.go:290`, `core/schemas/plugin.go:292`).
- Core logs PreLLM and PreRequest hook errors as warnings and continues (`core/bifrost.go:7279`, `core/bifrost.go:7284`, `core/bifrost.go:7331`, `core/bifrost.go:7336`).

Reasoning chain:

1. During a key compromise, bad route rollout, MCP tool abuse, Okta deactivation lag, or Aurora write outage, responders need a way to deny a narrow target quickly without becoming budget owners or route reviewers.
2. If the only emergency path is an Aurora write, Aurora outage or stalled convergence blocks response. If the only emergency path is broad pod shutdown, availability is sacrificed to enforce policy.
3. A local deny overlay can solve this, but only if it has bounded TTL, target type, actor identity, reason, propagation proof, alerting, and after-action review. Otherwise it becomes a hidden second authority.
4. The mechanism should be deny-only. It must never grant access, raise budgets, widen routing, publish skills, or enable raw capture.

Next-day action:

Specify `EmergencyDenyOverlay`: target types for virtual key, user, team, customer, route rule, provider key, MCP client/tool, skill SHA, and content sink; signed actor; incident ID; TTL; reason; optional second reviewer after a short window; pod receipt; alert fanout; and audit export. Test that overlay denial has priority over stale snapshots and that expired overlays cannot silently persist as durable policy.

## Risks

- Self-approval risk: requesters, route authors, budget owners, and reviewers collapse into one admin role.
- Silent-spend risk: retries, streams, fallbacks, shadows, or MCP calls consume spend without a named reservation or overdraft grant.
- Hidden-optimizer risk: routing, canary, or future semantic/bandit layers widen provider/model/key eligibility while optimizing quality or latency metrics.
- Credential-confused-deputy risk: MCP connection setup or nested tool paths obtain credentials before exact tool policy has been proven.
- Reviewer-overload risk: skill proposal automation optimizes for volume, pushing humans into rubber-stamp behavior.
- Privacy-reuse risk: logs or traces become an implicit eval/training corpus without destination-specific receipts.
- Responder-overreach risk: emergency tools mutate durable policy, widen access, or persist beyond the incident.
- Availability-coupling risk: optional evidence, evaluation, or learning workers become dependencies of provider I/O.

## Recommendations

### P0 - Before any enterprise launch gate

Effort: M

Build the mandatory request-guard contract around the existing Go path. It must produce or verify small receipts before provider I/O: authentication/entitlement, virtual-key freshness, budget reservation or overdraft grant, MCP invocation policy, privacy capture disposition, and eligible routing candidate set. Generic plugin errors must not be the failure mode for these controls. Tests should inject panics/timeouts/stale snapshots and prove zero upstream effects for denied or indeterminate requests.

### P1 - Authority records and separation of duty

Effort: L

Design Aurora authority tables and API shapes for `BudgetAuthorityPolicy`, `BudgetReservation`, `OverdraftGrant`, `RoutePolicyChange`, `MCPInvocationReceipt`, `EmergencyDenyOverlay`, and `SkillChangeProposal`. Each should name actor, owner, reviewer/approver where applicable, policy revision, TTL/expiry, rollback or terminal state, alert recipients, and audit lineage. Require reviewer-not-author for overdrafts, global/key-pin route changes, privileged MCP grants, and organization-scoped skill proposals.

### P2 - Simulation, dry-run, and receipts

Effort: M

Add dry-run surfaces before broad rollout: budget overshoot simulator, route-policy diff and eligible-candidate proof, MCP denied-call zero-wire test, privacy sink eligibility checker, and skill proposal privacy/permission diff. These can be admin/testing tools, not hot-path services. They should output receipts suitable for MR review and incident response.

### P3 - Optional advanced routing and learning

Effort: M to L

Allow weighted canary, shadow, lexical tool search, and offline eval adapters only as consumers of admitted candidate sets, privacy-approved evidence, and independent spend caps. Keep them out of the provider availability path. Online semantic/bandit routing remains omitted until offline replay demonstrates a real operational gain and the optimizer is proven monotonic with respect to entitlement, budget, and privacy receipts.

### P4 - Explicit deferrals

Effort: defer

Defer autonomous skill promotion, gateway-held merge credentials, employee-surveillance analytics, raw-log-by-default storage, training/fine-tuning/RL workloads in gateway pods, and any second marketplace state machine. These are not launch requirements and would dilute the human-approval and low-overhead constraints.

## Alternatives and New Ideas

- Pre-funded reservation wallets per budget and pod: lower hot-path cost and clear overshoot bounds, but require lease renewal, crash settlement, and stale-lease expiry.
- Aurora atomic counter for selected hard-dollar budgets: precise but should be limited to low-volume budgets where database availability coupling is explicitly accepted.
- Redis counters: optional only if measured reservation overshoot violates a hard business rule and operations accepts Redis as a supported runtime dependency.
- Route policy futures: every route change compiles to a future policy version with dry-run receipts, affected-scope preview, and an automatic rollback pointer.
- Reviewer-load budget: proposal workers receive a quota based on prior accepted defect reduction and reviewer effort, not proposal volume.
- Deny-only break-glass overlay: responders can remove authority quickly, but cannot grant, spend, route wider, capture raw content, or publish.
- Privacy receipt as a data product contract: downstream eval/proposal systems must reject any observation without destination eligibility and deletion lineage.

## Assumptions

- Aurora PostgreSQL is the durable control-plane authority; Redis is not mandatory at launch.
- Okta is the source of users/groups/deactivation, reconciled into local authority tables rather than queried live per inference request.
- A 1-5 second convergence bound is acceptable for ordinary policy propagation, with emergency deny reserved for urgent exposure reduction.
- Provider queues, fallback machinery, streaming paths, and plugin compatibility are preserved.
- Protected Git merge with mandatory human approval is the only launch skill-publication authority.
- The gateway can create issues, patches, and draft MRs, but cannot merge, publish, push protected branches, or deploy.
- This pass did not run runtime tests or benchmarks and intentionally does not invent performance numbers.

## Questions

- Which Okta groups are allowed to own budgets, approve overdrafts, review route changes, and operate emergency deny?
- Are any budgets legally or contractually hard-no-overdraft, even for emergency business continuity?
- Which MCP clients use shared admin credentials, and which require per-user credential resolution?
- What is the minimum reviewer quorum for global route rules, provider key pins, and privileged MCP grants?
- What raw-content use cases, if any, are approved for incident replay or eval, and who owns deletion?
- Should budget alerts page finance owners, service owners, on-call responders, or all three?
- What is the maximum acceptable emergency deny TTL before durable Aurora policy or a second human review is required?
- Which skill classes are allowed to generate draft MRs on day one versus issue-only proposals?

## Uncertainty

- Exact multi-pod overshoot cannot be calibrated from code reading alone; it depends on the future reservation algorithm, traffic shape, and stream/agent duration.
- MCP sequencing varies by connection type and call path. The direct execution path checks filters before connection acquisition, while the Starlark nested path currently acquires a connection before the plugin gate. Privileged MCP launch should treat this as unresolved until tests prove the intended invariant.
- Organizational role mapping is not visible in the codebase. The proposed owner/reviewer split assumes the enterprise can supply stable Okta groups and on-call ownership.
- Privacy detector quality, latency, and false-positive rates are outside this analysis and should not be assumed.
- Existing roadmap documents and Beads are treated as authoritative planning inputs, but this pass did not mutate Beads or validate every dependency edge.

## Tensions

- Low overhead versus strict global spend serialization: reservations preserve the hot path but require explicit overshoot acceptance and reconciliation.
- Availability versus revocation freshness: bounded stale snapshots keep inference alive, while emergency deny and max snapshot age bound exposure.
- Human approval versus learning velocity: protected Git prevents unsafe self-promotion but shifts optimization toward reviewer quality and workload.
- Metadata-only telemetry versus diagnosability: responders need enough evidence to debug, but raw content cannot become a default data lake.
- Route optimization versus policy monotonicity: better latency/cost is useful only after entitlement, budget, residency, and privacy constraints are frozen.
- Responder speed versus durable authority: local deny must be fast and narrow without becoming a hidden control plane.

## Final Confidence

Overall confidence: High that the launch-critical mechanism gaps are budget/overdraft receipts, owner/reviewer separation, route-policy approval, MCP policy-before-credential proof, destination-specific privacy receipts, and bounded emergency denial. Confidence is medium-high on the MCP-specific sequencing risk because exact behavior depends on connection type and call path. Confidence is medium on organizational role design because Okta group ownership and approval policy are not present in the repository.
