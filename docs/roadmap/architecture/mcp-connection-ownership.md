# ADR: MCP Connection Ownership and Failover

Status: accepted for Kubernetes launch design

Date: 2026-07-15

Related bead: `bif-kyy.15.18`

## Context

Bifrost's MCP manager currently owns shared MCP client connections inside one process. Shared auth clients keep a persistent `MCPClientState.Conn`, while per-user auth clients open ephemeral per-call connections. The existing runtime also has reconnect logic and health monitors, but it does not define a cross-pod ownership contract for stateful MCP connections.

Relevant current code shape:

- `core/mcp/clientmanager.go:24` documents `AcquireClientConn` returning either the persistent shared connection or a fresh ephemeral per-user connection.
- `core/mcp/clientmanager.go:47` reuses `state.Conn` for shared connection auth types.
- `core/mcp/clientmanager.go:54` opens an ephemeral transport for per-user auth types.
- `core/mcp/clientmanager.go:226` and `core/mcp/clientmanager.go:236` define process-local reconnect behavior.
- `core/mcp/clientmanager.go:1206` establishes and registers external MCP connections.
- `core/schemas/mcp.go:115` defines `MCPCredentialStore`; `core/schemas/mcp.go:156` distinguishes per-call connections from shared persistent connections.
- `core/schemas/mcp.go:576` defines `MCPClientState` with process-local `Conn`, `CancelFunc`, and `State`.
- `core/mcp/pluginpipeline.go:20` wraps MCP wire operations in the plugin pipeline, but plugin gating is distinct from connection ownership.

For internal Kubernetes launch, MCP governance must handle:

- OAuth callback routing.
- Stateful MCP server sessions.
- Pod loss while an upstream call may still be running.
- Ambiguous completion when Bifrost loses the owner before receiving the terminal tool result.
- Idempotent reconnect and retry where the MCP server or tool supports it.
- No mandatory Redis.

## Decision

Use sticky, fenced ownership for stateful MCP clients at launch.

Aurora PostgreSQL is the durable authority for ownership leases, fencing tokens, OAuth flow routing, server-session metadata, and in-flight invocation receipts. Each stateful MCP connection has exactly one owner pod at a time. The owner must hold an unexpired lease and current fence before opening, renewing, reconnecting, or using the connection. Non-owner pods route stateful work to the owner or attempt takeover only after lease expiry. A later fence invalidates all writes from older owners.

Restricted stateless mode is also allowed for clients that do not require server session continuity and can safely open a per-call connection after policy and credential checks. The dedicated broker design is deferred.

Redis is not required. PostgreSQL row locks, compare-and-set updates, `LISTEN/NOTIFY` as a hint, and bounded polling are sufficient for the launch convergence target.

## Compared Options

### Option A: Sticky, fenced ownership

Summary:

- A durable `mcp_connection_owners` row maps a connection key to `owner_pod_id`, `fence`, `lease_expires_at`, connection kind, resumability, server-session metadata, and health.
- The owner pod maintains the live MCP client connection.
- Every connection mutation and tool invocation carries the current fence.
- A replacement pod can claim ownership after lease expiry; the claim increments the fence.
- Old owners can no longer write terminal state, refresh OAuth flows, or mark calls complete.

Advantages:

- Preserves existing low-overhead local connection use for the common path.
- Works with Kubernetes pods and Aurora without mandatory Redis.
- Makes split brain mechanically testable through fence comparisons.
- Provides a place to record ambiguous in-flight operations after owner loss.
- Supports resumable server sessions when the MCP server exposes a session ID or resume token.

Costs:

- Non-owner pods need one internal forward, redirect, or retry-to-owner path for stateful calls.
- Lease TTL and renewal interval become launch SLOs.
- In-flight tool calls can become ambiguous; the design must surface this instead of pretending success or failure.
- Mutating tools without server-side idempotency cannot be blindly retried after ambiguity.

### Option B: Dedicated MCP broker

Summary:

- A separate broker deployment owns all stateful MCP connections and exposes an internal RPC API to Bifrost pods.
- Gateway pods become stateless MCP callers.

Advantages:

- Centralizes connection ownership, callbacks, and server sessions.
- Simplifies gateway pod routing.
- Can later add specialized scheduling, backpressure, and protocol-specific behavior.

Costs:

- Adds a new mandatory runtime service in the availability path for MCP.
- Requires broker HA, rolling update, and observability work before launch.
- Moves but does not remove ambiguity and idempotency problems.
- Conflicts with the launch goal of preserving the existing Go substrate and avoiding optional services in the hot path.

Decision:

Do not launch with a mandatory broker. Reconsider only if sticky/fenced ownership produces unacceptable operator load or cannot support a required MCP protocol after failure drills.

### Option C: Restricted stateless support

Summary:

- Treat selected MCP clients as per-call, no durable upstream session.
- Open connection, execute policy-approved tool call, close connection.
- No server-session continuity is promised.

Advantages:

- Simple.
- Good fit for per-user OAuth or per-user headers where credentials are resolved per call.
- Pod loss is ordinary request failure; there is no shared upstream connection to recover.

Costs:

- Cannot support STDIO/SSE/shared server-session semantics.
- Tool discovery and server-side session state must be cached or rediscovered safely.
- Repeated connect/initialize overhead may be material for some tools.
- Mutating calls can still be ambiguous if the pod dies after sending the request.

Decision:

Allow restricted stateless mode only for clients explicitly marked stateless, idempotent or read-only where applicable, and not dependent on server-side sessions. It is a complement, not the general MCP ownership design.

## Kubernetes Launch Design

### Ownership key

The ownership key is:

```text
tenant_or_global_scope
principal_scope
mcp_client_id
auth_mode
server_session_key
```

Examples:

- Shared server-level OAuth client: `global / service / jira / oauth / shared`.
- VK-scoped per-user session: `tenant-a / vk:abc / linear / per_user_oauth / session-123`.
- User-scoped OAuth client: `tenant-a / user:42 / github / per_user_oauth / session-456`.

### Durable rows

Launch needs these durable records:

- `mcp_connection_owners`: connection key, owner pod ID, owner pod UID, fence, lease expiry, state, connection type, auth mode, server session ID, resumable flag, config version, grant version, kill-switch version, last heartbeat.
- `mcp_invocations`: invocation ID, connection key, fence, request ID, tool name, argument hash, idempotency key, started at, terminal state, ambiguity flag, retry policy, result pointer or error class.
- `mcp_oauth_flows`: OAuth state, connection key, requested principal, initiating request ID, expiry, callback status, token storage status, privacy/audit receipt.
- `mcp_server_sessions`: server session ID or resume token, connection key, owning fence, resumability class, last validated at, expiry if known.

Rows that contain secrets remain in the existing credential storage path. Ownership rows hold references and hashes, not bearer tokens.

### Claim and renewal

Claim uses an Aurora transaction:

1. Read the ownership row `FOR UPDATE`.
2. If no owner or the lease is expired, increment `fence`, set owner pod identity, and set `lease_expires_at`.
3. If the requester is the current owner and the lease is live, renew idempotently without changing the fence.
4. If another owner has a live lease, return the current owner and lease deadline.
5. Emit an outbox event after commit. Pods treat notifications as hints and poll as a backstop.

Every owner-side operation checks the current fence before writing durable terminal state. Older fences lose.

### Request routing

For a stateful MCP call:

1. Run mandatory policy before credential and connection acquisition.
2. Compute the connection ownership key.
3. Read the owner row from the local snapshot. If the owner is this pod and the lease is live, use the local connection.
4. If another pod owns the lease, forward once to that pod's internal Kubernetes address with the expected fence, or return a retryable owner route response to the caller-side gateway code.
5. If the lease is expired, attempt claim. The winner reconnects; losers retry against the new owner.

The forwarding protocol must be internal-only and must preserve request ID, invocation ID, policy revision, privacy disposition, and expected fence. A forwarded call that reaches a pod no longer holding the fence is rejected and retried through the owner lookup.

### OAuth callback routing

OAuth callback URLs must be stable service URLs, not pod URLs. The OAuth `state` value maps to `mcp_oauth_flows`, which maps to the connection key and initiating principal.

On callback:

1. Any pod can receive the callback.
2. The pod validates the state, expiry, and CSRF binding.
3. The pod stores or exchanges credentials through the durable credential path.
4. The pod routes reconnect or verification to the current owner fence. If the old owner is gone and the lease has expired, a new owner claims and resumes.
5. Stale owner callbacks cannot overwrite a newer owner because token and connection updates are fenced.

This avoids pod-affinity requirements for external OAuth providers.

### Server sessions

Server session metadata is recorded only when the upstream MCP transport or server exposes a meaningful session ID, resume token, or equivalent state handle.

On owner loss:

- If the server session is resumable, the new owner reconnects with the stored server session ID under a newer fence.
- If not resumable, the new owner starts a fresh session and marks pending invocations from the old fence ambiguous.
- If the server has side effects but no idempotency mechanism, automatic retry is disabled unless the tool is declared read-only/idempotent by policy.

### Pod loss

Pod loss is detected by lease expiry, Kubernetes deletion, or failed owner forwarding. Lease expiry is the authority.

After expiry:

1. Another pod claims the connection and increments the fence.
2. Pending invocations from the prior fence become ambiguous.
3. The new owner reconnects fresh or resumes the server session.
4. Late writes from the old pod are rejected by stale fence.

The old pod may still receive a late upstream response after a network partition. It must not be able to mark the invocation successful after losing the fence.

### Ambiguous completion

An invocation becomes ambiguous when Bifrost sent or may have sent a tool request but lost ownership before observing a terminal result.

The receipt must distinguish:

- `denied`: policy blocked before credentials or wire I/O.
- `not_sent`: connection failed before sending.
- `sent_pending`: owner holds lease and awaits result.
- `ambiguous`: prior owner lost before terminal result.
- `succeeded`: terminal success written by current fence.
- `failed`: terminal failure written by current fence.

Ambiguous mutating calls are not retried unless the tool has an idempotency key accepted by the server, a read-only declaration, or a specific compensation policy. The caller or agent should receive a stable ambiguous-completion error with the invocation ID and operator-visible receipt.

### Idempotent reconnect

Each MCP tool invocation receives a Bifrost invocation ID before wire I/O. Where the upstream server supports idempotency, this invocation ID or a derived key is sent to the server. Reconnect behavior:

- If a terminal result for the invocation exists, return it without sending another tool call.
- If the prior attempt is ambiguous and the tool/server supports idempotency, retry with the same idempotency key under the new fence.
- If the prior attempt is ambiguous and the tool is non-idempotent, do not auto-retry. Return an ambiguous completion receipt.
- If the prior attempt was not sent, retry normally under the current fence.

## Prototype

An isolated prototype is in `core/mcpownership`. It is deliberately not wired into the existing MCP manager.

The prototype models:

- Lease claims and renewals.
- Monotonic fencing.
- Live-owner split-brain rejection.
- Server-session resume versus fresh reconnect.
- OAuth callback routing through a durable state-to-current-owner lookup.
- Pod loss marking pending calls ambiguous.
- Idempotent restart of an ambiguous invocation under a newer fence.
- Rejection of stale completions and stale renewals.

The deterministic tests are:

- `TestFencedOwnershipRejectsStalePodAfterPodLoss`
- `TestLiveOwnerPreventsSplitBrain`
- `TestOAuthCallbackRoutesToCurrentOwnerAfterReclaim`
- `TestNonResumableServerSessionStartsFreshButPreservesAmbiguity`
- `TestRenewRequiresCurrentFence`

Run with:

```bash
cd core
go test ./mcpownership
```

## Failure Policies

- Ownership store unavailable: existing owner may continue only until its lease/freshness bound. New claims fail closed for stateful MCP.
- Snapshot stale beyond bound: do not create new stateful MCP invocations; existing in-flight calls may complete only if the owner can prove current fence.
- Owner forwarding failed: check current owner row; if lease live, retry or surface retryable owner-unavailable; if expired, claim.
- OAuth callback with no route: fail closed and keep the flow pending until expiry; never drop into a random pod-local session.
- Server session lost and non-resumable: start fresh only for future calls; old pending calls are ambiguous.
- Ambiguous mutating call: no automatic retry without idempotency or explicit policy.
- Late old-owner completion: reject by stale fence.

## Security and Governance Notes

- Policy must precede credential and connection acquisition for tool execution. This ADR does not replace `bif-bpfk.19`; it supplies the connection ownership model that task can enforce.
- Ownership rows do not grant MCP access. They only decide which pod may hold or resume a connection after a separate policy decision.
- Fences protect durable state, not remote side effects already emitted to an MCP server. Idempotency and ambiguity receipts are still required.
- Emergency MCP kill switches should invalidate local snapshots and prevent renewals or new claims for affected clients/tools.

## Consequences

Positive:

- No mandatory Redis or broker for launch.
- Existing Go MCP code can be adapted incrementally.
- Stateful MCP failure behavior becomes explicit and testable.
- OAuth callbacks do not depend on pod affinity.

Negative:

- Requires new Aurora authority rows and an internal owner-forwarding path.
- Requires operators to understand ambiguous completion receipts.
- Some mutating MCP tools must fail safe after pod loss until idempotency support exists.
- Lease tuning becomes part of the MCP launch SLO.

## Acceptance Criteria Mapping

- Sticky/fenced, broker, and restricted stateless designs compared: yes.
- OAuth callback routing covered: yes.
- Server sessions covered: yes.
- Pod loss covered: yes.
- Ambiguous completion covered: yes.
- Idempotent reconnect covered: yes.
- Kubernetes launch design selected without mandatory Redis: yes.
- Isolated fenced-ownership reconnect prototype with deterministic tests: yes.
