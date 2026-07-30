# Enterprise Trace Intelligence: Independent and Composed Research Program

**Date:** 2026-07-30  
**Status:** Broad evidence audit and preregistered experimental program  
**Scope:** Frankengate trace history, trace mining, eval proposals, memory,
skill learning, collaboration support, retrieval, and organizational learning

## Executive decision

Frankengate should not be designed as a bundle of trace, memory, graph, vector,
and evaluation products. It should be designed as a controlled experiment over
separable mechanisms.

The minimum persistent architecture remains:

1. Frankengate as the capture and policy enforcement point.
2. Aurora PostgreSQL as the canonical evidence, authority, temporal, proposal,
   release, deletion, and influence ledger.
3. Object storage for large immutable payloads and replay artifacts.
4. An asynchronous worker for parsing, signals, embeddings, judges,
   experiment execution, and destination rendering.

That is a starting architecture, not a conclusion that PostgreSQL can solve
every future workload. A graph service, search sidecar, different PostgreSQL
distribution, vector engine, or adapted embedding earns a production role only
after it beats the minimum architecture on a frozen workload while preserving
the same authority, deletion, provenance, latency, and outcome requirements.

The research emphasis is broad mechanism value:

- Can cheap signals find informative traces?
- Can diagnosis localize a decisive failure?
- Can a real trace become an eval that catches a later regression?
- Can temporal memory or dreaming improve later work?
- Can success/failure contrasts produce a reusable skill?
- Can trace similarity identify genuinely related work?
- Can a brokered introduction or shared artifact improve outcomes?
- Can an enterprise-adapted embedding beat structured retrieval and a general
  embedding?

Privacy is one bounded constraint, not the research program. Authorized
internal analysis may retain full PII and classified content inside scope.
Reusable credentials remain excluded from the ordinary trace, model, index,
replay, and export planes.

## The questions the system must eventually answer

| ID | Enterprise question | Required claim class |
|---|---|---|
| Q1 | What has this user worked on, with which prompts, tools, models, and outcomes? | Deterministic evidence |
| Q2 | Where did a user or task family encounter repeated friction, and what changed before success? | Statistical candidate; causal only after replay/intervention |
| Q3 | Which production traces should become regression evals, and do those evals catch future regressions without rejecting benign variation? | Prospective evaluation |
| Q4 | Which facts or procedures should become user, team, enterprise, or harness memory, and do they help later work? | Reviewed proposal followed by causal utility |
| Q5 | Which reusable skills, prompts, tools, routes, or documentation should be proposed from trace evidence? | Reviewed intervention hypothesis |
| Q6 | Which support or education intervention improves a user or task-family outcome? | Causal |
| Q7 | Which users or teams are doing meaningfully related work, and does a shared artifact or reciprocal introduction help them? | Human-adjudicated similarity followed by causal utility |
| Q8 | Does an enterprise-adapted embedding or model materially improve a frozen hard slice over structured and general-model baselines? | Statistical promotion gate plus prospective safety |

No system in the current evidence answers all eight. The correct architecture
must preserve the boundaries between evidence, selection, retrieval,
hypothesis, proposal, release, exposure, and outcome.

## Evidence states

The following states must never be collapsed:

```text
observed trace
  -> deterministic selector
  -> retrieved candidate
  -> diagnosis hypothesis
  -> proposed eval / memory / skill / collaboration artifact
  -> independently reviewed immutable release
  -> controlled exposure
  -> later outcome
  -> independent validation or withdrawal
```

A selected trace is not a failure diagnosis. A diagnosis is not a cause. A
memory candidate is not a true memory. A released skill is not an effective
skill. A similar trace is not a useful collaborator. A later trace influenced
by an artifact is not independent validation of that artifact.

## Independent concept coverage

Status key:

- **Direct:** the mechanism or a close faithful implementation has been run.
- **Proxy:** a narrower Frankengate mechanism has been run.
- **Mechanics:** storage, authorization, projection, or replay conformance only.
- **Reviewed:** source and design reviewed; no empirical mechanism run.
- **Missing:** neither a faithful run nor a useful proxy exists.

| Concept | Independent role | Current evidence | Questions | Next decisive test |
|---|---|---|---|---|
| Canonical event DAG | Preserve branches, model/tool lifecycle, observations, outcomes, source revisions, and loss | **Direct/mechanics.** Native adapters and real OTel round trips exist | Q1-Q8 substrate | Natural end-to-end trace through SDK, Collector, canonical import, analysis, deletion, and replay |
| ATIF | Portable selected trajectory and eval interchange | **Direct.** Loss-aware projection exists; enterprise stress events lose canonical IDs/edges on reimport | Q1, Q3 | ATIF-to-AgentEvals export/reimport with denied calls, branches, and explicit loss assertions |
| OTel/OpenInference | Operational span topology, timing, and tool lifecycle | **Direct.** Real SDK -> Collector -> file -> reimport retained the tested projected topology | Q1-Q3 substrate | Production backend round trip with expected-trace manifest and whole-trace drop controls |
| Signals | Cheap rephrasing, stagnation, loop, failure, disengagement, and recovery selection | **Proxy.** Typed errors and bounded later-success candidates ran; full published signal set did not | Q2, Q3 | Frozen detectors versus random, length, and stage-count on human informative-trace labels |
| AgentRx | Canonical failure taxonomy, invariants, and decisive-step localization | **Proxy.** Deterministic invariants ran; faithful AgentRx did not | Q2, Q3, Q5 | AgentRx versus chronology, deterministic invariants, and blinded judge on decisive-step gold |
| OpenRCA | Join trace graph, logs, metrics, topology, and time-series evidence | **Reviewed/proxy.** A topology factor ran; multimodal RCA did not | Q2, Q5 | Modality-ablation RCA with independently verified incident causes and alternatives |
| AgentEvals | Promote stored traces into exact, ordered, unordered, invariant, or semantic assertions | **Proxy.** Assertion and mutation mechanics exist; changed-system replay does not | Q3 | Mine a trace, generate assertions, mutate the agent/system, and measure harmful-regression recall plus benign false positives |
| Phoenix | Trace -> annotation -> dataset -> experiment -> replay lifecycle | **Reviewed/mechanics.** Native lifecycle records borrow the pattern; Phoenix was not run | Q3, Q4 | Export/import parity test against the native lifecycle, not a second authority |
| Opik | Online evaluation rules, datasets, experiments, and aggregate views | **Reviewed/mechanics.** Product-specific rules were not run | Q3 | Same rule evaluated natively and in Opik with deletion/revision parity |
| Langfuse | Sessions, feedback, datasets, and prompt experiments | **Reviewed/mechanics.** Feedback ingestion and prompt experiment behavior were not run | Q1, Q3, Q4 | Human feedback import plus dataset revision and deletion parity |
| Temporal evidence / MemInsight concepts | Typed people, systems, tasks, outcomes, known time, valid time, gaps, and contradictions | **Direct/mechanics.** A cutoff-safe relational oracle passes synthetic tests | Q1, Q2, Q4-Q7 | Blinded natural longitudinal benchmark with online gold and interval-censored changes |
| Memory Palace / MemPalace | Verbatim retention, stable IDs, temporal revisions, personal navigation | **Proxy.** Verbatim and bitemporal retention mechanics ran | Q1, Q4 | Retrieval and later-task utility versus latest-only and no-memory |
| Graphiti | Incremental temporal knowledge graph and hybrid retrieval | **Proxy/mechanics.** Relational facts/edges and contradiction mechanics ran; Graphiti did not | Q4, Q7 | Equal-evidence relational versus ephemeral Graphiti benchmark on multi-hop temporal questions |
| LangMem | Structured memory candidate extraction and consolidation | **Proxy/mechanics.** Proposal lifecycle exists; extractor quality was not tested | Q4 | LangMem extraction versus deterministic and local-model extractors on cited memory gold |
| Dreaming | Query-independent background synthesis of useful/current memory candidates | **Proxy only.** Release mechanics exist; the first “dream” arm did not dream | Q4, Q5 | Real pre-cutoff dream generation, independent verification, immutable release, and later-task A/B |
| ReasoningBank | Contrast successful and failed experiences into retrievable lessons | **Reviewed.** No runner | Q5, Q6 | Family-held-out no-skill/placebo/expert/ReasoningBank comparison |
| Hermes stable memory | Protected writes, source provenance, curator, snapshots, rollback | **Reviewed.** No Frankengate integration | Q4, Q5 | Render a reviewed release to harness memory, record exposure, rollback, and deletion propagation |
| Hermes Self-Evolution | Search over skill variants | **Reviewed and rejected as current baseline.** Reviewed revision had contract defects | Q5, Q6 | Use only a corrected, pinned revision with a verified skill-body mutation and sealed evaluator |
| GEPA / SkillOpt / Trace2Skill / EvoSkill | Bounded candidate search and hierarchical skill updates | **Proxy.** One tiny Trace2Skill mechanics run; no adequate outcome study | Q5, Q6 | Sealed selection/test split with no-skill, length placebo, expert, mined, and optimized arms |
| “Jeopard” | Intended self-improving skill system | **Missing/unresolved** | Q5, Q6 | Identify the exact repository/protocol before substituting another system |
| RL environment histories | Reset, action, observation, resource, termination, reward, and replay divergence | **Direct/mechanics on some datasets.** Flat traces remain insufficient | Q2, Q3, Q5, Q6 | Attach frozen environment state and compare recorded versus replayed transitions |
| CASS | Exact/fuzzy/semantic personal history search and compact evidence UX | **Reviewed.** No connector or query parity run | Q1, Q2, Q4 | Import the same native history into CASS and Frankengate and compare fielded recall and evidence previews |
| Doodlestein / CM | Local memory, bookmarks, compact context, and agent control ergonomics | **Reviewed.** No integration | Q1, Q4 | Translate the useful interaction primitives into governed native records and user tests |
| `claude-history` / Prompt-Scope | Local-first history organization, exact-term preservation, and reflection | **Reviewed/proxy.** Native history import and exact search exist | Q1, Q2 | Side-by-side personal-history task study |
| Frankensearch | Progressive hybrid search, exact preservation, reranking, and local control | **Reviewed.** No authorized corpus bakeoff | Q1, Q7, Q8 | Same authorized candidates, labels, and deletion tests against PostgreSQL baseline |
| PostgreSQL JSONB | Sparse provider/harness payloads alongside typed authority fields | **Direct/mechanics** | All substrate | Schema-evolution, hot-key promotion, compression, and query-plan study |
| PostgreSQL FTS/trigram | Exact/lexical/fuzzy retrieval | **Direct.** Useful baseline; tested hybrid was slow and weak | Q1-Q3, Q7 | Frozen human relevance set and selective-RLS load test |
| pgvector | Dense candidate generation inside the authority database | **Direct locally.** Exact vectors worked; no Aurora scale proof | Q2, Q7, Q8 | Exact-versus-ANN under selective RLS, deletion churn, concurrency, and Aurora failover |
| VectorChord | Compressed PostgreSQL-native ANN | **Reviewed/missing.** Not Aurora packaged | Q7, Q8 | Only after pgvector fails; same corpus and authority oracle on extensible/self-hosted PostgreSQL |
| `pg_textsearch` | PostgreSQL-native BM25 | **Reviewed/missing.** Not Aurora packaged | Q1-Q3, Q7 | Only after built-in FTS fails; same labels, WAL, RLS, backup, and deletion tests |
| pgContext | Filter-aware ANN, hybrid fusion, grouping, and compaction | **Reviewed/missing** | Q4, Q7, Q8 | Source maturity plus equal-authority benchmark after a named native failure |
| TurboVec | Compact in-process compressed vector scoring | **Reviewed/missing.** Not a database or authority | Q7, Q8 | Ephemeral authorized-candidate reranking benchmark only |
| Turbopuffer | Managed dense/sparse/text/filter retrieval | **Reviewed/missing.** Adds a policy/deletion boundary | Q7, Q8 | Escape-hatch bakeoff only after Aurora/native failure |
| General embeddings | Semantic candidate retrieval | **Direct baseline.** Structured features contributed more on current silver labels | Q2, Q7, Q8 | Human enterprise task-similarity and hard-negative labels |
| Enterprise-adapted embeddings | Organization-specific jargon and task similarity | **Missing** | Q7, Q8 | Frozen user/project/time-held-out contrastive experiment after general baseline failure |
| Agentic coding/research traces | Real tool-call-rich histories and longitudinal work | **Direct for ingestion/mechanics; weak outcome labels** | Q1-Q5, Q7 | Human labels and prospective interventions; public traces remain fixtures, not workforce samples |
| NL2SQL traces | Executable enterprise-like skill and replay domain | **Direct/mechanics.** Isolation/replay works; first skill factorial failed protocol and showed no arm difference | Q2-Q6, Q8 | Repair terminal protocol, then family-disjoint trace-mined skill intervention |

Primary project evidence is indexed in the
[trace research README](../../../research/trace-intelligence/README.md), the
[combined composition audit](trace-intelligence-enterprise-question-composition-audit.md),
the [memory/skill/replay matrix](memory-skill-replay-evidence-composition-matrix-2026.md),
the [ATIF crosswalk](atif-trace-schema-crosswalk-and-gap-analysis.md), and the
[RL storage review](rl-environment-trace-and-replay-storage-review.md).

## What the empirical results currently say

The broad audit of the committed result records found substantial conformance
work but only a small number of comparative mechanism studies.

| Experiment | Sample/design | Result | Interpretation |
|---|---|---|---|
| Cheap friction selection | 300 balanced attempts across 30 tasks | Signals enriched failures but did not reliably beat trace length | Signals remain selectors, not diagnoses |
| CodeTrace review selection | 148 rows, 30 selected | Structural selection tied length; random audit improved the estimate | More features did not establish better selection |
| Retrieval factorial | 145 documents, 99 queries, 87 silver-positive pairs | Structured+dense Recall@20 0.818; exact 0.732; dense 0.737; lexical often hurt | Structured evidence mattered more than dense alone |
| PostgreSQL joint retrieval | Same corpus | Exact pgvector Recall@20 0.667 at 3.0 ms local p50; hybrid 0.672 at 256.8 ms | Current fusion is not worth its latency |
| Step diagnosis | 35 aligned labeled traces, 2^3 factors | Simple baseline Top-1 0.286; full combination 0.171 | Current deterministic “all together” diagnosis is worse |
| Stored-trace assertions | 191-284 mutants depending on arm | High harmful-mutant kill; raw combined arm had 48.6% benign false positives | Retrospective mutation is useful but not deployable eval evidence |
| MATM memory depth | 355 paired task-model blocks, 2,130 rows | All retrieval-depth effects near zero; intervals crossed zero | No attributable memory benefit |
| Longitudinal memory pilot | 5 labels x 17 units x 5 calls | Evidence arms behaved identically; no-memory “win” was a scoring artifact | Pilot invalid for memory/dream comparison |
| Defog NL2SQL skills | 4 tasks x 3 arms | Every arm passed 2/4; protocol failures 25-50% | Mechanics only; no skill benefit |
| AgentTrace command replay | 400 selected, 17 executable pairs | 9/17 stdout/exit equivalent | Replay coverage is the bottleneck |
| Wisp governed history | 104 histories, 17,505 canonical events | Personal history/search/review queues worked under local RLS | Supports mechanics for Q1, not enterprise outcome claims |
| OTel real round trip | 12 traces, 48 spans | Tested projected IDs, parents, links, and statuses retained | OTel is a strong operational projection |
| Signals -> diagnosis -> eval-proposal proxy | 104 Wisp histories, 11 selected traces, 10 promotable hypotheses | Ten stored audits passed source evidence and detected decisive-evidence removal; ten prospective assertions behaved correctly on trace mutations | First natural-history chain mechanics; zero changed-system executions, upstream AgentEvals runs, or diagnostic gold |
| Memory mechanism factorial fixture | Six mechanisms, 64 arms, four authored queries, 256 blinded decisions | Bitemporal, structured evidence, and verbatim singleton arms each scored 4/4; all mechanisms also scored 4/4 | Proves isolation/composition and blinding mechanics only; all-together did not beat the strongest singleton |
| Recovery adjudication packet | 104 Wisp histories, 89 structural candidates, 87 complete blinded packets | Human-review evidence packs now cover relation, task outcome, cause, evidence strength, exploration, and candidate usefulness | Unlocks construct validation; the packets are unlabeled and do not yet establish recovery or cause |

The negative results are part of the architecture decision:

- More diagnosis factors made localization worse.
- Current memory labels did not produce distinct treatments.
- General dense retrieval alone added little on the current benchmark.
- The tested lexical/dense fusion added about 250 ms for negligible recall.
- NL2SQL skill seeding and memory-depth changes did not show benefit.

These results argue for better constructs, labels, and prospective outcomes,
not for immediately adding a more powerful database or model.

## Compositions that should be tested

### C1: Signals -> diagnosis -> eval -> changed-system replay

```text
canonical trace
  -> cheap Signals selector
  -> AgentRx/OpenRCA hypothesis arms
  -> AgentEvals assertion candidates
  -> human review
  -> reset changed-system replay
```

Independent factors:

- selection: random, recency/length, Signals;
- diagnosis: none, chronology, deterministic invariants, AgentRx, OpenRCA,
  blinded LLM reasoner;
- assertion: exact, ordered, unordered, invariant, semantic;
- system: original, harmful mutation, benign mutation, independently changed.

Primary outcomes:

- informative-trace precision;
- decisive-step Top-1 and Top-3;
- diagnosis calibration and abstention;
- harmful-regression recall;
- benign false-positive rate;
- prospective changed-system catch rate.

Kill criterion: the composed path does not beat the cheapest baselines, or the
evals cannot tolerate benign variation.

### C2: Temporal evidence -> extraction -> graph -> dream -> later use

```text
pre-cutoff evidence
  -> latest / bitemporal / relational graph / Graphiti arms
  -> deterministic / LangMem / model extraction arms
  -> no synthesis / real Dream synthesis arms
  -> independent verification and immutable release
  -> controlled later-task exposure
```

Primary outcomes:

- exact state selection at the decision cutoff;
- stale, future, contradiction, and unsupported rates;
- citation support and authority intersection;
- later-task success, time, cost, correction burden, and anchoring harm;
- withdrawal/deletion closure.

Kill criterion: temporal, graph, extraction, or dream arms do not improve
cutoff correctness or later outcomes over latest/no-memory/placebo, or increase
stale and anchoring harm.

### C3: Success/failure contrast -> procedure -> skill intervention

```text
family-disjoint successful and failed trajectories
  -> deterministic contrast / ReasoningBank / Trace2Skill arms
  -> no optimization / GEPA / SkillOpt bounded search arms
  -> reviewed immutable procedure
  -> no-skill / length-placebo / expert / mined intervention
  -> sealed NL2SQL execution and independent evaluator
```

Primary outcomes:

- execution accuracy and semantic result equivalence;
- policy acceptance and unauthorized-observation rate;
- task-family-held-out paired win rate;
- protocol failure, latency, cost, and rollback;
- transfer outside the mined schema family.

Kill criterion: mined procedures do not beat placebo, cannot generalize across
families, or only work when generator/evaluator information leaks.

### C4: Similar work -> shared artifact -> reciprocal collaboration

```text
authorized task signatures
  -> exact/structured/FTS/general-dense/adapted-dense retrieval
  -> blinded human same-work labels
  -> anonymous pattern or reusable artifact
  -> reciprocal opt-in introduction
  -> randomized artifact/introduction outcome
```

Primary outcomes:

- human Recall@k and nDCG on task similarity;
- reviewer agreement and useful-artifact precision;
- opt-in rate;
- verified task outcome, duplicated effort, time, and satisfaction;
- harm and re-identification checks.

Kill criterion: retrieval similarity does not predict useful knowledge
transfer, or introductions do not improve outcomes.

### C5: Friction taxonomy -> support hypothesis -> education intervention

Every repeated-friction candidate must be labeled across alternative causes:

- missing domain skill;
- missing tool skill;
- permission/access;
- stale or absent documentation;
- model/provider behavior;
- tool/protocol defect;
- environment or incident;
- quota/budget;
- ambiguous task;
- deliberate exploration;
- insufficient evidence.

Only then may the program compare suggested documentation, prompt, tool, skill,
route/model, or training interventions.

Kill criterion: reviewers cannot reliably distinguish these causes, or the
suggested intervention does not create prospective uplift.

### C6: General versus enterprise-adapted embeddings

This experiment begins only after C4 produces adjudicated labels and a frozen
hard slice where exact/structured/FTS/general dense is inadequate.

Factors:

- representation: exact/structured, general dense, enterprise-adapted dense;
- model input: whole trace, task/attempt summaries, structured multi-view;
- negatives: random, exact-identifier hard negatives, same-project different
  task, same-language different intent;
- split: user, team, project, time, and source family held out.

Promotion requires at least a preregistered material lift, such as +0.05
absolute Recall@20 on the hard slice, with no exact-ID, subgroup, latency,
memorization, deletion, or rollback regression.

## Compositions that should not be built as production stacks

| Non-composition | Why |
|---|---|
| Phoenix + Opik + Langfuse as three lifecycle authorities | They duplicate dataset, evaluator, feedback, revision, and deletion truth |
| ATIF or OTel as the canonical evidence store | Both are useful projections but omit load-bearing enterprise evidence semantics |
| Signals + vector similarity = diagnosis | Both select candidates; neither establishes cause or skill |
| Graphiti group or graph neighborhood = authorization | Entity grouping and proximity do not prove current scope |
| LangMem/Dream output -> direct `MEMORY.md` write | It skips evidence review, temporal validity, influence tracking, rollback, and deletion |
| ReasoningBank/Hermes output -> live skill mutation | Generator, evaluator, and later evidence can become circular |
| Later influenced traces -> independent validation | The artifact may have caused the evidence said to validate it |
| Dense trace neighbor -> named collaborator | Similar work does not establish social usefulness or consent |
| Failure count -> employee skill gap | Skill is confounded with access, tools, models, protocols, environment, task ambiguity, and exploration |
| Custom embedding before task-similarity gold | There is no valid objective or hard-negative set to optimize |
| External search/vector system before a frozen native failure | It adds authority, deletion, cache, failover, and operations paths without a demonstrated benefit |

## Minimal architecture mapped to mechanisms

| Layer | Production responsibility | Experimental mechanisms |
|---|---|---|
| Capture | Full model and tool lifecycle, source receipt, request identity | Native harness and historical import adapters |
| Canonical evidence | DAG, payload refs, task/attempt segmentation, outcomes | ATIF and OTel projections |
| Authority | User/team/enterprise scope, purpose, classification, policy and deletion epochs | RLS and permission-oracle tests |
| Temporal | observed, known, valid, release, withdrawal, and influence time | Latest, bitemporal, Graphiti-like arms |
| Selection | Cheap deterministic review queues | Signals detectors |
| Retrieval | Exact, structured, FTS, bounded pgvector | General/adapted embeddings and sidecar bakeoffs |
| Diagnosis | Evidence-linked hypotheses and alternatives | AgentRx, OpenRCA, blinded reasoner |
| Lifecycle | Candidate, review, release, exposure, evaluation, rollback | Phoenix/Opik/Langfuse import/export adapters |
| Memory | Cited proposal and rendered destinations | LangMem, Memory Palace, Dream, Graphiti |
| Skill | Frozen procedure candidates and sealed interventions | ReasoningBank, Trace2Skill, GEPA, SkillOpt, Hermes |
| Evaluation | Stored assertions and reset replay | AgentEvals and changed-system experiments |
| Organization | Anonymous patterns and artifact-first support | Reciprocal collaboration and education trials |

The online inference path must not wait for parsing, embedding, diagnosis,
dreaming, evaluation, skill mining, graph projection, or organization-level
analysis. Those are quota-bound worker jobs. Their failure should degrade an
analysis feature, not chat inference.

## Sequenced empirical program

| Order | Experiment | Why now | Architecture decision unlocked |
|---:|---|---|---|
| 1 | Full Signals detector replication on Wisp, Trace Commons, share-codex, CodeTraceBench, and NL2SQL | Cheapest broad selector test; current proxies are incomplete | Whether Signals belongs in every-trace processing |
| 2 | Human/adjudicated recovery and decisive-step label set | Diagnosis and eval work currently lacks valid gold | Enables AgentRx/OpenRCA/AgentEvals comparison |
| 3 | C1 diagnosis-to-changed-system replay | Directly tests suggested eval usefulness | Enables eval proposal UI |
| 4 | Corrected C2 temporal/latest/real-dream replication | Existing memory pilot is invalid | Enables or kills memory/dream product work |
| 5 | Repair NL2SQL terminal protocol and run C3 | Best executable skill-learning domain | Enables or kills trace-mined skill work |
| 6 | Build same-work and useful-artifact labels, then C4 | Required before cross-user product claims | Enables anonymous task patterns and collaboration trial |
| 7 | C5 support-intervention labels and trial | Required before education or “missing skill” claims | Enables private support suggestions |
| 8 | C6 embedding adaptation | Labels and hard slice finally exist | Enables or kills custom embeddings |
| 9 | Aurora operations gauntlet | Run against actual cardinality and concurrency | Confirms Aurora or triggers a one-database/sidecar bakeoff |
| 10 | Relational versus Graphiti, and native versus search sidecar, only on failed slices | Prevents framework collection | Adds only the component that wins |

Every result must separately report:

- mechanics/conformance;
- construct validity;
- comparative mechanism effect;
- prospective outcome effect;
- authority/deletion behavior;
- runtime, cost, and operational burden;
- limitations and forbidden interpretations.

The first corrected checkpoint has begun orders 1 and 2 without claiming they
are complete. A dependency-light Signals/AgentRx/AgentEvals-inspired proxy ran
on Wisp, but remains a proxy with no changed-system replay. The Wisp
adjudication builder produced 87 complete blinded recovery packets, but those
packets still require independent reviewers. A deterministic six-mechanism
memory fixture also established isolation and composition mechanics while
showing no fixture advantage for the all-mechanism arm over the best
singleton. These results narrow the next work to labels and prospective
outcomes rather than more storage plumbing.

## Durable execution graph

The broad study is tracked by GitHub research epic
[#90](https://github.com/pierretokns/frankengate/issues/90) and publication
issue [#96](https://github.com/pierretokns/frankengate/issues/96). The
dependency-aware execution units are deliberately narrower:

| Experiment family | GitHub issue | Bead |
|---|---|---|
| Friction, diagnosis, and trace-to-eval | [#92](https://github.com/pierretokns/frankengate/issues/92) | `bif-kyy.17.13.4.2` |
| Signals x diagnosis x changed-system replay | #92 child | `bif-kyy.17.13.4.2.3` |
| Multimodal OpenRCA-style ablations | #92 child | `bif-kyy.17.13.4.2.4` |
| Same-work retrieval and Aurora gate | [#93](https://github.com/pierretokns/frankengate/issues/93) | `bif-kyy.17.13.4.3` |
| Enterprise-adapted embedding study | #93 child | `bif-kyy.17.13.4.3.2` |
| Temporal and procedural memory | [#94](https://github.com/pierretokns/frankengate/issues/94) | `bif-kyy.17.13.4.4` |
| Graphiti/LangMem/Dreams/ReasoningBank comparison | #94 child | `bif-kyy.17.13.4.4.5` |
| Cross-user patterns and collaboration | [#95](https://github.com/pierretokns/frankengate/issues/95) | `bif-kyy.17.13.4.5` |
| Shared-artifact and reciprocal-introduction outcomes | #95 child | `bif-kyy.17.13.4.5.2` |

These are not implementation tickets for adopting every named framework.
They are falsifiable experiment units. A framework earns an integration ticket
only after its independent mechanism adds value and its composed arm retains
that value.

## Architecture reversal gates

### Leave Aurora or add a persistent query system only if

- a representative concurrent workload fails declared history/search,
  selective-RLS, deletion, failover, connection, or inference-isolation SLOs;
- bounded cardinality, typed predicates, exact fallback, partitioning,
  preaggregation, pooling, and worker isolation have been tested;
- the replacement passes the same permission-oracle, deletion, backup,
  failover, and cost tests;
- the result simplifies total operations rather than merely adding features.

### Add a graph service only if

a bounded temporal multi-hop benchmark materially beats relational
facts/edges, recursive SQL, and materialized views under equal authority and
deletion rules.

### Add a search or vector sidecar only if

it materially improves a named failed slice under the same labels and returns
only currently authorized candidate identifiers. It must prove stale-index,
tombstone, cache, timing, count, and failover behavior.

### Train an enterprise embedding only if

the program has reviewed positives and hard negatives, influence/deletion
lineage, person/project/time/source-family holdouts, and a frozen hard slice
that the general baseline fails.

## Source map

Primary external sources and pinned reviews:

- [Harbor ATIF](https://github.com/harbor-framework/harbor/tree/459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc)
- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai/tree/434c91dcc34ed038e3048c07720ddfed2c6bddfc)
- [OpenInference](https://github.com/Arize-ai/openinference/tree/789d41974c08a9a13147977f28ef4142a07e2106)
- [AgentRx](https://github.com/microsoft/AgentRx/tree/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d)
- [Signals paper](https://arxiv.org/abs/2604.00356)
- [AgentEvals](https://github.com/agentevals-dev/agentevals/tree/221febbe05927923242a5edc12e68a2b70fd5ae9)
- [Arize Phoenix](https://github.com/Arize-ai/phoenix)
- [Opik](https://github.com/comet-ml/opik)
- [Langfuse](https://github.com/langfuse/langfuse)
- [OpenRCA](https://github.com/microsoft/OpenRCA)
- [Graphiti](https://github.com/getzep/graphiti/tree/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d)
- [LangMem](https://github.com/langchain-ai/langmem/tree/56d85939d80bb731bd5e237567148d817d7bfd16)
- [MemPalace](https://github.com/MemPalace/mempalace/tree/8ab251c452c43f2b07a76a28f2433e258307f571)
- [Memory Palace](https://github.com/jeffpierce/memory-palace/tree/fd88282c1e2404d35d284dd09f622b4c1ec9b506)
- [OpenAI memory dreaming product description](https://openai.com/index/chatgpt-memory-dreaming/)
- [ReasoningBank](https://github.com/google-research/reasoning-bank/tree/ed80611788292ea739f1effd31f16c53823b8a0d)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent/tree/3ef6bbd201263d354fd83ec55b3c306ded2eb72a)
- [Hermes Self-Evolution](https://github.com/NousResearch/hermes-agent-self-evolution/tree/0a929e3aa20e15cf04dc7c28492a7d41a5139125)
- [Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill/tree/3d0b52a140f002a512930252b613c49048f7d5ac)
- [SkillOpt](https://github.com/microsoft/SkillOpt/tree/51d0a4d96e88558c84dee637f98e24e3fb2d1547)
- [GEPA](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975)
- [OpenEnv](https://github.com/meta-pytorch/OpenEnv/tree/65c506ef94bb1f7279cb4359673b3ef81031d01f)
- [Agent Lightning](https://github.com/microsoft/agent-lightning/tree/3b5d733861cf313fc09821a23240bbdf3cb2ee5b)
- [Trace Commons](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf)
- [CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d)
- [Defog SQL-Eval](https://github.com/defog-ai/sql-eval)
- [Spider 2.0](https://github.com/xlang-ai/Spider2)
- [TurboVec](https://github.com/RyanCodrai/turbovec)
- [TurboQuant](https://arxiv.org/abs/2504.19874)

## Bottom line

The broad program is not blocked on privacy tooling, a graph database, a new
vector store, or a custom embedding. It is blocked on four scientific assets:

1. independently adjudicated labels for informative traces, decisive failures,
   recoveries, same work, support causes, and useful artifacts;
2. resettable prospective evaluations rather than retrospective trace scores;
3. genuine distinct treatments for memory, dreaming, and skill learning;
4. influence lineage so the system does not validate its own outputs.

The architecture is worthwhile only if the staged experiments show that these
mechanisms answer Q2-Q8. Until then, the defensible product is Q1 plus
evidence-linked review and proposal workflows—not a claim that Frankengate
already understands the enterprise.
