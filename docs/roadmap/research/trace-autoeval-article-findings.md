# Trace Autoeval: article findings and FrankenGate application

**Status:** design input, not a production validation claim  
**Source:** [Amar Singh, “How to evaluate models without actually running them”](https://x.com/amarsvs/status/2087215028860747960?s=46)  
**Reviewed:** 2026-08-12

## Why this matters

The article describes a simulation-free, off-policy method for estimating how a
new candidate model would perform on tasks already handled by an incumbent model.
It uses the incumbent's recorded traces rather than rerunning the agent in the
real environment or building a full environment simulator. This is the most
direct match for FrankenGate's proposed trace-native Autoeval workflow.

The article's target is narrower than a general production evaluator: it estimates
task-family model rankings from sampled next-action decisions. It does not prove
external side effects, exact future trajectories, causal improvement, or that the
method transfers unchanged to every agent workload.

## Reported recipe

1. Select up to five deterministic checkpoint positions per trace, always including
   the first and last and spacing interior checkpoints evenly.
2. Build a neutral prefix. Keep the original task instruction and controller
   protocol, previous tool calls as factual operations with exact arguments, bounded
   observations returned by the real environment, and later user messages. Remove
   the incumbent model's earlier assistant prose and explicit reasoning so the
   candidate is not forced to continue the incumbent's policy or narrative.
3. Ask the candidate model for the next protocol action using the available tool
   definitions, without executing real tools or mutating the real environment.
4. Judge **action value**: whether the action raises or lowers the probability of
   eventually satisfying the task-family rubric. This is different from judging
   whether the action is locally competent or syntactically clean.
5. Aggregate checkpoint scores within each trace first, then aggregate traces and
   task families. Preserve uncertainty, missingness, and model/task-family slices.

## Findings reported by the article

Across the author's matched experiment, neutral reconstruction reduced mean absolute
error from 1.96 to 1.54 (a reported 21% reduction), increased rank correlation from
0.38 to 0.73, and increased correct top-model family selections from two of four to
three of four. A fixed five-position sweep reduced checkpoints from 935 to 393
(58% fewer), with roughly 3x lower retrospective call cost; macro error changed
from 1.388 to 1.424 while rank correlation remained 0.850 in that comparison.

The important failure analyses are as valuable as the headline numbers:

- Full world simulation compounded small hallucinated state errors and produced a
  systematic negative bias. It is not the first FrankenGate implementation path.
- Raw-prefix regeneration had model-specific off-policy bias. A candidate was
  partly evaluated on the incumbent's plan, prose, and framing rather than on its
  own decision policy.
- “Locally competent” judging rewarded actions that looked clean but did not move
  the task toward success. Task-directed action value was a better target.
- Checkpoint observations are not independent samples. Hierarchical aggregation is
  required to avoid long traces dominating the result and to preserve uncertainty.

These are results from the article's four benchmark families and model set. They are
not FrankenGate SLOs. Any adoption must reproduce the direction and calibration on
our own task families with executed reference traces, random audits, temporal and
task-family holdouts, known mutants, and explicit abstention.

## Literature cross-check

The recipe is not without precedent, but the exact combination still appears
under-synthesized. The closest prior work is **ENIGMA**, which estimates dialogue
system value from a small amount of pre-collected experience without interacting
with the target policy and is model-free with respect to the behavior policy. This
corroborates the basic “logged traces → offline candidate estimate” premise, but it
is not an LLM tool-agent checkpoint reconstruction method.

Several newer papers corroborate individual design choices:

- [Abstract Counterfactuals for Language Model Agents](https://papers.nips.cc/paper_files/paper/2025/hash/7ed182aef7d9d19e8daf9148d0fd42c4-Abstract-Conference.html)
  argues that token-level counterfactuals are biased or meaningless for open-ended
  LM-agent actions and uses higher-level action abstractions. This supports
  semantic, protocol-level neutralization, but does not use incumbent traces to
  rank replacement models.
- [Autoregressive Diffusion World Models for Off-Policy Evaluation of LLM Agents](https://arxiv.org/abs/2606.05558)
  directly targets estimating a new agent policy from pre-collected trajectories
  without real-environment execution. It is the closest agent-specific technical
  neighbor, but it solves the problem with a learned world model; the article's
  result is evidence for a cheaper no-simulator checkpoint method, not a claim that
  world models are unnecessary in general.
- [ToolPRMBench](https://arxiv.org/abs/2601.12294) turns tool-agent trajectories
  into step-level cases containing history, a correct action, and a plausible wrong
  alternative. This supports action-level judging and hard negatives, while its
  offline sampling is not the same as retrospective candidate-model evaluation.
- [Aligning Agents via Planning](https://aclanthology.org/2026.acl-long.1062/)
  finds that trajectory judges degrade sharply on long horizons, supporting
  checkpointing, shorter local judgments, and explicit calibration rather than one
  opaque whole-trace score.
- [AgentDiagnose](https://aclanthology.org/2025.emnlp-demos.15/) demonstrates the
  value of trajectory-level diagnosis beyond end-task success, including state
  transitions and multiple agentic competencies. It is diagnostic tooling, not
  off-policy model comparison.

The resulting novelty assessment is: **do not claim “first offline agent eval from
traces.”** That claim is contradicted by ENIGMA and the newer LLM-agent OPE work.
There is nevertheless a credible publishable systems/evaluation contribution in
the narrower intersection: deterministic five-checkpoint selection, incumbent-policy
neutral reconstruction using real observations, action-value judging, hierarchical
trace aggregation, and empirical calibration of model rankings without tool
execution. To support publication, we need a reproducible benchmark with executed
candidate references, raw-prefix and simulator baselines, contamination checks,
held-out task families, judge ablations, uncertainty/coverage reporting, and an
explicit deployment-cost/accuracy tradeoff.

## FrankenGate implementation boundary

Autoeval has two related but distinct outputs:

- **Trace audit:** score a stored trajectory or approved eval case without provider
  calls or side effects. This is retrospective evidence.
- **Candidate-model estimate:** use neutral checkpoints from incumbent traces to
  estimate a candidate model's task-directed action value. This is off-policy
  retrospective evidence and must carry a contamination/transfer receipt.

Neither output is allowed to silently become a live route, prompt, skill, memory,
or policy change. Promotion requires a versioned evaluator and dataset, authorized
source lineage, privacy receipt, independent outcomes where applicable, held-out or
sandbox replay evidence, and a reversible human-approved release.

Do not capture or persist private chain-of-thought. The author's separate post about
using a `deep_think` tool to expose reasoning is not part of Autoeval. Observable
protocol actions, tool calls, tool results, terminal outcomes, explicit feedback,
and bounded evaluator explanations are the evidence surface.

## Local corroboration protocol

The local CASS corpus is large enough for a meaningful test, but size alone is not
evidence. The experiment must first freeze an authorized, redacted cohort with
complete tool-call/result pairs, observable terminal outcomes, task-family labels,
and provenance. Traces without outcomes can test judge agreement and contamination,
but cannot establish ranking fidelity.

For each eligible trace, compare these arms on the same deterministic checkpoint
sample: raw-prefix regeneration, neutral reconstruction, whole-trace judging, a
deterministic/rule-based control where available, and a random/no-op negative
control. Candidate models emit a next protocol action only; the harness executes no
real tool. A small executed-reference subset supplies the ground truth needed to
test whether retrospective action-value scores predict actual success.

Predeclare the primary metrics: Spearman/Kendall model-ranking correlation, mean
absolute error against executed-reference outcomes, correct top-model-family
selection, calibration/abstention, and evaluator cost/latency. Aggregate first by
checkpoint, then trace, then task family. Use bootstrap confidence intervals and
paired comparisons. Require temporal and task-family holdouts, contamination checks,
known bad-action mutants, user/deletion/auth/secret/mutation exclusions, and judge
agreement across model families.

Do not use small local models such as Ollama `qwen3:4b` or `llama3.2` as evidence
arms. They are acceptable only for plumbing, schema, redaction, and harness tests;
their judgments must be excluded from model rankings, calibration, corroboration,
and publication claims. The evidence arms must be frontier or production-scale
models with enough capability for the selected task families, with at least two
independent model families and preferably separate judge and candidate families.
ChatGPT/Codex and a current Meta frontier model are useful comparator arms when an
explicit batch-access path is available. No Meta model is installed in the local
Ollama inventory, so do not silently substitute a tiny local checkpoint. Do not
send private traces to an external provider without an approved redaction and
privacy path.

For the first local pilot, use [Meta Muse Glimmer 30B](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF)
and [Unsloth Qwen3-30B-A3B-Instruct-2507](https://huggingface.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF)
as candidate arms. The Codex sub can be an adjudicator or a third candidate only
if its model identity, system prompt, sampling settings, and tool protocol are
pinned; otherwise treat its output as expert analysis, not a reproducible model
measurement. Two candidates are sufficient for a harness/pairwise pilot, but not
for a persuasive multi-model ranking claim; add a third stable frontier candidate
or a hosted comparator before publication.

This Mac is an M2 Ultra with 64 GB unified memory and approximately 56 GiB free
disk at the time of planning. The 4-bit artifacts are roughly 16--18 GB each, so
the two-model pilot is storage-feasible, but downloading Muse and both Qwen/Muse
quant variants would consume nearly all remaining disk. Keep one inference model
resident at a time, avoid full-precision weights, and retain a safety margin for
KV cache, runtime files, CASS artifacts, and result manifests.

Support for the hypothesis requires neutral reconstruction to improve ranking
fidelity or calibration over raw-prefix regeneration on held-out families while
preserving the cost advantage. Disproof includes no improvement after confidence
intervals, improvements that disappear under provenance/task-family holdouts, or
judge rankings that fail to predict executed-reference outcomes. A null result is
still publishable as a boundary/negative study if the cohort and controls are
reproducible.

## Related profile signals

Two adjacent posts support the same direction but are weaker evidence than the
article's measured experiment:

- [Model simulations on your own data](https://x.com/AmarSVS/status/2084422908332638344)
  points toward a self-service model-comparison workflow over an application's own
  workload.
- [Task difficulty should determine model choice](https://x.com/AmarSVS/status/2084805035842736440)
  argues that many agents may not need the most capable model. FrankenGate should
  report task-family utility, cost, latency, and uncertainty—not only a global mean
  quality score.

The profile's [reasoning-probes post](https://x.com/AmarSVS/status/2087267529597341779)
was reviewed and intentionally excluded from the Autoeval evidence contract because
private reasoning capture is neither necessary nor an acceptable durable trace input.

## Local work item

The implementation is tracked under
`bif-kyy.17.13.2.1.1` (Trace-native autoeval recipe), with the article-specific
off-policy slice in `bif-kyy.17.13.2.1.1.5`.
