# Trace-tool execution feasibility for the public-trajectory empirical program

**Status:** source-pinned execution review
**Reviewed:** 2026-07-30
**Scope:** AgentRx, AgentEvals, Graphiti, LangMem, ReasoningBank, Anthropic Dreams, and adjacent trace-evaluation concepts
**Decision target:** which upstream implementations can be run fairly against stored public agent traces, which mechanisms should be reimplemented behind Frankengate's canonical trace contract, and which systems should not be experimental arms at all

## Executive decision

Do not build one large integration that pipes public traces through every upstream project. The projects accept materially different evidence, several silently discard trace structure, and two cannot faithfully consume arbitrary stored trajectories.

Use this execution split:

| System | Stored public traces without rerunning the agent? | Run upstream? | Frankengate decision |
|---|---:|---:|---|
| AgentEvals v0.9.7 | Yes, when adapted to Jaeger JSON or OTLP JSON/JSONL | **Yes** | Use as the direct stored-trace assertion arm. Keep the canonical trace outside AgentEvals because its internal model is intentionally narrower and has known lossy OTel decoding. |
| AgentRx commit `f228165` | Yes, after conversion to its role/content IR | **Parity sample only** | Run upstream in a locked-down disposable container for paper parity. Reimplement its trajectory IR, deterministic invariants, evidence log, and failure taxonomy for the real harness. |
| Graphiti v0.29.3 | Yes, after turning trace events into temporal episodes | **Yes, small offline ablation** | Run against an ephemeral graph database to measure whether temporal facts and graph traversal add value. Do not adopt its database or `group_id` as Frankengate's authorization boundary. |
| LangMem commit `56d8593` / package 0.0.30 | Yes, as message lists | **Yes, stateless extractor arm** | Invoke `create_memory_manager` without its store, with a Frankengate-owned evidence-bearing schema. Never allow direct promotion to durable user memory. |
| ReasoningBank commit `ed80611` / package 0.1.0 | Not generically; released runners expect SWE-Bench or WebArena artifacts | **No** | Reimplement the successful/failed-trajectory lesson induction and retrieval experiment. Do not run its harness or ingest its pickle artifacts. |
| Anthropic Dreams research preview | No; it accepts Anthropic-managed session IDs, not arbitrary trace records | **No for the public corpus** | Reimplement the copy-on-write consolidation experiment. A later black-box case study may use internally generated Managed Agent sessions if preview access is granted. |
| Signals-style cheap detectors | Yes | **Concept implementation** | Implement directly over the canonical trace before any embeddings or judges. |
| Phoenix, Opik, Langfuse | Yes as observability/evaluation lifecycle platforms | **No experimental arm** | Their useful contribution is lifecycle design, not an independent inference mechanism. Do not add three services to test the same trace-to-dataset workflow. |

The common experimental input must remain a lossless, provider-neutral Frankengate trajectory. Every tool gets an adapter and a machine-readable **loss manifest**. Results are joined back to the canonical trace by immutable trace, span, event, tool-call, and dataset-revision IDs.

## Why the tools cannot simply be chained

Their input contracts operate at different semantic levels:

1. AgentEvals reads trace spans but converts them into conversations, final responses, and tool calls for scoring.
2. AgentRx reduces a trajectory to ordered steps containing `role` and string `content`.
3. Graphiti treats each item as a time-referenced episode from which an LLM extracts entities and facts.
4. LangMem treats the input as chat messages and emits candidate memories.
5. ReasoningBank expects task outcome labels plus harness-specific thought/action logs.
6. Dreams accepts only server-side Managed Agent sessions and a server-side memory store.

A downstream system must therefore never receive another tool's reduced representation as if it were the original trace. For example, feeding AgentRx's stringified IR into AgentEvals would lose tool-call identity and span parentage; feeding LangMem memories into Graphiti as if they were observed facts would erase the distinction between evidence and model inference.

The valid composition is a fan-out from canonical evidence, followed by an evidence-aware join:

```text
canonical trace
  ├─ cheap structured signals
  ├─ AgentEvals adapter and stored-trace assertions
  ├─ AgentRx-style invariants and failure localization
  ├─ Graphiti temporal-fact ablation
  ├─ LangMem candidate-memory extraction
  └─ ReasoningBank-style lesson induction

all outputs
  └─ evidence join → blinded scoring → ablation analysis → promotion decision
```

## Common execution contract

Every arm should receive the same immutable unit:

```json
{
  "dataset_id": "publisher/dataset",
  "dataset_revision": "sha256-or-hf-commit",
  "trace_id": "stable-id",
  "session_id": "stable-id-if-present",
  "task_id": "stable-id-if-present",
  "outcome": {"label": "success|failure|unknown", "source": "gold|publisher|judge"},
  "events": [
    {
      "event_id": "stable-id",
      "span_id": "stable-id-if-present",
      "parent_span_id": "stable-id-if-present",
      "timestamp": "RFC3339-or-null",
      "actor": "user|assistant|tool|orchestrator|subagent",
      "kind": "message|model_call|tool_call|tool_result|error|state_change",
      "content": {},
      "ordinal": 0
    }
  ]
}
```

Each adapter must emit:

- the upstream input artifact;
- a mapping from upstream records back to canonical event IDs;
- fields omitted, flattened, inferred, truncated, or synthesized;
- adapter version and commit;
- model, prompt, temperature, seed where supported, and retry policy;
- token, latency, and dollar cost;
- failures and partial outputs without silently dropping a trace.

No arm may read held-out labels, future events, another arm's prediction, or memories induced from the same held-out task unless the experimental condition explicitly tests that composition.

## AgentRx v0.1.0, no stable tag (2026-05-28)

**Repo:** [microsoft/AgentRx](https://github.com/microsoft/AgentRx) @ [`f228165bfec60a801fd5fedd9d8ffe0f9de0c69d`](https://github.com/microsoft/AgentRx/tree/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d)
**License:** MIT
**Release status:** no tags or GitHub releases; pin the commit, container image, and dependency resolution
**Local verification:** source compiled under Python 3.13; the bundled Tau trajectory `invalid_invocation.json` converted to one 30-step IR trajectory without an API call

### Input contract

The canonical AgentRx IR is:

```json
{
  "trajectory_id": "string",
  "instruction": "string",
  "steps": [
    {
      "index": 1,
      "substeps": [
        {"sub_index": 1, "role": "assistant", "content": "string"}
      ]
    }
  ]
}
```

The loader recognizes JSON, JSONL, glued JSON objects, Markdown conversations, and wrappers under `traj`, `events`, `messages`, `trajectory`, or `spans`. Recognition of a `spans` key is not equivalent to OpenTelemetry support. Only Tau, Flash, and Magentic-One have handwritten converters. An unknown shape can trigger an LLM-based conversion, which may truncate a raw trajectory at 800,000 characters and synthesizes the step grouping.

Tool calls and results are ultimately string content in the IR. Span timing, status, attributes, links, event types, and parent/child identity are not part of the validated IR. Frankengate must supply its own deterministic adapter and retain the richer canonical trace.

### Commands

| Task | Command | Notes |
|---|---|---|
| Full pipeline | `python run.py trajectory.json --domain tau --endpoint azure` | Runs IR, static and dynamic invariant generation, checking, judge, and reports. |
| IR only | `python run.py trajectory.json --stage ir --domain tau --endpoint azure` | The runner still validates endpoint configuration before doing IR-only work. |
| Static invariants | `python run.py trajectory.json --stage static --domain tau` | LLM-backed generation; default template emits Python checks only. |
| Dynamic invariants | `python run.py trajectory.json --stage dynamic --dynamic-mode stepbystep` | `oneshot` is the lower-call alternative. |
| Invariant checking | `SKIP_NL=1 python agentrx/invariants/checker.py ...` | Skips semantic checks but still executes generated Python-check code. |
| Root-cause judge | `python agentrx/judge/judge.py --domain tau --log_file trajectory.json --mode combined` | Produces the ten-class failure attribution. |

### Runtime and services

- Python 3.10 or newer.
- Azure OpenAI with Azure identity, GitHub Copilot CLI, or Microsoft's internal TRAPI endpoint.
- No first-class standard `OPENAI_API_KEY`/custom-base-URL path in the released pipeline.
- Matplotlib and NumPy for reports.
- Dependencies have lower bounds but no published stable tag; resolve and freeze them in the experiment image.

### Mechanisms worth isolating

1. Canonical ordered trajectory representation.
2. Static invariants derived from policies and tool schemas.
3. Dynamic, step-context invariants.
4. Deterministic checks versus natural-language checks.
5. Per-check telemetry and evidence-bearing violation records.
6. Critical-step localization.
7. The ten-class grounded failure taxonomy.

The empirical program should test each mechanism separately before testing the complete pipeline. In particular, compare:

- cheap hand-authored invariants;
- LLM-synthesized invariants reviewed before execution;
- deterministic-only checks;
- semantic judge checks;
- failure classification with and without the invariant evidence log.

### Direct-run decision

Run the upstream project only on a small public-data parity subset inside a disposable container with:

- no host mounts except read-only inputs and one output directory;
- no cloud credentials other than a scoped model-proxy token;
- network access restricted to the model proxy;
- CPU, memory, process, and wall-time limits;
- generated invariants archived before execution.

Do not execute it in the Frankengate worker. Its checker joins LLM-produced `code_lines` and calls Python `exec`; the custom built-in allowlist reduces accidental access but is not a security boundary for adversarial generated code. The upstream runner also validates an LLM endpoint even for an IR-only stage.

Reimplement the accepted mechanisms in the research harness so checks are declarative. A safe invariant DSL should support field comparisons, ordered-event predicates, JSON Schema validation, numeric bounds, state-machine transitions, and bounded regex. Semantic checks should call a judge, not generate executable code.

### Gotchas

- **No stable release:** commit pinning is mandatory.
- **Lossy IR:** tool and span structure becomes role/content strings.
- **Unknown-format nondeterminism:** the LLM fallback can infer grouping and truncate long traces.
- **Generated-code execution:** upstream Python checks are executed with `exec`.
- **Endpoint coupling:** external users are directed to Azure or Copilot, while TRAPI is internal.
- **Recent pipeline churn:** PRs [#19](https://github.com/microsoft/AgentRx/pull/19), [#31](https://github.com/microsoft/AgentRx/pull/31), and [#32](https://github.com/microsoft/AgentRx/pull/32) fixed parsing, sandbox, pipeline, and judge failures after the initial release.
- **Open design question:** issue [#16](https://github.com/microsoft/AgentRx/issues/16) explicitly questions predeclared versus synthesized constraints. Treat that as an ablation, not an implementation detail.

### Sources

- IR loader and schema: [`trajectory_ir.py`](https://github.com/microsoft/AgentRx/blob/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d/agentrx/ir/trajectory_ir.py#L9-L27)
- IR validation and domain conversion: [`trajectory_ir.py`](https://github.com/microsoft/AgentRx/blob/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d/agentrx/ir/trajectory_ir.py#L308-L383)
- LLM fallback and truncation: [`trajectory_ir.py`](https://github.com/microsoft/AgentRx/blob/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d/agentrx/ir/trajectory_ir.py#L583-L744)
- Generated Python execution: [`checker.py`](https://github.com/microsoft/AgentRx/blob/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d/agentrx/invariants/checker.py#L549-L692)
- Pipeline stage and endpoint behavior: [`run.py`](https://github.com/microsoft/AgentRx/blob/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d/run.py#L597-L710)

## AgentEvals v0.9.7 (2026-07-10)

**Repo:** [agentevals-dev/agentevals](https://github.com/agentevals-dev/agentevals) @ [`221febbe05927923242a5edc12e68a2b70fd5ae9`](https://github.com/agentevals-dev/agentevals/tree/221febbe05927923242a5edc12e68a2b70fd5ae9)
**License:** Apache-2.0
**Release:** [v0.9.7](https://github.com/agentevals-dev/agentevals/releases/tag/v0.9.7)
**Local verification:** source compiled under Python 3.13; its auto-loader detected `samples/tempo_export_with_batches.json` as OTLP JSON and loaded one trace containing 86 spans without installing the full evaluator stack

### Input contract

AgentEvals directly accepts:

- Jaeger native JSON;
- OTLP JSON documents;
- OTLP JSONL;
- Tempo v1 `batches`;
- Tempo v2 `trace` wrappers.

Its GenAI converter recognizes OTel GenAI semantic-convention attributes and Google ADK attributes. It supports message payloads in span attributes, correlated log records, and legacy span events. The output being scored is an ADK-style list of invocations with user content, final response, tool uses, and tool responses.

Golden data uses Google ADK's `EvalSet` schema. Tool-call IDs pair calls and responses. The direct tool-trajectory match modes are `EXACT`, `IN_ORDER`, and `ANY_ORDER`; semantic response checks are separate judge-backed metrics.

This is the best upstream candidate for “turn a stored production trace into an eval without rerunning the agent.”

### Commands

| Task | Command | Notes |
|---|---|---|
| Evaluate stored traces | `agentevals run trace.json --eval-set eval_set.json` | Auto-detects Jaeger versus OTLP. |
| Exact tool trajectory | `agentevals run trace.json -e eval_set.json -m tool_trajectory_avg_score --trajectory-match-type EXACT` | Deterministic. |
| In-order tool trajectory | `... --trajectory-match-type IN_ORDER` | Allows extra calls while preserving expected order. |
| Any-order tool trajectory | `... --trajectory-match-type ANY_ORDER` | Tests set-like tool use. |
| Judge-backed metric | `agentevals run trace.json -m hallucinations_v1 --judge-model <model>` | Requires a supported judge credential. |
| Custom evaluator | `agentevals evaluator init friction_detector --runtime py` | Uses a versioned JSON stdin/stdout protocol. |
| Force format | `agentevals run trace.json --format otlp-json` | Useful for generated fixtures. |

### Runtime and services

- Python 3.11 or newer.
- Core package includes Google ADK evaluation support, FastAPI, OTLP protobuf types, and HTTP tooling.
- Deterministic stored-trace metrics need no live agent.
- LLM metrics need judge credentials.
- Optional Postgres stores run history, but it is unnecessary for the paper harness.
- Local code evaluators run as subprocesses; Python evaluators may create cached virtual environments and install their `requirements.txt`.

### Mechanisms worth isolating

1. OTLP/Jaeger loading and GenAI semantic-convention conversion.
2. Session-to-invocation extraction.
3. Golden trace creation.
4. Exact, ordered, and unordered tool-trajectory assertions.
5. Final-response string and judge comparisons.
6. The language-neutral custom-evaluator protocol.

Use upstream directly for these mechanisms. Add Frankengate custom evaluators for loop count, repeated tool errors, recovery after failure, permission denials, unsupported-tool attempts, and evidence completeness.

### Hard boundary

AgentEvals is an evaluation projection, not the enterprise trace warehouse. Its own open issues document that:

- the internal span model discards many OTel attributes ([#169](https://github.com/agentevals-dev/agentevals/issues/169));
- there are multiple AnyValue decoders and some are lossy ([#173](https://github.com/agentevals-dev/agentevals/issues/173));
- integration-marked tests were not yet run in CI at the reviewed release ([#177](https://github.com/agentevals-dev/agentevals/issues/177));
- X eval cases against Y traces remained an open use case ([#151](https://github.com/agentevals-dev/agentevals/issues/151)).

Therefore, export a purpose-built OTLP artifact to AgentEvals and join its scores back to the canonical trace. Never use its normalized span object as the only retained copy.

### Sources

- CLI and match modes: [`cli.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/cli.py#L76-L145)
- File-format detection: [`loader/auto.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/loader/auto.py#L1-L84)
- Narrow internal span model: [`loader/base.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/loader/base.py#L10-L41)
- Eval-set and tool-call schema: [`eval-set-format.md`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/docs/eval-set-format.md#L7-L27)
- Stored-trace, no-rerun behavior: [`eval-set-format.md`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/docs/eval-set-format.md#L240-L244)
- Custom evaluator protocol: [`custom-evaluators.md`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/docs/custom-evaluators.md#L111-L201)

## Graphiti v0.29.3 (2026-07-27)

**Repo:** [getzep/graphiti](https://github.com/getzep/graphiti) @ [`021d3a57d511f21b10adaf7fa923bd5c1fce5e9d`](https://github.com/getzep/graphiti/tree/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d)
**License:** Apache-2.0
**Release:** [v0.29.3](https://github.com/getzep/graphiti/releases/tag/v0.29.3)
**Local verification:** source compiled under Python 3.13; full execution was not attempted because it requires a graph database plus extraction, embedding, and reranking clients

### Input contract

`add_episode` accepts:

- a name;
- an `episode_body` string;
- a source description;
- a reference timestamp;
- an episode type of message, JSON, text, or fact triple;
- a `group_id`;
- optional entity and edge schemas;
- optional custom extraction instructions;
- optional saga identity.

An episode is not an OTel span. The adapter must decide whether an episode represents a whole trace, an agent turn, a tool interaction, or a bounded event window. For this experiment, use **one canonical event per episode**, serialize structured event content as JSON, set `saga=trace_id`, and use the event timestamp as `reference_time`. This preserves the trajectory chain and lets a fact point back to the exact episode.

### Runtime and services

- Python 3.10 or newer.
- A graph driver: Neo4j by default, or optional FalkorDB, Neptune/OpenSearch, or deprecated Kuzu.
- An LLM for node/edge extraction and deduplication.
- An embedding provider.
- A cross-encoder/reranker.
- The defaults are OpenAI clients plus Neo4j.

The upstream hybrid search combines BM25, cosine similarity, graph traversal, RRF/MMR/cross-encoder reranking, and temporal filters. That makes Graphiti a useful **combined temporal-graph ablation**, not a clean measurement of any one retrieval primitive.

### Commands and operations

| Task | Operation | Notes |
|---|---|---|
| Start test graph | `docker compose up` | Use an ephemeral dataset-specific graph. |
| Initialize | `Graphiti(uri, user, password, ...)` | Defaults to Neo4j and OpenAI clients. |
| Build schema | `await graphiti.build_indices_and_constraints()` | Required before ingestion. |
| Add event | `await graphiti.add_episode(...)` | Ingestion performs LLM extraction, deduplication, embedding, and invalidation. |
| Add batch | `await graphiti.add_episode_bulk(...)` | Faster, but still stochastic and resource intensive. |
| Hybrid fact search | `await graphiti.search(query, group_ids=[...])` | BM25 plus vectors; returns fact edges. |
| Advanced search | `await graphiti.search_(query, config=...)` | Enables BFS and reranker recipes. |

### Mechanisms worth isolating

1. Time-valid fact extraction with `valid_at`/`invalid_at`.
2. Contradiction and duplicate resolution.
3. Episode-to-fact provenance.
4. Entity relationships and multi-hop traversal.
5. Saga/trajectory ordering.
6. Hybrid lexical, vector, and graph retrieval.

Run upstream on a small, fully public subset to test whether those mechanisms improve:

- fact precision and support by source events;
- contradiction detection;
- retrieval of relevant prior traces;
- temporal “what was believed when?” questions;
- multi-hop entity/task relationship questions.

Run at least these ablations:

- BM25 only;
- vector only;
- BM25 plus vector;
- graph traversal without cross-encoder;
- full Graphiti hybrid;
- full Graphiti with temporal filtering.

### Direct-run decision

Use a separate ephemeral Neo4j instance for the scientific arm. Do not interpret that as a production architecture recommendation.

Do not use Graphiti `group_id` as an authorization boundary. It is an application-level partition/filter and, depending on driver, can rebind the active database/graph. The reviewed project had very recent group-routing fixes and retains an open concurrent multi-group corruption report. It also has an open request for fact-level access control, PII scanning, and audit hooks. Frankengate must enforce row-level authorization and evidence visibility before invoking any graph or semantic retrieval.

If Graphiti wins an ablation, adopt only the measured mechanism into the Aurora-first evidence model unless a later benchmark proves that a graph service is necessary.

### Gotchas

- **Stochastic multi-service pipeline:** ingestion conflates extraction, dedupe, embeddings, graph persistence, and temporal invalidation.
- **No database RLS contract:** `group_id` is not equivalent to PostgreSQL row-level security.
- **Concurrency risk:** open issue [#1676](https://github.com/getzep/graphiti/issues/1676) reports cross-group corruption from shared driver mutation.
- **Missing governance hooks:** issue [#1679](https://github.com/getzep/graphiti/issues/1679) requests fact-level access control and auditability.
- **Small-model contradiction sensitivity:** issue [#1666](https://github.com/getzep/graphiti/issues/1666) reports degraded dedupe/contradiction handling on non-reasoning small models.
- **Backend-specific behavior:** group routing required fixes in PRs [#1670](https://github.com/getzep/graphiti/pull/1670) and [#1675](https://github.com/getzep/graphiti/pull/1675).
- **Kuzu is deprecated:** the tagged package says the upstream project is unmaintained.

### Sources

- Dependencies and drivers: [`pyproject.toml`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/pyproject.toml#L1-L41)
- Default driver and model clients: [`graphiti.py`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/graphiti.py#L160-L240)
- Episode types: [`nodes.py`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/nodes.py#L54-L77)
- Episode ingestion contract: [`graphiti.py`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/graphiti.py#L980-L1059)
- Temporal invalidation in bulk ingestion: [`graphiti.py`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/graphiti.py#L1230-L1293)
- Hybrid recipes: [`search_config_recipes.py`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/search/search_config_recipes.py#L33-L108)
- Temporal and property filters: [`search_filters.py`](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/search/search_filters.py#L38-L67)

## LangMem 0.0.30, no stable tag (2026-07-25)

**Repo:** [langchain-ai/langmem](https://github.com/langchain-ai/langmem) @ [`56d85939d80bb731bd5e237567148d817d7bfd16`](https://github.com/langchain-ai/langmem/tree/56d85939d80bb731bd5e237567148d817d7bfd16)
**License:** MIT
**Release status:** no repository tag or GitHub release; the source declares package version 0.0.30
**Local verification:** source compiled under Python 3.13; a model-backed invocation was not run

### Input contract

The stateless `MemoryManager` accepts:

```python
{
    "messages": [...],
    "existing": [("memory-id", "SchemaName", existing_model)],  # optional
    "max_steps": 1
}
```

It emits `(id, Pydantic model)` pairs. A caller supplies one or more Pydantic schemas and can independently enable inserts, updates, and deletes. This is a clean way to test structured candidate-memory extraction over stored conversations.

The store-backed manager adds a LangGraph `BaseStore`, namespace templates, retrieval of existing memories, and mutation. Those storage features are unnecessary for the experiment and are not suitable as Frankengate's authority layer.

### Runnable operations

| Task | Operation | Notes |
|---|---|---|
| Candidate extraction | `create_memory_manager(model, schemas=[...])` | Use this stateless path. |
| Extract from stored chat | `manager.invoke({"messages": messages})` | No live agent rerun. |
| Consolidate candidates | Pass `existing` plus new messages | Measures update/contradiction behavior. |
| Multiple reflection steps | Set `max_steps` greater than one | More cost and nondeterminism. |
| Store-backed enrichment | `create_memory_store_manager(...)` | Do not use in the initial experiment. |
| Background execution | `ReflectionExecutor(...)` | Lifecycle mechanism only, not a quality mechanism. |

### Mechanisms worth isolating

1. Schema-constrained candidate extraction.
2. Insert versus update decisions.
3. Contradiction-aware consolidation.
4. One-step versus multi-step reflection.
5. Semantic, episodic, and procedural memory schemas.

Use a Frankengate-owned schema such as:

```text
CandidateMemory
  kind: fact | preference | procedure | lesson | unresolved_question
  subject_scope: user | team | enterprise
  statement
  evidence_event_ids[]
  observed_at
  valid_from?
  valid_to?
  confidence
  sensitivity
  promotion_recommendation
```

The upstream default output contains only an ID and memory content. Evidence IDs, provenance, sensitivity, validity interval, and authorization scope must be required by our schema and verified after generation.

### Direct-run decision

Run the stateless upstream extractor as one experimental arm. Instantiate a model client explicitly through Frankengate rather than allowing ambient provider configuration. Do not let LangMem write directly to durable memory. All outputs go to a candidate table and require evidence validation, policy checks, deduplication, and promotion rules.

Reimplement only if the stateless arm shows value and the LangChain dependency surface is not justified. Its core useful mechanism is small: schema-guided extraction plus comparison against a bounded set of existing memories.

### Gotchas

- **No stable tag:** source/package provenance is ambiguous unless both commit and resolved wheel are recorded.
- **Large mandatory integration surface:** the package directly depends on LangChain, LangGraph, OpenAI, Anthropic, LangSmith, and Trustcall.
- **No first-class provenance in output:** the default `ExtractedMemory` is only an ID and content model.
- **Memory poisoning not solved:** open issues [#163](https://github.com/langchain-ai/langmem/issues/163) and [#164](https://github.com/langchain-ai/langmem/issues/164) request an OWASP memory-poisoning guard.
- **Store interoperability issues:** open issues [#138](https://github.com/langchain-ai/langmem/issues/138) and [#140](https://github.com/langchain-ai/langmem/issues/140) report schema/search mismatches.
- **Provider and version friction:** issues [#130](https://github.com/langchain-ai/langmem/issues/130), [#132](https://github.com/langchain-ai/langmem/issues/132), [#142](https://github.com/langchain-ai/langmem/issues/142), [#143](https://github.com/langchain-ai/langmem/issues/143), and [#144](https://github.com/langchain-ai/langmem/issues/144) show release, dependency, and provider gaps.
- **Do not require hidden chain of thought:** public and production traces often contain observable actions and results, not private reasoning. Evaluate lessons from observable evidence only.

### Sources

- Package version and dependencies: [`pyproject.toml`](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/pyproject.toml#L1-L17)
- Output and input types: [`extraction.py`](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/src/langmem/knowledge/extraction.py#L64-L92)
- Extraction and update loop: [`extraction.py`](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/src/langmem/knowledge/extraction.py#L217-L339)
- Stateless factory: [`extraction.py`](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/src/langmem/knowledge/extraction.py#L536-L692)
- Store mutation path: [`extraction.py`](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/src/langmem/knowledge/extraction.py#L1006-L1120)

## ReasoningBank 0.1.0, no stable tag (2026-05-18)

**Repo:** [google-research/reasoning-bank](https://github.com/google-research/reasoning-bank) @ [`ed80611788292ea739f1effd31f16c53823b8a0d`](https://github.com/google-research/reasoning-bank/tree/ed80611788292ea739f1effd31f16c53823b8a0d)
**License:** Apache-2.0
**Release status:** no tag or GitHub release; repository contains only a small number of commits and declares package version 0.1.0
**Local verification:** source compiled under Python 3.13; the benchmark harness was not executed

### Actual released input contract

The released implementation is not a generic trace library.

- The WebArena path expects BrowserGym result folders, task configuration files, reward or auto-evaluation files, and step-level compressed pickle artifacts.
- The SWE-Bench path vendors mini-swe-agent and expects its result layout.
- Memory induction consumes a query, a success/failure signal, and extracted think/action pairs.
- Retrieval embeds the current task and ranks cached prior tasks, using Gemini embeddings or a local Qwen3-Embedding-8B path.

The portable concept is:

```text
task + observable trajectory + trusted outcome
  → induce at most three non-overlapping general lessons
  → index lessons by task
  → retrieve lessons for a different but similar future task
  → measure downstream outcome
```

### Upstream commands

| Task | Command | Notes |
|---|---|---|
| WebArena run | `bash WebArena/run.sh` | Contains environment-specific URLs and a hard-coded developer virtualenv path. |
| WebArena memory induction | `python WebArena/induce_memory.py --result_dir ... --output_path ... --task webarena.47` | Requires the upstream result layout. |
| WebArena scaling | `python WebArena/pipeline_scaling.py ...` | Runs live environments and models. |
| SWE-Bench run | `bash SWE-Bench/run.sh` | Requires the vendored mini-swe-agent and benchmark infrastructure. |
| Lesson retrieval | `select_memory(...)` | Requires precomputed cache alignment and an embedding provider. |

### Runtime and services

- Python 3.13 or newer.
- Pinned BrowserGym 0.14.1 family, Playwright, Torch, LangChain clients, Google GenAI/Vertex, Anthropic, and OpenAI.
- Live WebArena services or SWE-Bench containers for the upstream benchmark.
- Embeddings from Gemini or local Qwen3-Embedding-8B.
- A generation model for outcome judging and lesson induction.

### Direct-run decision

Do not run the upstream harness on arbitrary Hugging Face traces. Reimplement the mechanism behind the common canonical adapter:

1. Use publisher/gold outcome labels where available.
2. Use only observable messages, tool calls, tool results, errors, and final outcomes.
3. Emit structured lessons with evidence-event IDs.
4. Split by task and template before induction.
5. Exclude the current trace, task, near duplicate, and template family from retrieval.
6. Compare no memory, success-only memory, failure-only memory, mixed memory, and outcome-blind memory.
7. Measure retrieval precision, lesson factuality, transfer to held-out task classes, and negative transfer.

The upstream success/failure prompts are useful Apache-licensed starting points, but the format should be schema-constrained and evidence-bearing.

### Gotchas

- **Harness coupling:** paths, parsers, and configuration are specific to WebArena and mini-swe-agent.
- **Unsafe public-artifact ingestion:** the WebArena parser calls `pickle.load` on compressed step files; another helper uses Python `eval` to inspect action arguments. Never run those paths on untrusted downloaded datasets.
- **Hard-coded environment:** the released WebArena shell script includes a developer-specific virtualenv and project settings.
- **Reproducibility complaints:** issues [#2](https://github.com/google-research/reasoning-bank/issues/2), [#3](https://github.com/google-research/reasoning-bank/issues/3), [#6](https://github.com/google-research/reasoning-bank/issues/6), [#11](https://github.com/google-research/reasoning-bank/issues/11), and [#14](https://github.com/google-research/reasoning-bank/issues/14) report difficulty matching the paper and identifying exact model settings.
- **Evaluation leakage:** issue [#17](https://github.com/google-research/reasoning-bank/issues/17) requests leave-one-task-out retrieval to prevent self-retrieval contamination. Frankengate must make this a mandatory split invariant.
- **Outcome dependence:** lesson induction is only as reliable as the success/failure signal; model-generated auto-evaluation must remain distinguishable from gold.

### Sources

- Package and benchmark dependencies: [`pyproject.toml`](https://github.com/google-research/reasoning-bank/blob/ed80611788292ea739f1effd31f16c53823b8a0d/pyproject.toml#L1-L26)
- Success and failure induction prompts: [`instruction.py`](https://github.com/google-research/reasoning-bank/blob/ed80611788292ea739f1effd31f16c53823b8a0d/third_party/src/minisweagent/memory/instruction.py#L16-L61)
- WebArena artifact and pickle parsing: [`WebArena/induce_memory.py`](https://github.com/google-research/reasoning-bank/blob/ed80611788292ea739f1effd31f16c53823b8a0d/WebArena/induce_memory.py#L29-L68)
- Outcome-conditioned lesson induction: [`WebArena/induce_memory.py`](https://github.com/google-research/reasoning-bank/blob/ed80611788292ea739f1effd31f16c53823b8a0d/WebArena/induce_memory.py#L117-L186)
- Retrieval and embedding choices: [`memory_management.py`](https://github.com/google-research/reasoning-bank/blob/ed80611788292ea739f1effd31f16c53823b8a0d/third_party/src/minisweagent/memory/memory_management.py#L37-L86)

## Anthropic Dreams research preview (`dreaming-2026-04-21`)

**Implementation:** managed Anthropic API; no open-source implementation or stable source revision
**License:** service terms, not an OSS code license
**Release status:** gated research preview

### Input contract

A Dream takes:

- one existing Anthropic memory-store ID;
- one to 100 Anthropic Managed Agent session IDs;
- a supported Claude model;
- optional instructions of up to 4,096 characters.

It asynchronously creates a distinct output memory store. It does not mutate the input store. Its documented behaviors are deduplication, replacement of stale or contradicted entries, reorganization, and surfacing new insights.

### Why it cannot join the public-trace benchmark directly

Managed Agent session creation accepts initial user messages and user-defined outcomes, not an arbitrary historical stream of assistant messages, tool calls, tool results, and spans. Serializing an entire public trace into one synthetic user message would test a different task: Claude's interpretation of a trace document, not Dreams operating on the original session.

Therefore:

- do not report Dreams as an upstream baseline on Hugging Face traces;
- do not fabricate Managed Agent sessions to make the API accept the corpus;
- do not compare a black-box preview service to open implementations without exposing the incompatibility.

### Concept arm

Implement a provider-neutral “dream” arm:

```text
immutable input memory snapshot
  + bounded set of canonical past traces
  + consolidation instructions
  → immutable output memory snapshot
```

Score:

- duplicate reduction;
- contradiction resolution accuracy;
- stale-memory retirement;
- supported novel insight rate;
- unsupported insight/hallucination rate;
- evidence coverage;
- information retention;
- output stability across repeated runs;
- token cost.

If preview access is available later, run a separate, clearly labeled black-box case study using sessions generated natively through Managed Agents. Do not mix its results into the public-corpus leaderboard.

### Commands

| Task | Operation | Notes |
|---|---|---|
| Create empty input store | Memory Stores API | Required even when only sessions provide content. |
| Start dream | `client.beta.dreams.create(...)` | Requires both managed-agent and dreaming beta access. |
| Poll | `client.beta.dreams.retrieve(dream_id)` | Jobs can run from minutes to hours. |
| Inspect output | Read the output memory store | Output is separate from input. |
| Cleanup | Archive/delete output store | Failed and canceled jobs can leave partial stores. |

### Sources

- [Dreams API and lifecycle](https://platform.claude.com/docs/en/managed-agents/dreams)
- [Managed Agent session creation and permitted initial events](https://platform.claude.com/docs/en/managed-agents/sessions)
- [Managed Agents data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)

## Adjacent systems and concepts

### Signals-style cheap detectors

Implement these directly over canonical traces rather than looking for an upstream service:

- user rephrasing or repeated intent;
- repeated identical or near-identical tool calls;
- no-progress state repetition;
- assistant self-correction;
- tool error and retry sequence;
- permission denial;
- abandonment/disengagement;
- high latency or token growth without state progress;
- success after three or four failed attempts.

They are deterministic or inexpensive model features, make strong retrieval filters, and define cohorts for the more expensive arms. They should run over every trace.

### Phoenix, Opik, and Langfuse

These projects are useful references for the lifecycle from production trace to annotation, dataset, experiment, and result. They are not independent algorithms for the core enterprise questions. Running all three would mostly benchmark product plumbing and add services, not test whether Frankengate can identify shared work, skill gaps, friction, or useful memory.

Use the lifecycle concepts in Frankengate's existing trace and eval model:

- immutable production example;
- annotation with author and provenance;
- versioned dataset membership;
- reproducible experiment configuration;
- per-example and aggregate results;
- promotion of a real trace into a regression eval.

Do not add any of these services to the initial empirical architecture.

## Reproducible experimental arms

The minimum meaningful set is:

| Arm | Mechanism | Upstream or local |
|---|---|---|
| A0 | Canonical trace plus gold/publisher labels only | Local |
| A1 | Cheap structured Signals detectors | Local |
| A2 | Lexical and structured retrieval | Local |
| A3 | AgentEvals exact/in-order/any-order assertions | Upstream v0.9.7 |
| A4 | AgentRx deterministic invariants | Local reimplementation |
| A5 | AgentRx semantic invariants | Local reimplementation |
| A6 | AgentRx critical-step/failure judge without invariant evidence | Local prompt port |
| A7 | AgentRx judge with invariant evidence | Local prompt port |
| A8 | LangMem schema-constrained candidate memories | Upstream commit |
| A9 | ReasoningBank success/failure lesson induction | Local prompt/mechanism port |
| A10 | Copy-on-write Dream-style consolidation | Local |
| A11 | Graphiti temporal graph and hybrid retrieval | Upstream v0.29.3, ephemeral graph |

Then test compositions that answer a specific causal question:

- A1 → A7: do cheap signals improve which traces receive expensive diagnosis?
- A4 + A7 versus A7: do invariants improve failure localization?
- A3 + A9: do promoted evals plus lessons predict future failure better?
- A8 + A10: does consolidation improve candidate-memory precision without losing supported facts?
- A1 + A11: does graph structure add value after cheap cohorting and structured filters?
- A2 versus A11: does the graph justify its extra service and model cost over lexical/structured retrieval?

Avoid an unrestricted “all systems combined” arm until these pairwise mechanisms show independent value. Otherwise attribution is impossible and a positive result cannot support an architecture decision.

## Scientific and security controls

### Data splits

- Split by dataset, task family, template, repository, and agent harness where possible.
- Group near duplicates before splitting.
- For memory retrieval, exclude the same trace, task ID, template family, and derived variants.
- Separate gold outcome labels from model-judged outcomes.
- Keep a dataset card and license record for every corpus revision.

### Judge controls

- Blind the judge to method/arm identity.
- Randomize output order.
- Use repeated calls for stochastic arms.
- Include deterministic metrics and human adjudication on a stratified subset.
- Record prompt, exact model ID, model provider, temperature, seed where available, token counts, retries, and raw responses.
- Test prompt injection in trace content.

### Execution controls

- Never unpickle downloaded public artifacts.
- Never run generated Python/JavaScript from a trace or model outside a disposable sandbox.
- Route model calls through a scoped Frankengate research key.
- Deny upstream tools access to production databases, cloud metadata, developer credentials, and the host filesystem.
- Use read-only dataset mounts and per-run output directories.
- Hash every input and output artifact.

### Memory controls

- Treat every extracted memory as a candidate, not a fact.
- Require evidence-event IDs.
- Enforce visibility at evidence retrieval and again at output.
- Never widen scope from user to team or enterprise merely because similar text exists.
- Keep claims about a person, skill, or performance out of durable memory without an explicit governance and review path.
- Preserve tombstones and supersession rather than destructive in-place rewriting.

## Architecture implication

This review does not justify replacing Aurora or adding a permanent graph database.

The experiment runner can use:

- object storage/files for pinned public corpora and artifacts;
- the existing analytics/eval worker for orchestration;
- Aurora/PostgreSQL for canonical metadata, experiment state, evidence links, annotations, and results;
- temporary containers for AgentRx parity and Graphiti;
- model calls routed through Frankengate.

Graphiti's database exists only inside its experimental arm. AgentEvals' optional Postgres is unnecessary. LangMem's store is unnecessary. ReasoningBank's live benchmark infrastructure is unnecessary. Dreams' managed storage is inapplicable to the public corpus.

A production architecture change is warranted only if a measured capability:

1. materially improves one of the enterprise question benchmarks;
2. cannot be reproduced with the canonical trace plus PostgreSQL, lexical search, bounded vectors, and offline jobs;
3. preserves Frankengate authorization and evidence lineage;
4. produces enough benefit to justify its operational and data-governance cost.

## Final recommendation

Build the first empirical implementation around three directly runnable upstream components:

1. AgentEvals for stored OTLP trace assertions;
2. LangMem's stateless extractor for one candidate-memory arm;
3. Graphiti in a small ephemeral temporal-graph ablation.

Port concepts—not full runtimes—from:

1. AgentRx for canonical trajectories, invariants, evidence logs, and failure localization;
2. ReasoningBank for outcome-conditioned lesson induction and retrieval;
3. Dreams for immutable batch consolidation;
4. Signals for cheap universal detectors.

This split gives the paper honest implementation fidelity without allowing upstream storage models, lossy projections, or unsafe execution paths to dictate Frankengate's production architecture.
