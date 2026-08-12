# FrankenGate and Agentgateway A2A interoperability matrix

Compared against Agentgateway commit
`e9881bd182408b76eaa5aacc3d8c7199ec8a85a0` (2026-08-11). The comparison
covered `crates/agentgateway/src/a2a/mod.rs`, its 19 A2A unit tests, and the
`examples/traffic-a2a` proxy configuration.

## The product boundary

Agentgateway's A2A module is a transparent edge proxy. It classifies A2A
requests, forwards their bodies, rewrites upstream Agent Card URLs so clients
stay on the gateway, and extracts bounded telemetry from JSON responses. It
does not host an A2A task registry, implement task state transitions, or
provide the normative `A2AService` gRPC server.

FrankenGate's inbound surface is a hosted agent, and it now has an explicit
opt-in transparent proxy mode alongside it. The hosted surface owns task IDs,
task state, artifacts, subscriptions, push delivery, recovery, and model
execution; the proxy preserves upstream envelopes and only rewrites
gateway-owned URLs. Therefore hosted and proxy mode must not be compared as if
they had the same output contract.

## Behavior comparison

| Area | Agentgateway | FrankenGate | Compatibility decision |
| --- | --- | --- | --- |
| Agent Card discovery | Classifies both `/.well-known/agent.json` and `/.well-known/agent-card.json`. | Serves both paths and validates cards with bounded SSRF-safe discovery. | Match both paths. |
| Card URL rewriting | v0.3 top-level `url` becomes the gateway base; v1 `supportedInterfaces[*].url` keeps each upstream path/query under that base. Missing interface URLs are skipped. | Hosted cards publish gateway-owned interface URLs directly. | Port the exact rewrite semantics for a future transparent proxy; do not rewrite hosted cards after generation. |
| Request classification | JSON POST method is inspected without consuming the body; malformed/unsupported content is `unknown`. | Hosted HTTP handlers validate and execute supported methods. | Preserve the non-mutating classifier and unknown telemetry behavior at any proxy boundary. |
| Call response | Upstream body is preserved byte-for-byte; telemetry is derived only from complete JSON (`success`, `error`, or `unknown`). | Handler owns the response envelope and task state. | Hosted behavior remains authoritative; proxy mode must use the preserved-body inspector. |
| Streaming | Agentgateway safely inspects finite JSON bodies and skips telemetry for partial/invalid/non-JSON bodies. | FrankenGate emits ordered SSE lifecycle/artifact events with replay and durable journals. | FrankenGate is stronger for hosted streaming; port the safety rule to proxy inspection. |
| Task lifecycle | No task registry or hosted state machine in the A2A module. | Durable task state, subscriptions, cancellation, restart recovery, push outbox, and OTel lifecycle metrics. | Keep hosted lifecycle in FrankenGate; do not import proxy assumptions into it. |
| gRPC | A2A policy does not implement `A2AService`; generic gateway routing can proxy an upstream gRPC service. | Native hosted gRPC is a separate official-SDK adapter and remains health-gated; proxy mode is HTTP/JSON only unless a separate HTTP/2 policy is configured. | Do not infer native gRPC from proxy support. Advertise hosted gRPC only after its listener, auth, limits, streaming, and readiness gates are live. |
| Auth/token exchange | Shared Agentgateway traffic policies include backend OAuth, JWT assertion, token exchange, and cross-app-access examples. | FrankenGate has opt-in credential resolution, RFC 8693/7523 exchange, pass-through controls, audit, and fail-closed runtime seams. | Compare credential policy at the broker boundary; never copy proxy auth code into the hosted task handler. |

## Ported test intentions

`framework/modelcatalog/a2adiscovery/proxy_compat_test.go` ports the useful
Agentgateway cases into Go without copying Rust code:

- request method extraction and body preservation;
- original URL, deployment subpath, and forwarded-scheme handling;
- v0.3 and v1 card URL rewriting, including multiple interfaces, root paths,
  query strings, missing interface URLs, and malformed card shapes;
- success/error/unknown response projections;
- omission of telemetry for invalid JSON, non-JSON, partial, and oversized
  bodies.

The implementation lives in `proxy_compat.go` as bounded, body-preserving
helpers and is used by the explicit `A2AProxyHandler` route. The hosted handler
does not call these helpers because doing so would mutate a FrankenGate-owned
Agent Card or incorrectly replace a server task envelope.

## Breaking-signature audit

No existing FrankenGate hosted-agent signature was changed to imitate
Agentgateway. The meaningful differences are intentional:

1. FrankenGate's `A2AExecutionResolver` is an internal execution seam, not a
   wire API. Agentgateway has no equivalent because it does not execute tasks.
2. Fresh FrankenGate task IDs are server-generated and are not derived from a
   caller's `messageId`; explicit follow-up `taskId` values remain honored.
   This avoids conflating a message replay key with task identity.
3. FrankenGate's hosted response envelopes are generated from validated task
   state and artifacts. A transparent proxy must instead forward upstream
   bytes unchanged and limit itself to URL rewriting plus telemetry.
4. Agent Card URL rewriting must preserve each interface's path and query. A
   proxy that replaces every interface URL with one common base is a breaking
   client-routing change.

The comparison does not make proxy mode a substitute for hosted gRPC. The
native boundary remains documented in
`docs/roadmap/research/a2a-grpc-boundary.md`, including its independent
listener, metadata auth, cancellation/deadline, streaming, and card-health
gates.
