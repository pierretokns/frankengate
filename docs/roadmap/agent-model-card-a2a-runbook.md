# FrankenGate Agent Model Cards and A2A runbook

This is the operator-facing contract for the model-card center plane. A card
is a discoverability and routing-evidence record; it is not a credential, an
authorization grant, or proof that a remote agent is safe to invoke.

## Surfaces

- `GET /api/v1/agent-model-cards` lists only models visible to the caller's
  existing provider/model policy. `query`, `provider`, `limit`, `offset`, and
  `unfiltered` are filters, not authorization bypasses.
- `GET /api/v1/agent-model-cards/metadata` returns visibility-filtered
  revision/source metadata without card bodies.
- `GET /api/v1/agent-model-cards/versions?provider=...&model=...` reports the
  current immutable revision and whether durable history is available.
- `GET /api/v1/agent-model-cards/diff?provider=...&model=...&from_revision=...`
  returns an empty same-revision diff or an explicit unavailable-history result;
  it never fabricates a comparison.
- `GET /api/v1/agent-model-cards/evidence?provider=...&model=...` reports
  evaluation-source hints and health/evidence availability. Missing stores are
  returned as `unknown`/unavailable, never as a positive safety claim.
- `GET /api/v1/agent-model-cards/detail?provider=...&model=...` returns one
  card with the compiled revision and schema version.
- `GET /api/v1/agent-model-cards/export` emits a complete visible snapshot
  with `Content-Disposition: attachment` for review, offline diffing, or
  evidence ingestion.
- `POST /api/v1/agent-model-cards/validate` validates a candidate without
  persisting it. Validation reason codes are stable and suitable for UI and
  automation.
- `GET /.well-known/agent-card.json` and the legacy `/.well-known/agent.json`
  publish the canonical inbound FrankenGate card. JSON-RPC is available at
  `POST /a2a` and `POST /a2a/jsonrpc`, including the released PascalCase task
  lifecycle methods plus the legacy slash aliases. HTTP+JSON is available at
  `POST /message:send`, `POST /message:stream`, `GET /tasks`,
  `GET /tasks/{id}`, `POST /tasks/{id}:cancel`, and
  `POST /tasks/{id}:subscribe`. Push configuration uses the current
  `tasks/pushNotificationConfig/{create,get,list,delete}` JSON-RPC methods and
  `/tasks/{id}/pushNotificationConfigs` REST resources. These CRUD methods are
  disabled unless an operator-approved delivery implementation is injected.
  `BifrostHTTPServer.ConfigureA2APush(...)` installs the durable config,
  payload, and outbox stores; `StartA2APushRuntime(...)` starts recovery and
  retry polling, and `StopA2APushRuntime()` must run before the object store is
  closed. The guarded `a2apush.HTTPDelivery` resolves opaque references only
  at send time, blocks unsafe DNS/IP destinations, disables redirects, and
  signs/idempotently labels requests. Nothing automatically opens an egress
  path from a generic secret resolver.
  When `Config.A2APushDelivery` is supplied by the deployment, normal API
  bootstrap installs the same durable stores automatically; it intentionally
  leaves the worker stopped until the deployment's egress/readiness gate calls
  `StartA2APushRuntime(...)`. If object storage is unavailable, bootstrap fails
  rather than silently downgrading push recovery to memory.
  Outbound A2A task admission is available through
  `Config.SubmitOutboundA2A` and `Config.DispatchOutboundA2A`: the latter uses
  the configured OAuth, pass-through, or RFC 8693/7523 resolver only at
  dispatch time, requires a caller-supplied allowlist policy and Sender, and
  keeps credentials out of task/event state. The transport does not silently
  create a network sender.
  `Config.SetA2AOutboundSender(...)` plus
  `Config.DispatchConfiguredOutboundA2A(...)` is the explicit convenience
  path for a deployment-owned guarded sender; without it, configured outbound
  dispatch fails closed.
  Inbound execution can optionally be supplied by an application-owned
  `A2AExecutionResolver`. The resolver receives only bounded normalized task
  input and may return a direct Message, an input-required/rejected task, or
  validated text/raw-file/URL-file/JSON-data artifacts. The gateway owns task
  persistence, tenant scoping, SSE ordering/replay, push enqueue, and wire
  serialization. Leaving the resolver unset keeps the existing governed
  text-model execution path; production does not interpret conformance-test
  message IDs.
  When an object store is configured, credential decisions are durably written
  under the hashed `a2a/credential-audit` prefix before dispatch; an audit
  write failure blocks the downstream sender. Records contain only tenant/task
  correlation, endpoint, card digest, credential kind, and bounded outcome.
  `GET /extendedAgentCard` is authenticated and returns the extended card when
  the public card advertises that capability. All task access is bounded,
  tenant-scoped, and TTL-limited.

## Trust and routing semantics

Source freshness, capability state, provenance, health, and policy admission
are independent dimensions. `unknown` is not `unsupported`, and a fresh card
is not trusted merely because it was fetched successfully. Remote Agent Cards
must pass HTTPS/size/content-type/SSRF checks, canonical validation, trust
verification, quarantine policy, health evidence, and capability admission
before they are eligible for routing.

Inbound A2A tasks enter the same identity, governance, budget, MCP, model,
audit, and kill-switch middleware as other gateway inference. A publisher's
card never transfers publisher authority to the caller. Task identifiers are
idempotency keys scoped by the validated tenant/issuer/subject principal. When
an object store is configured, completed task envelopes are persisted under a
hashed key with an expiry tag; the process-local cache remains a bounded hot
cache. Object-store errors fail closed rather than re-running an already
completed task. Without an object store, the bounded in-memory adapter remains
explicitly non-durable.

If the configured authority store implements principal authorization epochs,
inbound A2A submission and retrieval require a matching epoch reference and
validate it against the durable store. The standard JWT identity middleware
supplies the trusted principal; the handler resolves the current durable epoch
for the concrete task ID, while token-bound callers may provide an explicit
reference. This prevents a delegated caller from reusing a task after
deactivation or epoch advancement. Legacy deployments without that store
retain the existing principal-only compatibility path.

## Evidence and observability

Evaluation evidence records should include metric, score/status, dataset URI
and immutable revision, report URI, methodology, verifier, confidence, run
revision, reproducibility, slice, and staleness. The metadata-only provenance
envelope in `framework/modelcatalog/provenance` is the join key for card
revision/digest, policy epoch, capability decision, task, remote agent,
outcome, artifact, trace/request IDs, and cost. Raw prompts, responses,
credentials, and tool payloads must remain behind purpose-scoped redaction.
Inbound A2A execution attaches these bounded fields to the live trace root and
updates outcome/artifact on completion; OTEL and audit exporters receive them
through the normal asynchronous observation path. Streaming requests forward
provider deltas as ordered `message` SSE events with bounded artifact chunks,
terminal status, disconnect cancellation, and a bounded replay cursor
(`Last-Event-ID`) persisted in the object store when configured. A non-terminal
stream found after process restart is closed as an explicit restart-interrupted
failure rather than left as a permanently live subscription. Push delivery
exports only bounded lifecycle outcomes through
`bifrost_a2a_push_events_total`; `/health` and `/readyz` expose redacted runtime
status and counters. Credential resolution exports only bounded kind/outcome
metrics through `bifrost_a2a_credential_events_total`; token and secret
material never enters OTLP or durable audit records. Outbound task lifecycle
observation is wired automatically when the OTEL plugin is configured and
exports only bounded state/retryability labels through
`bifrost_a2a_task_events_total`; task IDs, prompts, tokens, and artifacts never
enter metric labels. Registry manifests enter a
bounded pending-review store keyed by repository, immutable revision, and
content digest; approval requires a reviewer and reason, and quarantine is an
explicit later decision.

## Day-2 release gates

Run the offline gates from the repository root:

```bash
python3 tests/conformance/a2a/recoverychecks.py
python3 tests/conformance/a2a/validatefixtures.py
```

These gates cover malformed and oversized cards, SSRF denial, trust and
quarantine, admission, broker retry/terminal behavior, duplicate and
out-of-order events, stale cards, deterministic round trips, and recovery
bookkeeping. A release must also run focused Go tests for
`modelcatalog/agentcard`, `a2adiscovery`, `admission`, `a2abroker`, `evidence`,
`health`, `inbound`, `provenance`, and `registry`.
For the runtime seams, also run the `a2apush` package, inbound handler tests,
configured outbound sender tests, and their race variants. The official
Python, Go, and JavaScript SDK smoke harness is required for release interop;
the pinned official TCK result is tracked in the SDK matrix and must not be
summarized as fully green while its documented discrepancies remain.

## Recovery playbook

1. Freeze new remote-card promotion if digest, freshness, or trust failure
   rates breach the SLO; preserve the last known-good revision.
2. Quarantine the affected card/transport and remove it from admission. Do
   not delete evidence needed for incident review.
3. Drain or retry only idempotent tasks with the same task/idempotency key;
   never replay a side-effecting task without an explicit operator decision.
4. Restore catalog, trust, task, and evidence stores in dependency order;
   verify tenant/policy epoch fences before reopening routing. Restore the
   object-store task prefix before accepting idempotent retries; if it is
   unavailable, keep A2A task routes closed rather than falling back to a new
   inference attempt.
5. Re-run the offline gates and a signed-card/cross-tenant smoke test, then
   record the promoted card revision and release artifact digest.
