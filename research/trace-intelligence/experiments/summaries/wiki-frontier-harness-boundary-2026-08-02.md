# Wiki frontier-harness boundary — 2026-08-02

## Finding

The local wiki server passes direct protocol tests and a JSON-RPC transport
parity probe, but the non-interactive Codex CLI cancels the custom MCP call
before dispatch. A temporary debug run observed the Codex client send
`initialize`, `notifications/initialized`, and `tools/list`, but no
`tools/call`; the CLI then reported `user cancelled MCP tool call`.

This is a harness approval/transport boundary, not a retrieval result. The
server responds correctly to the same initialize/list/call messages when
driven directly, and the MCP registration was removed after the probe.

Claude Code remains installed but unauthenticated (`Not logged in`), so no
Claude score is claimed either.

## Consequence

Do not report the failed Codex calls as zero-answer or retrieval failures. The
frontier-agent arm must use one of these explicitly recorded paths:

1. an interactive/approved Codex MCP session;
2. a Codex-subscription OpenAI-compatible loopback runner that implements the
   same `search/get_page/expand_links` tools in the agent loop; or
3. an authenticated Claude Code session with the same MCP server.

The direct retrieval and protocol arms remain valid and are already receipted.
The frontier-agent comparison is still open in [issue #131](https://github.com/pierretokns/frankengate/issues/131).
