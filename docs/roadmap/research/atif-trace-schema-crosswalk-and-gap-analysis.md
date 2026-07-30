# ATIF trace-schema crosswalk and Frankengate loss analysis

**Date:** 2026-07-30
**Decision scope:** canonical trace evidence, portable trajectory interchange,
stored-trace evaluation, process mining, and reinforcement-learning projections
**Bottom line:** adopt ATIF v1.7 as a supported import/export format, not as
Frankengate's canonical authority or storage schema.

## Executive decision

ATIF v1.7 is the best *portable trajectory document* in this comparison. It
preserves ordered system/user/agent messages, structured tool proposals and
observations, model and tool configuration, multimodal text/images, token IDs,
completion log probabilities, context-copy markers, continuation references,
and recursively embedded subagent trajectories. It is materially richer than
AgentRx's role/content IR and much closer to training-ready data than an
OpenTelemetry span tree.

It is not a sufficient enterprise evidence model:

- an ATIF `Step` packages an LLM inference, zero or more proposed tool calls,
  zero or more returned observations, and possibly several underlying LLM calls
  into one sequential turn;
- it has one optional timestamp per step, not separate proposal,
  authorization, execution, response, retry, and state-transition clocks;
- its nested subagent representation is a tree plus file references, not a
  general event DAG with causal links, joins, concurrent branches, fallback
  edges, or cross-service propagation;
- neither its schema nor validator defines tenant, owner, team, classification,
  compartment, purpose, policy decision, or authorization-epoch semantics; and
- the RFC says that metrics may include RL reward, but the released v1.7
  `Metrics` model contains no `reward` field. A producer can only put reward in
  `metrics.extra`, where another implementation has no portable meaning.

Frankengate therefore needs one loss-aware canonical evidence envelope, with
purpose-built projections:

1. immutable source artifact plus source-format revision and content hash;
2. canonical typed event DAG plus normalized governance columns;
3. ATIF projection for interchange, visualization, SFT fixtures, and selected
   RL inputs;
4. OpenTelemetry/OpenInference projection for operational tracing;
5. AgentEvals projection for stored-trace assertions;
6. AgentRx projection for diagnosis parity only;
7. OCEL projection for process-mining experiments; and
8. RLDS/OpenRLHF projections for environment and policy optimization.

No lossy projection may replace the source artifact or become the input to a
different projection when the canonical events remain available.

## Reviewed, reproducible source pins

| Source | Reviewed version/revision | What was inspected |
|---|---|---|
| [Harbor ATIF](https://github.com/harbor-framework/harbor/tree/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc) | Harbor `v0.20.0`, commit `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`; ATIF v1.7 | RFC, Pydantic models, and validators |
| [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai/tree/434c91dcc34ed038e3048c07720ddfed2c6bddfc) | commit `434c91dcc34ed038e3048c07720ddfed2c6bddfc`, 2026-07-29; no release or schema URL yet | GenAI agent, model, memory, tool, and MCP spans |
| [OpenTelemetry core semantic conventions](https://github.com/open-telemetry/semantic-conventions/tree/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d) | `v1.43.0`, commit `89aae438b3b3b0a8dd33003c9d70592baf7dbd0d` | Core trace semantics and the GenAI repository move |
| [OpenInference semantic conventions](https://github.com/Arize-ai/openinference/tree/789d41974c08a9a13147977f28ef4142a07e2106) | Python semantic-conventions `v0.1.30`, commit `789d41974c08a9a13147977f28ef4142a07e2106` | Python constants, span kinds, message/tool structures |
| [AgentEvals](https://github.com/agentevals-dev/agentevals/tree/221febbe05927923242a5edc12e68a2b70fd5ae9) | `v0.9.7`, commit `221febbe05927923242a5edc12e68a2b70fd5ae9` | OTLP/Jaeger normalized span and ADK invocation projection |
| [AgentRx](https://github.com/microsoft/AgentRx/tree/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d) | untagged `v0.1.0`, commit `f228165bfec60a801fd5fedd9d8ffe0f9de0c69d` | Validated trajectory IR and loaders |
| [Trace Commons](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf) | dataset revision `112ebd4d03ce852b00e935d523107c3d0c9a65bf` | README and a raw Claude Code JSONL session |
| [Open Agent Traces](https://huggingface.co/datasets/juliensimon/open-agent-traces/tree/dff8ed6331f5abf9ec8ad825088eeb4caa6715a4) | dataset revision `dff8ed6331f5abf9ec8ad825088eeb4caa6715a4` | OCEL 2.0 output, normative workflow, manifest, Parquet schema |
| [CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d) | dataset revision `aa213b84ffb6690fc37ca15766d6ca174ec36d4d` | Verified Parquet manifest and one raw mini-SWE-agent artifact |
| [Gymnasium](https://github.com/Farama-Foundation/Gymnasium/tree/53bf3e9a884783eb72ad3fc8b15780914c97c3e1) | `v1.3.0`, commit `53bf3e9a884783eb72ad3fc8b15780914c97c3e1` | `Env.step` transition contract |
| [RLDS](https://github.com/google-research/rlds/tree/b35dac3a6b73396b0cb8773095999c4b5d70947c) | commit `b35dac3a6b73396b0cb8773095999c4b5d70947c` | canonical episode/step definition |
| [OpenRLHF](https://github.com/OpenRLHF/OpenRLHF/tree/ad1796e62b56bc9deae95542778336f88d24a3ed) | `v0.10.4`, commit `ad1796e62b56bc9deae95542778336f88d24a3ed` | token-level PPO `Experience` object |

The dedicated OpenTelemetry GenAI repository is currently pre-release: its
README still says `Schema URL: TODO`, and its agent/tool/memory surfaces are
marked Development. Frankengate must pin the reviewed revision in every
exporter and record the emitted convention revision on each export.

## ATIF v1.7, field by field

The source of truth for this section is the released
[`Trajectory`](https://github.com/harbor-framework/harbor/blob/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc/src/harbor/models/trajectories/trajectory.py#L12-L184),
[`Step`](https://github.com/harbor-framework/harbor/blob/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc/src/harbor/models/trajectories/step.py#L14-L139),
[`Metrics`](https://github.com/harbor-framework/harbor/blob/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc/src/harbor/models/trajectories/metrics.py#L8-L44),
and tool/observation models, not only the prose RFC.

### Root and agent

| ATIF field | What it preserves | Canonical interpretation | Irreducible gap or rule |
|---|---|---|---|
| `schema_version` | ATIF compatibility version | `source.format_revision` | Do not confuse it with Frankengate's canonical schema revision. |
| `session_id` | Optional logical run identity, shareable by parent, siblings, and continuations | `run_id` or `correlation_id` | It is explicitly not document-unique and is not enough to resolve causality. |
| `trajectory_id` | Per-document identity; required only for embedded children | `source_document_id` | It is not an event ID, distributed trace ID, or authorization scope. |
| `agent.name` | Harness/agent identity | actor name | Add stable internal actor ID separately. |
| `agent.version` | Harness/agent version | actor build revision | Preserve image/config digest too; a display version is not reproducibility. |
| `agent.model_name` | Default model | requested model default | Provider, endpoint, resolved model, key, region, and routing decision are absent. |
| `agent.tool_definitions` | OpenAI-shaped advertised tool definitions | tool-catalog snapshot | Add tool version/content hash and authorization filter result. |
| `agent.extra` | Producer-specific configuration | namespaced source attributes | Never grant query, RLS, or security meaning to an unregistered `extra` key. |
| `steps` | Complete ordered interaction turns | source-order projection | A sequence cannot encode general concurrency or multi-parent causality. |
| `notes` | Human explanation or discrepancy notes | import note | Not machine-enforceable; do not use for loss or policy facts. |
| `final_metrics` | Aggregate prompt/completion/cache tokens, cost, step count | derived aggregate | Retain component events because aggregate attribution is not reversible. |
| `continued_trajectory_ref` | Path to a continuation file | `continues` edge candidate | Resolve, hash, authorize, and validate target; a path string is not provenance. |
| `subagent_trajectories` | Complete nested child ATIF documents | delegated-run artifacts | Represents containment, not arbitrary joins, peer handoffs, or cross-service links. |
| `extra` | Root extension bag | quarantined namespaced attributes | Useful for fidelity, insufficient for interoperable enterprise semantics. |

ATIF's validator correctly distinguishes run-scoped `session_id` from
document-scoped `trajectory_id`, requires embedded child IDs to be unique, and
validates same-step tool-call references. That avoids several common importer
bugs. It does not validate a continuation target, a referenced external child,
or a whole-workflow DAG.

### Step

| ATIF field | What it preserves | Canonical interpretation | Irreducible gap or rule |
|---|---|---|---|
| `step_id` | Sequential ordinal starting at one | source sequence number | Preserve separately from event order; parallel children cannot share this ordering safely. |
| `timestamp` | Optional ISO-8601 point timestamp | source event time | No duration, monotonic time, clock domain, start/end, or separate tool/model clocks. |
| `source` | `system`, `user`, or `agent` | actor class | No tool, environment, policy engine, evaluator, or memory actor class. |
| `model_name` | Step-level model override | requested model | Resolved provider model and fallback choice remain absent. |
| `reasoning_effort` | Requested or assigned qualitative/numeric effort | model request parameter | It is not observed reasoning quality or a reward. |
| `message` | Text or text/image parts | conversation message payload | ATIF v1.7 supports text and referenced images, not general audio, video, file, blob, or provider-native parts. |
| `reasoning_content` | Explicitly exposed reasoning text | sensitive model output artifact | Store only under policy; absence must not be treated as “no reasoning.” |
| `tool_calls` | Structured model-issued tool names, IDs, and argument objects | `tool.proposed` events | A call is a proposal. The field does not prove authorization, dispatch, start, completion, or side effect. |
| `observation` | Results correlated to same-step calls, non-tool actions, or system events | result/observation candidates | The model has no required status, start/end, executor, state diff, or error type. |
| `metrics` | Per-step LLM token counts, cost, IDs, and log probabilities | model-call metrics | If `llm_call_count > 1`, the metrics are aggregated and per-call attribution is explicitly unavailable. |
| `is_copied_context` | Context duplicated across continuation/compression boundaries | provenance edge and SFT exclusion | Good training-safety signal; add source step/event ID and compaction artifact ID. |
| `llm_call_count` | Zero, one, multiple, or unknown underlying calls | capture-fidelity signal | Count does not reconstruct hidden calls. A count above one must create an explicit loss item. |
| `extra` | Producer-specific step metadata | namespaced source attributes | Retry, fallback, policy, and environment facts in `extra` are not interoperable. |

ATIF deliberately allows a complete agent turn to contain multiple parallel
tool calls and their results. The same-step ID check is useful, but it prevents
representing a result that arrives in a later step without producer-specific
workarounds. It also collapses proposed and executed actions unless the importer
retains separate native events.

### Tool, observation, content, and metrics

| ATIF structure | First-class fields | What is still missing |
|---|---|---|
| `ToolCall` | `tool_call_id`, `function_name`, object `arguments`, `extra` | proposal/execution distinction, tool instance/version digest, authorization, executor, status, clocks, attempt, idempotency key, side-effect class |
| `Observation` | required array of results | observation-level timestamp, environment identity, state version, checkpoint/diff, global status |
| `ObservationResult` | optional `source_call_id`, content, subagent references, `extra` | required outcome/status, error type, latency, partial/cancelled state, output hash, redaction lineage |
| `SubagentTrajectoryRef` | `trajectory_id`, informational `session_id`, external `trajectory_path`, `extra` | delegation ID, causal parent event, join/completion edge, authority transfer, child policy scope |
| `ContentPart` | `text`; or image MIME plus path/URL | inline blob digest, audio/video/file/provider parts, artifact authority, retention and deletion lineage |
| `Metrics` | prompt/completion/cache counts, cost, prompt/completion token IDs, completion `logprobs`, `extra` | tokenizer ID/revision, prompt logprobs, behavior/reference policy identity, action mask, reward, reward components, value, return, advantage, termination/truncation |

The released model mismatch matters. The
[`RFC` describes `metrics` as including reward](https://github.com/harbor-framework/harbor/blob/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc/rfcs/0001-trajectory-format.md#L130-L136),
but the
[`Metrics` class has no reward field](https://github.com/harbor-framework/harbor/blob/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc/src/harbor/models/trajectories/metrics.py#L8-L44).
Frankengate's adapter must test the executable model and emit
`atif.reward_in_extra` in its loss receipt when encountered; it must not
silently promote an arbitrary `extra.reward` to trusted ground truth.

## Capability and information-loss matrices

Legend:

- **F** — first-class and typed;
- **B** — supplied by the base container (for example, OTel span structure), but
  not specialized by the compared GenAI schema;
- **N** — present only in some native producers or dataset rows;
- **X** — extension bag, metadata, or a derivation rather than portable semantics;
- **P** — retained only in a downstream projection;
- **—** — absent or discarded.

### Portable, observability, and evaluation representations

| Capability | ATIF v1.7 | OTel GenAI + base trace | OpenInference + OTel | AgentEvals ADK projection | AgentRx IR |
|---|---:|---:|---:|---:|---:|
| Run/session identity | F | F | F | P | F |
| Ordered messages | F | F, content opt-in | F | P | F as strings |
| Per-operation start/end/duration | timestamp only | B | B | retained in normalized spans, lost from invocation | — |
| Parent/child causality | subagent tree only | B | B plus graph-node parent | tree while loading, lost from invocation | — |
| Span/event links and many-parent joins | — | B | B | — | — |
| Continuation/context-copy marker | F | compacted/previous-response attributes | X | — | — |
| Explicit subagent artifact | F | agent/workflow spans | agent span kind | flattened invocation | — |
| Retry/fallback/routing semantics | X | B/X | B/X | — | — |
| Tool proposal | F | F in model output messages | F in LLM messages | P | string content |
| Tool authorization decision | — | — | — | — | — |
| Tool execution operation | folded into observation | F `execute_tool` span | F `TOOL` span | P | string content |
| Tool result correlation | F, same step | call ID recommended | call ID attributes | P, may synthesize ID | string content |
| Tool status/error/timing | X | B/F | B/X | timing only before projection | — |
| LLM provider/model/request params | partial | F | F | mostly discarded | string content |
| Token counts/cost | F | token counts; no standard cost in reviewed span | F | discarded from invocation | — |
| Token IDs/completion logprobs | F | — | — | — | — |
| Retrieval documents | X | retrieval/data-source spans, content varies | F | — | string content |
| Memory operation | X | F operation/span, record content opt-in | generic span only | — | — |
| Evaluation event/score | X | evaluation event | evaluator span kind | result is separate | diagnosis output separate |
| Reward/termination/environment state | X/— | — | — | — | — |
| User identity | X | generic/custom | F `user.id` | — | — |
| Tenant/team/classification/purpose | X | custom | metadata only | — | — |
| Authorization epoch/policy decision | — | custom | metadata only | — | — |
| Immutable source provenance/loss receipt | — | resource/scope partial | metadata partial | — | — |

OpenTelemetry is the best transport for distributed operational causality. Its
current convention separately models agent/workflow invocation, planning,
retrieval, memory operations, and
[`execute_tool` spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/434c91dcc34ed038e3048c07720ddfed2c6bddfc/docs/gen-ai/gen-ai-spans.md#L831-L920).
The model's tool proposal can be retained in `gen_ai.output.messages`, while an
execution receives its own timed span and `error.type`. That is more faithful
than ATIF for latency and failure localization. Tool arguments/results remain
opt-in because they may be sensitive, and call ID is only Recommended; a valid
OTel trace can therefore still be inadequate for semantic replay.

MCP conventions additionally define JSON-RPC IDs, MCP session IDs, error
mapping, transport details, and W3C context propagation. They explicitly note
that MCP and HTTP contexts are independent and use a parent plus span link to
represent both. None of this establishes whether Frankengate authorized the
tool for a user or under which policy epoch.

OpenInference adds useful AI span kinds (`AGENT`, `CHAIN`, `LLM`, `TOOL`,
`RETRIEVER`, `EMBEDDING`, `RERANKER`, `GUARDRAIL`, `EVALUATOR`, `PROMPT`),
session/user IDs, prompt identity, graph-node identity, rich LLM messages,
retrieval documents, and tool call structures. Its
[`SpanAttributes`](https://github.com/Arize-ai/openinference/blob/789d41974c08a9a13147977f28ef4142a07e2106/python/openinference-semantic-conventions/src/openinference/semconv/trace/__init__.py#L5-L269)
are still attributes on an OTel trace, not an enterprise authorization model.

AgentEvals should be treated as an intentional evaluation projection. Its
normalized
[`Span`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/loader/base.py#L10-L41)
keeps trace ID, span ID, one parent, operation, start, duration, tags, and
children. It has no fields for OTel links, events, resource, instrumentation
scope, status, or status description. Its GenAI converter then emits only ADK
invocations with user content, final response, tool uses, and tool responses.
The converter may fall back to the span ID or `unknown` when a tool-call ID is
missing and drops that placeholder from the projected call ID. This is useful
for deterministic assertions, but it is not lossless evidence.

AgentRx is even narrower by design: its validated IR is
`trajectory_id`, `instruction`, and ordered steps/substeps containing only
`index`, `sub_index`, `role`, and string `content`. It is a suitable stable
input to invariants and a failure judge, not a trace archive.

### Public data and RL representations

| Capability | Trace Commons raw | Open Agent Traces / OCEL | CodeTraceBench raw + manifest | Gymnasium / RLDS | OpenRLHF `Experience` |
|---|---:|---:|---:|---:|---:|
| Real execution payloads | F, donated | —, synthetic | F | N by environment | generated token tensors |
| Cross-harness common schema | — | F | manifest only | transition/episode only | policy batch only |
| Ordered events | N | F sequence and time | F messages/stages | F episode steps | F token sequence |
| General causal graph | N by harness | F event-object many-to-many | — | — | — |
| Branches/parallel work | N, e.g. native parent IDs | F workflow pattern/relationships | — | extension | — |
| Retry/routing/fallback | N | F event types for retry/routing | implicit in messages | environment metadata | truncated only |
| Tool proposal/execution/result | N by harness | separate called/returned objects/events | usually embedded command/action and observation | action/observation | — |
| Environment state transition | command output/files only | task/tool object attributes | messages, config, final patch/artifacts | F observation/action/reward/terminal | — |
| Reward/outcome | weak/absent | conformant/deviation synthetic labels | solved plus step/stage labels | F | F reward/score |
| Human decisive-step labels | — | injected labels | F incorrect/unuseful | — | — |
| Policy logprobs/value/returns/advantage | — | — | provider response may contain usage only | reward/discount, not language policy | F |
| Governance/authorization evidence | — | — | — | — | — |
| Raw provenance and redistributable source | raw native files | generated fixtures and model | raw artifact paths plus annotations | environment-dependent | in-memory training object |

Trace Commons intentionally keeps
[`sessions/` as raw, native source files](https://huggingface.co/datasets/trace-commons/agent-traces/blob/112ebd4d03ce852b00e935d523107c3d0c9a65bf/README.md).
The inspected Claude Code fixture contains native `uuid`, `parentUuid`,
`isSidechain`, timestamps, queue operations, attachments, tool-use IDs, hook
events, stdout/stderr, exit codes, working directory, and version. That can
preserve branch and execution facts that ATIF loses. Those facts are
harness-specific, and the normalized Parquet row must not replace the native
JSONL.

Open Agent Traces is useful precisely because OCEL 2.0 is object-centric rather
than span-tree-centric. Its pinned incident-response file defines separate
objects for run, agent, agent invocation, tool call, LLM call, message, and task;
events relate to multiple objects with qualifiers. It also includes explicit
`routing_decided`, `retry_started`, `error_occurred`, `tool_called`, and
`tool_returned` event types and a normative workflow graph. This is excellent
for known-anomaly process-mining controls. It is generated data, not evidence
that a real model, tool, user, or policy decision occurred.

CodeTraceBench's verified manifest is an annotation index, not a canonical
trajectory. Its nested schema retains trajectory/task/harness/model identity,
solved status, stages, incorrect/unuseful step IDs, and optional action and
observation references. The inspected raw mini-SWE-agent artifact additionally
contains system/user/assistant messages with timestamps, provider response
metadata, harness and model configuration, Docker environment, final
submission, cost, and API-call count. Commands and observations remain encoded
in the harness conversation rather than portable proposal/authorization/tool
events. This makes it valuable for diagnosis labels, not for validating
Frankengate's governance or distributed timing.

Gymnasium's
[`Env.step`](https://github.com/Farama-Foundation/Gymnasium/blob/53bf3e9a884783eb72ad3fc8b15780914c97c3e1/gymnasium/core.py#L74-L113)
returns next observation, reward, `terminated`, `truncated`, and an untyped
`info` bag. RLDS makes the stored episode more explicit with `is_first`,
`is_last`, `is_terminal`, observation, action, reward, discount, and metadata.
Those are the missing environment-transition semantics in ATIF, but neither
format understands LLM messages, tool authorization, distributed spans, or RLS.

OpenRLHF's released
[`Experience`](https://github.com/OpenRLHF/OpenRLHF/blob/ad1796e62b56bc9deae95542778336f88d24a3ed/openrlhf/trainer/ppo_utils/experience.py#L28-L69)
is a training batch: prompt+response token IDs, attention/action masks,
current/reference/rollout policy log probabilities, values, returns,
advantages, KL, reward, score, truncation, lengths, and logging metadata.
ATIF can supply prompt/completion token IDs and completion log probabilities,
but not enough provenance to reconstruct this object safely. Token IDs without
tokenizer identity, behavior policy revision, sampling parameters, and action
mask are not a reproducible rollout.

### What the public Hugging Face corpora still do not provide

No reviewed public corpus contains all of the evidence needed for
Frankengate's enterprise questions. In particular, none combines:

- a complete OTel/OpenInference distributed graph with model, tool, MCP,
  routing, retry, fallback, and delegation lifecycles;
- native environment state, checkpoints, side effects, and deterministic replay
  boundaries that distinguish an agent failure from an environment failure;
- repeated attempts by stable, consented users on comparable real enterprise
  tasks, including the interventions or external help received between
  attempts;
- validated task, skill, friction, outcome, and decisive-step labels;
- token-, policy-, and reward-level rollout provenance sufficient for RL or
  embedding-model training; and
- tenant/team ownership, classification, compartments, purpose, policy
  revision, authorization decision, authorization epoch, retention, and
  deletion lineage.

The corpora are complementary, not interchangeable: Trace Commons contributes
real native harness artifacts; Open Agent Traces contributes synthetic
many-to-many process structure; CodeTraceBench contributes coding outcomes and
step-level error annotations; Gymnasium/RLDS contributes environment-transition
semantics; and OpenRLHF contributes policy-optimization tensors. Combining
their *concepts* can test the canonical model, but joining their rows cannot
manufacture missing identity, causality, governance, or intervention evidence.

The research program therefore needs two additional data sources: controlled
synthetic fixtures in which every event and intervention is known, and
governed first-party Frankengate capture in which identity and authority are
observed at the enforcement point. Public data can validate import breadth and
algorithmic hypotheses; it cannot validate enterprise authorization or prove
causal claims about employee learning.

## The canonical Frankengate evidence envelope

The smallest architecture that answers enterprise questions is not one
universal JSON document. It is one authoritative event relation plus immutable
payload artifacts and derived projections.

### Required event identity and causality

Every event requires:

```text
canonical_schema_revision
event_id
event_type
trace_id
run_id
session_id?
conversation_id?
turn_id?
attempt_id?
parent_event_id?
caused_by_event_id?
linked_event_ids[]
source_sequence?
started_at
ended_at?
observed_at
ingested_at
```

`parent_event_id` defines ordinary nesting. `caused_by_event_id` distinguishes
semantic causality from containment. `linked_event_ids` preserves joins,
transport contexts, cross-trace handoffs, and other non-tree relationships.
Retries and fallbacks receive distinct `attempt_id`s; they are never inferred
only from repeated text.

### Required typed lifecycle

The initial event vocabulary should be deliberately small:

```text
run.started                 run.completed                run.failed
conversation.message
model.requested             model.completed              model.failed
tool.proposed               tool.authorization.decided
tool.started                tool.completed               tool.failed
delegation.started          delegation.completed         delegation.failed
routing.decided             retry.started                fallback.selected
environment.observed        environment.transitioned     environment.checkpointed
memory.read                 memory.proposed               memory.approved
memory.written              memory.rejected
evaluation.recorded         outcome.recorded
```

Provider-native events are retained in the source artifact and namespaced
payload, but are not allowed to expand this vocabulary without a schema review.
The typed lifecycle is what makes questions such as “the model proposed a
forbidden tool but governance blocked it” distinguishable from “the tool ran
and returned an error.”

### Required actor, runtime, and environment data

Each event can reference:

```text
actor_type, actor_id, actor_version
harness_name, harness_version, config_digest, image_digest
provider, endpoint_id, region
requested_model, resolved_model, model_revision
tool_id, tool_version, tool_definition_digest, tool_call_id, idempotency_key?
environment_id, environment_revision
state_before_ref?, state_after_ref?, state_diff_ref?, checkpoint_ref?
status, error_type, error_code, terminal?, truncated?
reward_total?, reward_components?, reward_function_id?, evaluator_revision?
```

Large messages, images, source snapshots, patches, command output, provider
responses, token arrays, and state checkpoints live in immutable artifacts.
Events keep content hashes and authorized references, not arbitrarily large
payloads in request context.

### Required authority and RLS data

These fields must be normalized columns, not only JSONB:

```text
tenant_id
owner_user_id
team_id?
visibility_scope_type
visibility_scope_id
classification_level
compartment_ids[]
purpose
authn_subject_id
credential_id?
authorization_decision_id?
policy_id?
policy_revision?
authorization_epoch_ref
retention_policy_id
consent_basis?
```

An authorization event additionally records requested scopes, evaluated
resource, allow/deny/error, reason code, and policy inputs by content-hashed
reference. Never store the Bifrost/Frankengate token itself.

Every derived trace summary, cluster, memory, suggested skill, eval candidate,
embedding, and aggregate inherits the *intersection* of its source authority.
The materialization records all source event IDs and authorization epochs.
Deletion, reclassification, team changes, and epoch invalidation must make the
derivation ineligible until it is recomputed. ATIF `extra`, OpenInference
`metadata`, OTel baggage, and RLDS `metadata` are not substitutes for this
rule.

### Required provenance and fidelity

Each imported or derived record needs:

```text
source_format
source_revision
source_artifact_uri
source_content_hash
adapter_name
adapter_revision
capture_mode: observed | reconstructed | inferred | generated
redaction_revision?
derived_from_event_ids[]
loss_receipt_id
```

A loss receipt is a queryable object, not a log line. It contains counts and
identifiers for fields/events:

- preserved exactly;
- normalized without semantic loss;
- reconstructed deterministically;
- inferred probabilistically;
- aggregated;
- redacted;
- unsupported; or
- dropped.

This is essential when Exgentic-style chat spans reconstruct tool calls from
messages, AgentEvals supplies placeholder IDs, AgentRx stringifies tool
structure, or ATIF declares `llm_call_count > 1`.

## Projection contracts

### Canonical to ATIF

- Create one ATIF step per model inference whenever event boundaries exist.
- Emit `tool_calls` from `tool.proposed`, never merely from `tool.started`.
- Attach an observation only when a correlated result exists.
- Put execution status/timing in a registered Frankengate `extra` profile, but
  mark those fields as non-portable in the loss receipt.
- Export child trajectories for true delegation; do not model a provider
  fallback as a subagent.
- Set `is_copied_context` and retain the original event ID in the registered
  extension profile.
- If multiple model calls must be aggregated, set `llm_call_count` and record
  every hidden call ID in the loss receipt.
- Never export governance policy inputs, raw credentials, or classified
  content merely because ATIF permits `extra`.

### Canonical to OpenTelemetry/OpenInference

- Use OTel parent/child structure for containment and span links for joins,
  transport contexts, and cross-trace handoffs.
- Use separate model, agent/workflow, memory, retrieval, and tool spans.
- Preserve proposed calls in model output messages and execution in
  `execute_tool`; correlate with call ID.
- Record the exact dedicated GenAI convention commit because it has no stable
  schema URL.
- Emit low-cardinality Frankengate authority references only when the collector
  has equal or stronger authorization. Keep classified content in governed
  artifact storage.
- Do not assume an OTel collector preserves structured `AnyValue`, links,
  events, resources, and scopes until the round-trip conformance test proves it.

### Canonical to AgentEvals

- Generate a purpose-built OTLP/Jaeger fixture from canonical events.
- Include only the conversation turn and tool lifecycle under evaluation.
- Keep exact, in-order, any-order, and semantic response metrics as separate
  evaluator results.
- Join scores back by immutable canonical event IDs.
- Do not reuse AgentEvals' normalized `Span` or ADK `Invocation` as an importer
  for any other subsystem.

### Canonical to AgentRx

- Serialize a deterministic, versioned role/content view.
- Preserve canonical event IDs in a sidecar because the IR cannot hold them.
- Compare AgentRx diagnosis against invariant-only and judge-only ablations.
- Never infer that AgentRx's “critical step” is the earliest causal failure
  without evidence from the richer event DAG.

### Canonical to OCEL

- Map events to OCEL events and run, actor, invocation, model-call, tool-call,
  task, resource, and artifact entities to OCEL objects.
- Preserve event-object qualifiers and object-object relationships.
- Use this projection for process mining, conformance, and concurrency
  analysis, not for request replay or authorization.

### Canonical to RLDS and OpenRLHF

- RLDS receives explicit observation-before, action, observation-after, reward,
  discount, terminal, and truncation semantics plus environment revision.
- OpenRLHF receives token IDs only with tokenizer ID/revision, action mask,
  behavior/reference policy revisions, sampling parameters, reward function and
  component provenance, and split/contamination metadata.
- Human/tool events must remain connected to the source trajectory even when
  the training tensor projection omits them.

## Hard edges that no format combination solves automatically

1. **Observed user skill versus task success.** Trace structure can show actions
   and friction, not prove a person's underlying skill. That needs validated
   task/skill taxonomies, opportunity controls, uncertainty, and user-visible
   evidence.
2. **Causal benefit of memory, prompts, or suggested skills.** Stored traces
   produce hypotheses. Causality requires randomized replay or prospective
   intervention with no-memory, relevant-memory, and placebo arms.
3. **Hidden provider reasoning and tool behavior.** Absence of
   `reasoning_content`, token logprobs, or a tool span means unobserved, not
   absent.
4. **Environment replay.** A command and stdout do not recreate filesystem,
   service, identity, network, time, and external side effects. Replay requires
   versioned environments, checkpoints/diffs, and side-effect fences.
5. **Authorization replay.** A user ID or virtual-key ID does not prove an allow
   decision. The policy revision, authorization epoch, requested scope, and
   decision evidence must be captured at the gate.
6. **Classification-safe cross-user similarity.** RLS filters source rows; it
   does not automatically make embeddings, centroids, clusters, explanations,
   or aggregate counts safe. Derived artifacts need lineage and authority
   intersection.
7. **Clock and order truth.** Sequence numbers, wall clocks, span parents, and
   semantic causality are different facts. The canonical model must retain all
   available forms rather than select one “true order.”

## Conformance and empirical test plan

### Adapter fixtures

Create paired source/canonical/golden-projection fixtures for:

1. one model response with no tool;
2. one proposed and authorized successful tool;
3. proposed tool denied before execution;
4. tool error followed by retry and success;
5. provider failure followed by fallback model;
6. parallel tool calls returning out of order;
7. subagent delegation with siblings sharing one run/session ID;
8. continuation after context compaction with copied context;
9. cancellation before model completion;
10. environment truncation distinct from terminal failure;
11. MCP client/server spans plus independent HTTP transport context;
12. memory proposal rejected, and memory proposal approved/written;
13. classification or epoch change invalidating a derivation; and
14. multiple LLM calls aggregated into one ATIF step.

Every fixture must assert event count, edge count, tool-call correlation,
timestamps, authority columns, artifact hashes, capture modes, and expected
loss-receipt entries.

### Public-corpus loss audit

| Corpus | Primary experiment |
|---|---|
| MCP ATIF benchmark | ATIF v1.7 import, canonicalization, ATIF re-export, and exact field-loss diff |
| Trace Commons | native harness import versus normalized-row import; branch/tool/error preservation and privacy quarantine |
| Open Agent Traces | OCEL-to-canonical graph fidelity, concurrency, routing/retry invariants, and canonical-to-OCEL round trip |
| CodeTraceBench | raw harness import, annotation join, decisive-step localization, and comparison against lossy message-only projection |
| Exgentic OTel traces | observed tool span versus message-reconstructed tool event fidelity |
| pagarsky agent traces | deterministic tool replay and mutation of order/status/correlation |
| SPARK repeated attempts | attempt/recovery edges, copied knowledge, and non-causal memory hypotheses |
| CMU agent trajectories | multi-harness coverage and repeated-pass analysis, quarantined from redistribution until license terms are explicit |

### Quantitative measures

- exact field preservation by type;
- event precision/recall against hand-audited gold;
- edge precision/recall for parent, cause, link, retry, fallback, delegation,
  and continuation;
- tool proposal/execution/result correlation accuracy;
- timestamp and duration error;
- observed versus reconstructed event rate;
- unsupported and dropped bytes/events per adapter;
- diagnosis/eval score change caused by each projection;
- replay success and side-effect divergence;
- RLS and epoch-invalidation leakage tests; and
- query-answer accuracy for the enterprise question suite.

Report results by source harness and capture fidelity. A high aggregate score
must not hide that one harness loses every tool result or that classified
derivations fail invalidation.

## What Frankengate should build first

1. Implement the canonical identity, typed lifecycle, authority columns, raw
   artifact reference, and loss receipt before adding another analyzer.
2. Instrument Frankengate's own model routing, governance gate, tool lifecycle,
   retries/fallbacks, and MCP client/server boundary at the source, where these
   facts are still observable.
3. Add deterministic ATIF v1.7 and OTLP/OpenInference adapters with conformance
   fixtures and explicit loss receipts.
4. Add AgentEvals and AgentRx projections only after the canonical adapters
   pass.
5. Add OCEL and RLDS/OpenRLHF projections as research arms, without making
   another database or tracing product authoritative.

This creates one evidence system with several deliberately lossy views. Trying
to combine ATIF, OTel, OpenInference, AgentEvals, AgentRx, OCEL, and RL records
as peer canonical stores would duplicate identity, create contradictory
security semantics, and make the enterprise questions less—not more—answerable.
