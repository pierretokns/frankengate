# Empirical program for trace intelligence on public agent trajectories

**Status:** proposed preregistration and paper plan

**Date:** 2026-07-30

**Scope:** Independent and composed evaluation of trajectory selection, diagnosis,
retrieval, temporal facts, semantic memory, procedural memory, eval generation, and
utility-aware routing for Frankengate.

## Research claim

The study must not ask whether a collection of named projects can be made to run
together. It must ask which mechanisms add reliable information for a particular
decision:

1. Which traces deserve review?
2. Which traces represent the same or related task?
3. Where did an attempt become unrecoverable?
4. What changed between failure and recovery?
5. Which facts or procedures remain reusable?
6. Which retrospective trace should become an eval?
7. Does retrieving a memory or playbook cause better performance?
8. Which findings survive a transfer from public benchmarks to private enterprise
   traces?

The null hypothesis for every component is that a cheaper deterministic or
exact/lexical baseline performs as well. No component is adopted because its upstream
paper reports a benchmark improvement.

## Claim boundary

Public traces can validate parsers, trajectory representations, deterministic signals,
offline retrieval, retrospective assertions, outcome prediction, failure localization,
memory extraction precision, temporal contradiction handling, and replay effects when
the environment is reproducible.

Public traces cannot establish:

- which Frankengate users perform similar work;
- whether a person lacks a cloud or domain skill;
- the coverage of an enterprise's actual work;
- whether a recommendation helps a real user in their environment;
- whether cross-user learning remains useful after Frankengate authorization,
  classification, consent, and cohort privacy controls;
- whether a memory is appropriate for an enterprise policy or `MEMORY.md`;
- whether domain-adapted embeddings help with private terminology.

Those require private labels, scope-aware retrieval tests, and—where causation is
claimed—controlled interventions. The paper must label public-data findings as
**mechanism validation**, not enterprise validation.

## Primary source mechanisms

| Mechanism under test | Source | Operational treatment |
|---|---|---|
| Canonical trajectory, invariants, failure step and taxonomy | [AgentRx](https://github.com/microsoft/AgentRx) | Loss-aware event DAG; deterministic invariants; optional judge; decisive-step hypothesis |
| Cheap informative-trace selectors | [Signals](https://arxiv.org/abs/2604.00356) | Rephrase, stagnation, loop, failure, disengagement, cost, latency, and environment detectors |
| Retrospective ordered/unordered/exact/semantic assertions | [AgentEvals](https://github.com/agentevals-dev/agentevals) | Versioned assertions over stored trajectories without rerunning an agent |
| Separate log, metric, topology, and trace evidence | [OpenRCA](https://github.com/microsoft/OpenRCA) | Modality-specific features joined by task, time, dependency, and event identity |
| Temporal facts and attributed entities | [Graphiti](https://github.com/getzep/graphiti), [MemInsight](https://github.com/amazon-science/MemInsight) | Source-cited fact proposals with valid/system time, contradiction, entity and episode attributes |
| Candidate extraction and consolidation | [Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams), [LangMem](https://github.com/langchain-ai/langmem) | Separate immutable candidate release; deduplication, contradiction, preview and rejection |
| Procedural experience | [ReasoningBank](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/), [LEGOMem](https://www.microsoft.com/en-us/research/publication/legomem-modular-procedural-memory-for-multi-agent-llm-systems-for-workflow-automation/), [ACE](https://www.microsoft.com/en-us/research/publication/agentic-context-engineering-evolving-contexts-for-self-improving-language-models/) | Failure/success contrasts; separate orchestration and execution procedures; versioned incremental playbooks |
| Utility-aware memory and skill choice | [Memento-Skills](https://arxiv.org/abs/2603.18743), [MemRL](https://arxiv.org/abs/2601.03192) | Semantic candidate retrieval followed by task-specific utility ranking and a no-memory control |
| Exact, lexical, structured, dense, and reranked retrieval | [pgvector](https://github.com/pgvector/pgvector), PostgreSQL FTS/trigram and exact identifiers | Identical authorized candidate corpus; exact retrieval remains the recall oracle |

The implementation should reproduce mechanisms, not deploy upstream observability,
memory, or graph products as additional authorities.

The source-pinned execution review is
[`trace-tool-execution-feasibility.md`](trace-tool-execution-feasibility.md). It permits
direct AgentEvals assertions, stateless LangMem extraction and a small ephemeral
Graphiti ablation. AgentRx, Signals, ReasoningBank and Dreams mechanisms are
reimplemented behind Frankengate's declarative evidence model rather than installed as
trace, code-execution, memory or authorization authorities.

## Dataset portfolio

The first paper uses complementary sources rather than treating one downloadable
collection as representative:

| Stratum | Candidate source | Why it is useful | What it cannot prove |
|---|---|---|---|
| Human step labels | [`NJU-LINK/CodeTraceBench`](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench) | 3,316 unique coding traces; the contained 1,000-row verified split labels incorrect actions and redundant exploration | Software-engineering-only; no enterprise users or intervention exposure |
| Sequential recovery artifacts | [`EtaYang10th/SPARK_PDI_Trajectory`](https://huggingface.co/datasets/EtaYang10th/SPARK_PDI_Trajectory) | Multiple attempts, reflections and `SKILL.md`; 16 observed fail/error→pass sequences | Small recovery cohort and teacher/reflection confounding; observational, not causal |
| Deterministically replayable tool tasks | [`pagarsky/agent-trace`](https://huggingface.co/datasets/pagarsky/agent-trace) | Tool calls, errors, telemetry and deterministic verification support causal memory/playbook trials | Narrow synthetic programming and shell tasks |
| OTel-shaped sessions | [`Exgentic/agent-llm-traces`](https://huggingface.co/datasets/Exgentic/agent-llm-traces) | Substantial OTel-shaped corpus for ingestion and chat-level signals | Audited spans are chat operations; tool activity must be reconstructed from messages |
| ATIF assertion fixtures | [`obaydata/mcp-agent-trajectory-benchmark`](https://huggingface.co/datasets/obaydata/mcp-agent-trajectory-benchmark) | 49 raw ATIF trajectories for exact, ordered and unordered assertion tests | Tiny and mostly synthetic |
| Heterogeneous real coding sessions | [`trace-commons/agent-traces`](https://huggingface.co/datasets/trace-commons/agent-traces) | 30 donated Claude Code, Codex, Pi, Cursor and OpenCode sessions preserve real harness differences | Outcomes are sparse; privacy and volunteer-selection risk |
| Private Frankengate holdout | Governed, consented task attempts | Tests terminology, RLS, classifications, team boundaries, verified outcomes, capability-support hypotheses and interventions | Must never be public or mixed into public training by default |

The broader [`neulab/agent-data-collection`](https://huggingface.co/datasets/neulab/agent-data-collection)
may test importer breadth only through individually licensed configurations; its roughly
649 GB repository is not one admissible corpus. CMU Agent Trajectories is quarantined
until its missing license is clarified and its removal of 14.3% incomplete/crashed/
truncated records is modeled as survivorship bias. The source-pinned audit is
[`public-agent-trace-dataset-inventory.md`](public-agent-trace-dataset-inventory.md).

Hugging Face now supports native agent-session trace rendering for several harnesses,
but its own documentation warns that traces can contain secrets, paths, private code,
screenshots, and personal data. Native rendering is not a privacy guarantee:
[Hugging Face agent traces](https://huggingface.co/docs/hub/en/agent-traces).

## Dataset admission audit

Every source receives a versioned dataset card before any model call:

- immutable revision/hash, license, source and redistribution rights;
- source task, harness, model, tool inventory, reward and evaluator semantics;
- repeated task IDs, attempt IDs, timestamps and dependency relationships;
- which fields are observed, inferred, missing, redacted, or reconstructed;
- outcome independence: external test, environment state, judge score, or none;
- prompt/tool/repository duplication and likely benchmark contamination;
- demographic, language, domain, model and success-rate distributions;
- known collection, publication, survivorship and volunteer bias;
- raw-to-canonical information-loss receipt.

A source is quarantined from a claim if the claim's required field is missing. Missing
outcomes must never be replaced silently with an LLM judge.

## Gold annotation corpus

Create a preregistered, versioned gold subset with two blinded annotators and
adjudication. The minimum schema is:

| Label | Unit | Allowed values |
|---|---|---|
| Informative for diagnosis | trajectory | yes / no / insufficient evidence; severity and reason |
| Task boundary | ordered event range | start/end plus nested/subtask links |
| Task relationship | pair of attempts | same objective, same family, prerequisite, superficially similar, unrelated, insufficient |
| Outcome | attempt | independently verified success/failure/partial/unknown and source |
| Friction | event range | accidental, productive exploration, environment, permission/policy, tool, knowledge, model, unknown |
| Earliest preventable/decisive step | event or abstain | event ID, evidence IDs, alternative steps |
| Recovery delta | failed/successful attempt pair | added/removed/reordered action, environment change, permission, information, model/prompt change |
| Reusable fact | candidate statement | entailed/contradicted/unsupported/stale; valid time; cited events |
| Reusable procedure | candidate playbook | applicable/not applicable/unsafe; preconditions; verifier; cited attempts |
| Eval candidacy | trajectory | regression, safety, invariant, performance, rare-critical, none; assertions |
| Candidate capability support | task attempt | capability needed / environment explains / insufficient; never a person-level trait |

Annotators cannot see model identity, method output, reward, signal-selection status, or
experimental condition except where the label logically requires environment evidence.
Report raw agreement, Krippendorff's alpha or weighted kappa as appropriate, and
adjudicated uncertainty. If agreement is below 0.67 after a rubric revision, the label
remains exploratory. A shipping decision needs at least 0.80 on critical labels.

## Core enterprise questions as falsifiable hypotheses

| Enterprise question | Public-data hypothesis | Private/intervention hypothesis | Primary metric | Falsifier |
|---|---|---|---|---|
| Which attempts deserve review? | At equal review budget, deterministic Signals increase the fraction of gold-informative attempts over random and cost/length heuristics | The enrichment persists across tenants, roles, models, and quiet-success cohorts | Precision at fixed review budget; recall of critical failures | Less than 15 percentage-point enrichment, or more than 10% of critical failures missed after the random audit stratum |
| Who is doing related work? | A multidimensional task signature retrieves same-family attempts better than raw prompt FTS or a whole-trace embedding | Authorized users confirm anonymous task-pattern matches and reciprocal introductions at useful rates | Recall@20, nDCG@20, pairwise macro-F1, acceptance/false-introduction rate | No improvement over exact+lexical+structured baseline, unstable clusters, or privacy controls destroy utility |
| Where did work fail? | Invariants plus topology/modal evidence localize the gold decisive step better than last-error, first-error, and judge-only baselines | Localized causes predict which reversible intervention helps | Top-1 step accuracy, mean reciprocal rank, distance to gold step, selective risk | Less than 10 points over deterministic baseline, poor calibration, or the system rarely abstains on insufficient evidence |
| What changed before recovery? | Ordered failed/successful contrasts identify adjudicated recovery deltas better than unordered text similarity | Adding the proposed delta and removing it in replay changes success in the predicted direction | Delta macro-F1; add/remove average treatment effect | Observational deltas do not survive add/remove replay or are dominated by environment/permission changes |
| What should become an eval? | AgentEvals-style exact/ordered/unordered/invariant assertions catch seeded mutants with fewer false positives than semantic judge-only tests | Production-derived evals predict real regressions after a release | Mutant kill rate, false-positive rate, assertion stability, coverage | Mutant kill gain is negligible, normal variations fail often, or replay semantics are misrepresented |
| What should become memory? | Proposal-only temporal extraction achieves high citation support and detects contradictions/staleness better than a flat rolling summary | Reviewed memory-on improves later work without unsafe anchoring or scope leakage | Entailment/citation precision, contradiction recall, temporal accuracy, reviewer accept rate | Citation precision below 99%, factual precision below 95%, or any scope/classification leak |
| What procedure should be suggested? | Success/failure-contrast playbooks retrieve to novel but related tasks better than raw successful examples | Random assignment to a relevant playbook improves verified success, turns, cost, and correction rate | Success difference; turns/cost conditional on success; harm rate | No positive effect in two domains, critical-slice harm over 5%, or unrelated-memory placebo performs similarly |
| Is utility-aware routing needed? | A learned utility ranker beats semantic top-1 while approaching an oracle selector | Gains remain under distribution shift and after deletion/reclassification | Regret to oracle, success@budget, calibration | No gain over semantic+rules, unstable utility under time/model shift, or credit cannot be identified |
| Is a custom embedding needed? | Domain adaptation improves hard-negative task-family recall beyond exact+FTS+structured+general dense+reranker | The gain transfers to private terminology and remains privacy/deletion safe | Recall@20 and nDCG@20 on frozen hard slice | Less than five absolute Recall@20 points, exact IDs regress, or gain disappears on tenant/user/time holdout |
| Which skill support helps? | Public traces can validate task-to-capability label reliability only | A private, optional support intervention changes later observable task performance after environment blockers are controlled | Label agreement; randomized/stepped-wedge outcome difference | Annotators cannot distinguish capability from tool/permission/context, or intervention has no effect |

## Units and splits

The unit of independence is never a turn or span.

- **Selection:** task attempt/trajectory.
- **Task retrieval:** task pair for labeling; task ID or task family for splitting.
- **Diagnosis:** task attempt, with step-level predictions nested inside it.
- **Recovery:** ordered attempt pair for the same task and environment family.
- **Fact memory:** source episode/fact candidate.
- **Procedural memory:** held-out task, not the retrieved memory item.
- **Intervention:** independently rerun task instance.
- **Enterprise aggregation:** privacy-approved cohort release.

Use group splits that prevent all records sharing a task, issue, repository family,
template, near-duplicate prompt, generated memory, or upstream source from crossing
train/validation/test. Add user, tenant and time grouping for private data. Keep a
never-tune launch set. Report within-dataset results before any pooled score.

## Component experiments

### E0 — Canonicalization and information preservation

Convert each native format into the Frankengate canonical event DAG and back into a
source-neutral projection.

Positive controls:

- branch, retry, fallback and delegation;
- tool proposal, authorization, execution, result and independent state delta;
- stream interruption and resumed task;
- redaction, missing content, unknown event and schema version;
- duplicate/reordered delivery.

Metrics are typed-event recall, edge recall, order constraints preserved, field
missingness, unsupported-event quarantine and deterministic re-import hash. Require
100% preservation of tool calls, outcomes and authorization events in the gold sample,
and at least 99.5% of all typed events. Any silent loss stops downstream experiments.

### E1 — Signals selection trial

At identical annotation budgets compare:

1. uniform random sampling;
2. trace length/token/cost heuristic;
3. failure/reward heuristic where an external reward exists;
4. each cheap signal independently;
5. the preregistered union/score of Signals;
6. Signals plus a mandatory random audit stratum.

The method cannot use reward, gold labels or benchmark identity as input. Estimate
precision at fixed budgets, recall of critical cases, inverse-propensity-weighted
prevalence, compute cost per selected informative trace, and selection disparity by
dataset/model/outcome/length. Signals is a selector, never a diagnosis label.

### E2 — Retrieval factorial

Keep authorization and exact identifier constraints fixed. Evaluate the following arms
on identical candidates:

1. exact identifiers only;
2. PostgreSQL FTS/trigram;
3. structured task/trajectory signature;
4. general dense embedding of raw prompt;
5. general dense embeddings of separate objective, environment, failure and recovery
   views;
6. exact + lexical + structured;
7. exact + lexical + structured + dense fusion;
8. arm 7 plus cross-encoder/LLM reranker;
9. domain-adapted dense model, only after arm 8 fails a named slice.

Use human task-family labels and hard negatives that share repository, tools or jargon
but differ in objective. Report Recall@k, nDCG@k, MRR, hard-negative error, exact-ID
recall, calibration, latency, index bytes and API/compute cost. Use exact vector search
as the dense oracle before testing approximate search.

### E3 — Diagnosis factorial

Run the full interpretable \(2 \times 2 \times 2\) design:

- declarative invariants absent/present;
- ordered topology and modal evidence absent/present;
- calibrated LLM judge absent/present.

Include last-error, first-error, reward-only, random-step and full-trace-summary
baselines. This isolates the AgentRx invariant contribution, the OpenRCA-style evidence
contribution, and interaction with a judge. The judge must emit evidence IDs,
alternatives and abstention. Do not execute generated unrestricted Python checkers.

Primary metrics are top-1/top-3 decisive-step accuracy and selective risk at
preregistered coverage. Secondary metrics are failure-taxonomy macro-F1, evidence
entailment, Brier score/ECE, latency and tokens. Test shuffled order, wrong timestamps,
removed decisive step and irrelevant log injection as negative controls.

### E4 — Retrospective eval construction

For each adjudicated failure construct candidate assertions:

- exact event/value;
- ordered subsequence;
- unordered required set;
- forbidden event/invariant;
- semantic output condition;
- external state delta, only when independently observed.

Seed one mutation at a time: remove/reorder/duplicate a required tool call, change an
argument, replace a result, inject an error, alter a policy decision, or change the
terminal output. Compare deterministic assertions, semantic judge-only, and combined
assertions. Report mutant kill rate, false positives on allowed variation, evaluator
disagreement and assertion maintenance burden. Retrospective assertions must be called
audits unless an agent is actually rerun.

### E5 — Temporal fact and semantic-memory extraction

Freeze source episodes, then compare:

1. no extraction;
2. flat rolling summary;
3. LangMem-like candidate extraction;
4. Dreams-like separate consolidation release;
5. temporal/entity attributes inspired by Graphiti/MemInsight;
6. arm 5 plus consolidation.

Inject controlled contradictions, corrections, time-bounded facts, aliases and
same-name/different-entity cases. Score proposition entailment, source citation,
contradiction recall, valid-time answer accuracy, entity merge/split error,
compression, reviewer effort and abstention. The output remains a proposal; no arm may
write into a live memory file.

### E6 — Procedural-memory generation and causal replay

Generate procedures from disjoint training tasks using:

1. raw successful exemplar;
2. generic summarization;
3. ReasoningBank-style successful/failed contrast;
4. LEGOMem-style separate orchestration and execution procedures;
5. ACE-style incremental curated playbook;
6. a combined contrast + separation + curation arm.

Freeze all artifacts before testing. For each held-out deterministic task randomly
assign:

- no memory;
- relevant generated procedure;
- unrelated but superficially similar placebo;
- oracle human-authored procedure where available.

Run at least three seeds/orderings. Primary outcome is externally verified task success.
Secondary outcomes are attempts, turns, tokens, latency, cost, unsafe actions, verifier
use and correction burden. Retrieval is held fixed in the first trial; generation and
retrieval are not varied together.

### E7 — Utility-aware retrieval

After E6 establishes that some procedures have causal value, compare:

1. no memory;
2. random candidate;
3. semantic top-1;
4. semantic + deterministic applicability rules;
5. learned utility reranker;
6. retrospective oracle.

Train on intervention outcomes, not the model's self-score. Use doubly robust or
randomized exploration data when available and report regret to oracle, off-policy
uncertainty, calibration and distribution-shift performance. If treatment propensities
are unknown, label results associational.

## Meaningful combinations and invalid combinations

| Combination | Test? | Reason |
|---|---:|---|
| Canonical DAG + Signals + exact/structured retrieval | Yes, first | Cheap, deterministic and prerequisite to all later analysis |
| Invariants + ordered topology/modal evidence + judge | Yes, full factorial | Mechanisms make distinct diagnosis contributions and interactions are interpretable |
| Task-view embeddings + lexical/structured fusion + reranker | Yes | Tests candidate generation without treating vector similarity as truth |
| Temporal facts + separate consolidation release | Yes | Tests contradiction/time handling separately from live memory injection |
| Failure/success contrast + orchestration/execution separation + curation | Yes | Coherent procedural-memory composition; causal utility can be tested by replay |
| Semantic candidate retrieval + utility reranking | Yes, only after randomized utility data | Semantic relevance and causal usefulness are different quantities |
| Signals as failure/skill labels | No | Selection propensity is not diagnosis or competence |
| Whole-trace vector + named-person similarity | No | Conflates objectives, tools, errors and outcomes and creates a privacy-sensitive people finder |
| Self-judge extraction + self-judge promotion + same-model evaluation | No | Circular evidence and correlated error |
| Graph proximity as fact truth or authorization | No | Topology supplies neither entailment nor policy |
| Observed recovery delta as causal skill evidence | No | Environment, permission, tool and model changes confound it |
| All components in one factorial | No | A \(2^N\) trial is wasteful and its interactions are uninterpretable before component validity |

## Leakage and validity controls

1. **Task leakage:** split by task/issue/repository family; remove prompt and code
   near-duplicates with hashes and MinHash/manual audit.
2. **Metadata leakage:** analyzers and judges never receive reward, pass number,
   benchmark provenance, success filenames, model identity, or gold label.
3. **Memory leakage:** generated facts/procedures come only from the training partition;
   retrieval indexes are rebuilt per fold.
4. **Tool-menu leakage:** do not expose benchmark tags or the exact distraction
   provenance. The `cx-cmu` dataset explicitly warns that its global tool inventory is
   not the exact per-run generation menu.
5. **Judge leakage:** the same model/revision is not both artifact generator and sole
   evaluator; deterministic outcomes and blinded humans remain primary.
6. **Hyperparameter leakage:** one validation split; one untouched test and launch
   set; every prompt, threshold and model revision is versioned before test access.
7. **Turn pseudoreplication:** cluster all uncertainty and tests at task level.
8. **Public benchmark contamination:** report it as unknown where model training data
   are undisclosed; never interpret public task knowledge as enterprise adaptation.
9. **Missing-not-negative:** missing tool results, hidden reasoning, absent outcomes and
   redactions remain typed missingness.
10. **Selective publication:** register all arms, slices, exclusions, costs and failed
    runs; publish a results manifest even when a method loses.

## Statistical analysis

- Report effect sizes and 95% task-cluster bootstrap confidence intervals, not only
  p-values.
- Use paired tests wherever identical tasks are evaluated by multiple arms: McNemar's
  exact test for paired binary success, paired permutation/bootstrap for ranking
  metrics, and mixed-effects logistic/linear models for repeated seeds nested in task.
- Use dataset/domain/model as fixed or hierarchical effects; do not hide sign reversals
  behind a pooled average.
- Control confirmatory families with Holm correction. Mark all unregistered slices and
  interactions exploratory.
- For selection, estimate precision at a fixed review budget and inverse-propensity
  weighted prevalence using the random audit stratum.
- For retrieval, bootstrap by query task and report per-scope/hard-negative results.
- For calibrated abstention, report risk-coverage curves, Brier score and ECE with
  confidence intervals.
- For replay interventions, report intention-to-treat as primary. Failures to execute
  remain outcomes, not exclusions.
- Conduct power by simulation from pilot task-level variance. If the minimum detectable
  effect is larger than a worthwhile product effect, expand tasks rather than turns.

## API and compute tiers

All runs use pinned model IDs, prompt hashes, temperature/seeds where supported, tool
schemas, token counts, latency and a dated pricing manifest. A consumer subscription is
not assumed to equal API credit; the harness reads the available API budget and stops
before its hard cap.

| Tier | Budget shape | Work |
|---|---|---|
| 0 — local/deterministic | No model API | Parsing, canonicalization, exact/FTS/structured retrieval, signals, invariants, mutants, statistics |
| 1 — economical pilot | At most 10M input and 2M output tokens | Mini-model candidate extraction, task-view summaries, small embedding corpus; verify 10% with humans/frontier judge |
| 2 — calibrated study | At most 30M input and 5M output tokens | Full gold subset, independent judge family, reranking and memory extraction ablations |
| 3 — causal replay | Separate preregistered cap, initially no more than half the monthly budget | Baseline/placebo/treatment task reruns with repeated seeds |
| 4 — frontier replication | Only after a positive lower-tier result | Replicate decisive arms on a frontier model and new dataset/domain |

Use batch/cached requests where model semantics permit, compact evidence windows rather
than raw full traces, and deterministic preprocessing for every cheap operation. Do not
spend frontier tokens to parse JSON, compute signals, or execute exact assertions.

## Smallest reproducible initial study

The initial study is intentionally small enough to run and inspect end to end:

### Retrospective cohort

- Import a license-clean 300–400 trace pilot drawn from CodeTraceBench verified,
  SPARK's repeated-attempt sequences, pagarsky replay tasks, Exgentic OTel-shaped
  sessions, MCP/ATIF fixtures, and a quarantinable Trace Commons reality-check slice.
- Split by task, repository and upstream source; keep all repeated attempts and the
  CodeTraceBench `verified` rows with their corresponding `full` records in one fold.
- Canonicalize all trajectories; manually inspect at least 30 per native format and
  create a blinded task-level gold subset for each supported claim.
- Run E1 Signals, E2 retrieval arms 1–8, E3 diagnosis's eight factorial arms, and E4
  mutation tests.
- Freeze all prompts, thresholds and labels before opening the held-out tasks.

The already completed 300-record Nebius SWE-agent matched pilot remains a preliminary
outcome-proxy smoke test. It validates the harness and exposes that a fixed friction
score did not beat trace length at the review cutoff; it is not the paper's gold
diagnosis cohort.

### Causal replay cohort

- Select 40 deterministic NL2Bash tasks from `pagarsky/agent-trace`.
- Use 20 disjoint tasks to generate procedures and 20 for evaluation.
- Run four conditions—no memory, relevant contrast-derived procedure, unrelated
  placebo, and combined curated procedure—with three seeds: 240 test runs.
- Keep the model, tools, retrieval, limits and environment identical across arms.
- The task's deterministic verifier, not an LLM judge, is the primary outcome.

This study is large enough to discover parser loss, selection enrichment, retrieval
failure, diagnosis non-additivity, eval brittleness, and a coarse procedural-memory
effect. It is not powered to claim enterprise skill inference or general workforce
learning.

Proceed to the larger paper only if:

- canonicalization meets the preservation gate;
- gold labels are reliable enough for the intended claim;
- at least one nontrivial mechanism beats its cheap baseline;
- the causal replay harness reproduces identical control behavior;
- cost and failure manifests are complete.

## Kill and redesign criteria

Stop or narrow a claim when:

- canonicalization silently loses any authorization, tool, outcome, branch or
  provenance event;
- the relevant gold label remains below 0.67 inter-annotator reliability;
- Signals fail to enrich useful review while retaining a random audit sample;
- diagnosis gains less than 10 absolute top-1 points over deterministic baselines or
  cannot calibrate abstention;
- semantic retrieval does not beat exact+lexical+structured retrieval on a named hard
  slice;
- a domain embedding improves average retrieval by less than five Recall@20 points,
  hurts exact IDs, or fails a user/tenant/time holdout;
- memory proposals miss 99% citation support, 95% factual precision, temporal
  correctness, or zero scope leaks;
- procedural memory has no positive intention-to-treat effect in two domains, or causes
  more than 5% absolute harm on a critical slice;
- utility routing cannot be trained from randomized/known-propensity outcomes;
- privacy controls remove the utility of cross-user findings or allow re-identification;
- private results fail to reproduce the direction of public mechanism findings;
- API/compute cost per useful reviewed finding exceeds the value threshold set before
  the run.

Failure is a result. The paper should publish which attractive mechanisms did not add
information.

## Enterprise validation extension

Only after the public study, create a private, governed extension:

1. Sample personal histories randomly beside Signals-selected histories.
2. Establish source coverage and independently verified outcomes.
3. Annotate organization task families, environment blockers and capability
   requirements; include `insufficient evidence`.
4. Evaluate retrieval under the full RLS/classification/purpose/epoch lattice.
5. Run private suggestion cards before any team aggregate.
6. Test prompt, retrieval, skill and memory suggestions with randomized or stepped-wedge
   assignment and independent outcomes.
7. Release only minimum-cohort anonymous patterns and reciprocal opt-in introductions.
8. Fine-tune embeddings only after a frozen enterprise hard-negative benchmark proves
   the general hybrid baseline inadequate.

No public-data result authorizes employee scoring, named people search, automatic
memory injection, cross-customer training, or a causal skill-gap claim.

## Reproducible harness layout

```text
research/trace-intelligence/
  README.md
  CITATION.cff
  LICENSES.md
  pyproject.toml
  uv.lock
  Makefile
  configs/
    datasets/
    importers/
    signals/
    retrieval/
    diagnosis/
    memory/
    replay/
    models/
    budgets/
  schemas/
    canonical-trajectory.schema.json
    loss-receipt.schema.json
    annotation.schema.json
    experiment-manifest.schema.json
    result-manifest.schema.json
  adapters/
    cx_cmu/
    trace_commons/
    agenttrace/
    agent_data_protocol/
    otel_openinference/
  src/
    canonical/
    signals/
    retrieval/
    diagnosis/
    evals/
    facts/
    memory/
    procedures/
    routing/
    replay/
    stats/
  annotation/
    rubric.md
    examples/
    blinded/
    adjudicated/
  datasets/
    manifests/
    raw/                 # ignored; immutable hashes only in Git
    canonical/           # ignored; rebuildable
    splits/
    gold/
  experiments/
    preregistrations/
    manifests/
    runs/                # ignored; content-addressed
    summaries/
    failures/
  tests/
    fixtures/
    importer_conformance/
    leakage_controls/
    mutants/
    replay/
  reports/
    tables/
    figures/
    model-cards/
    dataset-cards/
    paper/
```

Each result manifest records source hashes, split hash, code commit, config and prompt
hashes, model revision, API organization/project alias without secrets, seeds, token
and dollar cost, wall time, failed attempts, exclusions, environment image, outputs and
lineage. Raw traces and credentials never enter Git.

## Paper structure

1. Motivation and claim taxonomy.
2. Dataset and canonicalization audit.
3. Human annotation methodology and reliability.
4. Component experiments: selection, retrieval, diagnosis, eval construction, memory.
5. Causal replay of procedural memory.
6. Composition and ablation results.
7. Transfer to private enterprise traces, if authorized.
8. Privacy, security, ethics and non-claims.
9. Cost and systems analysis.
10. Negative results, limitations and release artifacts.

The central scientific contribution should be a claim-aware composition study: which
trace-intelligence mechanisms remain useful after exact baselines, information-loss
accounting, task-level statistics, causal replay, and enterprise claim boundaries—not
another leaderboard of LLM summaries.
