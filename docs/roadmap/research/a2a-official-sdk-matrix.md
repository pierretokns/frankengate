# Official A2A SDK And Conformance Matrix

Observed on 2026-08-04 from official `a2aproject` GitHub repositories. All repository licenses below were verified as Apache-2.0 from repository metadata and/or checked-in `LICENSE` files. The pinned commit is the default `main` branch head observed that day; release/tag information is recorded separately because several repositories have no GitHub release.

This matrix is implementation guidance for FrankenGate. It does not vendor SDK runtimes, generated protobufs, or TCK code.

## Repository Matrix

| Repository | Pinned main commit | Release or tag observed | License | Verified protocol/version/transports | Reusable wire or test patterns | FrankenGate disposition |
| --- | --- | --- | --- | --- | --- | --- |
| [`a2a-python`](https://github.com/a2aproject/a2a-python) | `cff67270d1da52bad96172c57580dad9b002aa11` | GitHub latest release `v1.1.2`, tag commit `3e6fa6a41d64f0581202df214a0515a0b0194832` | Apache-2.0 | README states A2A Protocol Specification `1.0` plus `0.3` compatibility mode. Client and server support are documented for `JSON-RPC`, `HTTP+JSON/REST`, and `gRPC`. | Source patterns worth reusing by behavior, not code: FastAPI/Starlette route mounting, task/artifact/event helper construction, streaming task lifecycle events, optional OpenTelemetry hooks. | High-value behavioral reference for HTTP route shape, streaming event ordering, and legacy version compatibility. Do not import Python runtime into FrankenGate. |
| [`a2a-js`](https://github.com/a2aproject/a2a-js) | `24f2aeecedbbfe7f252c15f69ce998dc6a9c7118` | GitHub latest release `v1.0.1`, tag commit `f5ca7d05945a69cbf3dcd357203d4ce99201494f` | Apache-2.0 | README states A2A Protocol Specification `v1.0.0`, one package with `JSON-RPC`, `HTTP+JSON/REST`, and Node-only `gRPC`; also opt-in `v0.3` compatibility. | Samples include minimal streaming agent, multi-transport, cancellable tasks, push notifications, authentication, signing/JWKS verification, extensions, and interceptors. `src/version_utils.ts` is useful for semantic version comparison behavior. | Use as wire compatibility reference for JavaScript clients and signing/auth sample flows. Do not vendor SDK or generated types. |
| [`a2a-java`](https://github.com/a2aproject/a2a-java) | `fb4411f7efc9ff1d6b96e4c7d16f8184f8c9b4f7` | GitHub latest release `v1.1.0.Final`, tag commit `6f65898ea6ed1495460ace5a176a48d3c7d00879` | Apache-2.0 | README and modules document client/server support over `JSON-RPC`, `HTTP+JSON/REST`, and `gRPC`. `AgentInterface` documents protocol versions such as `1.0` and `0.3`; `compat-0.3` modules provide a backward compatibility layer. | Useful patterns: Java reference server/client separation, `VersionRouter`, transport-specific modules, and TCK code-generation target behavior. | Use for cross-checking version routing and Java ecosystem interop. Do not add Maven dependencies until an explicit integration bead owns that work. |
| [`a2a-go`](https://github.com/a2aproject/a2a-go) | `dda32acd9e7602c0414ef05b580730cb83d10906` | GitHub latest release `v2.4.0`, tag commit `5736cc7c76905476840257b2c3b0f84a6fea8134` | Apache-2.0 | README states A2A `v1.0` compliance and client/server SDKs. `a2a.Version` is `1.0`. Transport constants cover `JSONRPC`, `HTTP+JSON`, and `GRPC`; `AgentInterface` records `protocolBinding`, `protocolVersion`, `url`, and optional tenant. | Most relevant to FrankenGate because it is Go: JSON field naming, agent card/interface structs, client factory version negotiation tests, and transport factory boundaries. | Primary shape reference for eventual Go implementation, but keep current artifact work independent. Do not import the SDK into Bifrost without a separate dependency decision. |
| [`a2a-dotnet`](https://github.com/a2aproject/a2a-dotnet) | `8fe65cfaa65a72b2d63bc9bef2e2d32fddc12a18` | No GitHub latest release observed. Latest tag observed: `v1.0.0-preview2`, tag commit `87fd44843dd16339cdb59c2ff547fe374ac46736` | Apache-2.0 | README states A2A `v1.0` support. It documents full `JSON-RPC` binding and `HTTP+JSON/REST` binding including SSE streaming. It also documents a backward-compatible `A2A.V0_3` package. No official `gRPC` support was verified in this repo. | Useful patterns: ASP.NET route mapping, well-known agent card endpoint, REST/SSE examples, and .NET client ergonomics. | Treat as REST/JSON-RPC/SSE interop reference. Do not infer gRPC behavior from this SDK. |
| [`a2a-rs`](https://github.com/a2aproject/a2a-rs) | `515f6eacf2b4b9b17bd3910e93ac47027afaaf90` | GitHub latest release `a2a-grpc-v0.3.2`; tags are crate-specific. Use the pinned main commit for matrix stability. | Apache-2.0 | README states an A2A v1 Rust workspace. Supported bindings table covers `JSON-RPC 2.0 over HTTP`, `HTTP+JSON/REST`, `gRPC`, and `SLIMRPC`; it also documents SSE streaming and protobuf interop. No `0.3` compatibility claim was verified. | Useful patterns: Axum/Tonic transport split, REST error envelope behavior, SSE serialization, protobuf JSON handling, and middleware/interceptor shape. | Use as a second systems-language reference. `SLIMRPC` is out of initial FrankenGate scope unless a future bead adds it. |
| [`a2a-samples`](https://github.com/a2aproject/a2a-samples) | `6603ba3f2c31a7ef33e70b9d8b5b5f8be42ac9a3` | No GitHub latest release observed. Latest tag observed: `itk-v.023-alpha`, tag commit `4f903c487da6080350ac45307a8f05f9c98c6d51` | Apache-2.0 | Samples span Python, Go, .NET, Java, and JS. Protocol and transport support is inherited from the relevant SDK/sample; this repository is not the protocol authority. | Useful patterns: small scenario payloads, agent card examples, multilang sample topology, and explicit prompt-injection/security warning for untrusted external AgentCards/messages/artifacts/task statuses. | Use as scenario inventory only. Fixtures may be hand-reduced from sample shapes with provenance; do not copy runnable sample agents. |
| [`a2a-inspector`](https://github.com/a2aproject/a2a-inspector) | `8098818f97c6b8554f1f83636508a9608842f5a0` | GitHub latest release `v0.1.0`, tag commit `0792c21ca592f5a760fcdbcf0ba24e94ccca45be` | Apache-2.0 | README describes a FastAPI plus TypeScript web tool that connects to an A2A server, fetches the Agent Card, runs basic spec compliance checks, supports live chat, and displays raw JSON-RPC 2.0 messages. | Useful patterns: human-facing debug transcript, agent-card validation UX, and raw request/response inspection. | Future developer-tool reference only. Not a normative conformance source and not part of server runtime. |
| [`a2a-tck`](https://github.com/a2aproject/a2a-tck) | `5996b79f9cefa6fc390980e383e358a66fb9e49e` | No GitHub latest release observed. Latest tag observed: `v0.2.5`, tag commit `047afc4a3222ede51a9131898d6a744edd8d172b`; additional observed tags include `1.0.0.alpha2`, `0.3.0.beta4`, and `0.3.0.beta3`. | Apache-2.0 | README states validation across `gRPC`, `JSON-RPC`, and `HTTP+JSON`. It fetches the Agent Card from `/.well-known/agent-card.json`, creates clients for declared `supportedInterfaces`, and supports `must`, `should`, and `may` test levels. Checked-in `specification/a2a.json` is the main schema source for the fixtures in this slice. | Highest-value conformance source: transport selector, Agent Card schema, task/artifact/event schemas, generated Gherkin-to-test structure, and compatibility reports. | Use as external TCK target and fixture provenance. Do not vendor the TCK or modify existing conformance harness in this bead. |

## Protocol Decisions For FrankenGate

- Treat Agent Card `supportedInterfaces` as the authoritative transport/version advertisement. Each interface includes `url`, `protocolBinding`, and `protocolVersion`; core protocol bindings observed in official sources are `JSONRPC`, `HTTP+JSON`, and `GRPC`.
- Treat A2A protocol `1.0` as the current target. Preserve explicit compatibility hooks for `0.3`, but do not assume every SDK implements legacy compatibility. Python, Java, JavaScript, and .NET document explicit `0.3` compatibility; Go tests version negotiation but the matrix does not claim full legacy mode; Rust did not have a verified `0.3` compatibility claim.
- Keep `SLIMRPC` out of the initial FrankenGate server scope. It is present in `a2a-rs`, but not a core binding used by the official TCK transport selector observed here.
- Use the official TCK schema and SDK samples as fixture provenance only. The checked-in fixtures under `tests/conformance/a2a/fixtures/` are minimal golden payloads with manifest SHA-256s and source attribution; they are not copied SDK runtimes.
- Agent Card, message, task, artifact, and event fixtures follow the v1 schema shape observed in `a2a-tck/specification/a2a.json`: protobuf-style objects with fields such as `text`, `raw`, `data`, `mediaType`, `TASK_STATE_*`, and `supportedInterfaces`.

## Fixture Inventory

The checked-in fixtures are validated by:

```bash
python3 tests/conformance/a2a/validatefixtures.py
```

The manifest records each fixture path, fixture SHA-256, source repository URL, exact source ref, source path, source license, source file SHA-256, and intended use.

| Fixture | Case | Primary provenance | Intended use |
| --- | --- | --- | --- |
| `tests/conformance/a2a/fixtures/agent-card.multi-transport.v1.json` | Agent Card | `a2a-tck/specification/a2a.json` at `5996b79f9cefa6fc390980e383e358a66fb9e49e` | Validate v1 Agent Card transport/version/security advertisement. |
| `tests/conformance/a2a/fixtures/task.completed-with-artifact.v1.json` | Task | `a2a-tck/specification/a2a.json` plus Python helper construction patterns | Validate stable task snapshots with history, status, and artifact output. |
| `tests/conformance/a2a/fixtures/stream.task-lifecycle-sse.v1.json` | Streaming/event | `a2a-tck/specification/a2a.json` plus Python helper construction patterns | Validate decoded SSE event ordering for task/status/artifact updates. |
| `tests/conformance/a2a/fixtures/artifact.file-data.v1.json` | Artifact | `a2a-tck/specification/a2a.json` plus Python artifact helper patterns | Validate artifact parts covering text, structured data, and base64 raw content. |
| `tests/conformance/a2a/fixtures/auth-error.bearer-required.v1.json` | Auth/error | `a2a-tck/docs/AUTHENTICATION_SETUP.md` and `a2a-tck/specification/a2a.json` | Validate security scheme advertisement, HTTP bearer challenge preservation, and A2A auth-required task status mapping. |
| `tests/conformance/a2a/fixtures/version-negotiation.supported-interfaces.v1.json` | Version negotiation | `a2a-go/a2aclient/factory_test.go`, `a2a-go/a2a/core.go`, and `a2a-go/a2a/agent.go` | Validate deterministic selection of the highest compatible declared interface. |

## Limitations

## 2026-08-12 verification note

The current FrankenGate implementation was exercised against the official
Python, Go, and JavaScript SDKs over authenticated HTTPS; all three completed
Agent Card/client smoke flows, and the JavaScript stream produced three events.
The pinned TCK's Agent Card schema still expects the older
`securityRequirements[].schemes.<name>.list` object, while the current official
Go/JS SDK JSON implementation and released proto-compatible shape use
`securityRequirements[].schemes.<name>` as an array. FrankenGate keeps the
SDK/proto-compatible array form and accepts both forms while decoding. This is
recorded as a pinned-TCK schema discrepancy, not a reason to regress the
public card wire contract.

The rebuilt authenticated HTTPS harness reported `139 passed, 5 failed, 121
skipped` across the official TCK's JSON-RPC and HTTP+JSON suites (`76/102`
JSON-RPC and `72/96` HTTP+JSON requirements; Agent Card `9/10`; gRPC remains
skipped). The skip set is now classified: 72 are unadvertised gRPC transport
cases, 20 are push cases without an injected delivery runtime, 18 are
fixture-isolation cases from the TCK reusing a deterministic input-required
message ID, 4 are negative streaming cases that require streaming to be
unsupported, and the remainder are optional extension/negative cases. Fresh
server task IDs are no longer derived from `messageId`, so the 18 lifecycle
skips are not a production idempotency behavior. Structured artifacts, direct Message responses, input-required
states, live subscriptions, and streaming-order scenarios now exercise the
production handler through an injected executor seam and pass where the TCK
executes them. The remaining five reported failures are bounded discrepancies:
the pinned card-schema mismatch above (CARD-STRUCT-001 and CARD-EXT-001), and
two transport instances of CORE-SEND-003 where FrankenGate correctly returns
JSON-RPC `-32005`/HTTP `415` with `CONTENT_TYPE_NOT_SUPPORTED` but the TCK
requirement omits an `expected_error` and its runner labels the expected error
as an operation failure. Several history/cancel/subscription cases are also
recorded as skipped by the TCK collector because its long-lived SUT reuses the
same `tck-input-required` task ID after a prior test has completed it; this is
a fixture-isolation assumption, not a production task-idempotency defect.
The focused lifecycle, streaming/order, transport, recovery, and SDK smoke
checks pass; gRPC remains excluded by the separately documented native-gRPC
boundary.

The inbound handler now exposes an application-owned `A2AExecutionResolver`
boundary. A resolver can return a direct Message or a persisted Task with
`TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_REJECTED`, or another validated
terminal state, plus text, raw file, URL file, and JSON data artifacts. Output
variants are size-bounded, oneof-validated, and serialized in the released
A2A shape. A nil resolver preserves the normal governed text-model path; no
TCK message-ID prefixes are interpreted by production code.

The implementation now includes inbound JSON-RPC and HTTP+JSON handlers,
ordered SSE streaming with bounded replay/restart recovery, durable push
configuration/outbox/payload stores, guarded secret-reference delivery, and an
explicit configured outbound sender path. Normal server bootstrap installs
durable push stores only when a deployment supplies a delivery implementation
and object store; the worker remains stopped until an egress/readiness gate
explicitly starts it. These runtime seams are covered by Go unit and race
tests in addition to the offline fixtures.

Agentgateway interoperability was separately audited at commit
`e9881bd182408b76eaa5aacc3d8c7199ec8a85a0`. Its A2A module is a transparent
proxy: the body-preserving request classifier, Agent Card URL rewrite, and
bounded response inspector do not host tasks or implement the normative
`A2AService` gRPC service. FrankenGate ports those useful intentions as
transport-neutral Go helpers and tests in
`framework/modelcatalog/a2adiscovery/proxy_compat.go` and
`proxy_compat_test.go`; hosted task responses remain FrankenGate-owned. The
native hosted gRPC gap is tracked as Bead `bif-86bq.16.3` and is not hidden by
the current TCK skips.

- The official TCK schema file observed in this slice did not expose JSON-RPC error schema definitions, so the auth/error fixture intentionally treats the JSON-RPC error code as an implementation envelope and only asserts preservation of the HTTP challenge plus A2A `TASK_STATE_AUTH_REQUIRED` task state.
- No source with unverified or ambiguous provenance was used for fixtures. All retained source repositories are Apache-2.0.
- This slice does not add UI, SDK dependencies, protobuf generation, or native
  gRPC execution wiring. Native hosted gRPC is an explicit follow-up, not an
  advertised transport; the production HTTP handlers and external TCK/SDK
  harnesses are kept separate from the vendored fixture set.
