# FrankenGate agent center-plane NFRs and Day-2 contract

This document defines the operating envelope for the model/agent/MCP center
plane. Discovery and remote task work are asynchronous control-plane activity;
they must not block provider inference or silently become routing authority.
Targets are initial production gates and must be re-baselined with measured
capacity before a release is declared generally available.

## SLO and budget matrix

| Surface | Target | Budget / alert | Exit mode |
| --- | --- | --- | --- |
| Card fetch and validation | p95 <= 2 s, p99 <= 5 s | 1% failed or stale fetches / 10 min | serve last verified snapshot; never promote new endpoint |
| Admission lookup | p99 <= 10 ms, zero network calls | >0.1% policy-evaluation errors | fail closed for new routes; existing leases finish |
| Task start | p95 <= 1 s after admission | queue age > 5 s | bounded queue with 429/Retry-After |
| Unary task completion | provider/card-specific deadline, default 5 min | timeout/error rate > 2% / 10 min | retry only classified transient errors |
| Streaming task | first event p95 <= 2 s; idle gap <= 30 s | stalled stream count > 0 | cancel upstream, emit terminal failure, retain audit |
| Cancellation | acknowledge p95 <= 2 s | orphan task count > 0 | lease expiry and operator kill switch |
| Webhook/push delivery | p95 <= 10 s; at-least-once | DLQ age > 5 min | poll/replay from event ledger |

Availability SLOs should be measured per tenant and per remote agent, not only
globally. A remote dependency outage must not consume the gateway's provider
inference budget.

## Capacity, backpressure, and idempotency

- Bound card payloads, event sizes, task payloads, concurrent fetches, queued
  tasks, event history, and per-tenant retry budgets. Reject oversized input
  before parsing or signature verification.
- Use a per-tenant and per-destination concurrency limit. Queue admission is
  explicit; when full, return a retryable response with a bounded retry hint.
- Every outbound task has a caller-supplied or gateway-generated idempotency
  key bound to tenant, card digest, endpoint, and request hash. Replays return
  the existing task, never a second remote execution.
- State transitions are monotonic except `working -> input_required -> working`.
  Events carry sequence/attempt information; duplicate events are harmless and
  out-of-order events are quarantined for review.
- Retry only connection reset, timeout before response, 429, and explicitly
  classified 5xx conditions. Use exponential backoff with jitter and a hard
  attempt/deadline cap. Never retry an authorization, schema, policy, or
  invalid-card failure.
- Dead-letter terminal failures with the redacted request hash, card digest,
  remote endpoint, last event, and retry decision. Do not store raw secrets or
  unrestricted prompts in the DLQ.

## Security and identity controls

- Bind every decision to tenant, caller identity, delegated subject, policy
  epoch, card digest/version, and credential/key ID. A signature is evidence;
  only explicit policy admission authorizes routing.
- Card discovery uses the SSRF-safe resolver: HTTPS by default, DNS/IP
  rebinding protection, private/link-local/loopback denial, bounded redirects,
  egress allowlists, and separate callback/webhook policy.
- Rotate OAuth, SigV4, API, signing, and webhook secrets without changing
  immutable card identity. Revocation and kill switches must invalidate new
  admissions immediately and drain existing leases according to policy.
- Do not forward ambient credentials. Token exchange is audience-, tenant-,
  destination-, and lifetime-bound; log only key IDs and token fingerprints.
- Preserve four-level MCP filtering and apply it again on delegated or
  recursive turns. Internal recursion markers are typed and cannot be set by
  an untrusted client header.

## Freshness, trust, and schema compatibility

- Every active card has retrieved-at, observed-at, revision/ETag, digest,
  signature evidence, trust state, expiry, and reviewer/policy epoch.
- Stale verified cards may remain visible for diagnostics but cannot introduce
  a new endpoint, capability, credential, or publisher without review.
- Unknown schema fields are retained only within bounded extension/unknown
  limits. Producers and consumers must accept N and N-1 card versions during a
  rolling upgrade; unsupported versions are quarantined, not discarded.
- Keep immutable source snapshots and typed current pointers. Rollback is a
  pointer change to a previously verified digest, never an in-place mutation.

## Observability and evidence retention

Every discovery/admission/task span and audit row should include:

```text
tenant_id, request_id, trace_id, task_id, card_digest, card_revision,
source_uri, policy_epoch, trust_state, capability_decision, remote_agent,
attempt, outcome, latency_ms, artifact_digest, token/cost summary
```

Use OpenTelemetry context propagation across HTTP, A2A, MCP, and provider
hops. Metrics must be bounded-cardinality: hash or classify arbitrary agent
IDs and do not use raw URLs, prompts, tokens, or tool arguments as labels.

Default retention: 30 days for redacted task/audit events, 90 days for card
source snapshots and trust evidence, and 13 months for aggregate SLO/cost
metrics. Tenant policy may shorten retention; legal hold may extend it. Raw
payloads, transcripts, and artifacts require an explicit encrypted content
store reference and separate access control.

## Failure-mode and runbook matrix

| Failure | Detection | Immediate action | Recovery |
| --- | --- | --- | --- |
| Card endpoint unavailable | fetch error/age alert | keep last verified card; stop promotion | retry with jitter; operator revalidates |
| Signature invalid/revoked | trust rejection metric | quarantine digest; deny new routing | rotate key or review publisher; never auto-trust |
| DNS/egress policy violation | resolver denial | record security event; no network call | update allowlist through review |
| Remote 429/5xx storm | per-destination error budget | shed queue and cap retries | exponential recovery; compare remote health |
| Stream stalls | idle timer | cancel lease and emit failure | replay only if idempotent and policy permits |
| Duplicate/out-of-order event | sequence check | retain evidence; ignore duplicate | reconcile from task poll endpoint |
| Tenant policy epoch changes | epoch mismatch | deny stale admission; drain/revoke leases | re-admit against current snapshot |
| Event store unavailable | write failure metric | fail closed for new tasks; preserve provider path | restore store and replay durable outbox |
| Credential compromise | kill-switch audit event | revoke key/token and quarantine cards | rotate, validate, and staged re-enable |

## Recovery and release gates

- RTO: 15 minutes for control-plane catalog/admission state; RPO: 5 minutes
  for task/audit metadata. Provider inference remains independently available
  when the control plane is degraded.
- Back up immutable card snapshots, trust/key metadata, policy epochs, task
  state, and encrypted outbox records. Run a quarterly restore drill and a
  monthly key-revocation drill; record evidence in the release checklist.
- Test clean startup with an empty catalog, stale snapshots, unavailable
  registry, duplicate events, full queues, partial database restore, and
  incompatible card versions. Test rollback to the last verified digest and
  verify no new route is admitted during rollback.
- Conformance gates must cover A2A unary/streaming, cancellation, polling,
  artifacts, auth failure, SSRF denial, signature/quarantine, tenant
  isolation, MCP recursion, and OTel trace continuity. Chaos gates must cover
  DNS rebinding, remote flapping, event loss/duplication, store outage, and
  clock skew.

On-call ownership is split: catalog/provenance, policy/governance, transport/
broker, and provider inference each have a named escalation path. No single
remote agent or SDK outage may page the provider inference owner without an
exhausted local admission/queue budget.
