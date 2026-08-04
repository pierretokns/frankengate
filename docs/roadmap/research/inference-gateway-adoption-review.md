# inference-gateway adoption review

Reviewed 2026-08-04 against upstream `inference-gateway/inference-gateway` at
`75bd7b41f17426bd43fe3fc16db26107b81f24e0` (`v0.45.0`). The upstream project
is Apache-2.0 licensed. This is an architectural review, not a code import;
the current branch is the source of truth for what is still maintained.

## Adopt or reimplement

- **MCP tool selection by catalog, not prompt fan-out.** The upstream MCP
  middleware exposes a small set of meta-tools and resolves the selected tool
  against a cached catalog at execution time. Adopt the pattern for FrankenGate:
  bounded catalog lookup, tenant/request filters, and an explicit bypass for
  internal follow-up calls. Do not copy names or provider-specific middleware.
- **Explicit middleware bypass on recursive tool turns.** Upstream uses
  `X-MCP-Bypass` for follow-up requests so a tool loop does not rediscover and
  reinject the same tools. Our equivalent should be an internal typed context
  marker plus a wire header only at trust boundaries.
- **OpenTelemetry GenAI semantics.** Upstream wraps provider transports with
  `otelhttp` (commit `59b0a41`) and documents GenAI semantic conventions. Map
  this to our existing telemetry/OTel plugins, preserving request IDs,
  provider/model dimensions, stream lifecycle, and tool-call spans.
- **Operational toggles and health surfaces.** MCP enablement, bypass, health,
  and resource status are explicit configuration/endpoint concerns in upstream.
  Add equivalent readiness and per-route diagnostics to our day-2 contract,
  with fail-closed defaults for untrusted agent discovery.
- **OIDC as an edge concern.** The upstream examples show optional OIDC
  authentication and authorization. Reuse the separation of authentication
  from middleware policy, but keep FrankenGate governance, virtual keys, and
  tenant RLS as the source of truth.

## A2A-specific finding

The current `v0.45.0` tree does not contain the earlier A2A middleware/runtime.
The history shows a progression from a custom client to an ADK-backed client
(`34d8cf6`), service discovery and health/retry work (`9be30ff`, `1b49a06`,
`54033e8`), and finally removal of the A2A middleware and related components in
`a32c7e4` (PR #183). Historical implementation material was inspected at
`594573a5a1befe04098d5da9eb559873e9e454a6` and must be treated as reference
only, not as a maintained dependency.

Useful historical patterns to reimplement in our contracts:

1. capability discovery from an Agent Card before sending work;
2. bounded task polling and streaming event parsing;
3. retry classification for transient connection failures;
4. health status with an explicit degraded/down state; and
5. service discovery separated from request execution.

The removal is itself a warning: keep A2A as a protocol adapter behind stable
FrankenGate interfaces, with conformance tests and an admission policy, rather
than coupling the gateway core to a fast-moving client library.

## Do not copy

- historical A2A files or generated types without a license/provenance audit;
- global environment toggles as a replacement for tenant-scoped governance;
- prompt/tool injection behavior that bypasses our four-level MCP filtering;
- upstream provider-specific middleware when our fasthttp, plugin, and stream
  lifecycle contracts already provide the correct extension points.

## Recommended follow-up beads

- make the ingestion ledger feed model-card diff review and quarantine;
- add a small MCP selector/catalog adapter with recursion guards;
- add A2A broker task lifecycle and retry/health state machines;
- add OTel spans and metrics for card discovery, admission, task polling, and
  tool selection; and
- document readiness, replay, revocation, and rollback runbooks.
