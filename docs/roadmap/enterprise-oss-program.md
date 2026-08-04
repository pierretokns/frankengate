# Enterprise OSS Gateway Program

Status: discovery baseline, 2026-07-14
Upstream baseline: `maximhq/bifrost` at `596679bc03b54a64838f01e7e8ad094ee6b9bd5e`
Closest transport tag at discovery: `transports/v1.6.4`

## Purpose

This program turns the Apache-2.0 Bifrost gateway into an independently maintained,
fully open enterprise gateway. The target is not a cosmetic clone of Bifrost
Enterprise. It is a production control plane and data plane with testable behavior:
distributed credentials, identity-driven entitlements, atomic limits, highly
available routing, safe rollout and replay, honest operational UI, and reproducible
release artifacts.

The current upstream is not an empty community edition. It already contains virtual
keys, provider/model restrictions, team and customer governance, budgets, rate
limits, routing rules, key rotation UI, Helm autoscaling, and portions of cluster
configuration. Some enterprise schemas and import seams also exist beside fallback
UI components. Every workstream therefore begins with an implementation audit and
conformance tests. Existing working OSS code is extended, not rewritten.

## Non-goals and boundaries

- Do not obtain, decompile, or copy Maxim's unavailable enterprise source or images.
- Do not copy public documentation prose or screenshots into this repository. Public
  docs are behavioral research inputs, not assumed Apache-2.0 source.
- Do not transliterate competitor code until the exact file and pinned revision have
  passed a license/provenance review. Similar behavior may be independently
  implemented from protocols and tests.
- Do not place online RL or arbitrary evaluator execution in the latency-critical
  inference path.
- Do not promise strict global limits using gossip alone.
- Do not show dashboard features whose backing API and evidence are absent.
- Do not change the public project name or publish artifacts under a new identity
  until the owner selects a name and trademark posture.
- Launch is an internal Kubernetes/Aurora deployment using U.S. Bedrock profiles. Do not
  spend launch scope on public multi-tenant SaaS, mandatory Redis, active/active global
  control-plane writes, non-Kubernetes discovery, or shared-filesystem configuration.

## License and provenance policy

Bifrost OSS is Apache-2.0. Redistribution requires the full license, retention of
applicable notices, prominent modification notices in modified files, and compliance
with the patent and trademark clauses. A citation alone is insufficient.

Before the first public artifact:

1. Preserve `LICENSE` and all applicable upstream copyright, patent, trademark, and
   attribution notices.
2. Determine whether upstream ships a `NOTICE`; if it does, preserve applicable
   contents in source and binary distributions.
3. Add a fork attribution and modification policy without implying Maxim endorsement.
4. Maintain `docs/roadmap/provenance-ledger.md` for every imported algorithm, test,
   schema, asset, generated file, and dependency whose origin is not this fork.
5. Record origin URL, revision, exact paths, license, modifications, and reviewer.
6. Generate SPDX or CycloneDX SBOMs, scan dependency licenses, and bundle license
   material with binaries, images, Helm charts, and source archives.
7. Treat LiteLLM as mixed-boundary until each source path is proven usable. Prefer
   Apache-2.0 Envoy AI Gateway, standards documents, and independent tests.
8. Require legal review before claiming compatibility with protected product names.

This section is engineering policy, not legal advice.

## Architectural principles

### Separate control plane from data plane

The control plane owns users, groups, policies, key lifecycle, route definitions,
audit events, replay jobs, and durable configuration. The data plane authenticates,
authorizes, reserves quota, selects a route, invokes an upstream, reconciles usage,
and emits telemetry. A temporary control-plane outage must not silently widen data-
plane access.

### Durable authority, bounded caches

PostgreSQL is the durable source for identity, policies, credentials, route config,
and audit metadata. A shared atomic counter system such as Redis is the fast authority
for reservations and rate windows. Per-pod caches are performance aids with versions
and bounded staleness. Revocation has an explicit epoch/invalidation stream and a
fail-closed policy once the safe staleness bound is exceeded.

### Deny by default and intersect grants

Administrative RBAC answers who may manage resources. Data-plane entitlements answer
which models, providers, keys, tools, and operations a principal may invoke. They are
separate systems. Effective access is the intersection of enabled user, enabled key,
team/business-unit policy, access profile, provider/key availability, model allowlist,
and any request-scoped restriction. An empty grant set denies access; `*` is explicit.
`GET /v1/models` and actual invocation use the same evaluator.

### Make money and security invariants explicit

Revocation and monetary limits cannot depend only on eventual gossip. Quota is
reserved atomically before upstream work and reconciled against actual usage after
completion. Retry, fallback, canary, and replay must not double-charge or escape the
same entitlement decision.

### Evidence before UI

Every dashboard route is controlled by a server capability manifest. A feature is
visible only when its APIs, authorization checks, persistence, telemetry, and tests
exist. Placeholder charts and fabricated metrics are removed.

## Verified baseline and gap-audit method

For every feature below, classify each layer as `present`, `partial`, `stub`, or
`absent`: schema, migration, store, service, HTTP API, authorization, UI, Helm/config,
telemetry, unit tests, integration tests, multi-pod tests, documentation, packaging.
Capture file-and-line evidence and do not infer implementation from a config field or
fallback component.

Known baseline evidence includes:

- `plugins/governance`: virtual-key validation, hierarchical limits, model/provider
  filtering, routing, accounting, cache/store concurrency, and extensive tests.
- `transports/bifrost-http/handlers/governance.go`: virtual-key/team/customer APIs.
- `ui/app/workspace/virtual-keys`: create, revoke/enable, rotate, export, and details.
- `helm-charts/bifrost`: HPA, cluster ports/config, SCIM fields, and access-profile
  schema entries; presence does not prove runtime implementations.
- `ui/app/_fallbacks/enterprise`: explicit OSS placeholders for cluster, SCIM, RBAC,
  access profiles, adaptive routing, failover handling, audit, guardrails, and exports.
- `docs/enterprise`: detailed public behavior descriptions that can seed clean-room
  requirements and tests.

## Domain 1: distributed virtual-key lifecycle

### Data model

A virtual key has an opaque random secret shown once, a stable ID, tenant ownership,
display name, keyed secret hash, short fingerprint, state, issue time, optional
`not_before` and expiry, last-used time, rotation family, policy version, and audit
metadata. Plaintext secrets are never stored or logged. The lookup format supports
fast indexed identification plus constant-time verification.

States are `pending`, `active`, `rotating`, `revoked`, and `expired`. Rotation creates
a new credential transactionally, optionally leaves the predecessor valid for a
bounded overlap, and schedules final revocation. Revocation is idempotent and emits a
durable versioned invalidation event only after the database transaction commits.

### Multi-pod contract

- A key created on one pod authenticates on every ready pod within a measured bound.
- Revocation and policy reduction propagate within the configured security SLO.
- A pod that cannot prove its revocation cache is fresh beyond the bound fails closed.
- Duplicate invalidation events and reconnects are harmless.
- Cache entries carry key/policy versions; older events cannot overwrite newer state.
- Rotation overlap is explicit and visible; emergency rotation can skip overlap.
- Key lists never expose hashes or secret material.

### Operational API

Support create, reveal-once response, list/filter, inspect, disable/re-enable, rotate,
bulk rotate, revoke, and quota inspection/top-up with idempotency keys. Every mutation
is RBAC-scoped, audited, and returns the new resource version. Bulk operations expose
per-item results rather than claiming all-or-nothing success.

## Domain 2: budgets, rates, and top-ups

Limits apply at global, business-unit, customer, team, user, access-profile, virtual-
key, provider, and model scopes. The evaluator returns the tightest applicable denial
and records all affected accounting dimensions.

### Algorithms

- RPM/TPM use atomic token-bucket or fixed/calendar-window operations with server time.
- Spend budgets use atomic reservations based on estimated tokens and selected route
  pricing, then reconcile actual provider usage and refunds.
- Concurrent requests cannot race past a hard limit.
- Streaming cancellation, provider error, timeout, retry, and fallback have documented
  charge/refund semantics.
- Admin top-up/version change is immediately observable across pods and is audited.
- Calendar windows define timezone and daylight-saving behavior; rolling windows do
  not silently become calendar windows.
- Denials return HTTP 429, `Retry-After` when meaningful, stable machine-readable code,
  limiting scope, window/reset, and safe remaining quota.
- Counter-backend loss has configurable fail-closed behavior; money and security tiers
  default closed.

The ledger is idempotent by request/attempt ID. Reconciliation jobs detect stuck
reservations and repair them without creating credit.

## Domain 3: identity, Okta, groups, and access profiles

Identity work is split into four independently testable protocols instead of calling
everything "SCIM":

1. OIDC Authorization Code with PKCE for login; issuer/audience/nonce/state checks,
   JWKS refresh, encrypted sessions, logout, and refresh-token handling.
2. Standards-complete inbound SCIM 2.0 `/Users` and `/Groups` endpoints with bearer
   authentication, RFC 7643/7644 schemas, pagination, filters, PATCH, ETags, idempotent
   retries, group membership, deactivation, and bulk behavior where supported.
3. Provider directory import/reconciliation for Okta APIs, separately authenticated
   and rate-limited, with dry-run preview and resumable checkpoints.
4. Mapping/reconciliation engine for claims/groups to roles, teams, business units,
   and access profiles.

Group membership determines access profiles; profiles define allowed providers,
provider keys, models, budgets, rate limits, and MCP tools. Direct user grants can be
supported but precedence and intersections are explicit. Removing a user or group
revokes the derived entitlement and managed key within a measured bound. Manual and
managed resources cannot silently overwrite each other.

All mappings are versioned and explainable: an administrator can ask why a user can
or cannot access a model and receive the contributing grants and denials without
seeing secrets.

## Domain 4: high availability and Kubernetes operations

Request pods are horizontally scalable. Durable configuration lives outside a pod;
shared counters are atomic; local caches are rebuildable. Gossip/member discovery may
serve membership and non-authoritative health distribution, but not final revocation
or budget authority.

Required deployment behavior:

- Kubernetes service discovery plus explicit peer mode for non-Kubernetes installs.
- Startup migrations use a lock and support a documented mixed-version window.
- Readiness requires usable config, database, counter authority, and required provider
  initialization. Liveness detects dead process state without causing restart storms.
- SIGTERM stops new work, drains in-flight unary and streaming requests, and leaves the
  cluster before the grace deadline.
- HPA supports CPU plus request concurrency/queue depth/latency-derived external
  metrics. Scale-to-zero is out of scope for the primary gateway.
- PodDisruptionBudget, topology spread, anti-affinity, resource requests/limits,
  startup probes, and network policies have secure defaults/examples.
- Singleton reconciliation/export/replay schedulers use leases and fencing tokens.
- Multi-zone partitions and Redis/Postgres outages have a documented availability vs
  consistency decision for each function.

Acceptance tests run at least three pods and cover create/use/revoke/rotate, concurrent
overspend, pod death, rolling upgrade, delayed invalidation, counter loss, database
failover, and network partition.

## Domain 5: routing, circuit breaking, canaries, and shadow traffic

Routing is a staged policy engine:

`authenticate -> entitlement -> quota reserve -> candidate expansion -> health and
circuit filter -> deterministic rollout bucket -> weighted selection -> invoke ->
retry/fallback -> reconcile -> observe`.

No later stage may reintroduce a candidate removed by entitlement. Adaptive weights
use bounded, explainable error-rate, latency, throughput, saturation, and cost signals.
Health samples have decay and minimum-sample protection. failover handlings operate per
provider key and model, use closed/open/half-open states, and avoid synchronized probes.

Canary policies support stable hashing by tenant/user/key/session/trace, percentage or
header-based cohorts, explicit baseline/candidate routes, start/end windows, and
instant rollback. Shadow requests are separately budgeted, scrubbed, never returned to
the caller, and disabled for unsafe tools/side effects. Promotion gates consume real
metrics with minimum samples, confidence/guard bands, error and latency thresholds,
cost ceilings, and manual override audit events.

Envoy AI Gateway is the preferred open reference for policy separation, token-aware
rate limits, failover, and OpenTelemetry concepts. LiteLLM can supply behavioral test
ideas only after file-level license review. We do not port architecture mechanically.

## Domain 6: traces, replay, evaluation, and environment export

The gateway emits OpenTelemetry/OpenInference-compatible spans with request, route,
attempt, provider, model, key fingerprint, tenant, cost, token, cache, tool, and policy
decision correlations. Sensitive payloads are separated from searchable metadata,
encrypted, retention-scoped, redacted before export, and access-controlled.

Replay consumes an immutable, versioned trace envelope plus snapshots of route policy,
model/provider configuration, pricing, prompt/tool metadata, and evaluator versions.
Default replay is dry-run or shadow. External network calls and tool side effects are
blocked unless a policy and operator explicitly allow a sandboxed substitute.

Results compare output, tool trajectory, policy decisions, latency, tokens, cost, and
errors. Evaluator plugins can score rubrics, deterministic checks, model judgments,
and safety policies. Promotion uses the same canary gate primitives.

Prime Intellect Verifiers and Hugging Face OpenEnv inspire an export adapter: sanitized
trace-derived datasets, environment/tool harness, sandbox/context, and reward rubric.
Exports are reviewed and versioned. Training workers run outside the gateway; no RL
optimizer is linked into the request path.

## Domain 7: audit, observability, and honest dashboard

Audit events are append-only, actor- and tenant-scoped, contain before/after hashes or
redacted diffs, correlate to request/trace IDs, and can be exported. Tamper evidence
uses chained hashes or signed batches with verification tooling. Retention and legal
hold are policy-controlled.

Replace the current dashboard information architecture with:

- Overview: live SLOs, traffic, errors, saturation, and provider health.
- Keys: lifecycle, fingerprints, ownership, last use, rotation, and revocation.
- Identity: users, groups, mappings, sync health, and reconciliation failures.
- Entitlements: profiles and an explain-access tool.
- Limits: reservations, consumption, denials, resets, and audited top-ups.
- Routing: routes, circuits, canaries, shadows, and promotion history.
- Cluster: members, versions, cache/invalidation lag, counter and DB health.
- Traces: search, redaction state, replay jobs, diffs, and evaluator scores.
- Audit: filters, verification, retention, and export status.

Existing cost pages are retained only where backed by reconciled usage and pricing.
Fake, duplicate, upsell, or permanently stubbed pages are removed or capability-hidden.

## Domain 8: security posture

- Threat-model key theft, privilege escalation, confused deputy, tenant escape,
  replay side effects, stale authorization, counter bypass, injection, SSRF, and
  malicious provider responses.
- Encrypt secrets and sensitive payloads with envelope encryption and rotation.
- Enforce tenant scoping in every store query and authorization check.
- Use structured redaction and prohibit credentials in logs/traces/errors.
- Protect admin and SCIM APIs with rate limits, idempotency, CSRF/session controls,
  strict validation, and audit.
- Fuzz SCIM PATCH/filter parsers, policy expressions, route configuration, and
  authorization boundaries.
- Add race tests for cache/store/counter code and chaos tests for distributed safety.
- Publish vulnerability disclosure, supported versions, and signed provenance.

## Domain 9: build and release artifacts

The fork must build from a clean checkout with pinned toolchains. CI produces Linux,
macOS, and Windows binaries where supported; multi-architecture OCI images; Helm chart;
source archives; checksums; SBOMs; license bundle; vulnerability and license reports;
and SLSA-compatible provenance. Artifacts are signed with keyless Sigstore where the
publishing environment supports it.

Release gates include Go/UI lint and unit tests, governance race tests, schema and
migration tests, SDK compatibility tests, Playwright critical flows, multi-pod tests,
upgrade/rollback tests, Helm lint/install tests, image scan, license scan, reproducible
build comparison, benchmark regression thresholds, and verification of every published
asset. Release jobs must work in a fork without Maxim-owned secrets or registries.

## Delivery sequence

### Phase 0: fork safety and verified inventory

Establish `upstream`/fork remotes after the owner selects the destination. Pin the
baseline, create modification/provenance rules, enumerate all OSS/enterprise seams,
run the existing build/test baseline, and publish the layer-by-layer feature matrix.

### Phase 1: foundational invariants

Define tenant/identity/policy/key schemas, shared entitlement evaluator, versioned
cache invalidation, atomic reservation protocol, audit envelope, and capability
manifest. Add conformance tests before new UI.

### Phase 2: distributed keys and limits

Implement hashed reveal-once keys, rotation/revocation, shared cache coherence,
hierarchical reservations, reconciliation, top-ups, and three-pod failure tests.

### Phase 3: identity and entitlements

Implement OIDC, inbound SCIM, Okta directory reconciliation, group/profile mappings,
explain-access, lifecycle revocation, and UI/API workflows.

### Phase 4: resilient routing and operations

Implement health/circuit state, adaptive routing, deterministic canaries, shadowing,
Kubernetes readiness/drain/HPA/leases, and chaos/rolling-upgrade tests.

### Phase 5: trace replay and eval

Implement secure trace envelopes, replay sandbox, comparison/evaluator jobs, promotion
gates, and optional environment dataset export.

### Phase 6: product and release hardening

Remove/hide dashboard cruft, finish operator surfaces, benchmark and profile, complete
security review, create signed reproducible artifacts, and exercise upgrade/runbooks.

### Phase 7: governed learning and distillation

After trace, replay, identity and artifact foundations are stable, add immutable learning
datasets, evaluator and human-feedback registries, external Unsloth/TRL/Prime/OpenAI/DSPy
job adapters, teacher/student distillation, blind side-by-side evaluation, artifact
lineage and evidence-gated shadow/canary promotion. Training stays outside gateway pods.

## Global acceptance criteria

The program is not complete until all of the following are demonstrated in CI or a
repeatable release-candidate environment:

1. One newly created virtual key works across three pods.
2. Revocation and emergency rotation meet a measured propagation SLO during load.
3. Simultaneous requests cannot exceed a hard shared budget beyond the documented
   reservation bound.
4. Group removal removes model visibility and invocation rights consistently.
5. `/v1/models` and inference authorization share the same decision result.
6. Retry, fallback, canary, and shadow paths cannot escape entitlements or double-charge.
7. A network partition follows each subsystem's documented fail-open/closed policy.
8. Replay performs no external side effects by default and records every override.
9. A mixed-version rolling upgrade preserves requests, keys, counters, and migrations.
10. Dashboard pages expose only real API-backed state.
11. Clean-checkout CI emits verified binaries, image, chart, SBOM, notices, signatures,
    checksums, and provenance without Maxim infrastructure.
12. Performance remains within explicit, measured regression budgets established from
    the pinned upstream baseline.

## Agent flywheel

Wayfinder is not currently installed and should not be implemented yet. The local
toolchain already supplies codebase archaeology, research, planning, `br`, `bv`, NTM,
multi-model review, and Brenner-style hypothesis testing.

Use the following loop:

1. Complete Phase 0 evidence and convert unknowns into explicit research beads.
2. Review this plan through at least four strong-model rounds, grounding every load-
   bearing decision and stopping only at structural steady state.
3. Polish the bead graph six or more rounds; never remove functionality merely to
   simplify execution.
4. Require `br dep cycles` to be empty and inspect `bv --robot-insights` and
   `bv --robot-plan`; never launch bare `bv`.
5. Start a small NTM swarm only after foundational schemas and invariants stabilize.
   Security/control-plane foundations require strong reviewers; lower-cost workers are
   appropriate for bounded adapters, tests, docs, and mechanical UI after contracts exist.
6. Each agent claims one ready bead, reserves files or uses a worktree, implements and
   verifies it, closes it with evidence, and runs `br sync --flush-only`.
7. Use adversarial research for contested consistency, quota, replay, and rollout
   hypotheses. Do not use a swarm to manufacture consensus.

## Research sources

- Bifrost OSS repository and Apache-2.0 license: https://github.com/maximhq/bifrost
- Bifrost Enterprise overview: https://docs.getbifrost.ai/enterprise/overview
- Bifrost virtual keys: https://docs.getbifrost.ai/features/governance/virtual-keys
- Bifrost budgets and limits: https://docs.getbifrost.ai/features/governance/budget-and-limits
- Bifrost clustering: https://docs.getbifrost.ai/enterprise/clustering
- Bifrost adaptive load balancing: https://docs.getbifrost.ai/enterprise/adaptive-load-balancing
- Bifrost user provisioning: https://docs.getbifrost.ai/enterprise/user-provisioning
- Bifrost RBAC: https://docs.getbifrost.ai/enterprise/rbac
- Bifrost audit logs: https://docs.getbifrost.ai/enterprise/audit-logs
- Envoy AI Gateway: https://aigateway.envoyproxy.io/docs/
- Envoy token-aware rate limiting: https://aigateway.envoyproxy.io/docs/capabilities/traffic/usage-based-ratelimiting/
- AWS AgentCore observability: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html
- Prime Intellect Verifiers: https://github.com/PrimeIntellect-ai/verifiers
- Hugging Face TRL OpenEnv: https://huggingface.co/docs/trl/openenv

Further option and landscape research is maintained in:

- `docs/roadmap/base-repo-language-and-product-decision.md` — the downstream
  compatibility-distribution experiment, selective hexagonal seams, Rust bakeoff rule,
  conformance envelope, and naming/release decision gates.
- `docs/roadmap/technical-decision-options.md` — domain-specific state propagation,
  quota, membership, snapshot, multi-region and failover alternatives.
- `docs/roadmap/gateway-feature-landscape.md` — State of AI history recovery plus
  primary-source competitor, Mantle, logprob, replay, RL and identity-flywheel features.
- `docs/roadmap/learning-distillation-flywheel.md` — governed trace-to-dataset,
  evaluation, external training, teacher/student distillation, model artifacts and
  side-by-side promotion architecture.
- `docs/roadmap/realtime-friction-rag-quality-plane.md` — real-time friction events,
  non-collapsed RAG metrics, alerts, knowledge-gap cases, reviewed KB updates, and the
  NVIDIA evaluation/training-worker boundary.
- `docs/roadmap/mcp-tool-skill-governance-and-research.md` — approved tool/skill
  catalogs, deferred tool search, credential and invocation governance, adversarial MCP
  evaluation, and model/tool-dialect capability manifests.
- `docs/roadmap/privacy-redaction-and-learning-boundaries.md` — content-capture policy,
  Presidio plus small-model detection, pseudonymization/vault semantics, privacy-safe
  friction analytics, deletion lineage and learning-plane isolation.

These links establish research provenance, not permission to copy content or code.
