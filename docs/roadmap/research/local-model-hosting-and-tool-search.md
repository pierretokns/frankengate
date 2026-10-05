# Local model hosting and gateway tool search

## Decision

FrankenGate should remain the policy, routing, and MCP aggregation layer. A
local inference runner should be a separate upstream provider process. The
first supported CPU profile is a quantized GGUF model served by llama.cpp;
Ollama remains the easiest developer setup, and vLLM CPU is an optional Linux
throughput profile.

Unsloth is useful in the model lifecycle, but is not the runner we should
embed in FrankenGate. Unsloth Studio can run CPU-only inference and exposes
authenticated OpenAI- and Anthropic-compatible APIs backed by `llama-server`.
That makes it a good interactive workstation and fine-tuning/export workflow.
For a durable FrankenGate deployment, export the model to GGUF and run it in
llama.cpp (or Ollama), keeping authentication, quotas, MCP policy, and
observability in FrankenGate. Do not expose Unsloth Studio's server-side tools
on a shared network endpoint without an explicit security review.

## Tool discovery

The gateway now exposes an authorization-aware `frankengate_search_tools` MCP
tool. It searches the same filtered tool set used for normal injection and
returns full matching definitions, allowing an MCP host to defer large tool
schemas until they are needed. MCP itself does not standardize `tools/search`,
so the namespaced function is an explicit gateway extension.

The catalog is deterministic and bounded. Exact name matches rank above name
prefix/substring matches, which rank above description matches. Search is not
an authorization mechanism: invocation still goes through the existing
client, virtual-key, and request filters.

## MCP parity boundary

The core MCP manager has discovery hooks for upstream resources, resource
templates, and prompts, including connection acquisition and plugin-gate
integration. They are intentionally not preloaded into the global `/mcp`
server yet. A global background sync cannot prove the requesting tenant or VK,
and MCP resources/prompts have no equivalent of the current tool allow-list.
The next safe step is request/session-scoped discovery with explicit client
allow-lists, followed by list-changed notifications. Until then, exposing
unscoped resources would be a data-isolation regression.

## References

- [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Anthropic tool search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [Unsloth requirements](https://unsloth.ai/docs/get-started/beginner-start-here/unsloth-requirements)
- [Unsloth API inference endpoint](https://github.com/unslothai/unsloth/discussions/5285)
- [Unsloth repository](https://github.com/unslothai/unsloth)
