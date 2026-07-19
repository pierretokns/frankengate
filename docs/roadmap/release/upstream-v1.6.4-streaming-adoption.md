# Upstream v1.6.4 streaming/protocol adoption record

The release audit tracks the upstream correctness train as an adaptation
matrix. Entries below are evidence targets; a green provider race suite is not
treated as a live-provider differential proof.

| Upstream commit | Local adaptation/evidence | Decision |
| --- | --- | --- |
| `f829b4155` | Pooled channel-message lifecycle/reset tests in core schemas and provider suites | Adopted |
| `9f6ce58b9` | Nil-safe trace lookup covered by tracing/plugin tests | Adopted |
| `cc54d9132` | Structured stream-error handling covered by streaming/provider tests | Adopted |
| `6b8f02286`, `3f626179a`, `d1e8d2f41` | Responses usage, finish-reason, and citation accumulation covered by OpenAI/streaming tests | Adopted |
| `bb72fd4d0` | Gemini pooled web-search reset covered by Gemini lifecycle tests | Adopted |
| `6058f796e` | Bedrock reasoning fallback covered by Bedrock request-conversion tests | Adopted |
| `9fa78c645` | Anthropic tool-id sanitization covered by Anthropic converter tests | Adopted |
| `e15c02c5`, `03ae614aa` | Responses non-message roles and redacted thinking covered by Anthropic/OpenAI response tests | Adopted |
| `53ad48ac5` | Server tool-search behavior remains behind MCP governance policy and is covered by MCP tests | Adapted |
| `8e5fc53fa` | Compact input serialization covered by request-shaping tests | Adopted |

The current local evidence is the complete provider race sweep and SDK
compatibility suite. Live upstream differential tests, cancellation fault
injection, and leak matrices remain separate acceptance gates.
