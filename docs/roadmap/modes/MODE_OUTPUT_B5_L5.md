# B5 Option Generation + L5 Scope Control: Enterprise Gateway Launch

## Decision

Launch as a deliberately small enterprise control plane around the existing Go data plane. Keep Bifrost's provider queues, fallback machinery, streaming paths, and atomic runtime replacement intact. Use Aurora PostgreSQL as the durable authority, process-local immutable snapshots for hot reads, PostgreSQL notification as an invalidation hint, and bounded polling as the correctness backstop. Use protected Git merge requests as the **only** skill publication mechanism.

Do not make the gateway an evaluation platform, training platform, autonomous skill publisher, distributed workflow engine, or employee-monitoring product at launch. Those can consume its privacy-filtered telemetry later.

This is the smallest architecture that satisfies the stated constraints without putting Aurora, Git, Okta, Redis, or an experimental flywheel on the inference critical path.

## Scope rule

Classification means:

- **Launch**: required for a trustworthy internal gateway and must have an explicit failure disposition.
- **Optional**: a compatible seam or thin first version is useful, but absence cannot block launch.
- **Omit**: deliberately exclude from the launch product and data-plane binary.

The decision oracle for promoting optional work is evidence: a measured SLO miss, an operator workload threshold, a security requirement, or repeated user demand. Architectural ambition alone is not an oracle.

## Repo facts that constrain the design

1. The fast substrate already isolates providers with process-local queues and keeps providers/plugins behind atomic pointers (`core/bifrost.go:73-76`, `core/bifrost.go:99-132`). Provider replacement builds a fresh slice, compare-and-swaps it, publishes a fresh queue, and starts new workers before retiring old workers (`core/bifrost.go:3676-3719`). Enterprise control-plane state should follow the same build-then-swap shape, not mutate shared maps piecemeal.
2. Existing plugin errors are warnings and execution continues (`core/bifrost.go:7275-7297`). The once-per-request routing hook is also explicitly non-blocking (`core/bifrost.go:7300-7338`). Authentication, revocation, and hard budget denial therefore cannot rely on an ordinary plugin error; they require an explicit short-circuit or a non-optional reference-monitor boundary.
3. Fallback is already implemented and honors an explicit `AllowFallbacks=false` disposition (`core/bifrost.go:4787-4816`). Launch routing should compose this mechanism before inventing a second retry engine.
4. Governance already separates store, resolver, tracker, and routing engine (`plugins/governance/main.go:63-79`), exposes in-memory CRUD for keys/teams/users/rules (`plugins/governance/store.go:159-207`), and persists reset changes transactionally without overwriting concurrent configuration (`plugins/governance/store.go:2034-2059`). Extend those seams rather than create a parallel enterprise service graph.
5. Virtual-key hot state is already process-local and updated lock-free (`plugins/governance/store.go:3012-3047`), while the config-store interface already owns governance CRUD and transactions (`framework/configstore/store.go:288-312`, `framework/configstore/store.go:375-436`). Multi-pod coherence is therefore an invalidation/snapshot problem, not a reason to place a database lookup on every request.
6. MCP discovery and execution both enforce narrowing filters; request context cannot expand the configured allow-list (`core/mcp/utils.go:110-124`), and direct execution repeats the same checks (`core/mcp/exec.go:161-184`). Launch governance should attach identity-derived restrictions to this existing hierarchy.
7. Kubernetes deployment, readiness/liveness probes, and HPA already exist (`terraform/modules/bifrost/kubernetes/main.tf:66-80`, `terraform/modules/bifrost/kubernetes/main.tf:158-169`, `terraform/modules/bifrost/kubernetes/main.tf:239-275`). Launch work should harden and test these assets, not introduce a new scheduler.

## Recommended launch architecture

```text
Okta -> group reconciler -> Aurora authority tables -> transactional outbox/version
                                      |                         |
                                      | commit                  | NOTIFY hint
                                      v                         v
Admin API ----------------------> audit/event rows       pod reconcilers
                                                               |
                                                     fetch versioned snapshot
                                                               |
                                                     validate + atomic swap
                                                               |
request -> hard auth/VK gate -> immutable governance snapshot -> routing -> existing provider queue
                                                               |
                                                      async redacted evidence
                                                               v
                                                     issue or draft Git MR
                                                     (human approval only)
```

Aurora unavailability freezes administrative changes but does not stop inference with the last validated snapshot. A pod that cannot prove it has loaded an initial snapshot stays unready. Revocation convergence target is 1-5 seconds; an emergency local deny overlay can provide sub-second mitigation without becoming a second durable authority.

## Subsystem option matrix

### 1. Multi-pod control-plane propagation — **Launch**

**Option A — Aurora `LISTEN/NOTIFY` plus versioned outbox and 2-second polling (recommended).** A transaction updates authority rows and appends a monotonically versioned event. After commit, emit only `{tenant, kind, version}`. Pods treat notification as a hint, read committed state/outbox, build a complete snapshot, validate it, then atomically swap. Poll `max(version)` every two seconds and on reconnect.

- Tradeoff: one long-lived listener per pod and a small poll, but no mandatory Redis and no correctness dependence on lossy notifications.
- Decision oracle: choose this while measured p99 convergence is at most five seconds and Aurora connection budget remains healthy.

**Option B — Aurora polling only.** Poll a generation table every one second with jitter; fetch only when the generation changes.

- Tradeoff: simplest failure model and no listener reconnect logic, at the cost of predictable Aurora queries proportional to pod count.
- Decision oracle: prefer this for the first implementation if expected launch scale is below roughly 100 pods or notification lifecycle testing would delay launch.

**Option C — gossip/gRPC replication.** Pods exchange deltas and repair state peer-to-peer.

- Tradeoff: removes routine database polling but adds membership, split-brain, tombstone, version-vector, bootstrap, and network-policy complexity.
- Decision oracle: do not build unless load tests prove Aurora propagation is the bottleneck and the team is willing to own a distributed protocol. **Omit at launch.**

FSx/config-file mounting is not an option for revocable authority: atomic file replacement, watcher loss, stale mounts, secrets exposure, and lack of transactional audit make it inferior to the database already required.

### 2. Virtual keys and authorization — **Launch**

**Option A — opaque random VK, keyed hash lookup, snapshot policy (recommended).** Store only a keyed digest plus short display suffix; compare digests; attach user/team/model/tool entitlements in the immutable snapshot. Rotation creates a new key, permits an explicit overlap interval, then revokes the old key. Never log plaintext keys.

- Tradeoff: lookup is extremely cheap and revocation is snapshot-driven; key recovery is impossible by design.
- Decision oracle: default unless an external KMS-backed signing requirement emerges.

**Option B — signed self-contained token plus revocation generation.** Encode claims in a signed token but still consult a local revocation/entitlement snapshot.

- Tradeoff: adds signing-key rotation and claim-staleness complexity without eliminating the local lookup, so it has little launch value.
- Decision oracle: use only when offline verification by systems other than the gateway is a real requirement.

**Option C — database lookup per request.** Strong immediate authority but makes Aurora latency/failure part of every inference.

- Decision oracle: reject; it violates availability and latency goals.

Mandatory behavior: unknown, malformed, revoked, or policy-stale credentials fail closed. A stale-but-previously-valid snapshot may continue during Aurora failure only within a configured maximum snapshot age; revocation alerting must explicitly report the remaining exposure window.

### 3. Okta users/groups/model access — **Launch, narrow**

**Option A — SCIM or Okta API reconciler into local identity tables (recommended).** Reconcile users, groups, memberships, and deactivation; translate group IDs through declarative policy rows to models, providers, MCP clients, and tools. Inference uses only the local snapshot.

- Tradeoff: eventual consistency, but Okta outages do not take inference down.
- Decision oracle: choose SCIM if corporate Okta can push it; otherwise poll incrementally with cursor plus periodic full reconciliation.

**Option B — authenticate OIDC at request time, resolve groups from cached token claims.** Simpler provisioning when claims are complete.

- Tradeoff: group claim size/staleness and deprovisioning latency; still needs a local policy mapping.
- Decision oracle: use as authentication input, not as the sole lifecycle source, unless Okta guarantees required groups and short token TTLs.

**Option C — live Okta group lookup per request.** **Omit.** It couples inference availability to Okta and risks throttling.

Launch supports group-to-policy mapping and exceptional per-user overrides with expiry. Complex nested-group algebra, delegated marketplace administration, and attribute-based policy beyond a small fixed vocabulary are optional.

### 4. Budgets, limits, overdraft — **Launch**

**Option A — pod-local reservation with Aurora settlement (recommended for launch).** Each pod receives a bounded lease/reservation for a budget or rate window, charges locally, and asynchronously settles. Controlled overdraft is an explicit policy: amount/duration, alert recipients, and whether pre-approval exists.

- Tradeoff: bounded overshoot equals outstanding leases plus in-flight requests; avoids a database round trip and mandatory Redis.
- Decision oracle: use if the business accepts the calculated maximum overshoot and reconciliation passes failure tests.

**Option B — Aurora atomic counter per request.** Accurate but slower and database-dependent.

- Decision oracle: reserve for low-volume, hard-dollar limits where strict serialization is worth the availability cost; do not use globally.

**Option C — Redis atomic counters.** Fast shared enforcement but creates a mandatory runtime dependency.

- Decision oracle: optional only if measured overshoot from leases is unacceptable and operations approves Redis as a supported dependency.

At limit: deny by default. Permit overdraft only through a preconfigured rule or approved time-bounded grant; emit alerts at thresholds and on first overdraft. “Increase limit” is an audited authority-row update, not an in-memory mutation.

### 5. Routing and cross-region provider failover — **Launch, bounded**

**Option A — deterministic ordered policy over existing fallbacks (recommended).** Match tenant/group, model alias, request type, provider health, cost ceiling, and Bedrock inference profile; produce primary plus existing `Fallback` list. Use `AllowFallbacks=false` for governance/security denials (`core/bifrost.go:4801-4816`).

- Tradeoff: explainable and testable; does not continuously optimize.
- Decision oracle: launch until offline replay demonstrates a material quality/cost win from more complex routing.

**Option B — weighted canary/shadow.** Deterministically hash a stable request/tenant ID into a canary cohort. Shadow only when privacy policy permits; never delay the primary response; enforce a separate spend cap.

- Tradeoff: supports side-by-side evidence but doubles selected traffic cost and creates sensitive duplicate traces.
- Decision oracle: optional after baseline routing SLOs, accounting, and redaction are proven.

**Option C — online semantic/bandit router.** **Omit at launch.** It introduces model inference, exploration loss, causal evaluation, and feedback poisoning into the request decision.

For Bedrock, launch with configured U.S. cross-region inference profiles and ordered regional/provider fallbacks. Do not build an independent “Mantle” failover fabric until exact provider behavior and terminology are verified and a failure drill shows the configured profile is insufficient.

### 6. Kubernetes availability and day-two operations — **Launch**

**Option A — stateless Deployment, min three replicas, HPA, PDB, topology spread (recommended).** Readiness requires initialized providers and a validated governance snapshot; liveness tests process health only. Use rolling updates with `maxUnavailable=0`, graceful termination, queue drain, and provider-level circuit metrics.

- Tradeoff: conventional and already aligned with the repository Terraform/HPA seams.
- Decision oracle: default; tune HPA from queue saturation/in-flight work in addition to CPU after custom metrics are available.

**Option B — StatefulSet or sticky ownership.** Needed only for durable local state or MCP connection affinity.

- Decision oracle: omit for inference. Introduce a separate connection-owner component only if stateful MCP sessions prove they cannot tolerate reconnect/ambiguous completion.

Do not make control-plane freshness part of liveness. A temporary Aurora outage should freeze writes and alert; killing all healthy inference pods would amplify it.

### 7. Telemetry, privacy, and replay — **Launch core; optional depth**

**Option A — minimal structured envelope plus asynchronous sink (recommended).** Record logical request ID, attempt ID, actor/tenant IDs, policy/routing revision, provider/model, latency, token/cost, outcome, fallback index, and privacy disposition. Default to metadata only; redact before durable storage. Sampling and sink failure never block inference.

- Tradeoff: enough for operations, accounting, and later evaluation without creating a raw prompt warehouse.
- Decision oracle: raw content is collected only for explicitly approved datasets with retention, access, deletion, and purpose controls.

**Option B — OpenTelemetry spans plus encrypted replay objects.** Optional after schemas and privacy gates stabilize.

- Decision oracle: add when incident response or an approved offline evaluation cannot be answered from metadata.

**Option C — synchronous full-fidelity capture or inline PII model.** **Omit.** Presidio or a tiny classifier may run in an asynchronous ingestion service; deterministic secret/identifier filters can run at the boundary. No privacy model is allowed to delay or fail ordinary inference at launch.

Exact deterministic request replay, logprob-heavy comparison, perceived-friction inference, RAG evaluation, distillation corpora, and RL-environment export are optional downstream consumers—not gateway launch responsibilities.

### 8. Internal skills marketplace flywheel — **Launch only as Git proposal integration**

**Option A — evidence-backed issue or draft MR (recommended).** A separate worker reads privacy-approved evidence and a pinned skill revision, then emits a patch/issue. It has no protected-branch push, merge, production deploy, or gateway-admin credential. CI runs schema, lint, deterministic fixtures, permission diff, and sandbox tests; CODEOWNERS/human approval remains authoritative.

- Tradeoff: slower learning loop, dramatically smaller authority and rollback problem.
- Decision oracle: launch with issues first; enable draft MR creation only after ten consecutive proposals contain no secret/privacy-policy violation and reviewers find the patches useful.

**Option B — managed CASS-style per-user recall.** Optional as a separate service with opt-in private namespaces, deletion, export, quota, and no manager analytics.

- Decision oracle: build only after users repeatedly need cross-session recall and legal/security approves the evidence boundary.

**Option C — autonomous evaluation and promotion.** **Omit.** No gateway path may merge, publish, or silently select an unapproved skill. Self-improvement papers can inform proposal generation later, not authority at launch.

Rollback is Git revert or pinning the last-known-good commit SHA. The gateway stores and emits the selected immutable revision; it does not maintain a second marketplace state machine.

### 9. MCP governance and tool search — **Launch governance; optional search**

**Option A — identity-derived narrowing on existing filters (recommended).** Map group policy to allowed MCP clients/tools, stamp the request context, and rely on both discovery and execution enforcement already present (`core/mcp/utils.go:110-124`, `core/mcp/exec.go:161-184`). Audit attempted denials and tool outcomes separately.

- Tradeoff: reuses proven hierarchy; process-local live connections still require explicit reconnect behavior.
- Decision oracle: launch with explicit allow-lists and no wildcard auto-execution for privileged tools.

**Option B — lexical metadata tool search.** Optional when tool counts make full schema injection costly; search returns candidates, but authorization filters candidates before exposure and again before execution.

- Decision oracle: add when measured tool-schema tokens or model selection quality crosses an agreed threshold.

**Option C — embedding/LLM tool router or marketplace-wide autonomous execution.** **Omit at launch.** It adds latency, nondeterminism, prompt-injection surface, and authorization confusion.

### 10. Dashboard — **Launch operations only**

**Option A — replace cruft with four operator views (recommended).** Availability/provider health, configuration convergence, key/revocation/audit, and budget/overdraft/alerts. Link to the enterprise observability system for detailed traces.

**Option B — remove incomplete pages and ship no new dashboard.** Valid if Prometheus/Grafana and audit queries cover launch operations.

- Decision oracle: prefer removal over a misleading page; add UI only for an operator workflow that cannot be performed safely elsewhere.

Cost analytics, employee productivity, skill rankings, RL/training, friction scores, and experiment dashboards are optional/omitted at launch.

### 11. Training, evaluation, RAG, distillation, and RL — **Omit from gateway launch**

**Option A — stable privacy-filtered export contract (recommended seam).** Versioned envelopes and immutable routing/skill revisions let MLflow, Hugging Face, Prime environments, TensorZero-style evaluators, or internal training systems consume data independently.

**Option B — bundled offline evaluation service.** Optional only when one approved use case has an owner, dataset, metric, and promotion decision.

**Option C — train/distill/optimize inside gateway pods.** **Omit.** It competes for CPU/memory, expands credentials and dependencies, and destroys failure isolation.

## Launch cut line

### Must ship

- Aurora authority schema, audit log, version/outbox, snapshot loader, polling backstop, and atomic swap.
- Opaque virtual keys: create, rotate, revoke, overlap window, per-user/team ownership, model/provider policy.
- Okta reconciliation and deterministic group-to-policy mapping.
- Hard authentication/authorization boundary with explicit fail-closed behavior.
- Bounded budget/rate enforcement, controlled overdraft approval/rules, alerts, and reconciliation.
- Deterministic routing, health-aware ordered fallback, and Bedrock U.S. profile configuration.
- Kubernetes probes, HPA, PDB/topology/rollout settings, graceful shutdown, and failure drills.
- Metadata-first privacy-filtered telemetry and audit evidence.
- MCP allow-list governance at discovery and execution.
- Git issue/draft-MR proposal path with human approval and immutable skill SHA.
- Focused operator surfaces or removal of misleading dashboard pages.

### Compatible but non-blocking

- Weighted canary and asynchronous shadow traffic.
- Encrypted approved-content replay.
- Lexical tool search.
- Managed private recall/CASS service.
- Redis counters if lease overshoot proves unacceptable.
- A separate stateful MCP connection-owner service.
- Offline RAG/friction/evaluation adapters.

### Explicitly omit

- Gossip replication, FSx config authority, and database lookups on every inference request.
- Online semantic/bandit routing and inline evaluator/model dependencies.
- Autonomous skill merge/publication or gateway-held merge credentials.
- Training, fine-tuning, distillation, RL, or large replay execution in gateway pods.
- Employee-surveillance dashboards and raw-log-by-default storage.
- Net-new Rust rewrite before the Go launch architecture is measured.

## Decision oracles and stop rules

| Question | Launch choice | Reconsider only when |
|---|---|---|
| PostgreSQL notification or gossip? | Notify hint + poll, or poll first | p99 convergence exceeds 5s under tested pod scale, and Aurora—not application bugs—is proven limiting |
| Add Redis? | No | Calculated/measured lease overshoot violates a hard requirement and Aurora serialization is too slow |
| Autonomous skill promotion? | No | Never for protected internal marketplace; human MR approval remains invariant |
| Add semantic router? | No | Offline replay shows a statistically and operationally material gain after privacy/cost controls |
| Store raw traces? | No by default | Named approved use case has retention, access, deletion, and incident controls |
| Rewrite in Rust? | No | Profiled Go substrate cannot meet an agreed SLO after bounded optimization |
| Build a dashboard page? | Only core operations | It closes a measured operator workflow gap better than existing observability tooling |
| Build managed CASS/flywheel? | Separate optional service | Opt-in demand, privacy review, deletion semantics, and an owned SLO exist |

## Premortem gates before implementation fan-out

1. **Stale revocation:** kill notifications, disconnect/reconnect Aurora, reorder/duplicate events, and prove every pod converges by polling within five seconds.
2. **Partial snapshot:** inject malformed or referentially incomplete state and prove the old snapshot remains active and the pod alerts rather than partially mutating.
3. **Aurora regional outage:** prove existing inference continues from a bounded-age snapshot while all administrative writes clearly fail/freeze.
4. **Budget overshoot:** crash pods with outstanding reservations, retry/fallback requests, and lose settlement acknowledgements; measure the exact maximum overdraft.
5. **Plugin failure ambiguity:** inject governance/routing errors and prove security denials cannot degrade into the generic warn-and-continue plugin behavior documented at `core/bifrost.go:7279-7297`.
6. **Fallback double charge:** exercise multiple attempts and streams; prove logical-request and physical-attempt accounting reconcile.
7. **Okta deactivation:** deactivate a user during an Aurora/Okta interruption and prove the documented exposure bound and emergency deny path.
8. **MCP bypass:** hide a tool from discovery and invoke it directly; preserve the execution-side denial shown at `core/mcp/exec.go:161-184`.
9. **Skill proposal escape:** prove the proposal worker cannot merge, push protected branches, read production secrets, or place unredacted evidence in an MR.
10. **Bad rollout:** update provider/governance state under saturation and verify no no-worker window, queue corruption, or synchronized pod eviction; existing provider replacement deliberately starts new workers first (`core/bifrost.go:3706-3725`).

If these ten gates cannot be automated and repeatedly passed, the correct L5 response is to remove the dependent feature from launch—not compensate with more components.
