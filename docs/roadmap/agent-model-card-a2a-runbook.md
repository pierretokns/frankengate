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
- `GET /api/v1/agent-model-cards/detail?provider=...&model=...` returns one
  card with the compiled revision and schema version.
- `GET /api/v1/agent-model-cards/export` emits a complete visible snapshot
  with `Content-Disposition: attachment` for review, offline diffing, or
  evidence ingestion.
- `POST /api/v1/agent-model-cards/validate` validates a candidate without
  persisting it. Validation reason codes are stable and suitable for UI and
  automation.
- `GET /.well-known/agent-card.json` and the legacy `/.well-known/agent.json`
  publish the canonical inbound FrankenGate card. `POST /a2a` and
  `POST /a2a/jsonrpc` accept bounded `message/send`; `GET /a2a/tasks/{id}`
  retrieves a bounded, TTL-limited task result.

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
idempotency keys scoped by the validated tenant/issuer/subject principal;
retention is bounded and in-memory in this first transport adapter, so durable
recovery requires the Day-2 outbox/task-store work.

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
through the normal asynchronous observation path. Registry manifests enter a
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

## Recovery playbook

1. Freeze new remote-card promotion if digest, freshness, or trust failure
   rates breach the SLO; preserve the last known-good revision.
2. Quarantine the affected card/transport and remove it from admission. Do
   not delete evidence needed for incident review.
3. Drain or retry only idempotent tasks with the same task/idempotency key;
   never replay a side-effecting task without an explicit operator decision.
4. Restore catalog, trust, task, and evidence stores in dependency order;
   verify tenant/policy epoch fences before reopening routing.
5. Re-run the offline gates and a signed-card/cross-tenant smoke test, then
   record the promoted card revision and release artifact digest.
