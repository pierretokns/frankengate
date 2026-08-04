# A2A ecosystem disposition

Reviewed 2026-08-04. Awesome lists are lead generators, not dependency
authority. Each candidate below was checked against a repository file or API
tree, an exact revision where available, license evidence, tests/security
surfaces, and fit with the existing Agent Model Card beads. No third-party
runtime is vendored by this review.

| Candidate | Pin / license evidence | Disposition | FrankenGate use |
| --- | --- | --- | --- |
| [a2aproject/a2a-go](https://github.com/a2aproject/a2a-go) | `v2.4.0`, `5736cc7c76905476840257b2c3b0f84a6fea8134`, Apache-2.0; schema/event tests and CI | Reference | Conformance fixtures and wire-shape review for broker/API beads `.9`, `.14` |
| [a2aproject/a2a-python](https://github.com/a2aproject/a2a-python) | Official SDK; pin through the A2A project release process | Reference | Cross-language interoperability fixtures, not a Go runtime dependency |
| [a2aproject/a2a-js](https://github.com/a2aproject/a2a-js) | Official SDK; release pin required before automation | Reference | Browser/Node client behavior for UI and API tests |
| [a2aproject/a2a-inspector](https://github.com/a2aproject/a2a-inspector) | Official debugging/tooling surface | Adopt as external test tool | Manual/operator debugging only; never production routing |
| [a2aproject/a2a-tck](https://github.com/a2aproject/a2a-tck) | Official conformance project | Adopt as external gate | Add to `.14` release gate when its version is pinned |
| [inference-gateway/inference-gateway](https://github.com/inference-gateway/inference-gateway) | `v0.45.0`, `75bd7b41f17426bd43fe3fc16db26107b81f24e0`, Apache-2.0 | Reimplement patterns | MCP catalog selection, OTel, health/retry; current tree removed prior A2A runtime |
| [strands-agents/harness-sdk](https://github.com/strands-agents/harness-sdk) | `mcp/v0.2.8`, `8e6b33f4b180df8e83adf4d6b9e4b23beccd9ceb`, Apache license file | Reference | MCP/A2A test ideas and lifecycle semantics; no SDK dependency |
| [ai-boost/awesome-a2a](https://github.com/ai-boost/awesome-a2a) | MIT license; list head is mutable | Lead generator | Mine links only; pin each downstream candidate |
| [BenjaminScottAwk/awesome-a2a](https://github.com/BenjaminScottAwk/awesome-a2a) | Mutable curated list; downstream license varies | Lead generator | Search index only; reject entries without primary evidence |
| [nMaroulis/awesome-a2a-libraries](https://github.com/nMaroulis/awesome-a2a-libraries) | Mutable curated list; downstream license varies | Lead generator | Search index only; map candidates to registry bead `.11` |
| [pab1it0/google-maps-a2a](https://github.com/pab1it0/google-maps-a2a) | `HEAD`, `b4f292b6879b...`, MIT; sample app | Reference | Bearer-auth/SSE sample fixture; no production code import |
| [a2aserver/a2a-go](https://github.com/a2aserver/a2a-go) | `HEAD`, `0bce0b32aee171fdece513b0e884d2a0e82bccda`; no checked-in license found | Reject | Provenance/license gate fails |
| `opspawn/a2a-x402-gateway` | GitHub repository resolution failed during review | Reject | Unverifiable source |
| `Atlaskos/workprotocol` | GitHub repository resolution failed during review | Reject | Unverifiable source |
| [aws-samples/sample-a2a-gateway](https://github.com/aws-samples/sample-a2a-gateway) | Pinned sample revision; license checked in | Reference | Gateway deployment and auth examples only |
| [microsoft/agent-framework](https://github.com/microsoft/agent-framework) | Pinned tree inspected; broad multi-language framework | Reference | Compare graph/task abstractions and tests; do not create second runtime |
| [FastA2A](https://github.com/vishalmysore/fast-a2a) | Community project; version/license must be pinned per release | Reference | Parser/client fixture only if current protocol tests remain green |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | Active framework; external dependency/license review required per version | Reference | Python adapter contract and structured-output fixtures |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Active framework; external dependency/license review required per version | Reference | Workflow graph semantics; FrankenGate keeps policy/task authority |
| [OpenAgents](https://github.com/openagents-org/openagents) | Community project; candidate metadata varies by repo | Reference/reject per pin | Inspect only when a concrete adapter need appears |
| [Protolink](https://github.com/jxom/protolink) | Community protocol bridge; pin/license required | Reference | Protocol translation ideas; no gateway runtime import |

## Cross-cutting decisions

1. **Adopt:** official schema/TCK/inspector artifacts as release evidence once
   pinned; use their fixtures to exercise our own broker and API.
2. **Reimplement:** catalog-based MCP selection, explicit recursion bypass,
   health/retry state, OTel propagation, and registry provenance in the native
   packages already published on this branch.
3. **Reference:** SDKs and sample agents for interoperability fixtures,
   authentication examples, and protocol edge cases.
4. **Reject:** unresolved repositories, mutable default-head dependencies,
   missing/ambiguous license evidence, and any project that would introduce a
   second gateway/control-plane authority.

## Mapping to remaining work

- `.6/.7/.10`: official SDK and inspector behavior informs API/UI/inbound card
  examples and event fixtures.
- `.11`: manifest pinning, license, source digest, and registry outage rules
  are implemented in the registry adapter; OpenAPI-to-MCP remains a follow-up.
- `.14/.20`: TCK/inspector, malformed-card, replay, SSRF, registry-poisoning,
  and recovery cases become release/conformance gates.
- `.15`: retain this disposition with exact pins and update it whenever an
  external artifact is promoted from reference to runtime dependency.
