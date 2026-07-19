# A2A, agent discovery, and skill marketplace fit

Status: architecture recommendation, 2026-07-18.

## Decision

FrankenGate should add A2A v1.x compatibility, but not as another inference hot-path protocol and not as a second independent marketplace. Implement an optional, separately scalable A2A broker behind the same signed catalog, tenant/purpose policy, credential broker, audit, privacy, budget, health, and kill-switch contracts already required for MCP and the skill marketplace.

The protocols solve different problems:

| Surface | Resource being discovered | Interaction | FrankenGate responsibility |
|---|---|---|---|
| MCP | Servers, tools, resources, prompts | An agent/model invokes a bounded capability | Govern connection, discovery, credentials, arguments, side effects and results |
| A2A | Remote autonomous agents and their advertised capabilities | One agent delegates and follows a stateful task | Govern agent identity, delegation, task lifecycle, callbacks, artifacts, budget and provenance |
| Procedural skill marketplace | Versioned instructions, validators and required grants | A user/agent installs or loads governed procedural memory | Govern provenance, review, distribution, installation, execution environment, evidence and promotion |

An A2A `AgentSkill` is a capability claim in an Agent Card. It is **not** a downloadable FrankenGate/Codex/Claude procedural skill and must never be stored or shown as though it were one.

The current stable A2A specification is v1.0.1. It defines Agent Cards, multiple protocol bindings, messages, stateful tasks, streaming/push updates, artifacts, authenticated extended cards and security-scheme declaration. It intentionally permits well-known URLs, direct configuration and curated registries as discovery strategies; the protocol does not make a discovered endpoint trustworthy or authorized.

## Placement

```text
Clients / local agents
  -> one FrankenGate origin and identity session
      -> MCP gateway -----------------------> approved tools/resources
      -> skill catalog ---------------------> immutable Git-reviewed skill revisions
      -> A2A broker (separate Deployment) --> approved remote agents
                |                                  |
                +-> PostgreSQL task/receipt state  +-> Agent Card / A2A task API
                +-> S3 artifact manifests
                +-> async job/lease protocol

All three discovery paths
  -> signed CatalogEntity snapshot
  -> tenant + principal + purpose + data-class policy
  -> trust/risk/health/cost ranking
  -> invocation/delegation reauthorization
  -> audit, privacy receipt and kill switch
```

The A2A broker belongs beside the Rust analytics/control plane because A2A tasks may be long-running, asynchronous, streaming, callback-driven and artifact-producing. It gets its own Deployment, service account, PostgreSQL role/pool, egress policy, HPA signals and disruption budget. Gateway pods may authenticate and admit an A2A request or return a task handle, but they do not supervise remote tasks or hold their streams.

No new mandatory AWS service is needed. The broker can reuse EKS, Aurora PostgreSQL, S3, KMS, Secrets Manager, ALB/WAF, ECR and OpenTelemetry/CloudWatch. PostgreSQL outbox/leases remain the default task substrate; do not add SQS, EventBridge or ElastiCache until measured load or delivery semantics require them.

## Unified catalog without type confusion

Use a common envelope with a typed payload:

```text
CatalogEntity
  id, kind, tenant_scope, owner, publisher, source, version, digest
  signature, license, SBOM, lifecycle, policy_epoch, risk_class
  capabilities, data_classes, regions, cost/latency/health evidence
  auth_schemes, endpoint_refs, reviewed_at, expires_at, kill_state

kind = MCP_SERVER | MCP_TOOL | A2A_AGENT | A2A_CAPABILITY | PROCEDURAL_SKILL
```

Keep the decisions separate:

1. **Visible:** may the principal know the entity exists?
2. **Discoverable:** may it appear for this query and purpose?
3. **Installable:** may this procedural skill/package be installed?
4. **Invocable:** may this MCP tool be called with these parameters?
5. **Delegable:** may this A2A agent receive this task, context and artifacts?

Search only already-authorized metadata. Semantic ranking cannot expand visibility or authority. Reauthorize the selected immutable digest at invocation/delegation time. A registry result, Agent Card signature, healthy endpoint or high evaluation score is evidence—not a grant.

## A2A gateway surface

### Ingest and discovery

- Fetch `/.well-known/agent-card.json` only through an SSRF-safe egress broker.
- Support direct operator registration first; add registry federation later.
- Validate schema/protocol version, HTTPS, declared interfaces, security schemes, capability IDs, endpoint origins and size limits.
- Verify Agent Card signatures when present, but bind trust to approved publisher/domain ownership and review policy.
- Fetch authenticated extended cards only with audience-bound credentials and never cache them into a broader visibility scope.
- Diff every card change. Endpoint, skill, auth, schema, capability, publisher or signature changes can quarantine the entry and require reapproval.

### Delegation

- Provide outbound `discover_agents`, `get_agent`, `delegate_task`, `get_task`, `cancel_task` and bounded event/artifact retrieval APIs.
- Use idempotency keys and map A2A task/context/message IDs to canonical FrankenGate receipts without rewriting the remote IDs.
- Broker short-lived audience/scope-bound credentials; never forward the user's browser or virtual-key bearer token.
- Apply provider/tool/agent budgets and concurrency before delegation and reconcile remote cost/usage when evidence is available.
- Treat remote messages, status text, artifacts, URLs and instructions as untrusted tainted observations.
- Require explicit approval/policy for consequential delegation, cross-region transfer, external communication, code execution or sensitive data.

### Inbound service

Expose FrankenGate-hosted agents through A2A only after outbound governance is proven. Generate Agent Cards from the canonical catalog; do not hand-author a second capability truth. Each advertised capability resolves to a versioned internal workflow and explicit MCP/skill/model grants. The inbound A2A identity is reauthorized exactly like any other principal and cannot inherit the publishing agent's authority.

## Security and privacy gates

The critical threats are:

- malicious Agent Card URLs, redirects, callback endpoints, artifact URLs and DNS rebinding;
- signed-but-malicious publishers, stolen signing keys, capability rug pulls and registry poisoning;
- confused-deputy delegation, bearer-token forwarding, scope amplification and agent identity spoofing;
- prompt/tool-result injection crossing from a remote agent into MCP, skills or model context;
- task replay, duplicate side effects, cancellation races, callback forgery and orphaned long-running work;
- hidden cross-tenant correlation through discovery queries, task IDs, timing, health, evaluation or marketplace analytics;
- sensitive prompts/files in task history, push notifications, artifacts, traces or remote retention systems;
- autonomous agent/skill selection creating an unreviewed supply-chain or policy escalation path.

Required controls include SSRF-safe fetch/callback proxies, HTTPS and optional mTLS, JWS verification plus publisher approval, OAuth 2.1/OIDC audience binding, per-task capability tokens, DLP/classification before delegation, artifact allowlists and malware scanning, tenant/purpose-scoped encryption and retention, replay/idempotency protection, signed receipts, egress controls, human approval for consequential actions, and immediate tenant/agent/capability kill switches.

## Delivery order

1. Extend the existing MCP/skill catalog envelope with typed `A2A_AGENT` and `A2A_CAPABILITY` records; preserve Git as procedural-skill promotion authority.
2. Add read-only ingestion, validation, diff, health and policy-first search for operator-approved Agent Cards.
3. Add an outbound A2A broker for a small allowlisted internal-agent cohort with task/cancel/artifact conformance and adversarial security tests.
4. Expose selected FrankenGate workflows through generated Agent Cards and inbound A2A only after identity/delegation isolation is proven.
5. Add curated registry federation and semantic agent discovery only after authorized recall, false-agent selection, privacy leakage, cost and task-success metrics are reliable.

Do not launch with public autonomous agent routing, automatic installation, automatic skill promotion, marketplace-wide semantic delegation or arbitrary remote-agent callbacks.

## Acceptance evidence

- A2A v1.0.1 protocol conformance for the selected HTTP+JSON, JSON-RPC or gRPC binding; do not claim all bindings from one implementation.
- Cross-tenant discovery and delegation tests fail before metadata, card, task, event or artifact exposure.
- Agent Card mutation, signing-key rotation/revocation, endpoint takeover, redirect/DNS rebinding and registry outage tests fail safely.
- Duplicate send, retry, timeout, cancellation, broker restart and remote orphan tests produce one bounded typed outcome and no duplicate side effect.
- Prompt-injection and tainted-artifact tests cannot invoke MCP tools, install skills, expand scopes or alter policy without a new authorization decision.
- A2A saturation or outage does not change inference gateway latency/error SLO beyond the declared budget.
- Dashboard language distinguishes remote agent capability claims from installable procedural skills.

## Primary sources

- [A2A v1.0.1 release](https://github.com/a2aproject/A2A/releases/tag/v1.0.1)
- [A2A specification](https://a2a-protocol.org/latest/specification/)
- [A2A agent discovery](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [Official MCP Registry](https://registry.modelcontextprotocol.io/)
- [FrankenGate MCP/tool/skill governance](../mcp-tool-skill-governance-and-research.md)
