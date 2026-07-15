# ADR: Principal Deprovisioning by Authorization Epoch

Status: accepted primitive and launch architecture sketch

Date: 2026-07-15

Related bead: `bif-kyy.5.6`

## Context

Enterprise launch requires Okta deactivation and group-removal events to revoke every derived authority surface quickly and deterministically. The affected surfaces include:

- Unary in-flight requests.
- SSE streams.
- WebSocket sessions.
- Queued work.
- Virtual/provider key artifacts derived from a principal.
- Cache entries derived from a principal's authorization.
- MCP grants.
- MCP live connections.

The failure mode to avoid is a stale session, key, cache entry, queued job, MCP grant, or connection continuing to authorize a principal after Okta or the enterprise control plane has removed the principal or one of its groups. Another failure mode is reactivation accidentally making old derived artifacts valid again.

## Decision

Bind every derived artifact to:

```text
immutable tenant
immutable issuer
immutable subject
monotonically increasing authorization epoch
artifact kind
artifact id
```

The tuple `(tenant, issuer, subject)` is the principal identity. It must be immutable for the lifetime of derived artifacts. Display names, emails, group labels, team membership, and policy names are not identity keys.

The authorization epoch is the principal's revocation fence. Deactivation increments the epoch and marks the principal inactive. Group removal increments the epoch and keeps the principal active. Every derived artifact minted before the increment becomes stale. Reactivation must use a strictly greater epoch, so old epochs never revive.

## Isolated Primitive

The in-memory reference primitive is implemented in `core/authorityepoch`.

It provides:

- `Principal`: immutable tenant, issuer, subject.
- `Reference`: principal, epoch, artifact kind, artifact id.
- `Registry.Activate`: registers or reactivates a principal only at a strictly newer epoch.
- `Registry.Mint`: creates a derived authority reference from the current active epoch.
- `Registry.Validate`: fail-closed validation for unknown principal, inactive principal, stale epoch, malformed reference, and unsupported artifact kind.
- `Registry.Subscribe`: cancellation subscription for live artifacts.
- `Registry.AdvanceEpoch`: group-removal style invalidation that keeps the principal active.
- `Registry.Deactivate`: deactivation invalidation that also prevents new artifacts.

Supported artifact kinds:

- `unary`
- `sse`
- `websocket`
- `queued`
- `key`
- `cache`
- `mcp_grant`
- `mcp_live_connection`

The primitive uses deterministic logical revisions, not wall-clock sleeps. Invalidation delivers cancellation notifications synchronously in the same logical revision, so tests can prove the SLO without timing flakiness.

## Tests

The deterministic tests are in `core/authorityepoch/registry_test.go`:

- `TestMintedReferencesAreBoundToPrincipalAndEpoch`
- `TestGroupRemovalCancelsArtifactsWithinLogicalSLO`
- `TestDeactivationInvalidatesAndStaleEpochsNeverRevive`
- `TestValidationFailsClosedForUnknownMalformedAndStaleReferences`

They prove:

- Minted references are bound to immutable tenant, issuer, subject, and epoch.
- Tampering with issuer fails validation.
- Group removal cancels unary, SSE, WebSocket, queued, key, cache, MCP grant, and MCP live-connection references within the deterministic logical SLO.
- Group removal keeps the principal active at the next epoch for new artifacts.
- Deactivation cancels live artifacts, rejects new artifacts while inactive, and does not let stale epochs revive after later reactivation.
- Unknown principals, malformed principals, zero epochs, unsupported artifact kinds, and stale subscriptions fail closed.

Run with:

```bash
cd core
go test ./authorityepoch
```

## Production Aurora and Outbox Integration

The production control plane should persist the primitive's state in Aurora. Redis is not required for correctness.

### Authority tables

Recommended durable rows:

- `principal_authority_epochs`
  - tenant
  - issuer
  - subject
  - current_epoch
  - active
  - reason
  - policy_version
  - updated_at
  - updated_by

- `principal_epoch_outbox`
  - monotonic event id
  - tenant
  - issuer
  - subject
  - old_epoch
  - new_epoch
  - active
  - reason
  - committed_at

- Optional audit tables for artifacts that need durable replay:
  - artifact id
  - artifact kind
  - principal tuple
  - minted epoch
  - terminal state
  - cancellation event id

### Mutation transaction

Okta deactivation or group removal should run in one Aurora transaction:

1. Lock `principal_authority_epochs` for `(tenant, issuer, subject)`.
2. Verify the incoming Okta/control-plane event is newer than the last applied source cursor.
3. Increment `current_epoch`.
4. Set `active=false` for deactivation or keep `active=true` for group removal.
5. Append a `principal_epoch_outbox` row with old epoch, new epoch, active state, reason, and source cursor.
6. Commit.
7. Emit `LISTEN/NOTIFY` as a hint containing only the event id or new high-water mark.

Pods consume the outbox with bounded polling as the correctness backstop. Notification loss cannot preserve old authority beyond the configured stale-snapshot bound.

### Pod application

Each pod maintains an immutable local snapshot or small in-memory registry for hot validation. On an outbox event:

1. Fetch committed authority rows up to the new high-water mark.
2. Build a new local state.
3. Atomically publish the snapshot.
4. Cancel matching subscriptions for live artifacts from prior epochs.
5. Deny new artifacts for inactive principals.

Every gateway path that carries principal-derived authority validates the reference before use. If the local snapshot is missing, malformed, stale beyond the configured freshness bound, or cannot prove the epoch, validation fails closed.

### Surface mapping

- Unary requests: validate before provider I/O. Cancellation after provider I/O records an authorization-cancelled terminal state and prevents fallback or follow-up work from old epoch.
- SSE streams: subscribe at stream start; cancellation closes the stream with a stable policy-revoked error.
- WebSocket sessions: subscribe at upgrade/session bind; cancellation closes the socket and clears session authority.
- Queued work: store the reference with the queue item; validate on enqueue and again before dequeue execution.
- Keys: bind selected virtual/provider key authority to the principal epoch; stale key artifacts cannot select provider credentials.
- Caches: include authorization epoch in cache scope; stale cache entries are misses after group removal or deactivation.
- MCP grants: validate grant references before tool discovery and before execution.
- MCP live connections: subscribe the connection owner to the principal epoch; cancellation closes or fences the connection and invalidates derived tool calls.

## Deterministic Logical SLO

The primitive models the SLO as logical revisions. Production should translate this into an operational bound:

- Local in-process invalidation: same event application cycle.
- Cross-pod propagation: outbox poll/notify bound, expected within the accepted launch convergence window.
- Stale snapshot: fail closed after the configured maximum snapshot age.

The important property is not "best effort cancellation"; it is that every artifact carries enough data to be rejected after the epoch changes, even if the explicit cancellation signal is delayed or the artifact moves through a queue.

## Failure Policy

- Unknown principal: deny.
- Inactive principal: deny.
- Stale epoch: deny.
- Missing epoch: deny.
- Unsupported artifact kind: deny.
- Snapshot too old: deny new governed artifacts and close live artifacts when possible.
- Outbox unavailable: continue only within max snapshot age; admin writes fail/freeze.
- Duplicate or reordered Okta events: ignore events at or below the recorded source cursor; epochs remain monotonic.

## Consequences

Positive:

- One primitive covers sessions, keys, caches, queued work, MCP grants, and live connections.
- Epoch binding is cheap enough for the hot path.
- Deactivation and group removal share one revocation fence.
- Reactivation cannot revive old artifacts.
- The same model works with Aurora snapshots and without mandatory Redis.

Costs:

- Every derived artifact must carry principal tuple and epoch.
- Cache keys and queue payloads need schema updates before production integration.
- Long-lived SSE/WebSocket/MCP paths need cancellation subscriptions.
- Operators need explicit stale-snapshot alerts and dashboards.

## Acceptance Criteria Mapping

- Bind derived sessions, keys, caches, MCP grants and live connections to immutable tenant issuer plus subject and monotonically increasing authorization epoch: yes.
- Implement in-memory reference registry: yes, `core/authorityepoch`.
- Fail-closed validation: yes.
- Cancellation subscriptions: yes.
- Tests prove deactivation/group removal invalidates unary, SSE, WebSocket, queued, key and MCP artifacts within deterministic logical SLO: yes.
- Tests prove stale epochs never revive: yes.
- Production Aurora/outbox integration explained: yes.
