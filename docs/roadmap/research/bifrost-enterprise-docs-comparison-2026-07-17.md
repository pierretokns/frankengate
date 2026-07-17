# Bifrost enterprise documentation comparison (2026-07-17)

This is a current-source review of the upstream documentation, separate from the
implementation evidence in this fork. It is intentionally a decision record:
documented upstream behavior is not automatically accepted as the FrankenGate
contract.

## Findings

| Upstream surface | What the documentation actually promises | FrankenGate decision | Evidence / follow-up |
|---|---|---|---|
| Virtual keys | VKs authenticate through `x-bf-vk`, `Authorization`, `x-api-key`, and `x-goog-api-key`; they carry model/provider access and budgets. | Keep the compatible headers, but require durable fingerprints, rotation/revocation epochs, and cross-pod propagation before calling this enterprise-ready. | [Virtual Keys](https://docs.getbifrost.ai/features/governance/virtual-keys); `bif-kyy.6.*`, `bif-cks.*` |
| Budgets and limits | Customer → Team → VK → Provider Config hierarchy; independent budgets and rate limits are checked together. | Keep hierarchy. Add transactional reservations, controlled overdraft approval/alerts, and explicit 429 semantics as the stronger fork contract. | [Budget and Limits](https://docs.getbifrost.ai/features/governance/budget-and-limits); `bif-kyy.4.*`, `bif-kyy.6.10` |
| MCP governance | VK MCP configuration is deny-by-default; clients/tools must be explicitly allowed. | Keep deny-by-default and make ownership/authentication happen before connection or credential acquisition. | [MCP Tool Filtering](https://docs.getbifrost.ai/features/governance/mcp-tools); `bif-bpfk.19`, `bif-kyy.15.*` |
| Configuration and clustering | Schema lists enterprise guardrails/access profiles, cluster gossip/peer discovery, and PostgreSQL config storage. | Do not inherit gossip as an authority source. Aurora/Postgres remains durable truth; notifications are wake hints and consumers must reload before readiness. | [Schema Reference](https://docs.getbifrost.ai/deployment-guides/config-json/schema-reference); `bif-kyy.6.13`, `bif-kyy.6.12`, `bif-kyy.6.11` |
| Routing and failover | Routing rules can select providers and fallbacks centrally, including origin-based rules. | Keep deterministic routing/fallbacks, add canary/replay evidence and cross-region policy as separate explicit contracts. | [Claude for Office](https://docs.getbifrost.ai/cli-agents/claude-for-office); `bif-kyy.7.*` |
| Client integrations | Docs emphasize OpenAI-compatible clients, virtual keys, and observability across desktop/CLI agents. | Preserve drop-in compatibility and capture workstation/request attribution without making client-specific headers mandatory. | [Bifrost CLI](https://docs.getbifrost.ai/quickstart/cli/getting-started); `bif-kyy.14.2`, `bif-kyy.17.*` |
| Recent upstream release line | The current release page shows a v1.5.0 transport release and Helm chart v2.1.14, with dedicated provider-key APIs, wildcard/empty-array allow/deny conventions, deny-by-default VK/MCP configs, model aliases, Anthropic server tools/computer use, and Bedrock embeddings/images. | Treat these as an upstream change queue, not a blind merge. Prioritize semantic changes that affect compatibility (deny-by-default, key APIs, aliases) and provider correctness; separately test feature additions. | [Upstream releases](https://github.com/maximhq/bifrost/releases); `bif-kyy.14.11`, `bif-kyy.14.7`, `bif-kyy.14.2`, `bif-kyy.7.12` |

## What this changes in the roadmap

P0 is not nearly complete. The upstream review confirms that the remaining work
is concentrated in the enforcement path, not documentation polish:

1. Import and execute authority, reservations, admission, MCP ownership, and
   reload-consumer primitives in the actual gateway request path.
2. Prove three-pod behavior with durable Postgres state, notification wakeups,
   reload completion, and readiness fencing.
3. Add compatibility fixtures for upstream header, empty-array, key-ID, alias,
   provider capability, streaming, and error semantics.
4. Re-evaluate upstream release changes by behavior and tests, preserving our
   stronger durability, privacy, attribution, and controlled-overdraft rules.

This document does **not** claim that upstream clustering, budgets, or release
features solve the fork's open gaps. Each row still requires an executable oracle
in the linked bead.
