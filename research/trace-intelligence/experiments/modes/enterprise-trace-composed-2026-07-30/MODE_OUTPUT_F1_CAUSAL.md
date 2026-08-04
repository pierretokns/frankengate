# F1 Causal Inference Analysis

## Thesis

Frankengate's trace-intelligence program has enough governed evidence structure to run causal studies, but not enough causal evidence to claim that a missing skill, prompt, memory, tool, model, embedding, or collaborator caused an outcome. Most current successes are representation, authorization, retrieval, projection, and lifecycle mechanics. Those support deterministic facts and statistical candidate generation. Causal claims require an explicit intervention, assigned or otherwise identifiable exposure, comparable controls, independent outcomes, influence lineage, and analysis at the task/user/team cluster level.

The causal kernel is therefore:

```text
canonical governed trace evidence
  -> task/attempt unit and pre-treatment covariates
  -> candidate intervention with source-disjoint evidence
  -> randomized, stepped-wedge, encouragement, replay, or credible quasi design
  -> exact exposure and use receipt
  -> independent outcome and harm measurement
  -> influence quarantine and deletion-aware release decision
```

Retrieval, temporal memory, Signals, AgentRx, OpenRCA, Graphiti-style facts, LangMem/Dream candidates, ReasoningBank/Hermes skills, and embeddings are allowed to create hypotheses and artifacts. They are not allowed to validate their own downstream effects.

## Top Findings

1. **§F1 [Kernel Candidate]: The canonical governed evidence plane is necessary for causal inference, but it is not a causal result.**
   - **Evidence:** `research/trace-intelligence/experiments/summaries/frankengate-combined-evidence-matrix-2026-07-30.md` says real OTel conformance, governed history mechanics, synthetic memory invariants, and local PostgreSQL RLS/retrieval partially pass, while memory utility, diagnosis, causal skill benefit, cross-user learning, Aurora scale, and prospective enterprise utility do not. `research/trace-intelligence/experiments/summaries/canonical-projection-e0-conformance-2026-07-30.md` shows OTel/OpenInference retained 48/48 event identities and 34/34 parent edges, while ATIF retained 0/48 enterprise event identities after reimport. `research/trace-intelligence/configs/experiments/enterprise-question-composed-factorial-v3-2026.json` requires governed DAG fidelity including tool proposal, approval, execution, result, side effect, authority epoch, outcome verifier, and influence lineage.
   - **Reasoning chain:** Causal inference needs well-measured units, treatments, outcomes, time order, and eligibility. The canonical DAG and authority model are the measurement substrate for those variables. But a correctly measured trace still only shows what happened under one exposure path. It does not reveal the counterfactual outcome under a different memory, skill, route, tool, prompt, model, or collaborator.
   - **Deployment severity:** High. If mechanics are narrated as intervention effects, Frankengate will ship confident but unsupported organizational conclusions.
   - **Confidence:** 0.91.
   - **So what:** Product and research outputs must carry claim class. Current kernel features can say "observed", "authorized", "retrieved", "candidate", or "mechanics passed"; they cannot say "caused", "helped", or "skill gap" until exposure/control studies pass.

2. **§F2 [Owner-Acknowledged Limitation]: Signals, AgentRx, OpenRCA, retrieval, and embeddings are selectors or predictors, not causes.**
   - **Evidence:** `docs/roadmap/research/trace-intelligence-enterprise-question-composition-audit.md` states that "what skill is missing" is an attribution problem and "what intervention will help" is a causal experiment, not semantic search. `research/trace-intelligence/experiments/summaries/frankengate-combined-evidence-matrix-2026-07-30.md` reports CodeTraceBench structural selection precision at 0.567 versus random 0.426, below the preregistered +0.15 gate and tied with length/stage count; no evidence arm beat reverse chronology for step localization. `docs/roadmap/research/enterprise-trace-intelligence-transfer-validation-study.md` says observational recovery sequences are candidate generators, never causal effects.
   - **Reasoning chain:** A rephrase loop, SQL error, high vector similarity, invariant violation, or root-cause hypothesis can identify a review candidate. It cannot distinguish skill from permissions, stale docs, environment outage, policy denial, model routing, tool affordance, budget, ambiguous task, deliberate exploration, or hidden schema. Those are confounders and alternative causes.
   - **Deployment severity:** Critical for people-facing skill or productivity claims; medium for private triage cards.
   - **Confidence:** 0.90.
   - **So what:** Keep Signals, AgentRx, OpenRCA, and embeddings in the "hypothesis and selection" lane. A diagnosis card must list non-skill alternatives and the intervention ladder before making any recommendation.

3. **§F3 [Kernel Candidate]: Influence lineage is the main causal safety feature for memories, skills, prompts, retrieval, routes, models, and embeddings.**
   - **Evidence:** `docs/roadmap/research/memory-skill-replay-evidence-composition-matrix-2026.md` separates observed event, inferred candidate, reviewed immutable release, harness projection, influenced trajectory, and independent held-out evaluation. `research/trace-intelligence/experiments/summaries/bitemporal-memory-conformance-2026-07-30.md` passed 15/15 assertions including influence exclusion from independent validation. `research/trace-intelligence/sql/005_skill_release_lifecycle.sql` documents `trajectory_influences` as release IDs that influenced later traces and are required for leakage exclusion. `research/trace-intelligence/experiments/summaries/trace-commons-memory-h5-postgres-2026-07-30.md` passed authorized release exposure and influence checks, while `trace-commons-memory-h5-concurrency-postgres-2026-07-30.md` found exposure/withdrawal and REPEATABLE READ revocation gaps.
   - **Reasoning chain:** Once an artifact is shown, a later trace is a post-treatment outcome. It may reflect the artifact's causal effect, user compliance, model echoing, anchoring, or contamination. It cannot be pooled with pre-exposure traces as independent evidence that the artifact was true or useful.
   - **Deployment severity:** High. Without influence quarantine, every learning loop can self-validate and create circular releases.
   - **Confidence:** 0.89.
   - **So what:** Make artifact exposure and influence records mandatory before any memory, skill, route, model, prompt, retrieval, or embedding release. Descendant traces must be excluded from naive validation and analyzed only under an exposure model.

4. **§F4 [Hypothesis With Negative Result]: Memory, Dream, Graphiti, LangMem, MemInsight, Memory Palace, and `MEMORY.md` should be tested as randomized proposal exposures, not accepted as memory benefit.**
   - **Evidence:** `research/trace-intelligence/experiments/summaries/longitudinal-memory-local-model-replication-2026-07-30.md` completed 425 local calls and found all evidence-bearing arms had identical aggregate scores; `no_memory` scored 100% because it abstained, which the summary marks as a scoring artifact. The same summary lists confounds: visible arm labels, non-real dream arm, latest-only retaining context, incomplete bitemporality, and missing launch attestation. `trace-commons-memory-composition-2026-07-30.md` found 3/6 same-basename leaks for latest-only and 0/6 for contextual, but only three reconstructable later-read cutoffs and no comparative quality claim. `research/trace-intelligence/configs/experiments/longitudinal-memory-corrected-replication-v2-2026.json` fixes several causal problems with blinding, no future evidence, query-independent dream release, whole-item budgets, and paired analysis, but is preregistered before a corrected model run.
   - **Reasoning chain:** The evidence supports temporal representation and leakage controls. It does not support the counterfactual "the memory caused better future work." That estimand needs memory-on, current-memory, no-memory, and placebo arms with exact exposure and independent task outcomes.
   - **Deployment severity:** High for automatic memory; medium for proposal-only UI.
   - **Confidence:** 0.88.
   - **So what:** Do not auto-write `MEMORY.md`, LangMem stores, Graphiti facts, Dream outputs, or Memory Palace entries. Use them as reviewed, cited proposals until a corrected exposure study shows utility and no anchoring, stale, deletion, or scope harm.

5. **§F5 [Hypothesis]: NL2SQL is the best first causal skill-learning lab, but the current Defog result is a protocol failure and null mechanics result.**
   - **Evidence:** `research/trace-intelligence/experiments/summaries/nl2sql-enterprise-skill-domain-assessment-2026-07-30.md` selects NL2SQL because typed questions, schema inspection, SQL attempts, database observations, authorization outcomes, retries, and executable results make sub-skills observable. `research/trace-intelligence/experiments/summaries/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md` completed 12/12 episodes but every arm solved the same 2/4 tasks, paired risk differences were zero, and protocol failures were 25%, 50%, and 25% against a 10% gate. `nl2sql-capability-isolation-component-checkpoint-2026-07-30.md` reports 61/61 component tests and a real Linux/runc plus PostgreSQL role slice, but keeps P1 and hidden sealed until the full 27-gate proof and a fresh P0 pass.
   - **Reasoning chain:** NL2SQL has the clearest causal outcome among the domains because it can bind a candidate procedure to a read-only database, sealed result, policy acceptance, and semantic correctness. But the current intervention has no effect signal and the harness failed before the effect screen. Estimating skill benefit now would condition on a broken mediator: terminal protocol compliance.
   - **Deployment severity:** Medium for research sequencing; high if promoted into skill-product claims.
   - **Confidence:** 0.86.
   - **So what:** Repair the protocol arm-independently, rerun P0, then test no artifact, length-matched placebo, expert seed, and trace-mined reviewed procedure on family-disjoint tasks. Keep the estimand "artifact effect on task success", not "user SQL skill".

6. **§F6 [Negative Result]: Retrieval upgrades and enterprise embeddings are not causal levers until a retrieval failure and an intervention lift are both proven.**
   - **Evidence:** `research/trace-intelligence/experiments/summaries/codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md` reports structured+dense Recall@20 of 0.818 versus 0.732 for exact-only on silver labels, but says labels are not human-adjudicated and no skill, collaboration, enterprise transfer, or causal utility claim is supported. `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` reports local exact pgvector Recall@20 0.667 at 3.017 ms p50, while tested hybrid RRF reached 0.672 at 256.843 ms p50 and is rejected for that workload. `docs/roadmap/research/domain-adaptive-embeddings-and-secure-rag.md` requires governed query-document judgments, held-out hard negatives, ACL/deletion tests, shadow/canary, and human promotion before adaptation.
   - **Reasoning chain:** Better candidate recall can improve an upstream mediator: what evidence or artifact is presented. It does not establish that users perform better, that two people should collaborate, or that a missing skill exists. A custom embedding can only be justified for a retrieval estimand first; a user-benefit claim then needs a separate exposure design.
   - **Deployment severity:** Medium-high. Premature embeddings add deletion, memorization, and scope risks while distracting from labels and outcomes.
   - **Confidence:** 0.87.
   - **So what:** Leave Aurora or train embeddings only after exact/structured/FTS/general-dense/reranker baselines fail a frozen authorized slice and the replacement shows no RLS, deletion, latency, hard-negative, exact-ID, memorization, or rollback regression. Treat user benefit as a later causal endpoint.

7. **§F7 [Kernel Candidate]: Cross-user "similar work", collaboration, and skill-support features are interference-heavy causal questions and should default to artifact-first opt-in.**
   - **Evidence:** `docs/roadmap/research/enterprise-trace-intelligence-transfer-validation-study.md` sets the claim ceiling for "who is doing similar work" at deidentified task retrieval plus reciprocal opt-in, and says collaboration utility needs mutual acceptance and post-introduction outcomes. `research/trace-intelligence/experiments/summaries/frankengate-combined-evidence-matrix-2026-07-30.md` marks similar work across users, missing skills, and who should collaborate as not tested or not supported. `MODE_OUTPUT_I4_PERSPECTIVES.md`, `MODE_OUTPUT_H2_ADVERSARIAL.md`, and `MODE_OUTPUT_L2_DEBIASING.md` all warn that similarity can become people analytics.
   - **Reasoning chain:** Collaboration and capability support violate simple independent-unit assumptions: one user's treatment can affect another user's outcome; managers can alter behavior after seeing dashboards; rare cohorts can expose identities; and "same work" can be an artifact, not a social relation. These need cluster, pair, or encouragement designs, not nearest-neighbor outputs.
   - **Deployment severity:** Critical if tied to employee evaluation or manager drilldown; high even inside authorized enterprise scopes.
   - **Confidence:** 0.88.
   - **So what:** Build anonymous reusable patterns first. Reveal people only through reciprocal opt-in around a minimized artifact, and estimate collaboration benefit with randomized encouragement or stepped-wedge designs.

## Standalone Concept Assessment

| Concept or family | Enterprise question it can help answer | Causal status | Required evidence and labels | F1 verdict |
|---|---|---|---|---|
| ATIF | Can selected tasks/evals be exported? | Measurement projection | Loss receipts, source hashes, unsupported-field manifest, no reimport as truth | Useful interchange, not causal evidence or authority. |
| OpenTelemetry/OpenInference | What operations, spans, tool lifecycle, and topology occurred? | Measurement projection | Expected-trace manifest, backend round trip, content/authority allowlist | Operationally useful; cannot prove replay, memory, skill, or policy effects. |
| AgentRx | Which invariant failed or which step is suspect? | Hypothesis generator | Human decisive-step labels, sandboxed invariants, ablations, alternatives | Use for candidate localization; causal wording requires replay or intervention. |
| Signals | Which traces deserve review? | Statistical selector | Random/length baselines, fixed budget precision, critical miss audit | Keep as pre-treatment selector, not label or cause. |
| AgentEvals | Which stored traces should become evals? | Retrospective audit and proposal | Mutants, allowed variation, changed-system rerun | Stored-trace assertion does not prove future behavior. |
| Phoenix, Opik, Langfuse | Dataset/evaluator/release lifecycle | Infrastructure pattern | One native Frankengate release/evaluator registry and deletion lineage | Borrow concepts; do not create parallel causal/eval authorities. |
| OpenRCA | Which metric/log/topology alternatives explain incident-like failures? | Hypothesis generator | Modality ablations, clock/topology controls, intervention or replay | Output "RCA hypothesis", not cause. |
| Graphiti | Temporal entity/fact graph and contradiction handling | Representation and candidate retrieval | Entity namespace, scope, valid/system time, entity-merge negatives | Relational temporal facts first; graph backend only after relational failure. |
| MemInsight | Typed entities, constraints, outcomes | Schema inspiration and covariates | Ontology, entity resolution, sensitive-attribute tests | Useful for covariates and stratification, not a causal oracle. |
| LangMem | Memory extraction/update/delete workflow | Candidate generator | Citations, review, release, exposure, rollback, deletion | Proposal only; no live mutation. |
| Memory Palace | Verbatim/contextual recall and personal navigation | Representation/UX | State-retention tests, same-name negatives, review | Useful for memory packs; utility unproven. |
| Temporal evidence | Known-at/valid-at correctness | Causal identification guard | Cutoff oracle, interval gaps, conflict states, no future events | Kernel candidate; prevents future leakage. |
| `MEMORY.md` | Harness/user-facing memory destination | Treatment artifact | Release snapshot, citations, expiry, exposure, withdrawal | Destination, not source of truth. |
| Cloud dreaming | Background candidate synthesis | Candidate generator and treatment source | Query-independent pre-cutoff input, independent verifier, copy-on-write release | Experimental arm only; never automatic write. |
| ReasoningBank | Lessons from success/failure contrasts | Candidate procedure source | Source-disjoint outcomes, no self-judge, hidden-family eval | Useful only under no-artifact/placebo causal replay. |
| Hermes/GEPA/Trace2Skill/SkillOpt | Bounded skill/procedure search | Candidate search and release lifecycle | Frozen artifacts, sealed tasks, signed releases, rollback | Search is composable; live self-editing is not. |
| Jeopard-style skill learning | Unresolved source concept in project docs | Unknown | Concrete source, protocol, outcomes | Do not build or equate with other skill systems until specified. |
| RL environment histories | Action/observation/reward replay | Strong causal lab if environment is resettable | Reset state, action, observation, reward basis, termination, resources | Flat traces are insufficient; environment attachment required. |
| CASS, Doodlestein/CM, claude-history, Prompt-Scope | Personal search and reflection UX | Descriptive retrieval | Import receipts, local rights, exact fielded search, deletion path | Good UX/adapters; no enterprise causal or RLS proof. |
| Frankensearch | Hybrid/progressive search sidecar | Candidate generator | ACL-before-candidate, tombstones, stale-index tests, bakeoff | Default-off experiment only. |
| Aurora PostgreSQL, JSONB, FTS, pgvector | One authority plus exact/lexical/vector retrieval | Measurement and candidate-generation substrate | Typed authority columns, exact authorized oracle, deletion and latency gates | Current smallest architecture; not a causal engine by itself. |
| VectorChord, pg_textsearch, pgContext, Turbovec, Turbopuffer | Performance or feature upgrade | Retrieval/ops hypothesis | Same corpus, same RLS/deletion, p95/p99, failover, ops cost | Evaluate only after a named baseline failure. |
| General embeddings | Semantic candidate generation | Statistical predictor | Human positives/hard negatives, exact-ID slices, RLS/deletion | Conditional retrieval lane. |
| Enterprise-adapted embeddings | Jargon/task retrieval improvement | Retrieval treatment | Governed labels, train/test by user/team/time, memorization/deletion tests | Premature; needs +5 Recall@20 and safety gates before use. |
| Agentic coding/research traces | Mechanics, review candidates, memory/eval/procedure proposals | Observational substrate | Tool-call fidelity, task boundaries, outcomes, source rights | Good for mechanisms; weak for enterprise population/causal claims. |
| NL2SQL traces with complete tool calls | Skill/procedure intervention lab | Best current causal testbed | Complete tools, DB state, gold/evaluator separation, family-disjoint tasks | Prioritize after P0 protocol repair. |

## Composition and Non-Composition Matrix

| Combination | Clean causal interface | Main confound, leak, or double count | Smallest falsifier |
|---|---|---|---|
| Canonical DAG + OTel/OpenInference + ATIF | Canonical DAG owns evidence; projections carry loss receipts | Projection loss becomes measurement error or false side-effect evidence | Round-trip denied tools, branches, fallbacks, state deltas, and loss receipts. |
| Signals + AgentRx + AgentEvals | Selector -> hypothesis -> eval proposal | Selector/hypothesis/eval all relabeled "cause" | Random audit, decisive-step labels, and changed-system replay. |
| OpenRCA + logs/metrics/topology + traces | Alternative-cause graph with synchronized clocks | Correlation, shared incident timing, and topology proximity narrated as cause | Modality ablations and incident/replay interventions. |
| Phoenix/Opik/Langfuse concepts + Frankengate | Native dataset/evaluator/release tables | Duplicate feedback and deletion state counted as independent evidence | One authoritative release and deletion ledger. |
| Graphiti + MemInsight + temporal oracle | Scoped bitemporal facts as covariates/candidates | Entity merge or graph proximity substitutes for authorization/identity | Cross-scope traversal, alias collision, and contradiction tests. |
| LangMem + Dreams + `MEMORY.md` | Proposal -> verification -> release -> exposure -> outcome | Silent write influences later trace and validates itself | Memory-on/no-memory/current/placebo exposure with influence quarantine. |
| ReasoningBank + Hermes + NL2SQL | Frozen procedure artifact assigned to held-out task family | Generator sees hidden family, judges itself, or tunes on same outcomes | No-artifact/placebo/expert/trace-mined arms under sealed stages. |
| RL histories + canonical traces | Environment attachment supplies reset/action/reward | Transcript treated as environment state | Reset/resource/reward divergence controls. |
| CASS/Prompt-Scope/Frankensearch + enterprise search | UX/adapters behind Frankengate authority | Local index becomes shared evidence or post-filtered sidecar leaks | Import-rights receipts, tombstones, permission oracle, stale-index fail-closed. |
| General embeddings + structured retrieval | Candidate IDs reauthorized before snippets | Similarity becomes same work, skill, identity, or collaboration | Human task labels and reciprocal opt-in outcome study. |
| Enterprise-adapted embeddings + feedback loop | Versioned retrieval contract with held-out labels | Clicks/success traces/generated memories become unreviewed training positives | Frozen hard slice, train/test by time/user/team, deletion/memorization audit. |
| Memory/skill/model release + later traces | Exposure/influence records define treatment | Descendant traces double-counted as independent validation | Automatic exclusion of descendants from non-exposure analyses. |
| Team dashboards + similarity clusters | Aggregate artifact backlog only | Interference, rare-cohort reidentification, manager behavior changes | Minimum cohorts, repeated-query budget, randomized encouragement for intros. |

## Enterprise Questions Answered and Not Answered

| Enterprise question | Current answer class | Causal answer requires |
|---|---|---|
| Show a user their own authorized history | Deterministic/mechanics, with production gates open | Capture manifest, permission oracle, deletion/failover gauntlet. |
| What work are people doing? | Descriptive within observed Frankengate sources | Sampling/capture propensity; no claim about off-platform work. |
| Where did repeated friction happen before success? | Review candidate and ordered association | Same-task linkage, environment snapshots, add/remove replay or randomized suggestion exposure. |
| What caused the failure? | Hypothesis only | Alternative-cause controls, intervention/replay, independent outcome. |
| What should become an eval? | Proposal/audit mechanics | Mutants plus changed-system rerun and verifier independence. |
| What should become memory or `MEMORY.md`? | Proposal and representation mechanics | Randomized memory exposure, citation/review precision, delayed harm checks, deletion closure. |
| Which prompt, skill, tool, route, model, or retrieval should be suggested? | Causal hypothesis | No-help/relevant/placebo assignment, exact exposure/use, outcome and harm measurement. |
| Which cloud/domain skill might a user benefit from? | Unsafe as trait; possible private support hypothesis | Capability ontology, environment/permission controls, optional practical task or randomized support. |
| Who is doing similar work? | Candidate task similarity under authorization | Blinded task labels, privacy-safe cohorts, not people identity. |
| Who should collaborate? | Not supported | Reciprocal opt-in or randomized encouragement around an artifact and post-introduction outcomes. |
| Should Frankengate train an enterprise embedding? | Retrieval hypothesis only | Frozen hard-slice retrieval failure plus safe adapted lift; causal user benefit is separate. |
| Should Frankengate leave Aurora? | Operations hypothesis only | Production-like workload failure after bounded tuning and equal-authority replacement proof. |
| Who is productive, competent, loyal, or likely to leave? | Refuse | No legitimate trace-intelligence causal design for this product scope. |

## Empirical Tests and Falsifiers

1. **Causal memory utility trial**
   - **Unit:** pre-cutoff user-task or replayable task query, clustered by user/project/task family.
   - **Arms:** no memory, current memory, reviewed temporal memory, unrelated/placebo memory, optionally oracle memory.
   - **Controls:** same model, prompt wrapper, tools, budget, authority, and retrieval corpus; exact exposure/use receipt.
   - **Primary estimand:** intention-to-treat effect on independent task success and serious harm.
   - **Falsifier:** no lift over no-memory and placebo, any scope/deletion leak, harmful anchoring/stale selection, or effect only when future evidence leaks.

2. **NL2SQL procedure causal replay**
   - **Unit:** family-disjoint database task.
   - **Arms:** no artifact, length/vocabulary-matched placebo, expert seed, one frozen reviewed trace-mined procedure.
   - **Confounders blocked by design:** database family, prompt, model, tool limits, authority, snapshot, decoding, evaluator.
   - **Primary outcome:** `semantic_correct AND policy_accepted AND NOT unauthorized_observation`.
   - **Falsifier:** protocol failure above gate, no paired lift versus both no-artifact and placebo, any unauthorized observation, or gains only on visible/training families.

3. **Prompt/tool/route/model suggestion trial**
   - **Unit:** live user-task exposure or replayed task where reset is credible.
   - **Design:** randomized, stepped-wedge, or randomized encouragement if withholding is impractical.
   - **Mediators:** artifact viewed, accepted, edited, used, ignored; model/tool route actually selected.
   - **Falsifier:** ITT effect is zero or harmful; treatment-on-treated estimate appears only after conditioning on post-treatment success-prone usage.

4. **Friction/recovery add-remove test**
   - **Unit:** linked attempts or replayable task with known recovery delta.
   - **Design:** remove proposed recovery delta from a replay where safe, or add it prospectively as guidance.
   - **Falsifier:** delta does not change outcome, or outcome changes are explained by permissions, model revision, environment, or task ambiguity.

5. **Same-work retrieval to collaboration utility**
   - **Stage 1:** human-labeled task similarity with exact/structured/general-dense baselines.
   - **Stage 2:** artifact-first reciprocal opt-in or randomized encouragement introduction.
   - **Falsifier:** labels fail reliability, privacy controls erase utility, identity leaks occur, or introductions do not improve verified outcomes.

6. **Embedding adaptation gate**
   - **Unit:** frozen labeled retrieval query, split by source, project, task family, user/team, and time.
   - **Promotion threshold:** at least +5 absolute Recall@20 over best general hybrid/reranker, with zero exact-ID, RLS, deletion, subgroup, p95/p99, memorization, or rollback regression.
   - **Falsifier:** general hybrid meets target, adapted model memorizes private content, or retrieval lift does not survive held-out private terminology.

7. **Aurora replacement gate**
   - **Unit:** production-like workload period with concurrent ingest, search, pgvector, deletion, re-embedding, aggregation, failover, and inference isolation.
   - **Falsifier for Aurora-first:** recall, p95/p99, deletion closure, failover/reconnect, or cost fails after partitioning, typed predicates, bounded vector cardinality, exact fallback, pooling, and preaggregation.
   - **Causal relevance:** replacing storage is justified by operations and measurement failure, not by better causal inference alone.

8. **Projection-loss causal-control suite**
   - **Unit:** synthetic and real-safe traces containing denied tools, hidden branches, fallbacks, partial side effects, and delayed observations.
   - **Falsifier:** any ATIF/OTel/AgentEvals/AgentRx projection lets a downstream consumer assert execution, root cause, or completeness without a loss receipt.

## Architecture Consequences

- The minimum causal architecture is the same one-authority kernel endorsed by the project records: governed Aurora/PostgreSQL evidence, typed authority/time/deletion fields, exact/structured/FTS retrieval, optional bounded pgvector, proposal/release/exposure/influence/evaluation tables, and content-minimized OTel/ATIF projections.
- Add a first-class **intervention registry**: artifact ID, source evidence, eligibility, assignment unit, randomization/encouragement method, arm, exposure, use, outcome, harm, rollback, and deletion state.
- Add a first-class **influence quarantine ledger** for memories, skills, prompts, tools, routes, models, embeddings, rerankers, evals, and collaborator introductions.
- Store pre-treatment covariates separately from post-treatment mediators. Do not adjust away treatment effects by conditioning on artifact use, later trace length, generated memory acceptance, or successful terminal submission.
- Treat all repeated deterministic invocations as precision or protocol checks, not independent samples. `test_composed_system_factorial_v3.py` already encodes this by aggregating independent unit count separately from invocation count.
- Keep claim classes in schemas and APIs: deterministic observation, statistical selector, retrieval candidate, causal intervention result, hypothesis, abstention, prohibited.
- Do not add graph/vector/search/eval/memory products as separate authorities. Causal designs need cleaner exposure and outcome records more than more stores.

## Risks Identified

- **Confounding by environment:** permissions, stale docs, incidents, tool unavailability, schema ambiguity, model route, token budget, and task difficulty can all cause apparent friction or failure.
- **Selection bias:** public traces, successful traces, donated histories, manager-selected tasks, and signal-selected reviews are not representative of enterprise work.
- **Future leakage:** later reads, target outcomes, hidden tests, generated memories, and descendants can leak into pre-treatment evidence packs.
- **Post-treatment conditioning:** analyzing only users who used a suggestion, only submitted SQL, or only accepted memory can inflate apparent effects.
- **Interference:** one user's memory, collaboration, team artifact, or manager dashboard can affect other users' outcomes.
- **Circular feedback:** memory/skill/model outputs can create the traces that later validate or train them.
- **Double-counted evidence:** the same outcome label can appear in Signals, retrieval, AgentRx, evals, and release decisions as if independent.
- **Measurement error from projections:** ATIF/OTel/AgentEvals/AgentRx projections can collapse proposal, execution, authorization, state delta, and missing branches.
- **Socially unsafe causal stories:** "employee lacks skill" is a latent-trait claim not supported by task traces and can be harmful even when raw access is authorized.

## Recommendations

1. **P0:** Require every insight, dashboard metric, API response, and research row to declare claim class and whether causal utility has been tested.
2. **P0:** Implement influence quarantine before releasing memory, skill, route, model, embedding, prompt, reranker, or collaboration features.
3. **P0:** Preserve the Defog F0 protocol failure as a blocker. Repair protocol outside hidden families, then rerun P0 before any skill-effect screen.
4. **P1:** Run the corrected v2 memory protocol as a mechanics-corrected study, but label it exploratory unless diversity, power, blinding, and protocol gates pass.
5. **P1:** Build the intervention registry and randomization/encouragement service before team dashboards or automatic recommendations.
6. **P1:** Use NL2SQL as the first deep causal domain because it has executable outcomes and controlled tool calls; keep general coding/research traces for mechanism and external-validity work until outcomes are stronger.
7. **P2:** Train no enterprise embedding and add no persistent search/vector/graph authority until the preregistered retrieval and Aurora reversal gates fail.
8. **P2:** Start cross-user features as anonymous artifact backlogs. Move to named collaboration only through reciprocal opt-in and prospective outcome measurement.

## New Ideas and Extensions

- **Causal estimand cards:** Every proposed feature stores: unit, treatment, comparator, outcome, assignment, confounders, mediators, interference risk, exclusion rules, and claim ceiling.
- **Influence DAG overlay:** A graph over canonical evidence showing which artifact/version touched which trace, then automatically blocking descendant validation unless an exposure design is declared.
- **Negative-control library:** Permission-caused failure, stale-doc failure, model-protocol failure, hidden-schema failure, productive exploration, and deliberate no-submit examples to test false skill-gap claims.
- **Intervention ladder evaluator:** Before suggesting a skill or model change, require explicit checks for cheaper causes: permission, docs, tool description, retrieval alias, prompt, procedure, memory, route/model, embedding, fine-tune.
- **Cluster-aware result template:** Every experiment result reports independent users, task families, projects, source families, repeated invocations, discordant pairs, and influence-excluded traces separately.
- **Causal privacy canaries:** Synthetic rare cohorts and complement queries that test whether causal-effect dashboards enable identification or manager misuse.
- **Mediator-safe dashboards:** Show ITT as the primary causal estimate and treatment-received/use as secondary, with warnings when usage is post-treatment and self-selected.

## Assumptions Ledger

- The deployment is an internal enterprise tool where authorized users, teams, and admins may inspect full PII/classified content within scope; reusable credentials remain excluded from ordinary trace/model/index/replay paths.
- Existing project summaries, configs, tests, and docs are treated as primary project evidence for this pane.
- Public and donated traces are useful for parser, projection, retrieval, and mechanism qualification, not enterprise population or causal claims.
- Aurora/PostgreSQL remains the starting authority; several hundred GB of traces is not by itself a causal or operational reason to add another database.
- Human review and consented prospective studies are available for at least small pilot cohorts before team/enterprise causal claims.
- "Helped" means independently verified task or harm outcome under exposure/control, not retrieval score, user satisfaction alone, or model judge agreement.

## Questions for Project Owner

1. What exact outcomes count as intervention success for the first release: task success, fewer turns, lower cost, lower latency, fewer corrections, user acceptance, or delayed repeat success?
2. Which claims are categorically banned even for admins: person-level skill gaps, productivity, hidden manager search, collaboration ranking, morale/intent, or performance prediction?
3. What is the smallest ethical no-help/placebo design for internal users if an artifact appears likely useful?
4. Who owns randomization, exposure logging, and stopping decisions for memories, skills, prompts, routes, models, and collaboration trials?
5. What minimum cohort, cluster count, and reviewer agreement are required before team-level support hypotheses can be shown?
6. Which downstream traces become ineligible for independent validation after an artifact exposure, and for how long?
7. What Aurora SLO failure would justify replacing the one-authority design, and what user-facing causal claim would that replacement enable that Aurora cannot?

## Points of Uncertainty

- No corrected v2 memory model result exists yet; the causal hygiene is designed but unproven.
- Human label reliability for task similarity, friction type, recovery delta, capability support, and collaboration usefulness is unknown.
- Production Aurora behavior under selective RLS, vector search, deletion, failover, RDS Proxy, and analytics isolation remains untested.
- The real enterprise trace distribution may differ materially from public coding, synthetic memory, and NL2SQL corpora.
- User noncompliance and partial use may dominate treatment effects for memory/skill/prompt suggestions.
- Interference may be large for team artifacts and collaboration, reducing the value of individual-level randomization.
- General embeddings may be enough for most semantic retrieval, or they may fail on private jargon; current evidence does not settle this.

## Agreements and Tensions with Other Perspectives

- **Agreement with B9 Simplicity/MDL:** F1 agrees that the smallest architecture is one governed authority plus projections and proposal/release records. The causal reason is that duplicate authorities make treatment exposure, deletion, and influence lineage harder to identify.
- **Agreement with L2 Debiasing:** F1 agrees that metric relabeling and circular feedback are major failure modes. F1 frames them as identification failures: selectors are not treatment effects, and descendants are not independent evidence.
- **Agreement with I4 Perspective-Taking and H2 Adversarial:** Skill, productivity, and collaboration claims are socially unsafe because they are also causally weak. Contestability and opt-in are measurement controls, not just adoption features.
- **Agreement with G6 Multi-Criteria:** F1 accepts the upgrade gates for Aurora, embeddings, and sidecars, but treats them as upstream measurement and operations gates. They do not by themselves prove user benefit.
- **Likely tension with F7 Systems Thinking:** Systems thinking may favor richer feedback loops earlier. F1 would delay loops until exposure assignment, influence quarantine, and independent outcomes exist; otherwise the system destroys its own counterfactuals.
- **Likely tension with B3 Bayesian Reasoning:** Bayesian updates from sparse traces can rank hypotheses before experiments. F1 would keep those posterior beliefs out of manager-facing or causal wording until a design identifies an intervention effect.
- **Likely agreement with A1 Deductive:** Proposal is not release, projection is not evidence, similarity is not identity, and association is not cause. F1 adds the experimental designs needed to cross the last boundary.
- **Likely agreement with K2 Scientific:** Every mechanism should become a falsifiable claim. F1 narrows "falsifiable" to specific interventions, units, comparators, outcomes, and blocked leakage paths when the claim is causal.

## Confidence

Overall confidence: **0.88**.

Confidence is high that current evidence supports representation, authorization, retrieval, projection, and lifecycle mechanics but not causal memory, skill, prompt, model, route, collaboration, or embedding benefit. Confidence is lower on the eventual best intervention domains and storage/retrieval upgrades because corrected memory, repaired NL2SQL P0/P1, human labels, production Aurora gates, and consented enterprise trials have not run.
