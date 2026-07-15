# Flywheel Gauntlet: Codebase Archaeology and Attachment Map

Status: pre-implementation evidence baseline

## Scope and deployment context

This report maps where a managed agent-evidence and skill-improvement plane can attach to Bifrost without becoming a dependency of inference. The intended launch is an internal Kubernetes deployment backed by Aurora PostgreSQL, with no mandatory Redis, shared filesystem, gossip layer, or cross-region control-plane availability requirement. The gateway is continuously used by developer agents, so a feedback-system incident must not impair request serving.

The proposed Flywheel remains asynchronous and proposal-only. This report does not authorize self-modification or production promotion.

## System identity

Bifrost is a Go, multi-module, high-throughput LLM and MCP gateway. Its defining substrate is the provider-isolated request and streaming data plane, not its current UI, log store, or plugin inventory. Any feedback feature that changes the availability or latency behavior of that data plane changes the identity of the project and requires explicit evidence.

## Request and evidence flow

```text
HTTP/SDK request
  -> transport middleware and HTTP plugin hook
  -> once-per-logical-request PreRequestHook
  -> per-provider-attempt PreLLMHook
  -> provider queue/key selection/provider I/O
  -> per-attempt PostLLMHook
  -> stream accumulation and logging
  -> transport response

Separate asynchronous path:
  privacy transform receipt
  -> bounded AgentEvidenceEnvelope emitter
  -> durable evidence ingestion
  -> disposable lexical/semantic indexes
  -> offline evaluation and skill proposal workers
  -> replay/shadow/canary evidence
  -> human-governed promotion
```

The asynchronous path must have bounded queues and a metadata-only/drop disposition. Provider work never waits for evidence persistence, indexing, reflection, evaluation, or skill proposal generation.

## Load-bearing source findings

### 1. Generic plugin errors fail open

`core/bifrost.go` records `PreLLMHook`, `PreRequestHook`, and `PostLLMHook` errors, logs warnings, and continues. `core/schemas/plugin.go` documents that plugin errors are not returned to callers. This is appropriate for observability and optional enrichers but not for authentication, entitlement, quota reservation, privacy eligibility, or invocation authorization.

The existing governance implementation is a plugin. Therefore enterprise reference-monitor functions cannot inherit the generic plugin failure contract. They need a non-optional pre-provider boundary or typed dispositions such as `deny`, `degrade_metadata_only`, and `continue` whose defaults are mechanically enforced.

### 2. Logical request and physical attempt are distinct

`PreRequestHook` runs once per top-level request, while `PreLLMHook` and `PostLLMHook` run for every fallback attempt. Evidence, quota, replay, and evaluation schemas must preserve both a logical request identifier and a physical attempt identifier. Otherwise fallbacks can be double-counted as independent user outcomes or incorrectly collapsed into one provider event.

### 3. Streaming is accumulated for post-processing

The framework streaming package reconstructs complete responses for post-hooks and logging. Adding replay, PII detection, evaluator, shadow, or skill-learning consumers to the same materialization multiplies retained memory and sensitive-copy risk. Evidence emission must use purpose-specific bounded capture, rolling metadata, or explicitly approved encrypted spill; it must not implicitly retain another full copy.

### 4. Logging already has sensitive-content gates, but raw fields remain part of the model

The logging plugin supports per-request and global content-logging controls and sanitizes some error paths. The log store still includes raw request, response, passthrough body, structured history, and content-summary surfaces. A Flywheel consumer cannot equate “logging disabled” with “no sensitive derived copy.” Every sink requires a privacy receipt and deletion lineage, including summaries, embeddings, judgments, proposals, replay fixtures, and promoted artifacts.

### 5. Mutable context is a useful join carrier but not durable truth

`BifrostContext` carries request, selected-key, governance, retry, fallback, tracing, and logging decisions. It is appropriate for propagating opaque join identifiers and privacy decisions within a request. It is not an authoritative event ledger: values are mutable, some writes are restricted by plugin scope, and the context dies with the request.

### 6. Pooled request objects are a tenant boundary

HTTP and core request/response objects are pooled and manually reset. New evidence, privacy, tenant, subject, skill, or tool fields added to pooled types require generated or reflective reset conformance. A stale field is a cross-tenant leak even if pool lifecycle debug tests pass.

### 7. MCP has stateful in-process ownership

MCP client lifecycle and OAuth coordination are currently process-local concerns. A shared catalog or grant snapshot does not make live MCP connections stateless. Evidence must distinguish gateway observation from tool outcome, and the deployment needs an explicit connection-ownership and ambiguous-completion model before MCP execution becomes feedback for skill promotion.

### 8. Persistence is split across modules

Config and log stores have separate migration code while enterprise evidence, privacy, governance, replay, and evaluation cross those boundaries. Flywheel tables and events need a namespaced migration owner, adjacent-version compatibility, an external migration job, and a restore/rebuild contract. Search indexes are derived; durable evidence and immutable revision manifests are authoritative.

## Approved attachment points

| Concern | Attachment | Failure policy |
|---|---|---|
| Authentication, entitlement, quota, privacy eligibility | Mandatory reference monitor before provider I/O | Deny on indeterminate state according to risk-classified freshness contract |
| Logical-request metadata | Once-per-request boundary | Continue only if a bounded metadata envelope can be emitted or explicitly dropped |
| Provider attempt and fallback | Attempt boundary | Best-effort evidence; never changes retry decision |
| Usage and terminal result | Post-attempt/finalization | Best-effort bounded event, reconciled asynchronously |
| Streaming content evidence | Purpose-specific capture manager | Metadata-only/drop at byte or time budget |
| Local compiler/tool/user outcome | Sandboxed endpoint collector | Independent of gateway availability |
| Skill evaluation and proposal | Offline worker | Quarantine on malformed or untrusted evidence |
| Promotion | Separate signed control-plane operation | Human approval at launch; rollback pointer required |

## Non-negotiable invariants for later gauntlet stages

1. Inference never waits for Flywheel ingestion, search, reflection, evaluation, or proposal generation.
2. Evaluators cannot change their own holdouts, rubrics, promotion thresholds, or rollback rules.
3. Raw or derived content cannot enter a new sink without a privacy receipt and deletion lineage.
4. Personal evidence is private by default; team and organization promotion is explicit and provenance-preserving.
5. Every observation identifies logical request, physical attempt, model/version, skill/version, tool/version, policy revision, privacy revision, and missingness.
6. Negative feedback is not causal attribution. Promotion requires counterfactual or controlled evidence appropriate to the risk class.
7. Every promoted skill is immutable, signed, reversible, and evaluated against frozen holdouts plus adversarial tests.
8. No individual employee productivity score, hidden manager search, or cross-user private recall is permitted.
9. Evidence backpressure degrades to bounded metadata or drops; it cannot retain gateway pools or streams.
10. An unavailable or corrupt Flywheel leaves the last approved skill and the gateway data plane operational.

## Questions carried into the adversarial and Brenner stages

- Which reference-monitor functions belong in core versus a mandatory typed extension interface?
- What evidence distinguishes skill failure, model failure, retrieval failure, tool failure, and environment failure?
- Which skill classes can ever auto-promote, and which require permanent human approval?
- How are holdouts made tamper-resistant when the same system proposes skill and evaluator changes?
- What is the smallest controlled experiment that attributes an outcome to a skill revision?
- How do deletion and consent propagate into summaries, embeddings, proposals, replay fixtures, and promoted rules?
- What fleet-wide feedback prevents a successful per-user adaptation from becoming a harmful organization default?
