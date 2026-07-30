# Frankengate trace intelligence: all-together system and experiment ladder

**Status:** normative synthesis and preregistration scaffold
**Date:** 2026-07-30
**Scope:** the smallest system that can support personal trace history, recurring-friction
analysis, eval and memory proposals, procedural learning, privacy-safe collaboration,
and evidence about which interventions help
**Non-goal:** claiming that public agent benchmarks reveal employee competence,
organizational performance, or causal benefit

## Decision

Build one governed evidence and intervention system, not a stack of trace, graph,
memory, vector, and RL products:

```text
native trace / imported public episode
  -> loss-aware canonical evidence DAG
  -> current authority, purpose, classification, and deletion gate
  -> deterministic features and exact/lexical/structured retrieval
  -> independently versioned diagnosis, fact, eval, and procedure candidates
  -> human-reviewed copy-on-write release
  -> isolated replay or prospective intervention
  -> independently observed outcome
  -> scoped utility and privacy-safe aggregate release
```

The production persistence boundary remains:

1. **Aurora PostgreSQL** as the only required authority and query system;
2. **conditional content-addressed object storage** for a measured class of large
   immutable artifacts; and
3. the existing gateway plus a bounded asynchronous analytics/eval worker.

PostgreSQL owns canonical events, authority, lineage, tasks, facts, experiments,
releases, embeddings, and compact aggregates. The object tier never becomes a query
or authorization authority. ATIF, OpenTelemetry/OpenInference, AgentEvals fixtures,
memory files, and learner batches are versioned projections of the same governed
evidence, not parallel sources of truth.

This architecture is sufficient to test the product at several hundred GB. The hard
problems are evidence quality, task boundaries, authorization, causal identification,
and safe product policy—not vector throughput. The database decision and its
replacement gate are specified in the
[minimal storage architecture](./log-trace-vector-database-and-reflective-learning-review.md);
the field-level format boundary is specified in the
[ATIF crosswalk](./atif-trace-schema-crosswalk-and-gap-analysis.md).

## What the complete system can truthfully claim

Use four claim classes throughout the API, UI, experiment registry, and paper:

- **D — descriptive now:** computable from authorized evidence without a learned
  interpretation;
- **H — hypothesis now:** evidence-backed candidate that requires a person or
  independent verifier;
- **P — prospective only:** a causal or organizational claim requiring consented,
  private, longitudinal intervention data;
- **R — refuse:** not identifiable from the intended evidence or unacceptable as a
  workforce product.

| User or enterprise question | Class | Smallest truthful answer | Minimum evidence | Boundary |
|---|---:|---|---|---|
| Can a user see all their own prompts and tool activity? | D | “These are all currently authorized records, plus explicit missing, redacted, pending-object, and import-loss states.” | Subject identity, capture manifest, canonical events, current authorization epoch, stable pagination, deletion receipts | Never render absence as “no activity” when collection, import, cold-object, or authorization state is incomplete |
| Which of my attempts deserve review? | H | “These attempts triggered named deterministic signals; a random audit sample is also included.” | Versioned signals, selection propensity, evidence previews | A signal is not a failure or skill label; the completed Nebius pilot did not beat trace length at the fixed review cutoff |
| What repeated friction preceded eventual success? | H | “These linked attempts contain this ordered recovery delta and these plausible alternatives.” | Attempt lineage, environment/model/permission revisions, independently observed outcome, ordered delta | Observed recovery is associational until add/remove replay or a prospective intervention |
| Which tasks are similar? | H | “These authorized attempts share these objective, entity, tool, environment, artifact, and action dimensions.” | Adjudicated task boundaries, multi-view signature, hard-negative benchmark | Similar text is neither the same work nor permission to reveal another person |
| Who is doing related work? | P | “A privacy-approved reusable pattern exists; participants may opt into an introduction around the artifact.” | Stable private cohorts, mutual consent, minimum cohort, anti-differencing tests | No named people finder, manager drilldown, inferred collaboration graph, or productivity ranking |
| What work are people doing? | H/P | “These observed gateway-mediated task families occurred with this measured source coverage.” | Capture propensity, source coverage, task labels, privacy-safe aggregates | Frankengate cannot observe off-platform work, effort, motivation, or total workload |
| What cloud or domain capability might help? | H/P | “Capability X may help this task family; blocker Y and counterevidence Z remain possible; here is an optional private check.” | Organization task-capability ontology, environment/permission controls, expert labels, optional practical eval | Never assert that a named employee “lacks a skill” from prose, retries, model judgments, or failure counts |
| What should become an eval? | H | “This trace can become this exact, ordered, invariant, semantic, or replay case; here are the mutations it catches.” | Canonical evidence, target failure, evaluator revision, known mutants, scope-safe fixture | A stored-trace assertion is an audit unless the changed agent is rerun |
| What should become memory? | H | “This cited, temporal, scoped candidate can be reviewed for release to destination X.” | Source propositions, contradiction set, valid/system time, classification, reviewer, expiry, deletion lineage | No automatic transcript dump, silent in-place `MEMORY.md` mutation, or scope widening |
| Which procedure should be suggested? | P | “This versioned procedure is applicable here and improved held-out outcomes under this experiment.” | Independent induction/test tasks, applicability rules, no-memory and placebo controls, external verifier | Success of source traces does not prove that the induced procedure caused success |
| Which prompt, retrieval rule, skill, memory, route, or model helps? | P | “This reversible intervention improved named outcomes at this exposure rate and cost, with these harms.” | Exposure assignment, propensity, independent outcome, delayed harm, rollback | Historical co-occurrence cannot choose among interventions |
| Should we adapt an embedding? | H/P | “A domain adapter fixes this frozen retrieval error after exact, lexical, structured, general-dense, and reranking baselines.” | Purpose-authorized reviewed pairs/hard negatives, user/tenant/time split, exact-ID and deletion tests | Embedding adaptation cannot solve task segmentation, causal attribution, authority, or memory truth |
| Should we fine-tune a generator? | P | “Lower-cost reversible interventions failed on a stable behavior and a governed training release passed memorization, deletion, and regression gates.” | Prospective eval corpus, training authorization, immutable manifest, rollback | Public traces or every “successful” enterprise trace are not automatic training positives |
| Who is productive, loyal, competent, or likely to leave? | R | No answer | None | These are prohibited workforce inferences, not trace-intelligence questions |

Public datasets can support format, retrieval, localization, mutation, extraction, and
sandbox-replay mechanism claims. They cannot support the private organizational claims
in the P rows. The
[public dataset inventory](./public-agent-trace-dataset-inventory.md) documents this
external-validity boundary.

## The smallest complete system

### 1. One canonical evidence DAG

The canonical record preserves typed events and partial order:

- user, model, orchestrator, subagent, retrieval, memory, tool, policy, and external
  actor identity;
- task, session, attempt, provider-attempt, fallback, branch, join, and continuation
  identity;
- tool proposal, authorization decision, execution, observation, independently
  observed state delta, and later use in reasoning as separate events;
- retries, concurrency, streaming boundaries, truncation, cancellation, and malformed
  events;
- model, prompt, tool-schema, policy, environment, adapter, and source revisions;
- observed, reconstructed, inferred, missing, redacted, and quarantined provenance;
- source hash, adapter hash, loss receipt, and content-addressed artifact references;
- subject/team/enterprise scope, purpose, classification, consent, authorization
  epoch, retention, and deletion lineage.

ATIF v1.7 is the portable sequential conversation/action projection. OTel/OpenInference
is the operational timing/span projection. An environment manifest supplies reset and
replay semantics. A learner attachment supplies token IDs, masks, log probabilities,
and policy lineage only when training requires them. No projection may silently repair
or discard evidence; every adapter emits a machine-readable loss receipt. See the
[RL environment review](./rl-environment-trace-and-replay-storage-review.md) for the
R0 forensic, R1 action, R2 deterministic reset, and R3 state-continuation vocabulary.

### 2. One authority envelope on every source and derivative

Every evidence, feature, embedding, fact, diagnosis, eval, memory, procedure,
experiment, aggregate, cache entry, and artifact reference carries:

```text
tenant_id
subject_id?       team_id?          project/case_id?
audience
classification
purpose
consent/training eligibility
authorization_epoch
policy_revision
retention/deletion state
source_evidence_ids[]
derivation_revision
```

Derived scope is the **intersection** of its source scopes and current policy, never
their union. A team or enterprise result is a new privacy-reviewed release, not a
query-time change from `user_id = X` to `team_id = Y`. Evidence deletion,
reclassification, membership removal, or purpose revocation makes every derivative
immediately non-returnable; physical deletion may converge asynchronously under a
recorded SLO.

### 3. Five independent analysis planes

The system deliberately keeps these outputs distinct:

| Plane | Mechanism | Output | It does not establish |
|---|---|---|---|
| Selection | Deterministic rephrase, loop, stagnation, error, cost, latency, disengagement, and environment signals | A budgeted review queue plus sampling propensity | Failure, cause, intent, competence, or prevalence without random audit |
| Retrieval | Exact fields, FTS/trigram, structured task/action signatures, optional separate dense views and reranker | Authorized candidate evidence with why-matched fields | Truth, causal usefulness, identity disclosure, or a task label |
| Diagnosis/eval | Declarative invariants, topology/modal evidence, calibrated judge with alternatives/abstention, mutation-tested assertions | Evidence-linked hypotheses and retrospective/replay eval proposals | Root cause without intervention; future behavior from a stored trace |
| Knowledge/memory | Source propositions, bitemporal facts, contradiction handling, typed extraction, copy-on-write consolidation | Reviewed fact/memory release and destination projection | Policy, universal truth, or permission to mutate live memory automatically |
| Procedure/intervention | Success/failure contrast, modular playbook induction, applicability, isolated replay, exposure/outcome registry | Versioned skill/playbook and measured utility | General capability, clean credit, or transfer beyond tested tasks/scopes |

This separation is the core compositional rule. The planes join through immutable
evidence IDs and experiment releases, not through one mutable “insight” object.

### 4. A governed release graph

No stochastic analyzer writes directly into a user or organization memory, skill,
eval suite, prompt, router, or model. It proposes a release:

```text
candidate
  -> evidence and missingness review
  -> scope/classification/deletion closure
  -> contradiction and applicability checks
  -> frozen artifact
  -> shadow or replay
  -> human approval where required
  -> immutable release
  -> influence/exposure log
  -> promote, supersede, expire, rollback, or delete
```

Dreams contributes the copy-on-write input/output-store boundary. LangMem contributes
typed extraction. Graphiti contributes temporal fact and contradiction concepts.
Memory Palace contributes verbatim evidence and source-oriented retrieval. Hermes
contributes useful declarative/episodic/procedural destination ergonomics. ReasoningBank,
LEGOMem, ACE, GEPA-like methods, and other self-evolving-skill systems contribute
competing procedure-generation hypotheses. Their automatic mutation and separate
storage products do not compose; the
[dreaming and skill review](./dreaming-memory-palace-hermes-skill-learning-review.md)
specifies the safe release contract.

### 5. A prospective intervention registry

Every recommendation that could affect later work records:

- diagnostic hypothesis and alternatives;
- intervention type, artifact revision, owner, and applicability;
- eligible population and exclusion rules;
- assignment or exposure propensity;
- whether the user viewed, accepted, edited, or used it;
- immediate and delayed independently observed outcomes;
- cost, latency, corrections, privileged actions, safety events, and subgroup harms;
- influence lineage into later traces and derived artifacts.

This registry is the bridge between trace mining and learning. Without it,
Frankengate can generate plausible suggestions but cannot learn which ones help.

## User, team, and enterprise boundaries

### Personal scope

A user may search and inspect their own currently authorized history and personal
derived candidates. The personal UI may show source evidence, missingness, corrections,
and private support opportunities. A personal memory release may use only evidence the
user can currently inspect and must remain editable, expiring, and reversible.

### Team scope

Team membership does not automatically authorize raw peer traces. A team release may
contain:

- a reviewed runbook, eval, alias, task pattern, or procedure whose source owners and
  policy permit team use;
- a cohort statistic that passes minimum-count, contribution-bound, complementary
  suppression, rare-pattern, and query-history controls; or
- a reciprocal opt-in introduction escrow that reveals identities only after both
  participants consent.

It may not contain a named friction list, inferred skill ranking, raw nearest-neighbor
drilldown, or aggregate with a one-person complement.

### Enterprise scope

Enterprise views contain coverage-qualified task demand, recurring system/tool/policy
friction, missing shared artifacts, eval coverage, and intervention outcomes at
approved cohort granularity. They do not expose raw user histories or enable a manager
to pivot an aggregate into a person. Cross-team patterns must be materialized privacy
releases, not arbitrary live group-by queries.

### Required RLS and side-channel tests

The permission oracle must equal all rows, IDs, counts, snippets, distances, cursors,
object references, cache results, timing classes, and exports under:

- current and stale authorization epochs;
- membership removal during a query or stream;
- reader lag, failover, transaction-pool reuse, savepoints, and reconnect;
- FTS, exact-vector, filtered-ANN, reranker, and graph-edge traversal;
- classified evidence mixed into an otherwise shareable artifact;
- deletion after candidate generation but before expansion or object hydration;
- repeated aggregate queries, differencing, rare cohorts, and complementary subsets;
- model-generated output that quotes unauthorized evidence.

Any cross-scope disclosure blocks team and enterprise release. A fail-closed result
must distinguish malformed authority, denial, zero eligible candidates, zero matches,
and unavailable derived state so that the semantic-cache failure mode is not repeated
as silent “no results.”

## Compositions that are invalid or redundant

| Proposed combination | Decision | Why it does not compose |
|---|---:|---|
| ATIF + OTel as two canonical stores | Reject | ATIF linearizes; OTel omits environment and governance semantics. Duplication creates conflicting authority and deletion paths. Keep one DAG and tested projections. |
| Phoenix + Opik + Langfuse | Reject | Their overlapping trace/dataset/experiment products add authorities, not independent scientific mechanisms. Adopt the lifecycle once in native tables. |
| Graphiti as a production graph authority | Reject initially | Temporal facts and contradiction handling are useful; its stochastic extraction, graph backend, and `group_id` do not supply Frankengate RLS or truth. Test it ephemerally against relational facts. |
| Signals + whole-trace embeddings = diagnosis | Reject | Both are candidate selectors. Neither identifies the decisive step, environment blocker, missing knowledge, or causal intervention. |
| AgentRx lossy IR as canonical evidence | Reject | Tool/timing/topology semantics become strings or disappear. Project the richer DAG into a deterministic, evidence-linked invariant input. |
| Stored AgentEvals trace + changed-system claim | Reject | A historical assertion can audit the recording; only rerun/replay tests changed behavior. |
| Automatic Dream/LangMem/Memory-Palace writes | Reject | Extraction error becomes future context and can self-confirm. Use candidates, separate releases, influence lineage, expiry, and review. |
| Graph centrality or retrieval count = importance | Reject | Popularity feedback suppresses rare critical procedures and measures the system's previous choices. |
| Successful trace = good procedure | Reject | Success can coexist with unnecessary, unsafe, lucky, or policy-violating steps. Contrast failures and verify held-out utility. |
| Recovery delta = causal skill evidence | Reject | Environment, model, permission, incident, feedback, and task-difficulty changes confound it. |
| Semantic similarity = who should talk | Reject | It creates reidentification and surveillance risk and does not establish mutual usefulness. Share a minimized artifact; introductions are opt-in. |
| Custom embedding before frozen hybrid benchmark | Reject | It adds training, deletion, drift, and rollback burden without establishing a semantic failure worth fixing. |
| Utility ranker before randomized exposure | Reject | Historical selections have unknown propensities and confounded credit. Rules remain the baseline until intervention data exists. |
| Public coding traces = enterprise workforce evidence | Reject | Public corpora test mechanisms, not user consent, organizational scope, private jargon, delayed business outcomes, or competence. |
| RL trainer batch as evidence authority | Reject | Token masks, tensors, and policy log probabilities are disposable learner projections; they routinely omit raw failures, state, and authorization. |
| A full \(2^N\) “everything” factorial | Reject | It is underpowered, expensive, and uninterpretable. Validate blocks, freeze them, then run a staged end-to-end ladder. |

## Causal-identification boundary

Let:

- \(T\) be task family and difficulty;
- \(U\) be prior user knowledge and experience;
- \(E\) be environment, permissions, incidents, tools, model, and policy;
- \(S\) be a suggestion or memory/skill exposure;
- \(Y\) be the independently verified outcome.

Historical deployment generally contains:

```text
T, U, E -> probability of receiving S
T, U, E -> Y
S       -> Y  (the effect we want)
```

Consequently, \(P(Y \mid S)\) is not the effect of \(S\). Stronger users may seek a
playbook; the system may show help only on difficult tasks; permissions may be repaired
between attempts; and the model or environment may change. Outcome-conditioned memory
also creates feedback: a released artifact influences future traces, which can then
appear to validate the artifact.

Use this hierarchy of evidence:

1. **retrospective association:** useful for candidate generation, never causal
   wording;
2. **sandbox add/remove replay:** supports a causal claim only for the pinned,
   replay-fidelity-qualified environment;
3. **randomized user/task exposure:** preferred for prompt, retrieval, memory, and
   playbook utility;
4. **stepped-wedge or randomized encouragement:** acceptable when withholding a
   generally available intervention is impractical;
5. **observational adjustment/off-policy analysis:** exploratory unless propensities,
   overlap, negative controls, sensitivity bounds, and stable outcome collection pass;
6. **delayed private outcomes:** required before claims about durable skill support or
   business benefit.

Replay cannot prove real-world transfer. Public data cannot identify \(U\), enterprise
coverage, or delayed benefit. A model judge cannot be the sole measure of \(Y\).

## Component ladder

Each level is independently releasable and supplies prerequisites for the next. A
later level cannot rescue a failed earlier gate.

| Level | Added mechanism | Claim enabled | Pass gate | Kill or fallback |
|---|---|---|---|---|
| L0 — evidence conformance | Canonical DAG, raw source, adapter/loss receipt, ATIF/OTel projections, environment/evaluation/replay attachments | Imported evidence is represented honestly | 100% gold tool/auth/outcome preservation; at least 99.5% typed-event and edge preservation; deterministic reimport; zero silent loss | Quarantine unsupported sources; no downstream analysis on lossy imports |
| L1 — personal authority | Full subject/team/purpose/classification/epoch RLS, deletion closure, keyset history, exact search, corrections/export | A user can trust “all my currently authorized history” | Permission-oracle equality across rows, counts, snippets, objects, caches, failover; explicit capture/missingness status | Stop team/enterprise work on any leak; retain personal listing only if complete and explainable |
| L2 — cheap evidence finding | Materialized deterministic signals, structured task/action signatures, FTS/trigram, random audit stratum | Review queues and exact-first evidence retrieval | Exact IDs 100%; signals improve gold-informative precision by at least 15 points over random and do not miss over 10% of critical cases after audit; cost/latency SLO | Keep signals as filters or remove them; trace length remains an honest baseline |
| L3 — diagnosis and eval proposals | Invariants, topology/modal join, calibrated abstaining judge, mutation-tested assertions | A decisive-step hypothesis and candidate audit/replay eval | At least 10-point top-1 gain over deterministic error baseline; calibrated selective risk; meaningful mutant-kill gain without normal-variation brittleness | Ship deterministic evidence and manual eval builder; disable “cause” and automatic taxonomy |
| L4 — semantic candidate retrieval | Sparse task-view embeddings, exact vector oracle, optional HNSW, fusion/reranker | Semantically related task/failure/recovery candidates | Hybrid beats exact+lexical+structured on named hard slice; filtered ANN meets exact-oracle recall under most selective RLS; inference SLO isolated | Keep SQL/FTS/structured only; do not change database for an unproven quality gain |
| L5 — temporal knowledge and Dream releases | Source propositions, bitemporal facts, contradictions, candidate extraction, copy-on-write consolidation, review/diff/rollback | Cited memory/fact proposals that remain current and scoped | At least 99% citation support, 95% factual precision, strong contradiction/time accuracy, zero authority leak, bounded review burden | Keep verbatim retrieval and manual notes; no live-memory projection |
| L6 — procedural replay | Outcome-conditioned contrast, modular procedures, immutable variants, R0-R2 replay, placebo/oracle arms | A procedure helps held-out tasks in a pinned environment | Positive intention-to-treat effect in at least two domains, deterministic controls reproduce, no critical-slice harm above 5%, independent verifier | Retain procedures as reviewed documentation; no utility or learning claim |
| L7 — intervention learning | Exposure/propensity registry, no-intervention baseline, applicability rules, utility reranker, delayed outcomes | Which reversible intervention helps which task context | Prospective gain over semantic+rules; calibrated benefit, cost, and harm under time/model shift; adequate overlap | Keep deterministic applicability and user choice; no learned routing |
| L8 — team/enterprise releases | Stable cohorts, bounded contributions, suppression, privacy attack suite, reciprocal opt-in | Shared patterns, artifacts, demand, and collaboration opportunities | Useful results survive minimum-cohort and anti-differencing controls; no identity/classified recovery; correction/appeal works | Stay personal; do not weaken privacy to recover utility |
| L9 — domain embedding adaptation | Reviewed pairs/hard negatives, purpose-specific training release, frozen general-hybrid benchmark | Better semantic candidate recall for a named corporate failure | At least +5 absolute Recall@20 on frozen hard slice; no exact-ID, subgroup, deletion, latency, or rollback regression | Retain general model or no dense retrieval |
| L10 — generator adaptation | Governed training corpus, stable behavior eval, memorization/deletion tests, canary/rollback | Narrow model behavior improves after cheaper controls failed | Prospective benefit over prompt/skill/tool/retrieval/routing; no critical regression or unverifiable deletion obligation | Do not fine-tune; improve source, tool, procedure, or routing instead |

The initial product boundary is L0–L3 plus proposal-only parts of L5. L4 is a measured
retrieval optimization. L6–L10 are research or private prospective programs, not
launch promises.

## Experimental corpus

Use each source only for claims its evidence can support:

| Corpus | Primary role | Important limitation |
|---|---|---|
| MCP ATIF benchmark | ATIF conformance, tool-call/observation correlation, mutation fixtures | Small synthetic format fixture, not performance evidence |
| Exgentic v1 | OTel-shaped ingestion, session grouping, reconstructed-tool loss receipts | Reviewed sample represented tool activity inside chat spans, not independent timed tool spans |
| CodeTraceBench verified/full | Gold-like decisive-step, stage, task-family, retrieval, and mutation work | Coding domain; verified subset and parent records must remain in the same split |
| Nebius SWE-agent matched attempts | Cheap signals, within-task success/failure contrast, recovery candidates | Outcome proxy, no authorization, reconstructed tools, balanced sample cannot estimate prevalence |
| SPARK PDI | Repeated attempts, failure-to-success transitions, memos and skill artifacts | Observational passes differ in more than one mechanism |
| `pagarsky/agent-trace` | Deterministic tool preservation, assertion mutations, causal no/relevant/placebo procedure replay | Narrow NL2Bash/programming external validity |
| Trace Commons | Importer reality check, interruptions, exact identifiers, organic friction | Tiny volunteer sample, privacy/licensing review, sparse outcomes |
| Open Agent Traces | Known anomaly, order, branch, and process-mining controls | Synthetic regularity |
| BrowserGym/WebArena, τ²-bench, SWE-Gym | Forensic artifacts, reward evidence, state/action replay and replay-level qualification | Environment-specific fixtures; action history alone is not deterministic replay |
| **CMU `cx-cmu/agent_trajectories`** | Private exploratory repeated-pass, multi-benchmark, multi-model outcome analysis | Gated and no declared license; 1,445 incomplete/crashed/truncated trajectories were removed, creating survivorship bias |

The user has authorized using the CMU corpus for internal research. That does not
resolve its publication or redistribution rights. Pin its Hugging Face revision and
input hashes; store it outside Git; publish only code, manifests, and results permitted
by its eventual license. Until licensing is clarified, label every CMU result
“private exploratory,” never make it the sole evidence for a claim, and model the
documented failure-removal selection process. Do not infer natural failure prevalence
from it.

Split by task, issue, repository/template family, source, and near-duplicate group.
Private extensions add user, tenant, team, and time grouping. A trace, task, generated
memory, or close descendant cannot cross induction and evaluation folds. Failure,
crash, timeout, truncation, and infrastructure-error records are outcomes, not
exclusions.

## Block factorials and ablations

The experiment program uses small interpretable factorials. All outputs and thresholds
are frozen before downstream blocks consume them.

### F0 — representation and projection

For every source family:

```text
native -> canonical -> native-neutral rendering
                    -> ATIF projection + loss receipt
                    -> OTel projection + loss receipt
                    -> replay manifest where supported
                    -> learner attachment where present
```

A mutation suite independently deletes, duplicates, reorders, branches, retries,
redacts, truncates, and changes parentage, authorization, state-delta, environment,
reward, and token-lineage fields. Metrics are typed-field/event/edge recall, order
constraint preservation, missingness honesty, reimport hash, storage amplification,
and adapter runtime. Zero silent loss is non-negotiable.

### F1 — review selection

Compare at identical review budgets:

1. uniform random;
2. trace length/token/cost;
3. publisher outcome, reported only as an unattainable oracle where applicable;
4. each deterministic signal independently;
5. frozen union/score;
6. frozen score plus mandatory random audit stratum.

Annotators, blinded to outcome and arm, label “diagnostically informative,” accidental
versus productive friction, and insufficient evidence. Report precision/recall at
budget, critical-case miss rate, inverse-propensity prevalence, per-dataset disparity,
latency, and compute cost. The
[Nebius matched pilot](../../../research/trace-intelligence/experiments/summaries/nebius-matched-pilot-2026-07-30.md)
is a valid harness smoke test and a negative/ambiguous result: fixed friction scoring
had 73.3% failure-proxy precision at a 20% budget versus 76.7% for trace length, while
its AUROC was 0.639 versus 0.609; paired task-cluster intervals included zero.

### F2 — task and evidence retrieval

Use a blocked design rather than unrelated model bakeoffs:

| Factor | Off | On |
|---|---|---|
| Structured task/action views | Raw prompt fields | Objective, entities, tools, environment, artifact, failure, recovery, outcome |
| Lexical | Exact identifiers only | FTS/trigram with quoted identifier preservation |
| Dense | None | Separate general embeddings for objective, environment, failure, and recovery |
| Reranking | Deterministic fusion | Cross-encoder or calibrated LLM reranker |

Run the \(2 \times 2 \times 2\) structured/lexical/dense core first; rerank only the
best preregistered dense and non-dense candidates. Exact authorized vector search is
the dense recall oracle. Report Recall@20, nDCG@20, MRR, hard-negative error, exact-ID
recall, calibration, p50/p95/p99 latency, bytes, build/rebuild time, and cost under RLS
selectivity buckets. Add a domain-adapted model only if the best hybrid misses a named
important slice.

### F3 — diagnosis

Run the interpretable \(2 \times 2 \times 2\) design:

- declarative invariants absent/present;
- ordered topology and separate logs/metrics/policy/environment evidence absent/present;
- calibrated LLM judge absent/present.

Include random-step, first-error, last-error, reward-only, and full-summary baselines.
The judge emits event IDs, alternatives, missing evidence, and abstention. Negative
controls shuffle order, change timestamps, remove the decisive step, inject irrelevant
errors, and swap environment/permission context. Report top-1/top-3 step accuracy,
MRR, taxonomy macro-F1, risk-coverage, Brier/ECE, evidence entailment, latency, tokens,
and judge instability. Never execute generated unrestricted checkers.

### F4 — eval proposal

Cross assertion type with mutation type:

- exact value/event;
- ordered required subsequence;
- unordered required set;
- forbidden event or invariant;
- semantic terminal condition;
- independent state assertion when available.

Mutations remove, duplicate, reorder, deny, alter arguments/results, inject errors,
truncate, change fallback or policy decisions, and change terminal output/state.
Compare deterministic-only, judge-only, and combined assertions. Primary metrics are
mutant kill rate and false-positive rate on allowed variation. Maintenance edits and
audit-versus-replay labeling are first-class outcomes.

### F5 — fact and memory proposal

Run the \(2 \times 2 \times 2\) factorial:

- typed candidate extraction absent/present;
- bitemporal entity/fact/contradiction model absent/present;
- copy-on-write consolidation absent/present.

Include no-memory, verbatim retrieval, and flat rolling-summary controls. Inject
corrections, expiry, aliases, same-name/different-entity cases, conflicting sources,
scope changes, deletion, and prompt injection. Score proposition precision/recall,
citation support, contradiction recall, valid-time answers, entity merge/split error,
unsupported novelty, compression, reviewer effort, deletion closure, and scope leaks.
No arm writes live memory.

### F6 — procedure generation and replay

Separate generation factors from treatment assignment:

Generation \(2 \times 2 \times 2\):

- successful-only versus successful/failed contrast;
- monolithic versus orchestration/execution separation;
- one-shot summary versus incremental curated delta.

Freeze every procedure, then randomly assign held-out replay tasks to:

1. no procedure;
2. relevant procedure;
3. unrelated but superficially similar placebo;
4. oracle human-authored procedure where available.

Hold retrieval, model, tools, limits, and environment fixed; run repeated seeds. Report
intention-to-treat verified success, attempts, turns, tokens, latency, cost, unsafe or
privileged actions, verifier use, correction burden, replay divergence, and subgroup
effects. Run first on deterministic `pagarsky`/SWE-Gym/τ²-bench tasks, then replicate
winning mechanisms across at least two domains. A memory influenced by a source task
cannot validate itself.

### F7 — utility routing

Only after F6 finds procedures with causal utility, compare:

1. no intervention;
2. random eligible intervention;
3. semantic top-1;
4. semantic plus deterministic applicability;
5. learned utility reranker;
6. retrospective oracle.

Train on randomized exposure outcomes, not self-scores. Report success at budget,
regret to oracle, calibration, overlap/propensity diagnostics, time/model shift,
deletion behavior, and harm. If randomized exploration is unavailable, label the
result associational and do not ship learned routing.

### F8 — private enterprise validation

Public traces do not enter this block as user evidence. With consented Frankengate
data, test:

- task-family label agreement and source-coverage estimates;
- private support-card acceptance and correction;
- stable repeated-friction patterns after environment/permission adjustment;
- randomized or stepped-wedge prompt, retrieval, skill, and memory interventions;
- aggregate utility after minimum cohorts and suppression;
- red-team reconstruction of people/classified evidence from counts, snippets,
  similarity, timing, and repeated queries;
- reciprocal collaboration opt-in, false-introduction, and rejection rates.

The primary enterprise release is a reusable artifact or demand pattern, not an
employee score.

## End-to-end composition arms

After block gates pass, freeze one winner or honest baseline per block and add
components cumulatively:

| Arm | Frozen composition | Incremental question |
|---|---|---|
| C0 | Canonical evidence + RLS + exact fields | Can evidence be listed and audited safely? |
| C1 | C0 + FTS/structured retrieval + deterministic signals | Can useful evidence be found cheaply? |
| C2 | C1 + invariants/topology diagnosis + eval proposals | Can the system localize and turn failures into stable tests? |
| C3 | C2 + sparse dense task views/reranker, only if F2 passes | Does semantic retrieval add value after exact structure? |
| C4 | C3 + temporal facts + copy-on-write memory release | Does cited consolidation improve future context without truth/scope regressions? |
| C5 | C4 + contrast-derived procedures + isolated replay | Do learned artifacts improve held-out executable outcomes? |
| C6 | C5 + prospective applicability/utility routing | Can the system select the lowest-cost useful intervention? |
| C7 | C6 + privacy-reviewed team/enterprise releases | Does cross-user learning retain utility after governance controls? |

Do not interpret the C0-to-C7 difference as one causal component effect. The
incremental adjacent-arm difference is the estimand, and only when upstream releases,
task assignment, and outcome collection are frozen. If C3 fails, C4 proceeds from C2;
dense retrieval is not a mandatory dependency. If C5 fails, C6 has no learned utility
target. If C7 fails privacy or utility, the product remains personal.

## Local PostgreSQL/Aurora-like test topology

Use the existing
[`tests/kubernetes/local-aurora`](../../../tests/kubernetes/local-aurora/README.md)
fixture: PostgreSQL 16 plus pgvector 0.8.1 in the disposable
`frankengate-test` namespace. It can test SQL, transactions, RLS, indexes, leases,
restart, notification loss, cold bootstrap, and multi-process behavior. It is not an
Aurora emulator and cannot support claims about writer failover, RDS Proxy, AWS
parameter groups, cross-AZ/global-database behavior, or AWS cost.

The local experiment topology is:

```text
pinned read-only public/CMU input cache
  -> importer/adapters
  -> PostgreSQL canonical + experiment schemas
  -> bounded worker lanes
       deterministic projection
       retrieval/index
       diagnosis/eval
       memory/procedure
       aggregate/privacy
  -> content-addressed local artifact directory
  -> experiment manifests and paper tables
```

Use one database and one fixture at a time. Separate experiment schemas, run IDs,
leases, and resource quotas are sufficient; multiple permanent database containers or
per-method stores would test the wrong architecture. Ephemeral Graphiti or upstream
tool databases are allowed only inside a method-parity arm and are destroyed after
exporting evidence-linked results.

### Local database gauntlet

Run every relevant C arm while varying:

- 1, 10, and 50 concurrent interactive history/search clients;
- bounded background ingest, FTS, embedding, eval, and aggregate workers;
- RLS scopes from broad personal to highly selective classified subsets;
- exact vector versus HNSW candidates, iterative scan/overfetch, and exact fallback;
- source delete/reclassify during query, ANN, rerank, stream, and object hydration;
- PostgreSQL restart, connection loss, lost `NOTIFY`, lease expiry, and cold rebuild;
- stale cursor, old projection, job retry, duplicate delivery, and partial artifact
  upload;
- data volume scale factors, using generated metadata and vectors without claiming
  synthetic payloads reproduce Aurora I/O.

Primary operational metrics are inference p99 impact, history/search p95/p99,
authorized recall, queue age, connection saturation, index/rebuild time, WAL/storage
amplification, deletion non-returnability and physical convergence, worker CPU/memory,
and API/model cost. Analytics degrades or pauses before gateway inference.

Any release claim about Aurora additionally requires a real-Aurora conformance run for
supported extension version, parameter limits, RDS Proxy/session behavior, replica lag,
writer failover, backup/restore, and measured I/O/cost.

## Cost and complexity budget

Count persistent systems and scientific/model operations separately:

| Capability | Persistent-system cost | Incremental compute/cost | Main operational burden | Default |
|---|---:|---:|---|---:|
| Canonical history/RLS/FTS | 0 beyond Aurora | Low, deterministic | Migrations, indexes, deletion closure | Required |
| Deterministic signals/invariants | 0 | Low | Versioning and label calibration | Required |
| Sparse task embeddings | 0 beyond pgvector | Medium, batchable | Model manifests, re-embedding, filtered recall | Conditional |
| LLM diagnosis/extraction | 0 | Medium/high, budgeted sampling | Prompt/model drift, injection, calibration | Experimental/async |
| Temporal relational facts | 0 | Medium | Entity/contradiction review | Conditional |
| Dream/memory releases | 0 | Medium/high | Review, influence, expiry, rollback | Proposal-only |
| Replay environments | 0 permanent; object artifacts conditional | High and domain-specific | Sandboxing, fixtures, divergence, side effects | Research |
| Team/enterprise aggregates | 0 | Medium | Privacy accounting and appeals | Private gated |
| Domain embedding adaptation | 0 new authority | High episodic training | Dataset rights, deletion, evaluation, rollback | Late conditional |
| Graphiti/upstream parity arm | Ephemeral only | Medium/high | Extra runtime, nondeterminism | Research ablation |
| Separate graph/vector/search/trace platform | +1 or more authorities | High recurring | Duplicated RLS, deletion, HA, backups, incidents | Rejected |

Model calls use tiered budgets: deterministic local preprocessing first, economical
models for candidate extraction and summaries, a calibrated independent judge only on
a stratified subset, replay under its own cap, and frontier replication only after a
lower-tier positive result. Every run records exact model/provider/revision, prompt
hash, decoding, retries, tokens, latency, dated price manifest, input/output hashes,
and failure/partial-output state.

## Failure modes that can invalidate the entire program

| Failure | Consequence | Detection/control |
|---|---|---|
| Branches, retries, authorization, or outcomes are silently linearized/lost | Every later diagnosis, eval, and memory can be wrong | Adapter fixtures, raw source, mutation suite, loss receipt, quarantine |
| Tool proposal/result is treated as execution or side effect | False action, audit, and causal claims | Separate proposal/authorization/attempt/observation/state-delta events |
| Provider fallback becomes a new user attempt | Inflated friction and false repeated-work pattern | Separate task, agent attempt, provider attempt, fallback IDs |
| Missing authority fails closed as “zero matches” | Zero cache/retrieval value and hidden outage | Typed malformed/denied/zero-eligible/zero-hit metrics and canaries |
| ANN filtering or stale reranking omits authorized neighbors | Biased similarity and silent recall loss | Exact per-scope oracle, epoch recheck, fallback |
| Deleted source survives in vectors, facts, evals, memories, aggregates, exports, or model data | Privacy/compliance breach | Transitive lineage, tombstone priority, deletion-closure receipts |
| Stored prompt/tool content controls a judge or worker | Data exfiltration or poisoned artifacts | Treat traces as data, schemas, no credentials/tools, sandbox, safe rendering |
| Signal sampling excludes quiet cohorts | Biased prevalence, labels, and training | Random audit stratum and recorded propensity |
| Entity resolution merges same-name people/systems | Cross-user leakage and false facts | Typed namespace/stable keys; similarity only proposes |
| Memory/procedure influences traces that validate it | Circular evidence | Exposure lineage; independent holdout; no source-descendant validation |
| Public benchmark/model contamination | Inflated mechanism results | Report unknown exposure; executable/human outcomes; new/private holdout |
| Removed CMU failures create survivorship bias | Understates friction and changes model/task mix | Selection model, sensitivity bounds, no prevalence claim |
| Replay infrastructure errors are counted as task failures | Biased procedure effect | Separate `infra_error`; intention-to-treat plus fidelity report |
| Whole-system positive result hides a harmful component | Wrong architecture choice | Frozen adjacent-arm ladder and block factorials |
| Average benefit hides rare critical or subgroup harm | Unsafe promotion | Per-domain/subgroup/tail reporting and explicit harm gate |
| Analytics saturates Aurora/gateway | Creates failures and more biased trace data | Separate bounded pools/credits; inference priority; pause analytics |
| Private aggregates allow differencing | Reidentification and classified leakage | Minimum cohort, contribution bounds, complementary suppression, query ledger, attack tests |

## Paper-ready hypotheses

Pre-register these before opening held-out data:

1. **H1 — representation:** the canonical DAG preserves at least 99.5% of typed events
   and edges and 100% of gold tool/authorization/outcome events across ATIF, OTel,
   chat-native, and environment-native fixtures, with zero silent loss.
2. **H2 — selection:** frozen deterministic signals improve gold-informative precision
   by at least 15 absolute points over random at equal review budget without losing
   more than 10% of critical failures after the random audit stratum.
3. **H3 — retrieval:** structured multi-view plus lexical retrieval outperforms raw
   prompt FTS and whole-trace dense retrieval on hard task-family negatives.
4. **H4 — dense increment:** separate dense task views improve Recall@20 by a
   practically meaningful amount over exact+lexical+structured retrieval; otherwise
   embeddings are not required for launch.
5. **H5 — diagnosis:** invariants and ordered modal/topology evidence each contribute
   incremental decisive-step accuracy beyond a judge-only arm, with a positive
   interaction only where evidence is complete.
6. **H6 — evals:** combined deterministic and semantic assertions kill more seeded
   trajectory mutants than either alone without an unacceptable false-positive rate
   on allowed variation.
7. **H7 — temporal memory:** bitemporal facts plus copy-on-write consolidation improve
   contradiction and valid-time accuracy over a flat rolling summary while retaining
   at least 99% citation support.
8. **H8 — procedure induction:** successful/failed contrast plus modular curated
   procedures improves held-out replay success versus no-procedure and unrelated
   placebo conditions in at least two domains.
9. **H9 — relevance versus utility:** semantic top-1 is inferior to deterministic
   applicability plus a utility ranker trained from randomized exposure outcomes.
10. **H10 — architecture:** native PostgreSQL relational facts/retrieval meet the
    preregistered quality and latency gates; ephemeral Graphiti or another specialized
    system supplies no benefit large enough to justify another persistent authority.
11. **H11 — privacy-utility:** team/enterprise pattern and artifact releases retain
    useful acceptance/outcome rates after minimum-cohort, suppression, and
    anti-differencing controls; if not, the product remains personal.
12. **H12 — adaptation:** a domain embedding adapter is unnecessary unless the frozen
    hybrid baseline misses a named corporate terminology/task boundary; if trained, it
    must add at least five absolute Recall@20 points without exact-ID, subgroup,
    deletion, latency, or rollback regression.

For all hypotheses, report task-clustered effect sizes and 95% confidence intervals,
not just p-values. Use paired tests on identical tasks, mixed-effects models for
repeated seeds, within-dataset results before pooled summaries, and Holm correction for
confirmatory families. Label unregistered slices exploratory. Human annotations use
blinding, adjudication, and `insufficient_evidence`; critical shipping labels require
agreement of at least 0.80 after rubric stabilization.

## Program stop rules

Stop or narrow the relevant claim when:

- canonical evidence cannot preserve material source semantics;
- current-authority RLS or derived deletion closure leaks any row, identifier, count,
  distance, snippet, object, aggregate, or generated quotation;
- task/recovery/skill labels remain below acceptable human agreement;
- independently verified outcomes are too sparse for attribution;
- a learned mechanism does not beat the cheapest valid baseline;
- replay cannot reproduce controls or intervention effects fail replication;
- a suggestion has no positive prospective effect, placebo performs similarly, or
  critical harm exceeds the preregistered bound;
- privacy controls remove cross-user utility or attacks recover people/classified data;
- a custom embedding improves an average metric but regresses hard negatives, exact
  identifiers, selective scopes, deletion, or tails;
- analytics threatens inference isolation or costs more than the demonstrated product
  value; or
- the organization will not prohibit manager drilldown and individual
  productivity/skill scoring.

Negative results are first-class. The correct end state may be:

- personal history plus exact/lexical search;
- deterministic evidence and manual eval proposals;
- no embeddings;
- no automatic memory;
- reviewed documentation rather than learned skills;
- no cross-user product; or
- no model adaptation.

That smaller product is preferable to an impressive system whose central enterprise
claims are not identifiable.

## Recommended execution order

1. Finish L0 source adapters and projection/loss conformance for MCP ATIF, Exgentic,
   CodeTraceBench, Nebius, SPARK, `pagarsky`, selected environment fixtures, and
   privately cached CMU.
2. Implement L1 authority/deletion schemas and the permission-oracle gauntlet in the
   local PostgreSQL 16/pgvector fixture.
3. Run F1 and F2 exact/lexical/structured arms; publish the already negative/ambiguous
   Nebius signal pilot rather than tuning it away.
4. Build the blinded gold set, then run F3 diagnosis and F4 mutation experiments.
5. Run F5 with deterministic/verbatim, LangMem-like, temporal, and Dream-release arms;
   keep all outputs proposal-only.
6. Run F6 in deterministic replay domains before any private user recommendation.
7. Integrate passing components as C0–C5 and measure each adjacent increment, cost,
   deletion behavior, and operational isolation.
8. Collect consented private longitudinal traces, exposure, and outcome data for F7/F8.
9. Add C6/C7 only if causal and privacy gates pass.
10. Consider domain embeddings or generator adaptation only at L9/L10 after the frozen
    lower-level failure exists.

## Source map

This synthesis composes, and is bounded by, the source-pinned reviews:

- [ATIF trace-schema crosswalk and gap analysis](./atif-trace-schema-crosswalk-and-gap-analysis.md)
- [RL environment trace and replay storage review](./rl-environment-trace-and-replay-storage-review.md)
- [Dreaming, Memory Palace, Hermes, and self-evolving-skill review](./dreaming-memory-palace-hermes-skill-learning-review.md)
- [Trace-tool execution feasibility](./trace-tool-execution-feasibility.md)
- [Enterprise-question composition audit](./trace-intelligence-enterprise-question-composition-audit.md)
- [Public-dataset empirical program](./trace-intelligence-public-dataset-empirical-program.md)
- [Public agent-trace dataset inventory](./public-agent-trace-dataset-inventory.md)
- [Minimal log, trace, vector, and reflective-learning architecture](./log-trace-vector-database-and-reflective-learning-review.md)

Primary external anchors include
[Harbor ATIF v1.7](https://github.com/harbor-framework/harbor/blob/f5e9d0b71ac4493a4f0620653e2913aee7fc0767/rfcs/0001-trajectory-format.md),
[OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions),
[OpenInference](https://github.com/Arize-ai/openinference),
[AgentRx](https://github.com/microsoft/AgentRx),
[AgentEvals](https://github.com/agentevals-dev/agentevals),
[Agent Lightning](https://github.com/microsoft/agent-lightning),
[Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams),
[Graphiti](https://github.com/getzep/graphiti),
[LangMem](https://github.com/langchain-ai/langmem),
[ReasoningBank](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/),
[pgvector](https://github.com/pgvector/pgvector), and the
[NIST NICE framework](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/getting-started).

## Bottom line

The combined system is not a universal trace model followed by an insight model. It is
a governed chain of falsifiable reductions:

```text
event evidence
  -> selected evidence
  -> related evidence
  -> diagnostic hypothesis
  -> eval/fact/procedure candidate
  -> reviewed immutable release
  -> measured exposure
  -> independent outcome
  -> privacy-safe shared artifact
```

Each arrow can fail independently, retains source lineage, and has a cheaper baseline.
That is what allows Frankengate to answer useful open-ended enterprise questions
without pretending that embeddings reveal skill, that traces prove causation, or that
cross-user analytics is automatically collaboration.
