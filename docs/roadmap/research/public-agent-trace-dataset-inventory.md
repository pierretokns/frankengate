# Public Agent-Trace Dataset Inventory for Frankengate

**Status:** source-pinned admission review
**Date:** 2026-07-30
**Scope:** Hugging Face datasets for canonicalization, trace mining, diagnosis,
retrieval, eval construction, memory, and replay experiments

## Verdict

No public corpus is a complete production OpenTelemetry/OpenInference agent graph with
chat, first-class tool execution, retrieval, retries, outcomes, governed identities,
authorization epochs, and longitudinal enterprise context.

That does not block a useful study. It requires a portfolio in which each dataset is
admitted only for the claim its observed fields support:

- **CodeTraceBench** for human-labeled failure localization and redundant exploration;
- **SPARK PDI** for limited observational fail→partial→pass contrasts and generated
  `SKILL.md` artifacts;
- **pagarsky/agent-trace** for deterministic tool replay and telemetry;
- **Exgentic v1** for OTel-shaped ingestion and chat-level signals;
- **MCP Agent Trajectory Benchmark** for ATIF conversion and stored-trace assertions;
- **Trace Commons** for a small, biased but ecologically real harness check; and
- **Open Agent Traces** for synthetic process-mining controls.

CMU Agent Trajectories is scientifically attractive but cannot enter the publishable
corpus until its missing license is clarified. Its removal of incomplete/crashed traces
also creates survivorship bias around Frankengate's target failure modes.

## Admission rules

Before any model call, pin:

1. dataset ID and immutable revision;
2. license and redistribution rights for every configuration;
3. observed versus generated/reconstructed fields;
4. task, attempt, trajectory, model, harness, and tool identities;
5. outcome/evaluator semantics and independence;
6. timestamps, branch/retry edges, telemetry, and missingness;
7. privacy, secret, source-code, and personal-data risk;
8. known removals, publication bias, and benchmark contamination; and
9. task/repository/source grouping needed to prevent split leakage.

A Hugging Face viewer or download URL does not establish a license. Missing outcomes
remain unknown; they are not replaced silently by an LLM judge.

## Recommended pilot portfolio

| Dataset | Pinned revision | License | Use | Principal limitation |
|---|---|---|---|---|
| [NJU-LINK/CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench) | `aa213b84ffb6690fc37ca15766d6ca174ec36d4d` | MIT | Failure localization, stagnation, redundant exploration, task similarity | Software engineering only |
| [EtaYang10th/SPARK_PDI_Trajectory](https://huggingface.co/datasets/EtaYang10th/SPARK_PDI_Trajectory) | `02e297a366c6a56eb754852cd15a78838546d965` | MIT | Repeated attempts, recovery contrasts, procedure and `SKILL.md` comparison | Only 16 observed fail/error→pass sequences; teacher/reflection confounding |
| [pagarsky/agent-trace](https://huggingface.co/datasets/pagarsky/agent-trace) | Pin at import | Verify in manifest | Tool calls, errors, timing/resource telemetry, deterministic replay | Narrow synthetic programming and shell tasks |
| [Exgentic/agent-llm-traces](https://huggingface.co/datasets/Exgentic/agent-llm-traces) | `70036b93a04e61b0ea2706a68b962f4f26774587` | Verify in manifest | OTel-shaped ingestion, chat signals, replay projection | Tool activity is inside messages rather than first-class tool spans |
| [obaydata/mcp-agent-trajectory-benchmark](https://huggingface.co/datasets/obaydata/mcp-agent-trajectory-benchmark) | `f4f449d65271abc1e4ccd5157d121a59a1dd38c4` | Verify in manifest | ATIF conversion and exact/ordered/unordered AgentEvals assertions | Tiny and mostly synthetic |
| [trace-commons/agent-traces](https://huggingface.co/datasets/trace-commons/agent-traces) | Pin at import | Per-source audit | Human coding sessions across Claude Code, Codex, Pi, Cursor, and OpenCode | 30 volunteer sessions; privacy risk, selection bias, weak outcomes |
| [juliensimon/open-agent-traces](https://huggingface.co/datasets/juliensimon/open-agent-traces) | Pin at import | Verify in manifest | Process-mining and invariant controls | Fully synthetic |
| [microsoft/AgentRx](https://huggingface.co/datasets/microsoft/AgentRx) | Pin after approval | Access terms apply | Decisive-step and root-cause ground truth | Gated; current authenticated account lacks approval |

The first selective download should remain roughly 3,000–4,000 traces and 1–2 GB. Do
not download a collection wholesale merely because it exists.

## Source-specific findings

### CodeTraceBench

The dataset has 3,316 unique traces, not 4,316. The 1,000-row `verified` split is
contained within `full`; adding the advertised split sizes double-counts it.

The verified subset is unusually valuable because human annotations mark incorrect
actions and redundant/unhelpful exploration. It supports:

- trace informativeness and signal-selection labels;
- decisive-step localization;
- friction categories such as redundant exploration and stagnation;
- task-similarity hard negatives; and
- comparison of deterministic versus judge-assisted diagnosis.

It does not establish enterprise transfer or human skill.

An aggregate query against the pinned 1 MB `verified` Parquet found 1,000 rows, 504
solved trajectories, a mean 46.5 steps and 6.74 stages, and 405 trajectories with at
least one incorrect/error stage. The nested annotations contain 1,695 `incorrect` and
224 `unuseful` step labels. This is large enough for task-level diagnosis and
signal-selection splits without downloading the repository's per-run tarballs.

### SPARK PDI Trajectory

The card reports 86 tasks, while the pinned repository contains 69 task directories and
64 `attempts.json` files. Thirty tasks have multiple attempts; 16 contain an observed
fail/error→pass sequence.

Those 16 sequences can test ordered recovery-delta extraction and compare raw attempts,
reflections, memos, and distilled `SKILL.md`. They cannot establish causal learning:
later attempts may differ in teacher feedback, prompt/reflection, model state, or
environment. The `SKILL.md` is an artifact to score, not a gold procedure.

### pagarsky/agent-trace

This narrow corpus is the best pilot substrate for:

- exact tool-call and error preservation;
- timing and resource telemetry;
- mutation of ordered/unordered assertions; and
- randomized no-memory/relevant-memory/placebo replay with deterministic verification.

Its narrow local-model programming tasks limit external validity, which is acceptable
for a causal mechanism pilot.

### Exgentic v1

This is the closest substantial OTel-shaped public source. A 100-session audit found
2,188 spans, all with `gen_ai.operation.name="chat"`. Tool activity is embedded in
messages rather than represented as independently timed tool spans.

It can test OTel ingestion, trace/session grouping, chat-level Signals, and information-
loss receipts. It cannot independently validate tool latency, authorization, or
tool-root-cause analysis. Any derived tool event must be marked reconstructed.

### MCP Agent Trajectory Benchmark

The Dataset viewer exposes 38 summary rows, while the repository contains 49 ATIF
trajectory files. The raw files—not the viewer projection—are needed for:

- source-to-ATIF-to-canonical loss testing;
- exact event and argument assertions;
- ordered and unordered tool-use assertions; and
- mutation testing.

The small, synthetic corpus is a conformance fixture, not a general performance sample.

### Trace Commons

Thirty donated real sessions are insufficient for a benchmark leaderboard, but they
are the strongest reality check for:

- importer diversity across human coding harnesses;
- organically occurring interruptions and friction;
- exact identifier preservation; and
- failure of conclusions learned only from synthetic environments.

Volunteer selection, best-effort anonymization, private-code leakage, absent outcomes,
and tiny sample size must be reported. Raw records require a privacy scan and may need
quarantine.

### Open Agent Traces

Fully synthetic traces are useful positive/negative controls for process mining,
invariants, branch/order preservation, and known injected anomalies. Synthetic
regularity must not be reported as evidence about real users.

## Expanded paper corpus

After the pilot stabilizes:

- add selected partitions from
  [NVIDIA Open-SWE-Traces](https://huggingface.co/datasets/nvidia/Open-SWE-Traces),
  revision `9c0e4579a4ee0effa3e5f7a552494a045f29377d`;
- expand CodeTraceBench and Exgentic v1;
- admit uniformly licensed sources from
  [Thoughtworks Agentic Coding Trajectories](https://huggingface.co/datasets/thoughtworks/agentic-coding-trajectories);
- select individual licensed configurations from
  [Neulab Agent Data Collection](https://huggingface.co/datasets/neulab/agent-data-collection);
  never download the roughly 649 GB collection wholesale; and
- admit AgentRx after its terms are accepted.

Open-SWE-Traces contains 207,489 synthetic trajectories across multiple harnesses and
models, roughly 18.3 GB compressed and 60.5 GB decoded. It is an expansion corpus, not
the first download.

## Hold or exclude

| Dataset | Decision | Reason |
|---|---|---|
| [cx-cmu/agent_trajectories](https://huggingface.co/datasets/cx-cmu/agent_trajectories) | Hold | Missing declared license and gated access; 1,445 incomplete/crashed/truncated trajectories—14.3% of the original collection—were removed |
| [Exgentic v2](https://huggingface.co/datasets/Exgentic/agent-llm-traces-v2) | Hold | No declared license; deliberately removes `invoke_agent`, `execute_tool`, failed-retry groups, and simulator/judge spans |
| [agent-evals/hal_traces](https://huggingface.co/datasets/agent-evals/hal_traces) | Hold | No card/license, malformed viewer, roughly 161 GB stored |
| Full Neulab collection | Exclude as one corpus | Per-source licenses and semantics; roughly 649 GB |
| [Agent Trace Sentiment](https://huggingface.co/datasets/davanstrien/agent-trace-sentiment) | Weak-label comparison only | Synthetic sentiment labels are not diagnosis ground truth |

The CMU corpus remains methodologically useful for private exploration because it has
8,653 trajectories, six benchmarks, multiple models, up to four passes, and outcome
labels. It must not enter a released dataset or paper artifact without license
clarification, and results must model its failure-removal selection bias.

## Concept-to-dataset mapping

| Mechanism | Best evidence |
|---|---|
| AgentRx taxonomy and decisive-step localization | CodeTraceBench verified, AgentRx, pagarsky |
| Signals rephrasing/stagnation/loops/disengagement | CodeTraceBench, Exgentic v1, Trace Commons |
| AgentEvals exact/ordered/unordered/semantic assertions | MCP ATIF, pagarsky, Exgentic projection |
| ReasoningBank success/failure experience | SPARK; selected matched Open-SWE outcomes; CMU only after licensing |
| Dreams/procedural consolidation | SPARK attempts, memos, and `SKILL.md` artifacts |
| Task similarity and skill retrieval | CodeTraceBench categories, Open-SWE metadata, selected ADP domains |
| Graphiti time/contradiction behavior | Public support is weak; use controlled fact-change and expiry injections |
| Human friction and repeated attempts | Trace Commons for realism; SPARK for limited sequences |
| Process mining and invariants | Open Agent Traces synthetic controls |
| OTel ingestion | Exgentic v1, with tool reconstruction explicitly typed |

## What public corpora cannot establish

No listed source can directly answer:

- which real employees should collaborate;
- whether a person lacks a particular skill;
- whether a suggestion caused better work;
- whether a memory remained valid through policy/system changes;
- whether retrieved evidence was authorized at use time; or
- whether an intervention improved delayed business outcomes.

Those require consented Frankengate-native longitudinal data with stable governed
identities, team/task ontology, classification and authorization epochs, tool
permissions, environment state, intervention exposure, and downstream outcomes.

“Skill gap” must initially mean retrieval of task-relevant capability evidence, not an
assertion about a person. SPARK recovery is observational; repeated independent passes
in other datasets do not establish learning.

## Reproducible loading examples

```python
from datasets import load_dataset

verified = load_dataset(
    "NJU-LINK/CodeTraceBench",
    revision="aa213b84ffb6690fc37ca15766d6ca174ec36d4d",
    split="verified",
)

exgentic = load_dataset(
    "Exgentic/agent-llm-traces",
    revision="70036b93a04e61b0ea2706a68b962f4f26774587",
    split="train",
    streaming=True,
)

open_swe = load_dataset(
    "nvidia/Open-SWE-Traces",
    "sweagent",
    split="minimax_m25",
    revision="9c0e4579a4ee0effa3e5f7a552494a045f29377d",
    streaming=True,
)
```

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="EtaYang10th/SPARK_PDI_Trajectory",
    repo_type="dataset",
    revision="02e297a366c6a56eb754852cd15a78838546d965",
    allow_patterns=[
        "all_model_pdi/*/attempts.json",
        "all_model_pdi/*/trajectory.jsonl",
        "all_model_pdi/*/SKILL.md",
    ],
)

snapshot_download(
    repo_id="obaydata/mcp-agent-trajectory-benchmark",
    repo_type="dataset",
    revision="f4f449d65271abc1e4ccd5157d121a59a1dd38c4",
    allow_patterns=["*/trajectory.json"],
)
```

Split by task or benchmark instance—not trajectory—so identical tasks across models or
attempts cannot cross folds. Treat model reasoning as an artifact, never observed
causal ground truth.
