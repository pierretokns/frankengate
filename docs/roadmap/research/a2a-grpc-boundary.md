# A2A native gRPC boundary

FrankenGate supports A2A JSON-RPC and HTTP+JSON, with a separately registered
native A2A gRPC binding built on the official `a2a-go/v2` generated service.
The published Agent Card advertises gRPC only after the configured gRPC
listener is healthy and the metadata authenticator is installed. The proxy
mode is a separate HTTP/JSON edge feature and is not evidence of native gRPC
hosting.

This is an intentional, tested boundary rather than a compatibility claim:

- the official generated service is registered only through the explicit
  `RegisterA2AGRPCServer`/`NewA2AGRPCServer` APIs;
- a nil authenticator fails closed and caller-supplied tenant metadata is never
  trusted;
- bounded receive/send sizes and context deadlines apply at the gRPC server;
- the inbound card test still fails if the default card advertises `GRPC`
  before a healthy configured endpoint exists.

Native gRPC is eligible only when the pinned generated service, auth and
tenant middleware, deadline/cancellation limits, streaming semantics,
conformance fixtures, and healthy Agent Card advertisement are enabled
together. Deployments without that listener should use the advertised
HTTP+JSON binding.

The Agentgateway comparison does not remove this requirement. Its A2A module
is an HTTP proxy policy: it can route an upstream gRPC service through generic
gateway machinery, but it does not implement the normative hosted `A2AService`
itself. FrankenGate's hosted-service gap is tracked explicitly as Bead
`bif-86bq.16.3`; TCK gRPC coverage remains a release gate for deployments that
enable the binding, not something to silently claim for HTTP-only deployments.
