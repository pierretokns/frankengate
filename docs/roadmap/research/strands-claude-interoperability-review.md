# Strands and Claude Agent SDK interoperability review

Reviewed 2026-08-04 against the current official documentation and upstream
SDK repositories. The goal is an adapter contract for FrankenGate, not a
runtime dependency or a promise that every SDK feature is gateway-executable.

## Strands Agents

The Strands SDK exposes A2A both ways: `A2AAgent` wraps a remote Agent Card and
supports unary and raw protocol-event streaming, while its A2A server wraps a
local agent. Strands also treats remote A2A agents as nodes in deterministic
graphs. Python and TypeScript advertise A2A, MCP, streaming, lifecycle hooks,
graphs, workflows, and agents-as-tools as supported capabilities.

Sources:

- <https://strandsagents.com/docs/api/python/strands.agent.a2a_agent/>
- <https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/>
- <https://strandsagents.com/docs/user-guide/quickstart/overview/>
- <https://strandsagents.com/docs/user-guide/versioning-and-support/>

### Adopt in FrankenGate

1. Treat `A2AAgent`-style remote nodes as ordinary model-card candidates with
   an immutable card digest, protocol version, task ID, and delegated identity.
2. Preserve both result mode and raw event mode in the broker; never flatten
   task status/artifact events into text before audit and policy hooks run.
3. Represent graph/workflow edges as an orchestration concern above the broker.
   The gateway should enforce per-edge admission, budgets, timeouts, and
   cancellation rather than own a second workflow runtime.
4. Support authenticated card discovery and message transport through the
   existing HTTP client/plugin path. Strands documents a configurable client
   for both discovery and sending; this is the right boundary for OAuth,
   SigV4, tenant egress, and SSRF controls.

### Do not adopt wholesale

- Do not expose a model-driven `discover_agent` tool without applying the
  FrankenGate card admission and four-level MCP filtering rules.
- Do not infer public reachability from a server's bind address. A2A card URLs
  must be explicit externally visible URLs and pass endpoint/egress policy.
- Do not put graph state in request context; use a durable task/run manager
  keyed by task ID with bounded event history.

## Claude Agent SDK

The official Python SDK is a programmatic client around Claude Code. Its key
interoperability surfaces are asynchronous message streams, bidirectional
`ClaudeSDKClient` sessions, in-process SDK MCP servers, external MCP servers,
permission allow/deny controls, and lifecycle hooks. The SDK repository also
documents session forking and programmatic subagents as supported concepts.

Sources:

- <https://github.com/anthropics/claude-agent-sdk-python>
- <https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/types.py>
- <https://platform.claude.com/docs/en/managed-agents/events-and-streaming>
- <https://platform.claude.com/docs/en/managed-agents/sessions>

### Adopt in FrankenGate

- Map SDK session IDs, subagent IDs, tool-use IDs, hook event names, and
  `stop_reason`/cost fields into a common trace and audit envelope.
- Treat `allowed_tools`, `disallowed_tools`, `permission_mode`, and
  `can_use_tool` as an SDK-side policy layer. FrankenGate remains the outer
  tenant, budget, egress, secret, and tool-governance authority.
- Support MCP servers as registered capability sources, including in-process
  adapters, but normalize them into the same card/provenance model and never
  let a client-provided MCP config silently bypass server policy.
- Preserve streaming and cancellation semantics as first-class events. A
  proxy may redact or deny an event, but must not fabricate completion.
- Pin SDK/CLI compatibility at integration boundaries and expose a degraded
  mode when the CLI or MCP server is unavailable.

### Security and operations implications

The SDK can execute powerful local tools, including file and shell operations.
The gateway integration must therefore default to an explicit tool allowlist,
isolated working directory, network domain policy, secret redaction, and
operator-visible permission decisions. Hook ordering and concurrency must be
documented: hooks are policy callbacks, not a substitute for the gateway's
authoritative admission decision.

## Native FrankenGate contract

The smallest stable adapter surface is:

```text
discover(card_url, tenant, egress_policy) -> immutable card snapshot
admit(card_digest, required_capabilities, delegated_identity) -> decision
send(task_id, card_digest, message) -> task/event stream
execute_tool(tool_id, tenant, policy_epoch) -> redacted result
cancel(task_id, reason) -> terminal event
```

Strands, Claude Agent SDK, A2A, MCP, and future SDKs adapt to this contract.
The implementation remains provider-neutral and keeps remote discovery,
workflow orchestration, and SDK process management off the inference hot path.
