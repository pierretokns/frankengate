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
