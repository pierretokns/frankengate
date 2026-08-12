# A2A native gRPC boundary

FrankenGate currently supports A2A JSON-RPC and HTTP+JSON. Its published Agent
Card advertises only those bindings, and the HTTP transport has no native A2A
gRPC service endpoint.

This is an intentional, tested boundary rather than a compatibility claim:

- the repository does not contain the normative A2A protobuf service contract
  and generated Go stubs needed to define a stable gRPC API;
- advertising `GRPC` without that service would cause clients to select an
  endpoint that cannot accept the protocol;
- the inbound card test fails if the default card ever advertises `GRPC` before
  the service is implemented.

Native gRPC becomes eligible only after a separately reviewed change adds the
pinned A2A protobuf contract, generated stubs, auth and tenant middleware,
deadline/cancellation limits, streaming semantics, conformance fixtures, and
an Agent Card advertisement test. Until then, gRPC clients should use the
advertised HTTP+JSON binding.

The Agentgateway comparison does not remove this requirement. Its A2A module
is an HTTP proxy policy: it can route an upstream gRPC service through generic
gateway machinery, but it does not implement the normative hosted `A2AService`
itself. FrankenGate's hosted-service gap is tracked explicitly as Bead
`bif-86bq.16.3`; the current TCK gRPC skips are therefore honest exclusions,
not evidence that the hosted gRPC contract is complete.
