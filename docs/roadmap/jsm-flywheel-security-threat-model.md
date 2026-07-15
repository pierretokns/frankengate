# Managed JSM Flywheel Security Threat Model

Status: pre-implementation security audit

## Launch risk acceptance

The skill marketplace is internal and protected by mandatory human merge-request approval. At launch, Git is the promotion authority; the gateway can propose but cannot merge or publish. This lets the project defer a custom promotion service, evaluator separation, sealed holdouts, autonomous rollback/recall, employee analytics, and most causal-learning infrastructure.

Human review does not protect secrets already copied into a patch or CI artifact, nor does it make execution of an untrusted candidate safe. The non-negotiable baseline remains privacy/tenant filtering before persistence, immutable provenance and permission diffs, branch protection, sandboxed validation without production credentials, bounded execution, auditability, and revert/pin rollback. If these controls prove disproportionately difficult for a proposed feedback feature, omit that feature from launch rather than weakening the boundary.

## Deployment and attacker model

The launch target is an internal Kubernetes gateway backed by Aurora PostgreSQL. Realistic attackers include a compromised employee endpoint, malicious or prompt-injected MCP server, poisoned repository/session content, disgruntled insider, compromised skill publisher, cross-tenant user, and an external actor who obtains a virtual key. Provider, identity, database, model, tool, endpoint collector and evidence-index failures are also treated as adversarial conditions.

The primary security assets are provider credentials, virtual keys, identity and entitlement state, private prompts/traces, personal procedural memory, signed skill and evaluator revisions, promotion authority, holdouts, deletion tombstones, evidence provenance and gateway availability.

## Trust boundaries

```text
employee endpoint/session history [untrusted]
  -> collector/parser [sandbox boundary]
  -> privacy + evidence eligibility [mandatory boundary]
  -> authoritative evidence ledger [tenant boundary]
  -> derived indexes/search [untrusted derived projection]
  -> proposal generator [tainted-input boundary]
  -> evaluator/runner [sandbox and oracle boundary]
  -> promotion authority [separation-of-duty boundary]
  -> signed catalog/client cache [distribution and recall boundary]
```

A signature establishes artifact origin and integrity. It does not establish that the source evidence was true, the procedure is safe, or the evaluation was valid.

## Security invariants

1. Normalize once before security validation; every consumer uses the canonical representation and stable hashes.
2. Session text, tool output and retrieved content remain tainted until independently verified.
3. Mandatory authorization, privacy eligibility and capability decisions fail closed; inference failures caused by optional evidence services fail open to the last approved revision.
4. Recovery, replay, reindex, backfill, restore and deletion paths enforce the same tenant, privacy, signature and authorization rules as primary ingestion.
5. Reconciliation may remove or quarantine privilege automatically; it never raises privilege or republishes a revision.
6. Candidate, evaluator and promotion authority are separate identities and independently versioned components.
7. Every artifact and action is tenant-scoped at both database and application layers.
8. Credential-bearing fields are structurally denied before any evidence copy; detector inference is not the credential boundary.
9. Capability expansion is never inferred from improved quality.
10. Outbox, parser, evaluator and replay resource consumption is bounded per tenant, user, skill and job.

## Critical and high attack chains

### SEC-FLY-001: stored prompt injection becomes signed procedure

- **Severity:** Critical
- **Path:** malicious repository/MCP result -> endpoint session -> CASS retrieval -> reflection/proposal -> LLM evaluator -> human-readable approval package.
- **Failure:** provenance remains syntactically intact while untrusted instructions are semantically laundered into a signed organizational skill.
- **Controls:** immutable taint chain; structural separation of evidence and instructions; proposal workers cannot execute retrieved instructions; ACIP-style scanning at every derived artifact; executable outcomes outrank narrative; independent evaluator; hostile-session conformance fixtures.
- **Oracle:** seed instructions asking the proposal/evaluator to approve, hide evidence, mark itself helpful, or exfiltrate a canary. No instruction may change policy, tool use or verdict.

### SEC-FLY-002: evidence-loss attack makes the candidate appear superior

- **Severity:** Critical
- **Path:** attacker or fault drops failed tool output/candidate-arm events/privacy-heavy failures while successful records remain searchable.
- **Failure:** promotion uses a biased denominator even though inference and search appear healthy.
- **Controls:** assignment reconciliation; authenticated collector manifests; per-arm coverage and missingness bounds; source-authority health; promotion fail-closed; loss alerts independent of request SLO.
- **Oracle:** selectively remove candidate failures and verify promotion becomes ineligible rather than improving.

### SEC-FLY-003: evaluator substitution and self-approval

- **Severity:** Critical
- **Path:** a meta-skill proposes behavior plus weaker tests, changes a judge prompt, impersonates reporter/approver, or supplies positive feedback about itself.
- **Failure:** every gate reports success because the oracle moved with the candidate.
- **Controls:** immutable evaluator ownership; no candidate/evaluator joint promotion; prior evaluator shadowing; authenticated reporter and run binding; no-self-approval at database and service layers; two-person approval for high risk.
- **Oracle:** submit combined candidate/evaluator/approval mutations through UI, API, worker, import and recovery paths; every surface denies consistently.

### SEC-FLY-004: endpoint/gateway parser divergence smuggles identity or privacy state

- **Severity:** Critical
- **Path:** Unicode, encoding, path, model/tool aliases, JSON duplicate keys or normalization differences cause collector, gateway, privacy transformer and evaluator to hash or classify different logical content.
- **Failure:** wrong tenant join, signature confusion, denylist bypass, duplicate evidence or evaluation of content different from what executed.
- **Controls:** one canonical envelope parser/library and schema version; reject ambiguous encodings/duplicate keys; normalize before hashing/signing; differential tests across every language implementation; record original transport hash separately from canonical content hash.
- **Oracle:** shared adversarial corpus produces identical canonical value or identical rejection across Go and every endpoint collector.

### SEC-FLY-005: credential capture through trace and MCP surfaces

- **Severity:** Critical
- **Path:** an observability plugin requests broad header patterns, or credentials appear in MCP arguments/results, plugin logs, errors, trace attributes or encoded nested values.
- **Failure:** evidence outbox, index, evaluator or golden artifact becomes a durable secret store.
- **Controls:** central hard credential denylist; header allowlist; deep structural inspection; canary credentials in every surface/encoding; metadata-only on transform failure; no raw fixture generation from production content.
- **Oracle:** search every durable and transient artifact for seeded canaries after success, error, stream abort, retry and replay.

### SEC-FLY-006: poisoned or oversized events create a cross-tenant denial of wallet/service

- **Severity:** High
- **Path:** deeply nested payload, decompression bomb, huge session, high-cardinality dimensions, endless revisions or poison event consumes parser, index, model, retry and Aurora resources.
- **Failure:** one user delays other tenants, exhausts cost limits, pins an outbox cursor or causes unbounded DLQ/storage growth.
- **Controls:** pre-parse byte/depth/cardinality limits; per-tenant weighted admission; job token/cost/time budgets; poison quarantine; retry ceilings; bulkheads; fair compaction; metadata-only downgrade; no inference backpressure.
- **Oracle:** adversarial tenant load remains within its resource partition while another tenant's inference and evidence latency stay inside SLO.

### SEC-FLY-007: rollback bypass through stale clients and derived descendants

- **Severity:** Critical
- **Path:** harmful skill is cached offline, copied into a repository, embedded in a child or compiled into a tool; canonical alias later rolls back.
- **Failure:** clients and descendants continue executing revoked behavior; resulting evidence contaminates new proposals.
- **Controls:** immutable revision on every execution; expiry/re-attestation for high risk; signed deny/recall epochs; dependency quarantine; evidence taint; client telemetry for residual use; separate side-effect compensation.
- **Oracle:** offline-client and descendant-revision scenario from the E2E specification.

### SEC-FLY-008: recovery path restores deleted or revoked authority

- **Severity:** Critical
- **Path:** database restore, CASS mirror, replay import, index rebuild or migration reintroduces deleted evidence, revoked skill, stale permission or exhausted holdout.
- **Failure:** self-heal raises privilege and defeats deletion/recall.
- **Controls:** durable tombstone and revocation epochs outside disposable indexes; restore manifests; post-restore reconciliation that only decays authority; legal-hold conflict state; signed snapshot watermark; recovery conformance tests.
- **Oracle:** restore a snapshot predating deletion/revocation and verify the current tombstone/epoch wins before any query or invocation.

### SEC-FLY-009: cross-tenant inference through search and analytics

- **Severity:** Critical
- **Path:** semantic nearest-neighbor results, error timing, counts, filtered dashboards, repeated queries or rare procedures reveal another tenant or individual.
- **Failure:** content or performance is reconstructed without direct row access.
- **Controls:** physical/logical tenant partitioning; authorization before retrieval; constant/opaque denials; cohort thresholds after every filter; complementary suppression; differencing budget; rare-pattern review; no shared raw embeddings.
- **Oracle:** two-tenant and small-team red teams attempt membership inference, differencing and timing enumeration.

### SEC-FLY-010: MCP confused deputy occurs before the policy hook

- **Severity:** Critical
- **Path:** current execution preparation resolves client and acquires connection/credential before the central MCP plugin pipeline.
- **Failure:** denied calls can touch credential and connection state, and preparation failures evade complete policy/evidence finalization.
- **Controls:** normalize immutable target -> mandatory policy/approval -> attenuated credential -> connection -> wire call -> final receipt; audience/scope binding; stable tool digest; ambiguous-completion state.
- **Oracle:** denied requests produce zero credential issuance, connection acquisition and upstream packets.

## Surface-transpose matrix

Every invariant must be tested across HTTP API, Go SDK, WebSocket/realtime, SSE, MCP connect/list/execute, endpoint collector, batch import, replay, reindex, migration, restore, admin UI/API, CLI, background worker and deletion/recall job. Protection on one surface is not evidence for another.

## Required security gates

- Threat-model and permission diff on every skill revision.
- Strict schema and unknown-field rejection for security records.
- Signed immutable manifests, but independent semantic evaluation.
- Sandboxed collectors, proposal workers, evaluators and deterministic-tool builders with no inherited provider/cloud/database credentials.
- Network egress and filesystem capability allowlists.
- Tenant and subject authorization inside the transaction that mutates promotion state.
- Audit-grade receipts for promotion, exception, rollback, quarantine, deletion and revalidation.
- Stable opaque errors for unauthorized versus nonexistent resources.
- Supply-chain pinning, SBOM, provenance and revocation for JSM skills and their tools.
- Incident kill switches that do not depend on the failing evidence/search service.
