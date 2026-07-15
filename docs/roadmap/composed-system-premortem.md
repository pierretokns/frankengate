# Composed-System Pre-Mortem and Failure Discovery Program

Status: active architecture gate
Date: 2026-07-15

## Why this exists

The highest-leverage decisions are often limitations, not features: connection-pool
semantics, stale-state boundaries, idempotency after streaming begins, identity joins,
and what happens when independently reasonable subsystems interact. Competitor feature
lists do not reveal these constraints. This program searches for them before code and
repeats after every major architecture revision.

## JSM skill stack

No installed JSM skill is literally named `premortem`. Use this composition:

1. `modes-of-reasoning-project-analysis`: failure-mode, robust/worst-case, systems,
   dependency-mapping, counterfactual, adversarial, edge-case, reference-class,
   second-order-effects, and debiasing lenses.
2. `grill-with-docs` when available outside the JSM catalog: challenge decisions against
   primary documentation and force unresolved questions into the open.
3. `research-software`: inspect stable source, recent PRs, issues and real defaults for
   every borrowed mechanism. Code and failure reports outrank marketing documentation.
4. `codebase-archaeology` and `codebase-audit`: find the actual seams and implementation
   hazards in Bifrost rather than designing against an imagined architecture.
5. `reality-check-for-project`: compare the vision, Beads, implementation, tests and
   shipped artifacts; label missing coverage and proof explicitly.
6. `deadlock-finder-and-fixer`, `profiling-software-performance`, `security-audit-for-
   saas`, and the repository release checklist for specialist reviews.
7. `testing-conformance-harnesses`, `testing-fuzzing`, `testing-metamorphic`,
   `testing-golden-artifacts`, and `testing-real-service-e2e-no-mocks`: convert each
   accepted risk hypothesis into a reproducible oracle.
8. `multi-model-triangulation` and `dueling-idea-wizards`: resolve consequential design
   disagreements and generate alternatives before an ADR is frozen.

## Finding contract

Every finding records: invariant; evidence; triggering conditions; local symptom;
propagation path; affected tenants and state; severity, likelihood and confidence;
detection oracle; containment; recovery; at least two design options; smallest decisive
experiment; ADR/Bead owner; and residual risk. Owner-acknowledged risks are separated
from discoveries. A feature is not accepted because another project implements it.

For borrowed designs, also record exact source revision/license, original deployment
assumptions, state authority, consistency model, mandatory dependencies, load shape,
failure model, security boundary, operational staffing, and which assumptions differ
here. Imported code never imports its correctness argument automatically.

## High-leverage hypotheses to resolve

### Aurora eventing and immutable snapshots

- `LISTEN/NOTIFY` requires session-affine dedicated connections. RDS Proxy, pool modes,
  failover, idle timeouts and reconnect gaps can silently remove the low-latency path.
  The outbox cursor—not notification receipt—must prove convergence.
- Autoscaled pods make per-consumer cursors and retention ambiguous. Consumer identity,
  dead-pod leases, compaction, tombstones and resnapshot thresholds need one contract or
  the outbox grows forever or deletes events a lagging pod still needs.
- A notification storm can cause every pod to refetch the same large snapshot. Coalesce
  revisions, fetch deltas, jitter repair, and benchmark Aurora read amplification.
- Cold-start behavior differs from restart behavior. No pod may become ready without a
  verified snapshot; persisted encrypted snapshots require key availability, expiry,
  rollback protection and a defined bootstrap trust root.
- Database time, pod time and identity-provider time can disagree. Security leases use
  authoritative timestamps and tolerate bounded skew without extending revoked access.

### Virtual keys, identity and entitlements

- SCIM and OIDC identify the same human through different immutable identifiers. Email,
  display name and group name are mutable and cannot be join keys. Define account-link,
  rename, rehire, duplicate, merge and tenant-migration behavior.
- Okta delivery is not an ordered transaction log. Pagination, rate limits, retries,
  webhook loss, group-rule lag and delete-before-create reorderings require periodic
  full reconciliation, generation markers and tombstones.
- Group union alone escalates privilege. Deny precedence, constraint intersection,
  nested/dynamic groups, direct grants, break-glass grants and entitlement provenance
  need one explainable evaluator.
- Virtual-key rotation creates an overlap window across pods and clients. Define
  activation, grace, revocation, hashed lookup, prefix collision, cache eviction,
  in-flight stream handling and proof that plaintext keys never enter telemetry.
- Revocation within five seconds conflicts with availability during authority outage.
  Each security resource needs a freshness lease and explicit fail-closed behavior;
  “last known good” cannot mean indefinite last known privilege.

### Quotas, budgets and cost

- Provider usage and price can arrive after streaming, retries or disconnect. Admission
  is a reservation, not truth; reconciliation must handle abandoned streams, partial
  usage, duplicate callbacks and late price corrections without double charging.
- A single strongly consistent counter becomes a hot row; sharding creates overshoot.
  Quantify acceptable overdraft, reservation chunking, fairness, contention and the
  maximum loss/overspend under pod or database failure.
- RPM, TPM, dollars, concurrency and provider quotas have different windows and clocks.
  Avoid pretending one token-bucket primitive gives correct hierarchical enforcement.
- Pricing is versioned by provider, model, region/profile, modality, cache class and
  negotiated discount. Historical cost must bind the price revision used, while budget
  admission needs a conservative estimate when output length is unknown.
- Retry budgets must be end-to-end. Client, gateway, SDK and provider retries composed
  independently create exponential traffic, duplicate spend and correlated overload.

### Kubernetes, Go runtime and long streams

- PDB, HPA and three replicas do not prove capacity after zone loss. Long streams delay
  scale-down and drain, while rollout surge and HPA can compete. Test N+1/zone-loss
  capacity with realistic stream-duration and request-size distributions.
- Liveness tied to provider/Aurora health causes restart storms; readiness tied too
  loosely serves stale policy. Separate process health, snapshot eligibility and local
  admission capacity.
- Large request bodies, streaming buffers, JSON transformations, high-cardinality maps
  and slow clients can drive Go GC or memory-limit kills before CPU-based HPA reacts.
  Bound every buffer/cache/queue and profile RSS, allocations and goroutine retention.
- Per-tenant/provider bulkheads can themselves explode cardinality. Define bounded
  admission structures, eviction semantics and a safe overflow bucket.
- Shutdown after first byte cannot transparently replay a generation. Drain semantics
  must distinguish admitted, provider-connected, streaming and tool-side-effect states.

### Routing, provider failover and canaries

- Model names do not imply capability equivalence. Tool dialect, structured output,
  reasoning fields, tokenizer/template, context limits, safety behavior, logprobs,
  caching and regional availability must be capability-manifest fields.
- Bedrock inference profiles can move inference to a destination region with different
  quota, latency, policy and evidence requirements. The gateway must record actual
  destination and distinguish runtime, profile, provisioned and cross-region routes.
- Health-based routing can synchronize every pod onto the same fallback and collapse it.
  Use capacity-aware weighting, deterministic jitter, shared-but-bounded health evidence
  and anti-flap hysteresis; test correlated failure rather than one dead endpoint.
- Hedging improves tails but duplicates cost/capacity and may create side effects. It is
  legal only before externally visible output and only for idempotent operations with a
  winner/cancellation/reconciliation protocol.
- Sticky canary assignment must bind tenant/subject, experiment revision and request
  family across pods. Config changes during an experiment otherwise contaminate cohorts.
- Learned routers can exploit proxy labels, leak tenant identity, fail OOD, or trade a
  safety floor for aggregate reward. Promotion requires calibration, abstention,
  critical-slice floors, strongest deterministic baseline and immediate rollback.

### Traces, replay, evaluation and learning

- A trace is not automatically replayable. Time, randomness, model nondeterminism,
  mutable retrieval indexes, external tools, credentials and side effects must be frozen,
  stubbed or explicitly classified as counterfactual.
- Replay of tool calls is a privileged execution surface. Network and writes default to
  denied; fixtures cannot mutate quotas, audit authority, production data or the world.
- Sampling creates selection bias: failures and expensive traces are oversampled while
  silent success may be absent. Dataset and evaluator claims must publish inclusion
  probabilities, missingness and slice coverage.
- LLM judges share correlated model biases and can be prompt-injected by traced content.
  Treat rationales as untrusted fresh output, isolate judge prompts, scan outputs, use
  deterministic validators and calibrate against blinded human labels.
- Evaluation, reward and user perception are different typed evidence. Collapsing them
  into one score enables Goodhart effects and unsafe optimizer tradeoffs.
- Continual skill/router/KB improvement creates coupled experiments. Use one canonical
  candidate/assignment/evidence/promotion receipt so simultaneous revisions remain
  attributable and rollbackable.
- Training on production traces risks consent/license violations, cross-tenant leakage,
  holdout contamination, duplicated sessions across splits and inability to honor later
  deletion. Dataset snapshots require lineage and tombstone hooks before compilation.
- Teacher logprobs are not portable supervision without tokenizer, vocabulary, template,
  sampling and retention-permission compatibility. Behavioral distillation and logit
  distillation remain distinct pipelines.

### MCP, tools and skills

- A server can mutate a tool name, description or schema after approval. Capabilities
  are immutable digest-addressed manifests; new or changed tools enter quarantine.
- Tool descriptions and search results are an adversarial ranking surface. Policy filters
  before search, normalized publisher-independent metadata, collision rules and call-
  time revision checks prevent discovery from becoming authorization.
- Remote tools create SSRF, DNS rebinding, redirect, private-address, decompression,
  unbounded-stream and binary-malware risks. Invocation policy applies after resolution
  and on every redirect, with byte/time limits.
- OAuth bearer forwarding creates a confused deputy. Credential exchange must attenuate
  audience, scopes, actor chain, tenant and lifetime; inability to attenuate fails closed.
- Tool retry can repeat an irreversible action. Approval binds normalized arguments,
  manifest/policy revision, nonce and side-effect class; mutation or retry may require a
  new approval or an idempotency contract.
- Skill improvement proposals are supply-chain changes. The proposer/evaluator cannot
  approve its own revision; deterministic helpers run outside gateway pods under a
  separately governed workload identity and sandbox.

### Privacy, audit and observability

- PII scanners miss secrets, code, encoded/binary data, evaluator rationales, profiles,
  heap dumps, dead-letter queues and support bundles. Every sink and derived artifact
  needs an eligibility rule and re-scan boundary.
- Streaming redaction across chunk boundaries can leak split tokens; buffering enough
  context adds latency and memory. Measure recall/latency and define block, redact or
  metadata-only behavior per destination.
- Stable pseudonyms enable cross-purpose correlation. Use tenant- and purpose-scoped
  tokens, protected reversible mappings, rotation and crypto-shredding.
- Tamper-evident audit conflicts with deletion only if content is embedded. Preserve a
  non-identifying event/tombstone proof while deleting or crypto-shredding mappings and
  propagating deletion to object stores, caches, indexes, datasets and backups by policy.
- Telemetry backpressure must never block inference, but dropping security evidence
  silently is unacceptable. Bound buffers, prioritize event classes, expose loss counters
  and degraded-audit state, and decide when high-risk mutations fail closed.
- Cardinality can bankrupt or disable observability. Tenant/model/tool/trace labels need
  explicit budgets, aggregation and exemplars rather than unconstrained dimensions.

### Schema, release and operational composition

- Mixed-version rolling deployment is the real schema consumer. Every snapshot, API and
  database migration declares min/max reader/writer versions and downgrade behavior.
- Heavy migration work at boot can deadlock the rollout behind Aurora advisory locks.
  Expand/contract, concurrent/background work and prior-version rollback are release
  fixtures, not review checklists alone.
- In-process plugins expand the gateway failure and memory boundary. Panics, leaks,
  unbounded latency and ABI/version mismatch need isolation or a very small trusted set.
- Signed artifacts are useless if the old image, verification key or compatible schema
  cannot be retrieved during an incident. Rehearse registry outage, key expiry, rollback
  and restore rather than checking that signatures exist.
- License obligations attach separately to code, models, weights, datasets, prompts,
  containers and generated/translated derivatives. The provenance ledger must block an
  artifact whose obligations or compatible licenses are unresolved.
- Configuration, policy, identity, price, catalog, experiment and model revisions can
  produce a cross-plane split brain even when each plane is internally consistent. Every
  decision receipt records the complete revision vector used; replay and audit surface
  absent or incompatible revisions explicitly.

## Recurring execution

Run a deep pre-mortem before freezing each major ADR and again at compatibility alpha,
three-pod alpha, private beta and release candidate. Each round must include at least one
primary-source/issue-history check per borrowed mechanism, one composed failure scenario,
one falsifiable experiment, and one independent debiasing review. Stop a round only when
new findings are duplicates or low-confidence observations—not because the document is
long.
