# RL Environment Trace and Replay Storage Review

**Status:** source-pinned architecture review
**Date:** 2026-07-30
**Scope:** agent/RL environment trajectories, tool and observation capture, reward
provenance, replay, curriculum, learner feedback, and ATIF/OpenTelemetry
interoperability

## Decision

Frankengate should not adopt an RL framework's rollout object, ATIF, or OpenTelemetry as
its sole canonical record. They solve different problems:

1. **Frankengate canonical evidence** is the governed, loss-aware event graph used for
   search, diagnosis, eval mining, and audit.
2. **ATIF v1.7** is the portable conversation/action exchange projection.
3. **OpenTelemetry/OpenInference** is the operational timing and causal-span projection.
4. **An environment replay manifest** makes a task resettable and records snapshots,
   fixtures, external dependencies, and replay divergence.
5. **An optional learner attachment** carries tokenizer-dependent token IDs, role/loss
   masks, behavior-policy log probabilities, and policy/checkpoint lineage.

This is one logical trajectory with typed attachments, not five databases or five
independent ingestion systems. PostgreSQL stores the relational envelope, event graph,
governance labels, reward facts, and artifact metadata. Large and unsafe artifacts such
as screenshots, DOM snapshots, Playwright traces, repository layers, audio, and tensor
payloads belong in governed content-addressed object storage. ATIF and OTel are generated
views.

The existing
[`canonical-trajectory-v1`](../../../research/trace-intelligence/schemas/canonical-trajectory.schema.json)
already has a loss receipt and typed, provenance-qualified events. The smallest useful
addition is therefore **not** a replacement schema. It is three required subdocuments
(`environment`, `evaluation`, and `replay`) plus one optional `learner` attachment and
content-addressed artifact references.

## Method and pinned source set

The review used released source code where a release exists and a pinned repository
commit where one does not. Marketing descriptions were not treated as storage
contracts.

| System | Source inspected | Why it matters |
|---|---|---|
| ATIF / Harbor | [ATIF RFC v1.7 at `f5e9d0b`](https://github.com/harbor-framework/harbor/blob/f5e9d0b71ac4493a4f0620653e2913aee7fc0767/rfcs/0001-trajectory-format.md) | Portable step, tool, observation, token, and subagent interchange |
| Agent Lightning | [v0.3.0, `3b5d733`](https://github.com/microsoft/agent-lightning/tree/3b5d733861cf313fc09821a23240bbdf3cb2ee5b) | OTel-native rollout/attempt/resource correlation and reward attribution |
| OpenEnv | [v0.4.1, `65c506e`](https://github.com/meta-pytorch/OpenEnv/tree/65c506ef94bb1f7279cb4359673b3ef81031d01f) | Environment API, episode collection, delayed trajectory rubrics |
| BrowserGym | [v0.14.3, `0a785fb`](https://github.com/ServiceNow/BrowserGym/tree/0a785fbed075224ae81ca9c1fe924f66050696fe) | Rich browser observations and forensic artifacts |
| WebArena | [commit `dce0468`](https://github.com/web-arena-x/webarena/tree/dce04686a56253aefba7b18a4fa0937cf1dc987b) | Playwright traces, rendered action histories, mutable web environments |
| τ²-bench | [v1.0.1, `fc0055d`](https://github.com/sierra-research/tau2-bench/tree/fc0055dc4e0a316c3f83133267fbd6faaa770992) | Initial database state, tool/action evidence, rich verifier breakdowns, duplex timelines |
| SWE-agent | [v1.1.0, `0f3acaf`](https://github.com/SWE-agent/SWE-agent/tree/0f3acafacabc0def8cc76b4e48acb4b6cf302cb9) | Action replay from recorded histories and repository environment configuration |
| SWE-Gym | [commit `b681068`](https://github.com/SWE-Gym/SWE-Gym/tree/b681068ca20628c6987b7416cc4cf03f06b77ba5) | Containerized software tasks, terminal test reward, derived training records |
| SkyRL | [v0.3.0, `f5bc3b7`](https://github.com/NovaSky-AI/SkyRL/tree/f5bc3b78dfddfb352870d5d7430cd226e5785838) | Multi-turn token masks, per-token rewards, rollout-policy data |
| VERL | [v0.8.0, `7aed6b2`](https://github.com/verl-project/verl/tree/7aed6b230776f963fa09509c10d9c3a767d1102c) | Tensor/non-tensor training batches and off-policy correction fields |
| AgentGym | [commit `3ef9235`](https://github.com/WooooDyy/AgentGym/tree/3ef9235d23e68e7c2920c5422ad957dc8ced5c6c) | Environment diversity and the cost of loosely typed per-environment histories |

AgentGym and SWE-Gym do not provide a suitable recent stable release for this review;
their exact commits are therefore part of every claim. Their instability is itself an
integration risk.

## The format boundary: ATIF versus OTel versus an environment record

ATIF v1.7 is considerably richer than a chat transcript. It has sequential system,
user, and agent steps; correlated tool calls and observations; tool definitions;
multimodal references; prompt/completion token IDs; completion log probabilities;
context-copy markers; continuation files; and embedded or referenced subagent
trajectories. The RFC recommends one ATIF step per LLM inference when the source can
provide it ([step semantics](https://github.com/harbor-framework/harbor/blob/f5e9d0b71ac4493a4f0620653e2913aee7fc0767/rfcs/0001-trajectory-format.md#stepobject)).

That makes ATIF the right **exchange and eval fixture**. It does not make it an exact
environment replay record:

- its primary structure is a sequential list, while concurrent tools, streaming,
  retries, fallbacks, browser network activity, and full-duplex audio are event DAGs;
- it has no normative environment image digest, dataset revision, reset parameters,
  deterministic clock, network fixture, initial/post-state snapshot, or replay
  divergence report;
- reward is a metric, not a versioned assertion/rubric execution with evidence;
- `llm_call_count > 1` explicitly permits aggregate steps where per-call attribution is
  unavailable; and
- `extra` can carry missing data, but arbitrary extensions do not create portable
  semantics.

OTel has the opposite strength. Agent Lightning demonstrates that spans can carry
rollout, attempt, sequence, trace, parent, link, resource, event, timing, and reward
correlation data in a standard operational shape
([span model](https://github.com/microsoft/agent-lightning/blob/3b5d733861cf313fc09821a23240bbdf3cb2ee5b/agentlightning/types/tracer.py#L213-L295)).
OTel naturally represents overlap, retries, latency, and cross-service causality. It
does not define what a browser reset, repository snapshot, database fixture, action
space, reward rubric, or policy tensor means.

Frankengate's canonical event graph must therefore preserve more than either projection.
Every projection must emit a machine-readable loss receipt. For example, converting a
τ²-bench duplex timeline to sequential ATIF steps is allowed only if the receipt records
that overlap and voice timing were flattened.

## Findings by system

### Agent Lightning: the strongest OTel control-plane overlay

Agent Lightning's durable concepts are worth adopting:

- `Rollout` separates task input, mode, resource snapshot, retry policy, lifecycle, and
  arbitrary metadata; `Attempt` gives retries their own identity, sequence, worker,
  heartbeat, and status
  ([models](https://github.com/microsoft/agent-lightning/blob/3b5d733861cf313fc09821a23240bbdf3cb2ee5b/agentlightning/types/core.py#L136-L216)).
- Its span model extends normal OTel correlation with rollout and attempt identifiers,
  while retaining links, events, resource attributes, and serializable extra fields
  ([span implementation](https://github.com/microsoft/agent-lightning/blob/3b5d733861cf313fc09821a23240bbdf3cb2ee5b/agentlightning/types/tracer.py#L251-L337)).
- The store treats prompts, model checkpoints, and other resources as immutable
  snapshots associated with rollouts
  ([store contract](https://github.com/microsoft/agent-lightning/blob/3b5d733861cf313fc09821a23240bbdf3cb2ee5b/agentlightning/store/base.py)).
- The triplet adapter has explicit policies for associating rewards with spans,
  reconstructs missing roots, and extracts raw prompts, completions, token IDs, and
  log probabilities
  ([adapter](https://github.com/microsoft/agent-lightning/blob/3b5d733861cf313fc09821a23240bbdf3cb2ee5b/agentlightning/adapter/triplet.py)).

The hard edge is equally important: reward-to-span assignment is sometimes heuristic,
lost parents require synthetic roots, and LLM calls without recorded token IDs can be
excluded from training conversion. Those conditions must become explicit provenance
and missingness, never silently “repaired.” Frankengate should adopt the rollout /
attempt / resource concepts and OTel projection, not Agent Lightning's Mongo-specific
scheduler/store or its training adapter as ground truth.

### OpenEnv: a clean environment API but an incomplete durable episode

OpenEnv's core types correctly separate actions, observations, reset requests, step
requests, and state. Reset accepts a seed and episode ID; an observation carries
`done`, scalar reward, and metadata
([environment types](https://github.com/meta-pytorch/OpenEnv/blob/65c506ef94bb1f7279cb4359673b3ef81031d01f/src/openenv/core/env_server/types.py#L50-L194)).
Its collector writes append-only JSONL `EpisodeRecord`s with messages, scalar reward,
flat tool traces, metrics, verifier metrics, artifacts, task, and extension data
([collector](https://github.com/meta-pytorch/OpenEnv/blob/65c506ef94bb1f7279cb4359673b3ef81031d01f/src/openenv/core/harness/collect.py#L63-L138)).

That record is useful for dataset collection but does not require the state needed for
exact replay: environment/image version, reset config, seed, initial snapshot, action
timestamps and parentage, or post-state. Tool traces are flat and reward is scalar.
The delayed `TrajectoryRubric` keeps `(action, observation)` pairs in memory until the
episode finishes, but intentionally does not serialize the live trajectory in its
state dictionary
([rubric](https://github.com/meta-pytorch/OpenEnv/blob/65c506ef94bb1f7279cb4359673b3ef81031d01f/src/openenv/core/rubrics/trajectory.py)).

OpenEnv's Echo world-model example exposes a second missing layer: an episode-level
record is insufficient for RL when roles differ at token granularity. It adds
`context`, `action`, `env_output`, and `warning` segments plus token-aligned masks
([trajectory conversion](https://github.com/meta-pytorch/OpenEnv/blob/65c506ef94bb1f7279cb4359673b3ef81031d01f/examples/echo_world_model/trajectory.py)).
Frankengate should adopt the environment boundary and verification-agreement check, but
add a replay manifest and keep token masks in a separate learner attachment.

### BrowserGym and WebArena: forensic evidence is not deterministic replay

BrowserGym observations can include URLs, active page, screenshot, DOM snapshot,
accessibility tree, last action, action error, and page properties. Its experiment
record stores step, observation, action, reward, termination, agent details, timing,
and task details
([step record](https://github.com/ServiceNow/BrowserGym/blob/0a785fbed075224ae81ca9c1fe924f66050696fe/browsergym/experiments/src/browsergym/experiments/loop.py#L146-L291)).
Screenshots are written separately, while goal and step objects are compressed Python
pickles; package versions are also recorded.

WebArena's supplied human trajectories add rendered accessibility-tree views,
screenshots, parsed actions, and Playwright trace ZIPs containing HTML and network
activity
([artifact description](https://github.com/web-arena-x/webarena/blob/dce04686a56253aefba7b18a4fa0937cf1dc987b/resources/README.md)).
These are excellent evidence for diagnosis. They are not sufficient to reproduce a
mutable website after its content, services, credentials, time, or network responses
change.

Frankengate must call this **forensic replay**, not deterministic replay. Pickle files
are unsafe for untrusted imports and language-specific. Playwright traces may contain
cookies, headers, credentials, or classified page content. Store such data as scanned,
encrypted, content-addressed artifacts with classification and authorization-epoch
metadata. Do not inline screenshots, DOM trees, or trace ZIPs into Postgres rows.

### τ²-bench: the best reward-evidence and initial-state contract

τ²-bench makes tool calls first class with an ID, name, arguments, and requestor
([tool call](https://github.com/sierra-research/tau2-bench/blob/fc0055dc4e0a316c3f83133267fbd6faaa770992/src/tau2/data_model/message.py#L61-L81)).
Messages carry turn index, timestamp, cost, usage, raw provider data, generation time,
and voice timing. A task's `InitialState` records initialization data and actions, while
the task also identifies its scenario, evaluation criteria, required documentation,
issues, and user tools
([task state](https://github.com/sierra-research/tau2-bench/blob/fc0055dc4e0a316c3f83133267fbd6faaa770992/src/tau2/data_model/tasks.py#L506-L581)).

Its `RewardInfo` is the best model in this source set: the scalar result is accompanied
by database checks, environment assertions, action checks, natural-language
assertions, communication checks, a reward basis, and a breakdown
([reward evidence](https://github.com/sierra-research/tau2-bench/blob/fc0055dc4e0a316c3f83133267fbd6faaa770992/src/tau2/data_model/simulation.py#L1053-L1136)).
`SimulationRun` further stores termination reason, costs, trial, seed, mode, reviews,
authentication classification, policy, provider session, and an effect timeline
([run model](https://github.com/sierra-research/tau2-bench/blob/fc0055dc4e0a316c3f83133267fbd6faaa770992/src/tau2/data_model/simulation.py#L1247-L1355)).

Two caveats constrain interoperability. Initial state lives in the task definition,
not necessarily inside each run, so imports must freeze the referenced task revision.
Full-duplex simulations contain overlapping ticks and voice/tool events; flattening
them into a sequential transcript destroys causal timing. Frankengate should adopt the
reward-evidence breakdown and effect timeline, while preserving duplex events as a DAG.

### SWE-agent and SWE-Gym: useful action replay, not exact state replay

SWE-agent's trajectory steps contain model query, thought, action, output, observation,
execution duration, completion status, submission, step state such as a diff, structured
tool calls, and extra data
([trajectory types](https://github.com/SWE-agent/SWE-agent/blob/0f3acafacabc0def8cc76b4e48acb4b6cf302cb9/sweagent/types.py#L42-L82)).
Its replay runner extracts assistant actions or tool calls from the history and
executes them in a fresh environment using saved replay configuration
([replay runner](https://github.com/SWE-agent/SWE-agent/blob/0f3acafacabc0def8cc76b4e48acb4b6cf302cb9/sweagent/run/run_replay.py)).
This is the right model for **action replay** and for detecting parser/tool-interface
incompatibility.

It is not exact state replay unless repository commit, image digest, dependency
repositories, test harness, clock/network fixtures, and every external service are
also frozen. SWE-Gym's task containers, base commits, patches, and terminal test
outcomes are useful replay ingredients
([OpenHands task setup](https://github.com/SWE-Gym/SWE-Gym/blob/b681068ca20628c6987b7416cc4cf03f06b77ba5/docs/OpenHands.md)).
Its verifier conversion produces derived message examples from issues, code spans,
patches, and resolved labels
([conversion](https://github.com/SWE-Gym/SWE-Gym/blob/b681068ca20628c6987b7416cc4cf03f06b77ba5/scripts/moatless-verifier/parse_to_orm_data.py)).
That derived record is training input, not canonical evidence; it can omit the actions
and failed observations that explain an outcome.

### SkyRL and VERL: training batches are disposable projections

SkyRL's generator output carries prompt and response token IDs, scalar or per-token
rewards, loss masks, rollout-policy log probabilities, stop reasons, trajectory IDs,
timings, environment metrics, and optional pixel or expert-routing tensors
([generator output](https://github.com/NovaSky-AI/SkyRL/blob/f5bc3b78dfddfb352870d5d7430cd226e5785838/skyrl/train/generators/base.py#L36-L98)).
Its agent loop retains observation token IDs, action token IDs, turn reward, and masks,
and masks observation/tool output from the model loss
([agent loop state](https://github.com/NovaSky-AI/SkyRL/blob/f5bc3b78dfddfb352870d5d7430cd226e5785838/skyrl/train/generators/skyrl_gym_generator.py#L43-L106)).

VERL's `DataProto` is a flexible TensorDict plus object-valued non-tensor batch and
metadata, optimized for distributed training rather than long-lived evidence
([protocol](https://github.com/verl-project/verl/blob/7aed6b230776f963fa09509c10d9c3a767d1102c/verl/protocol.py#L318-L430)).
PPO/GRPO pipelines carry response masks, loss masks, old/rollout/reference log
probabilities, token-level rewards, group identifiers, reward-model ground truth, and
extra data. Their compact JSONL rollout dumps decode prompts and outputs but commonly
discard raw tool/environment structure and token-level tensors.

The consequence is architectural: Frankengate must retain enough immutable lineage to
reconstruct a training example, but should not make framework-specific tensors its
query model. Token IDs are meaningless without tokenizer and chat-template revisions;
behavior log probabilities are meaningless without policy and sampling lineage; reward
vectors are ambiguous without the algorithm's credit-assignment convention.

### AgentGym: environment diversity, schema fragmentation

AgentGym is valuable evidence that one universal environment payload does not exist.
Its environments expose heterogeneous state and action representations; several tool
environments maintain loosely typed state/history lists and cumulative scalar reward,
while tutorials persist ad hoc JSON/JSONL trajectories. That breadth is useful for
curriculum design, but it is a poor canonical storage contract
([environment package](https://github.com/WooooDyy/AgentGym/tree/3ef9235d23e68e7c2920c5422ad957dc8ced5c6c/agentenv)).

Frankengate should take task-suite, environment-family, curriculum-stage, sampling
weight, parent-corpus, and iteration lineage from this family of work. It should not
copy string-parsed actions or environment-owned history schemas.

## Interoperability matrix

Legend: **native** means structurally represented; **partial** means available only in
extensions/derived artifacts or without enough replay semantics; **no** means the
format does not provide it as a durable contract.

| System | Tools/actions | Observation/state | Reward evidence | Retry/concurrency | Replay level | ATIF projection | OTel projection | Must remain environment-specific |
|---|---|---|---|---|---|---|---|---|
| Agent Lightning | Native spans/attributes | Partial; application payload | Reward spans, attribution policy | Native attempts, links, timestamps | R0 forensic | Good, but span overlap and retries can be lost | Native | Application state, training adapter assumptions |
| OpenEnv | Native API; flat durable tool trace | Live state native, durable snapshot partial | Scalar plus verifier metrics; rubric may be delayed | Request IDs, little durable causality | R1 action if reset data supplied | Good for messages/tools; loss on state and rubric | Good with instrumentation | Environment server state and reset implementation |
| BrowserGym/WebArena | Native browser actions | Rich observations/artifacts, mutable live state | Scalar/task validator | Timing native; page/network concurrency in Playwright artifact | R0 forensic; sometimes R1 action | Good visual/action summary; loses network DAG | Good for operational steps | DOM, AX tree, screenshots, browser storage/network fixtures |
| τ²-bench | First-class tool calls and effect timeline | Initial DB/actions plus message observations | Excellent versionable assertion breakdown | Duplex ticks and rich termination | R2 when task fixture/version is frozen | Good for half duplex; lossy for duplex | Good, if ticks remain linked events | Domain DB schema, user simulator, voice stream |
| SWE-agent/SWE-Gym | Native actions/tool calls | Step diff plus repository/container fixture | Terminal tests/resolution | Sequential attempts; limited causal graph | R1 action; R2 with image/commit/test freeze | Good | Good | Repository layer, filesystem, dependency/test images |
| SkyRL | Tokenized action/observation turns | Token IDs and in-memory env output, not durable state | Scalar/per-token reward | Trajectory repetition IDs; trainer concurrency | Not an audit replay record | Partial; can export turns/tokens | Partial; add spans at generation boundary | Tensors, masks, rollout-engine state |
| VERL | Decoded output or agent-loop data | Flexible object batch, no standard env snapshot | Token-level/model/outcome fields | Distributed batch IDs, not evidence causality | Not an audit replay record | Partial and potentially very lossy | Partial | TensorDict, optimizer/checkpoint/distributed runtime |
| AgentGym | Per-environment actions, often parsed strings | Per-environment state/history | Mostly scalar cumulative reward | Inconsistent | Environment-dependent | Adapter per environment | Instrumentable, not normalized | Nearly all state/action payload semantics |

### Replay-level vocabulary

- **R0 — forensic view:** render what was recorded; no action execution.
- **R1 — action replay:** execute the recorded action/tool sequence in a fresh
  environment; compare observations.
- **R2 — deterministic reset replay:** recreate a pinned initial environment and replay
  under controlled clock, randomness, dependencies, and network fixtures.
- **R3 — exact state continuation:** restore a state snapshot and continue from a
  selected event.

No reviewed system provides R3 uniformly. Frankengate must never label an ATIF render,
an OTel span replay, or a Playwright viewer as R2/R3.

## What is portable and what is not

### Portable canonical facts

The following map cleanly across these systems:

- trajectory/run, attempt, event, parent/link, task, actor, tool-call, and observation
  identifiers;
- event type, start/end time, sequence and partial order;
- raw model request/response and tool arguments/results, using governed artifact
  references when large;
- termination status and typed error;
- model/provider, agent/harness, tool definition, resource, and policy revisions;
- cost and token usage;
- reward/evaluation facts with scorer identity, version, target, evidence, and
  production time;
- dataset/task revision, split, seed, and trial;
- observation provenance (`observed`, `reconstructed`, `inferred`, `missing`);
- classification, subject/team/enterprise scope, authorization epoch, retention, and
  consent; and
- explicit conversion and missingness receipts.

### Environment-owned payloads

The following need typed artifact envelopes and environment-specific media types, not
columns in a universal `events` table:

- browser DOM/accessibility trees, screenshots, cookies/storage state, Playwright
  network traces, and mutable site/database snapshots;
- repository trees, container/VM layers, dependency mirrors, patches, test artifacts,
  and filesystem checkpoints;
- full-duplex audio frames and simulator ticks;
- game/robot/simulator world state;
- provider-native raw responses and opaque server session handles; and
- trainer tensors, tokenizer-specific masks, optimizer state, and distributed engine
  checkpoints.

## Minimal additions to Frankengate

Extend the canonical object rather than introducing a parallel RL schema.

### 1. Required `environment`

```json
{
  "environment_id": "tau2-retail",
  "environment_version": "1.0.1",
  "runtime_digest": "sha256:…",
  "task_dataset": "tau2",
  "task_revision": "…",
  "task_id": "retail-42",
  "seed": 7,
  "reset_parameters": {},
  "initial_state_ref": {"artifact_id": "…", "sha256": "…"},
  "external_dependencies": [],
  "clock_policy": "recorded|frozen|live",
  "network_policy": "blocked|recorded|live"
}
```

`initial_state_ref` may be absent only with a recorded reason. An image tag without an
immutable digest is not reproducible.

### 2. Required `evaluation`

Store evaluations as append-only facts, never overwrite the trajectory outcome:

```json
{
  "evaluation_id": "…",
  "scorer": "tau2-db-check",
  "scorer_version": "sha256:…",
  "rubric_version": "…",
  "target_event_ids": ["…"],
  "dimensions": [{"name": "db_check", "value": 1.0}],
  "aggregate": 1.0,
  "evidence_refs": ["…"],
  "credit_assignment": "terminal|step|token|heuristic",
  "produced_at": "…",
  "provenance": "observed|recomputed|judge|human"
}
```

This takes τ²-bench's evidence breakdown and Agent Lightning's reward targeting without
pretending heuristic attribution is observed truth.

### 3. Required `replay`

```json
{
  "supported_level": "R0|R1|R2|R3",
  "action_source": "recorded|normalized|reconstructed",
  "side_effect_policy": "deny|sandbox|allowlisted",
  "replay_attempts": [{
    "attempt_id": "…",
    "runtime_digest": "…",
    "status": "matched|diverged|infra_error",
    "first_divergent_event_id": "…",
    "observation_comparison": {},
    "evaluation_comparison": {}
  }]
}
```

Infrastructure errors must not become task failures. A divergent replay is evidence, not
a reason to rewrite the original trace.

### 4. Optional `learner`

Keep this sparse and artifact-backed:

- behavior policy/model/checkpoint revision;
- tokenizer revision and chat-template hash;
- sampling parameters and rollout engine version;
- prompt and completion token IDs;
- action/observation/context/warning/loss masks;
- behavior-policy and reference log probabilities;
- token/step/terminal reward alignment;
- curriculum stage, sampler, sampling probability, repetition/group ID; and
- the canonical event IDs from which each training example was projected.

Never require these fields for ordinary user trace mining. Never query arbitrary
pickled/TensorDict payloads in the analytics path.

### 5. Content-addressed artifact references

Every reference needs artifact ID, digest, byte length, media type/schema, compression,
encryption/key version, classification, tenant/team/user scope, authorization epoch,
retention, redaction status, and origin event. PostgreSQL RLS protects the metadata row;
the object fetch path must re-check the same policy. A signed object URL alone is not an
authorization model.

## Failure modes to test before implementation

| Failure | Consequence | Required control |
|---|---|---|
| Treating sequential ATIF as the source graph | Loses overlap, retries, fallback, streaming, and duplex causality | Preserve event DAG; ATIF projection emits loss receipt |
| Treating OTel as environment state | “Replay” cannot recreate browser, DB, repo, or simulator | Required replay manifest and snapshot references |
| Aggregate reward without scorer/evidence | Cannot distinguish task outcome, judge opinion, or shaping reward | Append-only evaluation facts and versioned credit assignment |
| Derived SFT records replace raw evidence | Failed actions and observations disappear; success bias | Canonical raw record remains immutable; training data is a projection |
| Token IDs without tokenizer/template revision | Retokenization or mask alignment is unverifiable | Learner lineage is mandatory whenever token arrays are present |
| Log probabilities without behavior-policy lineage | Invalid off-policy correction and false reproducibility | Policy/checkpoint/sampling metadata and alignment checks |
| Pickle/TensorDict accepted as trusted input | Remote code execution and cross-version failure | Quarantine, scan, convert in sandbox, retain digest only |
| Browser trace stored as ordinary log text | Credential/classified content leaks; Postgres bloat | Sensitive artifact class, encryption, redaction, object storage |
| Environment image identified only by mutable tag | Replay silently changes | Immutable runtime digest and dependency manifest |
| External site/API remains live | Non-deterministic results and unintended side effects | Network fixture or explicit `live` replay classification |
| Reconstructed parent/tool/reward presented as observed | False root-cause and credit claims | Per-field provenance and confidence; no silent repair |
| RLS protects events but not artifacts/evals | Cross-user/team evidence leakage | Same subject scope and authorization epoch on every derived row/ref |
| Curriculum selects related tasks across train/test | Benchmark contamination and inflated learning claims | Task/repository/source grouped splits and corpus lineage |
| Failure/crash traces are discarded | Survivorship bias hides exactly the enterprise friction of interest | Persist all terminal states, including infra errors and truncation |
| Reward attached after response truncation | Credit disappears or lands on wrong token/event | Boundary invariant plus explicit unassigned-reward state |
| Context compression replaces original messages | Diagnosis sees only policy input summary | Preserve immutable raw history and separately version prompt projections |

## Empirical interoperability program

The first experiment should test conversions and replay semantics, not RL performance.
Use one fixture family per distinct claim:

1. **ATIF conformance:** MCP ATIF fixtures for exact tool-call/observation correlation,
   subagent references, copied context, token arrays, and malformed mutations.
2. **OTel causality:** Agent Lightning examples for rollout/attempt/resource mapping,
   linked rewards, missing parents, and concurrent spans.
3. **State and reward evidence:** τ²-bench for initial database state, tool effects,
   verifier dimensions, authentication classification, and duplex flattening.
4. **Action replay:** SWE-agent trajectories in pinned SWE-Gym containers; mutate one
   action, image digest, dependency, and parser configuration independently.
5. **Forensic browser evidence:** BrowserGym/WebArena artifacts; prove rendering works
   while marking exact replay unsupported unless site/database/network fixtures exist.
6. **Episode import:** OpenEnv JSONL; measure which reset, state, time, reward, and
   causal fields need loss-receipt entries.
7. **Learner projection:** the same canonical episode projected separately into SkyRL
   and VERL-shaped batches; verify masks, token alignment, reward placement, and policy
   lineage without making either batch canonical.
8. **Schema-stress corpus:** selected AgentGym environments to prove that unknown
   environment payloads remain usable through typed artifacts without schema churn.

For each source, test `source → canonical → ATIF`, `source → canonical → OTel`, and,
where supported, `canonical → fresh environment replay`. Report:

- observed event/tool/argument/observation preservation;
- lost, reconstructed, and inferred fields;
- causal-edge and concurrency preservation;
- first replay divergence and reason;
- verifier/reward reproducibility;
- token/mask/log-probability alignment;
- storage amplification and artifact deduplication;
- RLS and authorization-epoch leakage attempts; and
- crash, timeout, truncation, and infrastructure-error retention.

An adapter passes only when zero fields disappear silently. “Valid ATIF” and “valid
OTel” are conformance results, not replay or scientific-validity results.

## What not to build

- Do not add MongoDB because Agent Lightning uses it.
- Do not store screenshots, DOMs, Playwright archives, repository snapshots, or model
  tensors in ordinary JSONB event rows.
- Do not make a framework rollout batch the enterprise query schema.
- Do not claim deterministic replay from recorded actions alone.
- Do not collapse multiple reward sources into one mutable `reward` column.
- Do not require token-level RL data for every production trace.
- Do not import arbitrary Python pickle/checkpoint files into an online service.
- Do not create separate ATIF, OTel, RL, and analytics sources of truth.

## Bottom line

The reviewed systems combine well only when their contracts remain layered. Agent
Lightning contributes attempt/resource correlation and reward links; OpenEnv contributes
the action/observation/reset boundary; τ²-bench contributes evidence-backed evaluation
and effect timelines; BrowserGym/WebArena contribute rich forensic artifacts; SWE-agent
contributes action replay; SWE-Gym contributes pinned repository/container evaluation;
SkyRL/VERL contribute optional learner lineage; and AgentGym contributes curriculum and
environment-diversity pressure.

They do **not** combine into a universal replayable record by concatenating their JSON.
The hard missing bridge is a governed environment/replay manifest plus immutable
artifact references and versioned evaluation facts. Add that bridge to Frankengate's
existing loss-aware event graph, then expose ATIF, OTel, and trainer-specific batches as
tested projections. That is the smallest architecture that can support enterprise trace
mining now and credible replay or learning experiments later.
