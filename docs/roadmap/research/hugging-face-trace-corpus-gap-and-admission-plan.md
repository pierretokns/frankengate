# Hugging Face trace corpus gap and admission plan

**Status:** source-pinned admission decision
**Date:** 2026-07-30
**Scope:** the smallest public corpus that can falsify Frankengate trace,
diagnosis, retrieval, replay, and memory claims

## Decision

Do not turn the Hugging Face search into a collection exercise. The current
corpus already covers ordered chat/tool trajectories, step-level diagnosis,
repeated task attempts, OTel-shaped import, real harness diversity, and a small
ATIF fixture. It still does **not** contain a real production trace that combines
branch/DAG structure, retry and provider-fallback lineage, agent delegation,
authorization decisions, replayable environment state, longitudinal memory,
stable users or teams, and independently verified outcomes.

The smallest defensible next corpus is:

1. keep the already admitted selective sources;
2. add only the 4.24 MB ALFWorld `population_runs` shard from
   [MATM](https://huggingface.co/datasets/toeunkim/matm-trajectories/tree/d84d6454fc5fcc337e2527533f484b79cf6f0872)
   for paired retrieval-condition experiments;
3. use
   [CMU Agent Trajectories](https://huggingface.co/datasets/cx-cmu/agent_trajectories)
   as an internal, quarantined multi-benchmark stratum as soon as the current
   Hugging Face account is approved, but do not redistribute its rows, derived
   text, embeddings, or checkpoints while no license is declared;
4. add
   [AgentRx](https://huggingface.co/datasets/microsoft/AgentRx/tree/88e871fecb58b2d090449f37ec80b8865594e0b5)
   only after approval, for multi-agent root-cause labels; and
5. generate a small first-party conformance corpus for branch, retry, fallback,
   delegation, authorization, redaction, duplicate delivery, and replay edges.

No additional large Hugging Face download is presently justified. Public data
cannot validate employee skill gaps, team matching, authorization safety, or
longitudinal learning. Those remain Frankengate-native, consented experiments.

## Corpus admission ledger

| Source | Immutable revision | Declared license | Size or records | Decision | Unique claim it may support | Hard boundary |
|---|---|---:|---:|---|---|---|
| [Nebius SWE-agent](https://huggingface.co/datasets/nebius/SWE-agent-trajectories/tree/68195a1450865274106246d0d0296a1d6807b88e) | `68195a1450865274106246d0d0296a1d6807b88e` | CC-BY-4.0 | 80,036 total; 300 already sampled | **Admit existing sample** | Matched same-task success/failure signal pilot | Coding only; no timestamps, branch edges, authorization, or explicit tool-call IDs |
| [CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d) | `aa213b84ffb6690fc37ca15766d6ca174ec36d4d` | MIT | 3,316 unique; 1,000 verified | **Admit verified manifest; selectively admit raw artifacts** | Human step labels and decisive-step diagnosis | The verified split is contained in full; software tasks only; 25 raw artifacts are absent |
| [MCP ATIF benchmark](https://huggingface.co/datasets/obaydata/mcp-agent-trajectory-benchmark/tree/f4f449d65271abc1e4ccd5157d121a59a1dd38c4) | `f4f449d65271abc1e4ccd5157d121a59a1dd38c4` | Apache-2.0 | 49 raw trajectories | **Admit all** | ATIF v1.2 import and exact/ordered/unordered tool assertions | Tiny, mostly synthetic, linear, and not an environment replay benchmark |
| [AgentTrace](https://huggingface.co/datasets/pagarsky/agent-trace/tree/4b05b2f00eea267a5bb4d841c228059d1bf9ac0c) | `4b05b2f00eea267a5bb4d841c228059d1bf9ac0c` | Apache-2.0 | 1,400 rows; 32.1 MB repository | **Admit all** | First-class tool timing, exit status, resource telemetry, deterministic fixture, and bounded replay feasibility | No task-correctness verdict, expected output/state digest, seed, memory intervention, or shared proposal/execution ID |
| [Exgentic v1](https://huggingface.co/datasets/Exgentic/agent-llm-traces/tree/70036b93a04e61b0ea2706a68b962f4f26774587) | `70036b93a04e61b0ea2706a68b962f4f26774587` | CDLA-Permissive-2.0 | 1,781 traces; 984 MB | **Admit a grouped, stratified sample** | OTel IDs, parent IDs, timing, GenAI attributes, model/harness transfer | In the audited sample every span was a chat operation; tool events were embedded in messages, not separately timed tool spans |
| [SPARK PDI](https://huggingface.co/datasets/EtaYang10th/SPARK_PDI_Trajectory/tree/02e297a366c6a56eb754852cd15a78838546d965) | `02e297a366c6a56eb754852cd15a78838546d965` | MIT | 64 observed `attempts.json`; 16 fail/error→pass sequences | **Admit recovery pairs and their artifacts** | Attempt contrast, reflection, memo, and `SKILL.md` scoring | Later attempts are observational and confounded by feedback, reflection, prompt, model, and environment changes |
| [Trace Commons](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf) | `112ebd4d03ce852b00e935d523107c3d0c9a65bf` | CC-BY-4.0 compilation; embedded content may differ | 30 sessions; 207 MB | **Quarantine, then admit parser/reality-check rows** | Ecologically real native sessions across human coding harnesses | Volunteer bias, sparse outcomes, best-effort anonymization, content-license and erasure risk |
| [MATM](https://huggingface.co/datasets/toeunkim/matm-trajectories/tree/d84d6454fc5fcc337e2527533f484b79cf6f0872) | `d84d6454fc5fcc337e2527533f484b79cf6f0872` | Apache-2.0 | 15,696 total; 2,130-row ALFWorld evaluation shard is 4,237,969 bytes | **Admit ALFWorld evaluation shard only** | Same task/model under no retrieval and five reranked retrieval-depth conditions | No retrieved-item IDs or content, no memory lineage, no timestamps, and no replay snapshot |
| [CMU Agent Trajectories](https://huggingface.co/datasets/cx-cmu/agent_trajectories/tree/88e2af82c116a9a57f29be6f21b9924da081c2bd) | `88e2af82c116a9a57f29be6f21b9924da081c2bd` | **NOASSERTION** | 8,653 retained; approximately 2 GB download shown by the Hub | **Access-quarantine only; analyze once approved** | Six benchmark strata, five models, four independent passes, external/benchmark rewards, failures and trace metadata | Current authenticated account receives “requires approval”; no declared license prevents a redistribution/training-right claim but not analysis; 1,445 incomplete/crashed/truncated traces were removed; runtime tool menu is not reconstructable |
| [AgentRx](https://huggingface.co/datasets/microsoft/AgentRx/tree/88e871fecb58b2d090449f37ec80b8865594e0b5) | `88e871fecb58b2d090449f37ec80b8865594e0b5` | CC-BY-4.0 | under 1,000 rows; 4.73 MB | **Access-quarantine** | Multi-agent failure category, failing actor, and designated root cause | Failed trajectories only; current account lacks approval |

Dataset tags, files, revision hashes, and stored sizes above were checked with
the authenticated Hugging Face API on 2026-07-30. A repository size is not
decoded memory size. The study records byte hashes for every downloaded file.

## The exact coverage gap

Legend: **O** = observed as a first-class source field; **R** = reconstructible
from source content but not independently timed or attributed; **—** = absent or
not reliable enough for the claim.

| Required evidence | ATIF MCP | AgentTrace | Exgentic v1 | CodeTraceBench | SPARK | MATM | CMU retained | Trace Commons |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Stable trace/session ID | O | O | O | O | O | R | O | O |
| Ordered steps/messages | O | O | O | O | O | O | O | O |
| Per-step wall-clock time | O | O | O | — | R | — | R | varies |
| Tool name, arguments, result | O | O | R | R | R | action/observation | O | varies |
| Separate proposal → authorization → execution → result → state delta | — | execution/result only | — | — | — | — | — | — |
| Tool duration, status, exit code | — | O | — in audited sample | — | varies | — | — | varies |
| Parent/child span topology | — | span sequence | O | stage sequence | — | — | — | varies |
| Explicit alternative branch or pruned path | — | — | — | — | — | — | — | varies, not portable |
| Retry linked to the failed operation | — | R | R | R | attempt-level only | — | R | varies |
| Provider/model fallback edge and reason | — | — | — | — | — | — | — | — |
| Delegating actor, target, handoff, and join | — | — | — | — | — | — | — | varies, not normalized |
| Environment version, initial state, seed, and replay handle | — | partial fixture | — | partial artifact | varies | task ID only | benchmark-dependent | — |
| Step reward and final externally checked outcome | — | task-dependent | status, not a uniform reward | O | attempt outcome | O | O | sparse |
| Repeated independent runs of the same task/model | — | up to four run IDs | varies | varies | O | six retrieval arms | up to four passes | — |
| Retrieved memory IDs, version, rank, score, and content | — | — | — | — | artifact only | **—** | — | — |
| Memory state before/after an episode | — | — | — | — | artifact snapshots only | — | — | — |
| Stable real user/team/tenant across sessions | — | — | — | — | — | — | — | — |
| Classification, policy, consent, and authorization epoch | — | — | — | — | — | — | — | — |
| Intervention exposure and delayed business outcome | — | — | — | — | — | retrieval condition only | — | — |

The table prevents a common mistake: a dataset containing the text of a tool
call does not provide tool execution telemetry; repeated attempts do not imply
memory; multiple agents do not imply real teams; and benchmark reward does not
imply a delayed enterprise outcome.

## ATIF-specific finding

A pinned audit of
[`accountant/trajectory.json`](https://huggingface.co/datasets/obaydata/mcp-agent-trajectory-benchmark/blob/f4f449d65271abc1e4ccd5157d121a59a1dd38c4/accountant/trajectory.json)
found:

- top-level `schema_version`, `session_id`, `agent`, `steps`, and
  `final_metrics`;
- linear integer `step_id` values and one timestamp per step;
- `user` and `agent` sources;
- model, usage, tool-call ID, function name, arguments, observation results, and
  source-call IDs; and
- total prompt tokens, completion tokens, and steps.

The sample joins a parallel set of tool calls and all returned observations into
the same agent step. It does not separately record authorization, tool start,
tool end, tool error taxonomy, environment mutation, retry cause, branch edge,
fallback, delegation, or reward. Its SHA-256 is
`981192b1f951d0e06abe64e10ee3ea2dd73cdbb25eb088809f9bd289b6279a94`.

Therefore ATIF is a good portable **evaluation projection**, not Frankengate's
lossless storage authority. The canonical importer must:

1. preserve the complete ATIF object and unknown fields in JSONB;
2. split tool proposals and observations into derived canonical events linked
   by `tool_call_id`;
3. label their timing and authorization fields `unknown`, never infer them;
4. emit an information-loss receipt; and
5. retain the original step as the evidence source for every derived event.

Frankengate-native DAG events may be projected to ATIF for AgentEvals-style
assertions, but a round trip is not expected to preserve governed execution
semantics.

## The one admitted addition: MATM ALFWorld

The [MATM card](https://huggingface.co/datasets/toeunkim/matm-trajectories)
describes action/observation/reasoning trajectories from ALFWorld and WebArena
under `no_retrieval`, dense retrieval, and reranked retrieval conditions. A
pinned local audit of `alfworld/population_runs.parquet` found:

- 2,130 rows, 355 unique tasks, and 34 models;
- exactly six rows per task;
- the same model for all six conditions of each task;
- one no-retrieval arm and `rerank_{1,5,10,15,20}` arms;
- overall success `42.8%`;
- by condition, success ranged only from `42.0%` to `43.7%`; and
- mean steps ranged from `12.1` to `12.2`.

The file SHA-256 is
`626e2e6351d763739b0e2695a1bc442e1c851c1153c44301017739e3bd1155aa`.
Those near-null aggregate differences are useful: MATM must not be admitted on
the assumption that more retrieved traces help.

The dataset does **not** retain retrieved memory IDs, content, rank scores,
source lineage, or the prompt after memory injection. It can answer:

> Did this retrieval condition change observed success for the same task/model?

It cannot answer:

> Which memory helped, whether it was authorized, whether the model used it, or
> what should be consolidated into a skill?

Admission is full for the 4.24 MB ALFWorld evaluation shard. Hold the 100.46 MB
WebArena evaluation shard until the ALFWorld paired analysis, missingness audit,
and condition-independence review pass. Do not download either prepopulation
shard merely to imply lineage that the evaluation rows do not contain. If item
attribution becomes necessary, rerun the open MATM mechanism with retrieved-item
IDs and prompt construction captured in Frankengate-native events.

## CMU: use plan and survivorship correction

The [CMU card](https://huggingface.co/datasets/cx-cmu/agent_trajectories)
documents 8,653 retained trajectories:

| Benchmark | Retained | Average turns | Reward | Reported retained success |
|---|---:|---:|---|---:|
| tau2bench | 984 | 32.0 | binary | 39.1% |
| swebench | 747 | 69.6 | binary | 21.4% |
| terminalbench | 1,429 | 33.4 | binary | 19.2% |
| mathhay | 1,324 | 3.8 | binary | 46.5% |
| search | 3,270 | 15.0 | binary | 22.1% |
| mcpbench | 899 | 26.1 | continuous 0–10 | 13.1% |

Each task was run from scratch up to four times per model, across DeepSeek-R1,
DeepSeek-V3.2, Gemini-2.5-Flash, Qwen3-235B, and Qwen3-Next. The 14 fields
include benchmark/domain/task/model/pass, messages, reward, evaluator details,
trace metadata, cleaning details, and pass completeness. `trace_meta` may contain
steps, rounds, tokens, timestamps, errors, and benchmark-specific servers.
The card explicitly says each pass begins with no memory.

The current account is authenticated but the CLI returns:

```text
Error: Access denied. This repository requires approval.
```

User approval to use the corpus does not technically complete the Hugging Face
contact-sharing gate. Once that gate is accepted, use the following bounded
protocol.

### Initial internal sample

1. Pin revision `88e2af82c116a9a57f29be6f21b9924da081c2bd`
   and hash every source file.
2. Download JSONL plus the removal sidecars, not both JSONL and duplicate
   Parquet.
3. Select five task/model groups per benchmark and model, with all four passes:
   \(6 \times 5 \times 5 \times 4 = 600\) trajectories.
4. Within each benchmark/model, stratify groups into all-fail, mixed-outcome,
   and all-success where available. Select by a published hash, not length.
5. Split by task ID, never trajectory or message. No task may cross
   train/validation/test.
6. Keep `eval_details` hidden from selectors and judges except when computing
   the frozen outcome metric.
7. Preserve the raw messages and `trace_meta`; derive tool events only when a
   source tool-call ID exists and mark reconstructions.

### Removed-trace audit

The released data removed 1,445 of the original 10,098 runs, or 14.3%:

- 121 empty/API-no-response traces;
- 193 crashes before the first response;
- 15 repeated API-failure/harness-gave-up traces; and
- 1,116 mid-conversation truncations.

All removed records have reward zero except 61 records with explicitly
unreliable positive rewards. The released dataset additionally guarantees that
every retained trace ends with an assistant message. This is direct selection
on completion and failure, not random missingness.

Using the card's rounded benchmark rates, the retained weighted success rate is
approximately 26.3%. Treating all removed runs as failures lowers the original
collection estimate to approximately 22.5%, a 3.8-point difference. The paper
must not report a retained-only rate as the collection rate.

Required analyses:

1. ingest all removal-log rows into a separate `trace_missingness` table;
2. report removal probability by benchmark, model, pass, task family, observed
   prefix length, and error type where present;
3. report both retained-only and “removed as failure” bounds;
4. use inverse-probability weighting only if the selection model is calibrated
   on observed pre-removal fields;
5. treat no-response, crash, repeated failure, and truncation as first-class
   deterministic failure signals; and
6. prohibit decisive-step, semantic-memory, or tool-root-cause claims for rows
   whose relevant content does not exist.

### Legal and publication gate

The repository declares no license in its card or API tags. Until the publisher
adds one or counsel confirms permitted use:

- internal mechanism testing is quarantined from distributable artifacts;
- do not commit raw rows, source-derived text, embeddings, model weights, or
  replay prompts;
- commit only manifest hashes, code, aggregate statistics, and synthetic
  fixtures; and
- label paper tables “internal exploratory—license pending” or omit them from a
  public release.

## Hugging Face sources that do not close the gap

### Hermes traces

The native-format
[five-session Hermes sample](https://huggingface.co/datasets/cfahlgren1/hermes-agent-trace-samples-2026-06-05/tree/80c32a72cc94906492d67f34353f477f9e38b182)
is useful only as a parser fixture. It is Apache-2.0, 284 KB, synthetic, and has
five sessions. The
[quality-filtered Hermes SFT corpus](https://huggingface.co/datasets/DJLougen/hermes-agent-traces-filtered/tree/f91a8ef669194408a706741cd6f32a1686a8fd78)
has 3,679 Apache-2.0 conversations but was selected by automated reasoning-style
markers. It lacks independent outcomes, longitudinal state, intervention
assignment, and source-environment replay.

**Decision:** admit at most the five raw sessions as format conformance
fixtures. Kill both as evidence that skill saving or memory improves work.
Fine-tuning examples are not longitudinal learning experiments.

### Synthetic multi-agent failure corpora

[Who&When Pro](https://huggingface.co/datasets/tmpxv7/who-when-pro/tree/16b24b2a453b413be9d5f538fe9a99d00ef4c448)
contains over 13,500 CC-BY-4.0 multi-agent traces with one injected error and a
known actor/step/mode, but its 3.50 GB bundle is unnecessary for the first
study. CodeTraceBench provides human step labels, AgentRx is the smaller
multi-agent attribution complement, and Frankengate can seed known topology
mutants locally.

[Open Agent Traces](https://huggingface.co/datasets/juliensimon/open-agent-traces/tree/dff8ed6331f5abf9ec8ad825088eeb4caa6715a4)
contains 17,019 generated OCEL events across 500 workflows with inter-agent
messages. Retain it only as a small process-mining/conformance control; never
use its synthetic “enterprise” domains as evidence about employees or teams.

**Decision:** kill Who&When Pro for the initial corpus; keep Open Agent Traces
optional and synthetic-labeled. Revisit only if the small root-cause and local
mutation tests expose a multi-agent topology failure they cannot measure.

### Bulk aggregations and successful SFT corpora

- [Exgentic v2](https://huggingface.co/datasets/Exgentic/agent-llm-traces-v2/tree/4b8ad4ab198438e5a170f9171c19c6a2cf7c1814)
  has 10,057 sessions but declares no license. Its own pinned build description
  says it collapses failed-retry groups, drops the failed spans, shifts later
  timestamps backward, removes `invoke_agent` and `execute_tool`, and excludes
  simulator and judge context. That is useful for chat replay but destructive
  for Frankengate's retry, latency, tool-root-cause, and evaluator-provenance
  questions. Kill it for this study; more rows do not recover removed evidence.
- [Neulab Agent Data Collection](https://huggingface.co/datasets/neulab/agent-data-collection/tree/31a76bfb0124d77ae7322eabbb0171bf11ee2c67)
  is approximately 649 GB and has per-source licenses and semantics. It is a
  catalog, not one admissible dataset.
- [Open-SWE-Traces](https://huggingface.co/datasets/nvidia/Open-SWE-Traces/tree/9c0e4579a4ee0effa3e5f7a552494a045f29377d)
  is useful later for scale but redundant with the frozen coding strata in the
  first mechanism study.
- Successful SFT-only corpora, including web-agent and Hermes reasoning sets,
  are selected on the desired behavior and cannot estimate failure prevalence,
  recovery, or memory treatment effects.
- Small self-described “real-world” reliability datasets without external
  verifiers, source-environment provenance, or an auditable generation process
  remain excluded regardless of row count.

## First-party conformance corpus instead of another download

No searched Hugging Face source closes the graph/governance gap. Generate a
small source-controlled fixture set with one positive and at least one mutant
for each condition:

| Fixture | Required events and edges | Primary assertion |
|---|---|---|
| Parallel tools | proposal, authorization, two executions, two results, join | unordered tools plus explicit join; no invented serial order |
| Retry | failed execution → retry decision → second execution | same operation lineage; two attempts preserved |
| Provider fallback | provider error → policy decision → alternate provider | requested and selected provider/model plus fallback reason |
| Delegation | parent proposal → child task → child trace → returned artifact → join | actor, role, parent/child, and evidence lineage |
| Authorization denial | proposal → scope/epoch decision → denied result | no execution event may exist |
| State change | tool result plus independently captured before/after state | result text is not treated as state proof |
| Branch and resume | branch fork, abandoned path, checkpoint, resumed path | all edges survive import and reordering |
| Stream interruption | partial chunks → transport error → terminal status | incomplete output never becomes successful final response |
| Redaction/deletion | classified payload → redacted projection → tombstone | lineage remains, inaccessible payload cannot be retrieved |
| Duplicate/out-of-order delivery | duplicated events with sequence/version | idempotent import and deterministic DAG hash |

These fixtures validate schema preservation. They are not evidence about how
often a production behavior occurs.

## Frozen admission and kill gates

### Admit a source only if

- revision, license/terms, file hashes, and source provenance are recorded;
- the field needed for the claim is observed or explicitly reconstructed;
- task/model/harness/outcome identities support leakage-safe grouping;
- tool definitions and results have a documented relationship to the run;
- evaluator independence and reward meaning are known;
- privacy and embedded-content scans pass;
- unsupported events are quarantined rather than flattened; and
- its unique mechanism cannot be tested by a smaller admitted source or local
  fixture.

### Quarantine when

- approval or contact-sharing is pending;
- license or embedded-content rights are unclear;
- data may contain private code, secrets, or personal data;
- runtime tool menus, environment snapshots, or outcomes are only partially
  reconstructible;
- failed/incomplete runs were removed; or
- a transformation dropped retries, tool spans, failure groups, branches, or
  evaluator context.

### Kill from the first study when

- the source is only a larger duplicate of an admitted mechanism;
- it contains successful demonstrations only;
- “reasoning quality,” “skill,” or “recovery” labels are synthetic heuristics
  without an external verifier;
- multiple runs are independent best-of-k attempts but advertised as learning;
- multiple model agents are advertised as evidence about human teams;
- no stable task ID exists for group splitting;
- a viewer projection is the only accessible representation;
- missing outcomes would have to be replaced with an LLM judge; or
- raw download and operational cost exceed the unique information gained.

## What the public corpus can and cannot answer

With the admitted sources and first-party fixtures, Frankengate can test:

- loss-aware import from ATIF, native harness, OTel-shaped, and action/observation
  records;
- cheap trace selection and decisive-step localization;
- exact, ordered, unordered, invariant, and semantic retrospective assertions;
- same-task failure/recovery contrasts;
- condition-level effects of retrieved trajectory context in ALFWorld;
- outcome and failure robustness across benchmark, model, and harness strata;
- parser reality checks on volunteered sessions; and
- whether every governed DAG event survives storage and projection.

It still cannot infer from public data:

- which employees perform similar work;
- whether a person is missing a cloud or domain skill;
- which two real people should collaborate;
- whether a memory was authorized at retrieval time;
- whether a suggestion caused delayed improvement;
- whether private organizational terminology needs a custom embedding; or
- whether a consolidated memory remains valid after policy, code, or
  classification changes.

Those questions require stable consented principal IDs, tenant/team scope,
classification and authorization epochs, task ontology, intervention exposure,
memory version and provenance, environment/tool version, and downstream
outcomes captured by Frankengate itself. Public traces validate mechanisms;
they do not validate enterprise conclusions.

## Reproducibility notes

The two new spot audits used only immutable files:

```text
MATM revision:
d84d6454fc5fcc337e2527533f484b79cf6f0872
alfworld/population_runs.parquet:
4,237,969 bytes
SHA-256:
626e2e6351d763739b0e2695a1bc442e1c851c1153c44301017739e3bd1155aa

MCP ATIF revision:
f4f449d65271abc1e4ccd5157d121a59a1dd38c4
accountant/trajectory.json:
26,007 bytes
SHA-256:
981192b1f951d0e06abe64e10ee3ea2dd73cdbb25eb088809f9bd289b6279a94
```

Every downstream manifest must preserve dataset ID, revision, source path,
source hash, source license/terms, observed/reconstructed/unknown field status,
task-group split, and raw-to-canonical information-loss receipt.

## Primary sources

- [Hugging Face agent-trace format and privacy warning](https://huggingface.co/docs/hub/en/agent-traces)
- [CMU Agent Trajectories card and processing audit](https://huggingface.co/datasets/cx-cmu/agent_trajectories)
- [MATM pinned dataset](https://huggingface.co/datasets/toeunkim/matm-trajectories/tree/d84d6454fc5fcc337e2527533f484b79cf6f0872)
- [MCP ATIF benchmark pinned dataset](https://huggingface.co/datasets/obaydata/mcp-agent-trajectory-benchmark/tree/f4f449d65271abc1e4ccd5157d121a59a1dd38c4)
- [AgentTrace pinned dataset](https://huggingface.co/datasets/pagarsky/agent-trace/tree/4b05b2f00eea267a5bb4d841c228059d1bf9ac0c)
- [Exgentic v1 pinned dataset](https://huggingface.co/datasets/Exgentic/agent-llm-traces/tree/70036b93a04e61b0ea2706a68b962f4f26774587)
- [Exgentic v2 pinned dataset and destructive filtering disclosure](https://huggingface.co/datasets/Exgentic/agent-llm-traces-v2/tree/4b8ad4ab198438e5a170f9171c19c6a2cf7c1814)
- [CodeTraceBench pinned dataset](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d)
- [SPARK PDI pinned dataset](https://huggingface.co/datasets/EtaYang10th/SPARK_PDI_Trajectory/tree/02e297a366c6a56eb754852cd15a78838546d965)
- [Trace Commons pinned dataset and privacy/rights caveats](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf)
- [AgentRx pinned dataset](https://huggingface.co/datasets/microsoft/AgentRx/tree/88e871fecb58b2d090449f37ec80b8865594e0b5)
- [Hermes raw-session sample](https://huggingface.co/datasets/cfahlgren1/hermes-agent-trace-samples-2026-06-05/tree/80c32a72cc94906492d67f34353f477f9e38b182)
- [Who&When Pro pinned dataset](https://huggingface.co/datasets/tmpxv7/who-when-pro/tree/16b24b2a453b413be9d5f538fe9a99d00ef4c448)
- [Open Agent Traces pinned dataset](https://huggingface.co/datasets/juliensimon/open-agent-traces/tree/dff8ed6331f5abf9ec8ad825088eeb4caa6715a4)
