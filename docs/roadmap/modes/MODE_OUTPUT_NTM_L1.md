# NTM L1 Meta Evaluation: Enterprise Gateway Launch

## Thesis

The launch plan is directionally right: keep the Go inference/provider substrate hot, use Aurora-backed snapshots for control-plane authority, and keep learning/skill promotion outside the availability path. The main remaining risk is not that the plan lacks controls. It has many controls. The risk is that several controls answer adjacent questions rather than the launch question: "Can this request, with this actor, snapshot revision, budget reservation, route, MCP tool, and privacy disposition, produce any upstream or durable side effect?"

For this deployment, the launch artifact should be a small number of executable oracles: admission, routing, budget reservation, MCP invocation, privacy evidence, and stale-policy behavior. Without those oracles, the roadmap can accumulate accurate warnings while still producing duplicated controls, analysis theater, and false precision.

Roadmap warnings are treated here as confirmed known risks, not discoveries. Beads were read-only; relevant open work already tracks mandatory guards, MCP ordering, evidence envelopes, stale-policy semantics, and quota reservations. `br dep cycles --json` reported no active dependency cycles.

## Findings

### NTM-L1-01 - The plan still asks "which plugin owns governance?" when the launch oracle is "which membrane is mandatory?"

Severity: P0 launch blocker for enterprise auth, budget, privacy eligibility, and invocation authorization.
Confidence: High.

Evidence:
- `core/schemas/plugin.go:192-198` documents that plugin errors are logged as warnings and not returned to callers; only an `LLMPluginShortCircuit` may skip the provider call.
- `core/schemas/plugin.go:200-204` makes `AllowFallbacks = nil` permissive by default for ordinary LLM errors.
- `core/schemas/plugin.go:283-294` documents that `PreRequestHook` can mutate routing fields but cannot abort; auth/content policy must use HTTP prehook or `PreLLMHook` short-circuit.
- `core/bifrost.go:7275-7297` logs `PreLLMHook` errors and continues unless a short-circuit is returned.
- `core/bifrost.go:7311-7336` logs `PreRequestHook` errors and continues.
- `plugins/governance/main.go:398-405` keeps `HTTPTransportPreHook` as a no-op and routes all routing through `PreRequestHook`.
- `plugins/governance/main.go:1271-1310` does block governance denials through `PreLLMHook` short-circuit, which is the right local mechanism but not yet a named enterprise reference-monitor membrane.
- Confirmed tracking: Bead `bif-kyy.2.4` is "Separate mandatory request guards from best-effort plugin hooks."

Reasoning chain:
1. The plugin contract is intentionally best-effort for extensibility and availability.
2. Enterprise launch controls are not best-effort; they are authorization boundaries.
3. Governance currently spans a no-op transport hook, a mutating non-blocking routing phase, and a short-circuit LLM phase.
4. That can work only if the architecture names and tests the short-circuit path as the mandatory membrane and proves no hard decision is represented as an ordinary plugin error.

Next-day action:
Write a one-page `AdmissionDecision` contract and a failing conformance test with a plugin panic, plugin error, corrupt governance snapshot, and denied virtual key. The assertion should be zero provider writes and a stable terminal denial; optional telemetry/eval failures must degrade with explicit dispositions.

### NTM-L1-02 - Routing mixes deterministic policy, weighted load balancing, fallbacks, and error skipping under one label.

Severity: P0 for deterministic launch routing; P1 for optional canary/shadow routing.
Confidence: High.

Evidence:
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:126-136` says launch routing is deterministic ordered policy, while weighted canary/shadow is optional and should use stable hashing.
- `plugins/governance/routing.go:79-87` implements scoped first-match precedence and chain-rule semantics.
- `plugins/governance/routing.go:202-218` skips routing rules on compile/evaluation errors and continues.
- `plugins/governance/routing.go:229-260` selects a target from matched rule targets.
- `plugins/governance/routing.go:301-348` implements weighted random selection with `rand.IntN` and `rand.Float64`.
- `plugins/governance/main.go:557-561` returns nil and continues without modification when no eligible provider config remains, with a TODO for proper errors.
- `plugins/governance/main.go:580-599` uses weighted random provider selection for virtual-key load balancing.
- `plugins/governance/main.go:619-645` builds fallback chains from weighted configs.
- `plugins/governance/routing_test.go:270-279` obtains deterministic behavior by using a 1.0 versus 0.0 weight fixture, not by a stable cohorting oracle.
- `core/bifrost_test.go:2838-2870` verifies routing key pins commit to the reserved key-selection context, which is useful but narrower than route determinism.

Reasoning chain:
1. Ordered policy, weighted LB, canary, and fallback are different mechanisms with different audit and replay properties.
2. Random selection is acceptable for "advanced routing" only when explicitly labeled as stochastic, capped, and reproducible enough for audit.
3. Skipping malformed rules is operationally friendly but is the wrong default for rules that encode mandatory tenant/provider restrictions.
4. A launch plan that says "deterministic routing" while sharing implementation paths with random weighted selection invites false precision in audit trails and failure drills.

Next-day action:
Define three route modes with separate invariants: `ordered_fail_closed`, `weighted_cohort_hash`, and `best_effort_fallback`. Launch only `ordered_fail_closed` for hard policy. For mandatory rules, compile/eval failure and zero eligible providers must produce typed denials, not "skip and continue."

### NTM-L1-03 - Budget overdraft needs a reservation oracle; current accounting is post-facto measurement.

Severity: P0 launch blocker for controlled overdraft across pods.
Confidence: High.

Evidence:
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:111-124` requires pod-local reservations with Aurora settlement, bounded overshoot, denied-by-default limits, and approved overdraft rules.
- `plugins/governance/main.go:1322-1388` collects governance IDs and starts a goroutine after `PostLLMHook` to process usage.
- `plugins/governance/main.go:1639-1728` calculates cost/tokens after result/error and calls `tracker.UpdateUsage`.
- `plugins/governance/tracker.go:91-114` queues usage accounting and dedupes terminal settlements by request/attempt.
- `plugins/governance/tracker.go:217-264` dumps/reset counters from a background worker every `workerInterval`, currently 10 seconds at `plugins/governance/tracker.go:65-70`.
- `plugins/governance/store.go:2104-2192` dumps rate limits to the DB; deadlocks return nil because a future cycle is expected.
- `plugins/governance/store.go:2194-2264` dumps budgets similarly and still references gossip in deadlock comments, while the launch plan omits gossip.
- `plugins/governance/tracker_test.go:203-284` verifies per-attempt idempotent billing, not pre-call reservations or cross-pod overshoot.
- Confirmed tracking: Bead `bif-kyy.4.9` calls for fenced renewable reservations for long streams and agent trajectories.

Reasoning chain:
1. Post-response accounting tells the business what was spent; it does not bound what can be spent before settlement.
2. Across pods, retries, streams, MCP tool turns, and fallbacks, controlled overdraft requires an admission-time reservation or lease.
3. Async dumps and deadlock retry behavior are compatible with reconciliation, but not sufficient as the authority that denies at limit.
4. The launch oracle is a formula and test: maximum overshoot equals outstanding leases plus in-flight attempts plus explicitly approved overdraft, under crash and settlement loss.

Next-day action:
Write the reservation algebra before coding: lease scope, renewal cadence for streams, attempt epoch, settlement CAS, abandoned lease sweeper, overdraft policy, and alert transition. Add a three-pod failure test design that crashes holders and proves the maximum overdraft bound.

### NTM-L1-04 - MCP governance proves filtering, but the missing oracle is "no credential or connection before mandatory policy."

Severity: P0 for privileged MCP tools and Okta-derived entitlements.
Confidence: High.

Evidence:
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:185-190` recommends identity-derived narrowing on existing MCP filters and no wildcard privileged tools.
- `core/mcp/exec.go:85-91` explicitly resolves the upstream client and acquires its connection before the execute-tool plugin gate.
- `core/mcp/exec.go:91-104` returns preparation errors before the plugin gate is invoked.
- `core/mcp/exec.go:133-189` enforces disabled/client/tool/request filters, then calls `AcquireClientConn`.
- `core/mcp/clientmanager.go:24-40` documents shared persistent connections and per-user ephemeral connections; per-user credentials are layered after the connect-plugin gate.
- `core/mcp/clientmanager.go:80-126` resolves auth headers, creates the streamable HTTP transport, and starts the temporary client.
- `plugins/governance/main.go:1400-1488` enforces MCP execution governance and direct tool allow-lists in `PreMCPHook`.
- `plugins/governance/main.go:1570-1586` says `PreMCPConnectionHook` only populates identity context; budget, rate limit, and tool allow-list checks stay on `PreMCPHook`.
- `core/bifrost.go:7456-7495` logs `PreMCPHook` plugin errors and continues unless a short-circuit is returned.
- Tests such as `core/internal/mcptests/agent_context_filtering_test.go:17-35`, `core/internal/mcptests/agent_context_filtering_test.go:87-128`, and `core/internal/mcptests/tool_filtering_test.go:77-117` verify narrowing and deny-all behavior, not zero credential/connection side effects.
- Confirmed tracking: Bead `bif-bpfk.19` is exactly this refactor and requires tests for zero credentials, zero connections, and zero upstream packets on denied calls.

Reasoning chain:
1. Discovery and execution filters are necessary and present.
2. For privileged tools, "tool was not executed" is not enough if credentials were minted, an ephemeral client was started, or an upstream service observed a connection for a denied call.
3. The current sequence wraps `CallTool`, not the whole invocation preparation.
4. The policy oracle must be earlier: normalize immutable target, evaluate mandatory policy, issue attenuated credential, acquire connection, call tool, finalize terminal receipt.

Next-day action:
Create a sequence-conformance test with a fake credential store, fake client manager, and fake upstream transport. Denied tool execution should increment none of them. Then move mandatory policy before `AcquireClientConn` behind a feature flag.

### NTM-L1-05 - Privacy-safe traces/evals need sink receipts, not more logger flags.

Severity: P0 for privacy boundary; P1 for eval usefulness.
Confidence: High.

Evidence:
- `docs/roadmap/privacy-redaction-and-learning-boundaries.md:16-31` requires classification before capture, deterministic recognizers before durable sinks, `PrivacyTransformReceipt`, and independent re-scan of tool results, model output, evaluator explanations, and skill patches.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:155-168` says telemetry is metadata-first and raw content is only for approved datasets.
- `framework/logstore/tables.go:165-205` contains structured input/output histories, params, tools, raw request/response, passthrough bodies, routing logs, and plugin logs.
- `framework/logstore/tables.go:211-213` contains redaction data/mapping fields.
- `plugins/logging/main.go:122-141` sanitizes raw request/response from error details when raw storage is disabled.
- `plugins/logging/main.go:144-157` makes content logging enabled by default unless disabled globally or by permitted per-request override.
- `plugins/logging/operations.go:432-475` persists streaming output content and raw bytes when content/raw gates allow it.
- `plugins/logging/operations.go:557-575` does the same for non-streaming response output.
- `framework/tracing/tracer.go:259-307` propagates input messages onto LLM/root spans.
- `framework/tracing/tracer.go:309-393` propagates output messages and routing/cost attributes.
- `framework/tracing/tracer.go:699-757` applies redaction replacements, snapshots the trace, and injects it into observability plugins asynchronously.
- `plugins/otel/main.go:86-104` distinguishes full content disablement from root-span-only content disablement; root-only disablement leaves child spans with content.
- Tests such as `framework/tracing/tracer_test.go:76-124`, `plugins/logging/sanitize_test.go:24-71`, and `plugins/logging/redaction_test.go:14-77` cover important local redaction paths, but not a single cross-sink receipt.
- Confirmed tracking: Bead `bif-bpfk.18` requires an `EvidenceEnvelopeBuilder`, `PrivacyTransformReceipt`, bounded outbox, and privacy-canary tests across headers, trace attributes, plugin logs, MCP data, errors, and nested encodings.

Reasoning chain:
1. The code has multiple sinks and each has separate gates.
2. "Disable content logging" does not imply no sensitive derived copy in spans, plugin logs, MCP logs, errors, proposals, or future eval records.
3. The roadmap already names the correct abstraction: a receipt attached to each sanitized copy.
4. Without sink-by-sink receipts, later eval/skill work can look compliant while consuming correlated or partially redacted evidence.

Next-day action:
Define a `PrivacyTransformReceipt` fixture and a sink registry. Run one canary secret through logstore, OTEL spans, plugin logs, MCP logs, errors, and proposal/evidence envelope paths; require either metadata-only, redacted placeholder, encrypted approved storage, or explicit drop.

### NTM-L1-06 - Git/MR approval reduces authority, but it does not make evidence independent.

Severity: P1 before draft MRs; P2 for issue-only suggestions.
Confidence: Medium-high.

Evidence:
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:5-18` makes protected Git and mandatory human approval the launch promotion authority.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:20-31` says no component may evaluate, promote, or rewrite itself; native feedback is observation only.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:34-56` treats raw histories as non-ground-truth and model-family evidence as correlated.
- `docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:95-115` requires frozen evaluation bundles, hard floors, holdouts, and signed promotion receipts.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:170-183` allows issues first and draft MRs only after privacy/utility gates, with no merge/deploy/gateway-admin credentials.
- `docs/roadmap/MODES_ANALYSIS_PROGRESS.md:9-13` records the same launch boundary and says learning/evaluation must not enter the inference availability path.
- Confirmed tracking: Bead `bif-bpfk.12` requires evidence trust, taint, terminal outcome, missingness, privacy receipt, and evidence-plane health.

Reasoning chain:
1. Human MR approval solves authority, not evidence quality.
2. If the issue/draft MR is generated from the same traces, model judgments, and evaluator rationales that suggested the change, the evidence can be correlated even when the workflow is human-approved.
3. Promotion should therefore require independent executable or human/domain oracles before a patch is treated as "useful", especially for high-risk internal skills.
4. Issue-only launch is safer because it makes suggestions cheap and reversible while preserving skepticism.

Next-day action:
For launch, default to issue suggestions. Require draft MR enablement to depend on an evidence envelope with `source_type`, `verification_state`, `terminal_disposition`, `missingness`, `privacy_receipt`, and an independent CI or reviewer outcome field.

### NTM-L1-07 - Control-plane convergence has a time target but not enough stale-use semantics.

Severity: P0 for revocation, tool kill switches, privacy policy changes; P1 for additive routing/pricing changes.
Confidence: Medium-high.

Evidence:
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:52-61` sets the 1-5 second revocation/convergence goal using Aurora notification hints plus polling.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:77-91` requires unknown/malformed/revoked/policy-stale credentials to fail closed and stale snapshots to continue only within a maximum age.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:144-153` says readiness requires initialized providers and a validated governance snapshot, while liveness must not depend on control-plane freshness.
- `docs/roadmap/modes/MODE_OUTPUT_B5_L5.md:264-275` lists premortem gates for stale revocation, partial snapshot, Aurora outage, budget overshoot, Okta deactivation, MCP bypass, and bad rollout.
- `plugins/governance/main.go:97-105` allows in-memory-only governance when `configStore` is nil.
- `plugins/governance/main.go:144-152` only logs warnings when config/model/MCP catalogs are missing.
- `plugins/governance/main.go:181-213` startup reset failures are warnings and initialization continues.
- Confirmed tracking: Bead `bif-kyy.6.7` calls for disconnected authorization semantics and stale-policy kill behavior.

Reasoning chain:
1. `p99 <= 5s` is necessary but not a complete oracle.
2. Staleness risk differs by mutation type: additive access, restrictive access, revocation, budget/pricing change, routing change, MCP tool kill switch, and privacy policy update.
3. Availability goals require continuing inference during Aurora outage; security goals require bounded stale authority and emergency kill overlays.
4. Without a per-mutation stale-use table, tests can pass convergence timing while still leaving unclear behavior for Okta deactivation or privacy-policy changes during partitions.

Next-day action:
Write a mutation-class table: source of authority, snapshot field, stale action, max stale age, emergency overlay behavior, readiness/liveness behavior, audit field, and chaos test. This should be an oracle before implementation fan-out.

## Risks

- Analysis theater: More roadmap pages or mode outputs can restate the same confirmed risks without creating executable tests.
- Duplicated controls: HTTP prehooks, `PreRequestHook`, `PreLLMHook`, MCP filters, routing rules, and fallbacks can each look like enforcement while only one path is mandatory.
- False precision: A convergence p99, a weighted route percentage, or a content-logging flag can imply stronger guarantees than the code currently proves.
- Correlated evidence: Skill proposals can be human-approved but still based on self-referential or weak observations.
- Availability inversion: If privacy/eval/learning exporters become synchronous, they can violate the core constraint that optional learning services never enter the inference availability path.
- Stale authority ambiguity: Aurora/Okta partitions require explicit fail-open/fail-closed semantics per mutation class, not one global policy.

## Recommendations

P0, 1-3 days each:
- Define the mandatory admission/reference-monitor membrane and typed dispositions: allow, deny, metadata-only, stale-allow, stale-deny, degraded-telemetry.
- Specify budget reservation/settlement algebra and maximum overdraft calculation before coding.
- Move mandatory MCP policy before credential/connection acquisition or feature-flag a new path with zero-side-effect tests.
- Define `PrivacyTransformReceipt` and a sink registry; add canary tests across logstore, OTEL, plugin logs, MCP logs, errors, and evidence envelopes.
- Write stale-policy semantics by mutation class.

P1, 3-7 days each:
- Split routing into deterministic hard policy, stable-hash canary, and fallback modes with separate conformance tests.
- Build a three-pod local/integration harness for snapshot convergence, partial snapshot rejection, Aurora outage, revocation, and rolling update behavior.
- Make governance/routing failures observable as stable reason codes and alert dimensions, not only logs.

P2, 1-2 weeks:
- Build the bounded evidence/outbox path as an asynchronous consumer with idempotency, DLQ, shutdown drain, and drop/metadata-only backpressure.
- Add proposal evidence envelopes and issue-only workflow before draft MR creation.
- Add operator views only for workflows that close a measured operational gap.

P3, post-launch:
- Add stable-hash weighted canary and async shadow only after budget, privacy, and audit receipts are proven.
- Consider Redis counters only if measured lease overshoot violates a hard requirement and Aurora serialization is too slow.
- Consider a separate stateful MCP owner only if reconnect/ambiguous completion cannot meet tool governance requirements.

P4, omit from launch:
- Online semantic/bandit routing, inline evaluators, training/RL, autonomous skill merge/publication, mandatory Redis, gossip replication, DB lookup per inference request, and a Rust rewrite.

## Alternatives And New Ideas

- Compile a per-request `AdmissionPlan` from the immutable snapshot: actor, entitlement revision, route, budget lease, MCP manifest digest, privacy disposition, stale status, and allowed side effects. Providers and tools receive only the plan, not raw control-plane state.
- Add negative capability tests: fake provider, fake credential store, fake MCP transport, and fake log sink counters must remain zero on hard denials.
- Emit a `StaleUseReceipt` on every request during control-plane degradation: snapshot version, age, mutation class, stale decision, emergency overlay version, and remaining exposure window.
- Treat weighted canary as a policy output with a stable cohort hash and declared spend cap, never as process-local random selection.
- Generate a privacy sink matrix from a registry so adding a new exporter/log field requires declaring content class, transform, receipt, retention, and deletion behavior.

## Assumptions

- Aurora PostgreSQL is the durable control-plane authority; the hot inference path should not do a DB lookup per request.
- Redis is optional and should not become mandatory without measured overshoot evidence.
- The Go provider/queue/plugin substrate remains the inference data plane.
- Internal skill promotion uses protected Git merge requests with mandatory human approval; the gateway may create issues, patches, or draft MRs but cannot merge or publish.
- Existing roadmap warnings and relevant Beads are confirmed known risks, not new discoveries.

## Questions

- What is the acceptable maximum unauthorized-use window for Okta deactivation, virtual-key revocation, MCP tool kill switch, and privacy-policy tightening?
- What dollar/token/request overdraft is acceptable per tenant and globally during pod crash, settlement outage, and fallback storms?
- Which MCP tools are privileged enough to forbid shared persistent connections or require per-call attenuation?
- Is metadata-only telemetry sufficient for launch incident response, or are there named approved raw-content datasets with retention/access/deletion controls?
- Who owns the control-plane convergence SLO, stale-use alerts, and emergency deny overlay during off-hours?

## Uncertainty

- I did not run benchmarks or full test suites; this is read-only planning analysis.
- I did not inspect every provider or every HTTP handler. Findings focus on roadmap-critical governance, routing, budget, MCP, tracing/logging, and nearby tests.
- Exact implementation effort depends on existing enterprise-wrapper code not visible in this pass.
- Severity assumes internal enterprise Kubernetes, Aurora authority, Okta entitlements, and privileged MCP tools as stated in the prompt.

## Tensions

- Availability versus revocation freshness: stale snapshots keep inference alive but widen exposure windows.
- Privacy versus evaluation utility: metadata-only protects users but limits improvement evidence.
- Plugin extensibility versus mandatory enforcement: the same hook surface cannot be both best-effort and authoritative without typed membranes.
- Determinism versus optimization: explainable launch routing conflicts with process-local weighted randomness and online learning.
- MCP connection reuse versus least privilege: persistent connections are efficient but weaken per-call authorization proof.

## Final Confidence

Overall confidence: 0.78.

High confidence on the shape of the blockers: mandatory membrane, reservation oracle, MCP sequencing, and privacy receipts. Medium confidence on implementation effort and exact stale-use policy because those require operator/business thresholds not present in the repository.
