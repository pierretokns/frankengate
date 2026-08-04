# B3 Bayesian Reasoning Analysis

## Thesis

Frankengate should treat enterprise trace intelligence as sequential belief
updating over clustered, biased, partially observed evidence, not as a pipeline
that converts traces into facts. The current posterior is strong for a governed
canonical evidence plane, personal history mechanics, temporal provenance, and
proposal lifecycles. It is weak for automatic diagnosis, employee skill
inference, automatic memory, collaborator matching, custom embeddings, and
leaving Aurora.

The Bayesian kernel is: maintain explicit priors, update by evidence class,
discount source-dependent traces, widen uncertainty when labels are proxy or
post-treatment, and spend expensive model or storage work only when expected
information gain is higher than cheaper exact, structured, lexical, human-label,
or randomized evidence.

## Top Findings

1. **§F1 [Kernel Candidate]: Source dependence should dominate posterior
   calibration.**
   - **Evidence:** `enterprise-question-composed-factorial-v3-2026.json` states
     that repeat invocations are not independent samples and that the primary
     unit is query or task, not model call. `longitudinal-memory-local-model-
     replication-2026-07-30.md` reports 17 units and 425 attempts, with five
     temperature-zero repeats per unit-arm. `longitudinal-memory-cohort-
     expansion-2026-07-30.md` passes small count gates but fails the
     confirmatory diversity gate: two source families observed versus three
     required, and three source-scoped project contexts versus five required.
   - **Reasoning chain:** Five repeated calls over the same unit update protocol
     reliability, not population effect. Fable and Trace Commons update within
     their source-family clusters, not enterprise-wide behavior. Treating 425
     attempts or mirrored archives as independent would overstate the precision
     of every memory, similarity, and skill posterior.
   - **Deployment severity:** High. Overconfident internal claims can become
     product, policy, or manager-facing labels before the evidence supports
     them.
   - **Confidence:** 0.92.
   - **So what:** Store and report posterior intervals clustered by source
     family, project/task family, user/team where available, and intervention
     exposure. Do not unlock confirmatory claims until an independent internal
     cohort or whole-source-family validation updates the prior.

2. **§F2 [Kernel Candidate]: Evidence conformance has high posterior support;
   semantic and intervention claims do not inherit it.**
   - **Evidence:** `canonical-projection-e0-conformance-2026-07-30.md` shows
     OTel/OpenInference retained 48/48 event identities and 34/34 parent edges,
     while ATIF retained 0/48 enterprise event identities and 0/34 parent
     edges in the stress fixtures. `otel-collector-roundtrip-e0-2026-07-30.md`
     preserved all projected span identities and links through a pinned SDK and
     Collector path but required an out-of-band manifest for whole-trace drops.
     `frankengate-combined-evidence-matrix-2026-07-30.md` still classifies
     memory utility, diagnosis, causal skill benefit, cross-user learning,
     Aurora scale, and prospective enterprise utility as not proven.
   - **Reasoning chain:** A successful transport or projection round trip has a
     high likelihood under "the mechanics preserve selected topology." It has
     low likelihood ratio for "the trace explains cause" or "a proposed memory
     helps future work." ATIF's negative result further lowers the probability
     that a generic trajectory format can be the enterprise evidence authority.
   - **Deployment severity:** High if observability success is marketed as
     intelligence success; medium if kept as an engineering gate.
   - **Confidence:** 0.90.
   - **So what:** Keep canonical governed records as the likelihood source.
     Treat ATIF, OpenTelemetry/OpenInference, AgentEvals, Phoenix, Opik, and
     Langfuse as projections or lifecycle patterns unless they produce
     independent outcome evidence.

3. **§F3 [Owner-Acknowledged Limitation]: Cheap trace signals have nonzero
   predictive value, but current data barely updates belief that they beat
   trivial baselines.**
   - **Evidence:** `nebius-matched-pilot-2026-07-30.md` reports deterministic
     friction precision at 73.3% versus trace length at 76.7% at the 20% review
     budget, with paired confidence interval from -11.7 to +6.7 points.
     `codetracebench-manifest-e1-e3-e4-2026-07-30.md` reports structural
     selection precision of 0.567, below the preregistered +0.15 lift gate and
     tied with trace length/stage count. `codetracebench-raw-e3-e4-factorial-
     2026-07-30.md` reports the best raw deterministic localization arm tied
     reverse chronology at top-1 0.286.
   - **Reasoning chain:** The posterior should move from "signals are useless"
     to "signals are plausible review selectors," but not to "signals diagnose
     cause, skill, or intervention." Length and recency are strong nuisance
     predictors in these corpora, and the labels are proxies for review value or
     released incorrect steps, not causal failure.
   - **Deployment severity:** Medium-high. Selector scores are likely to be
     relabeled as root-cause or skill evidence in UI and dashboards.
   - **Confidence:** 0.88.
   - **So what:** Keep Signals, AgentRx invariants, and OpenRCA-style joins as
     hypothesis generators with random audit strata. Expensive LLM judges should
     be tested only after deterministic selectors and human labels define which
     cases can update belief.

4. **§F4 [Kernel Candidate]: Memory mechanics update the lifecycle posterior
   strongly, but memory utility remains near-prior.**
   - **Evidence:** `bitemporal-memory-conformance-2026-07-30.md` passes 15/15
     deterministic assertions for valid/system time, authority intersection,
     rollback, deletion closure, and influence exclusion. `trace-commons-
     memory-composition-2026-07-30.md` retains 48/48 unique revisions in
     verbatim/bitemporal arms, while latest-only retains 20 and leaks across
     same-basename placebos in 3/6 cases. `longitudinal-memory-local-model-
     replication-2026-07-30.md` reports identical aggregate scores for all four
     evidence-bearing arms and visible-label, non-dream, incomplete-bitemporal,
     and runtime-attestation confounds.
   - **Reasoning chain:** The evidence has a high likelihood under "relational
     bitemporal proposal/release mechanics can preserve provenance and prevent
     leakage." It has low likelihood ratio for "released memory improves later
     tasks." The corrected v2 protocol improves future identifiability through
     blinding, cutoff-safe oracles, whole-item budgets, and hard leakage gates,
     but no corrected model result exists yet.
   - **Deployment severity:** High. Automatic memory writes create circular
     evidence and stale guidance.
   - **Confidence:** 0.89 for mechanics; 0.65 for eventual utility.
   - **So what:** Implement Graphiti, LangMem, MemInsight, Memory Palace,
     cloud-dreaming, and `MEMORY.md` semantics as untrusted candidate,
     release, exposure, rollback, and deletion records. Do not auto-promote
     memory or widen scope until a randomized or paired prospective utility
     study moves the posterior.

5. **§F5 [Hypothesis]: Same-work retrieval justifies a conditional dense lane,
   not custom embeddings, named collaborator search, or a new vector authority.**
   - **Evidence:** `codetracebench-e2-authorized-retrieval-factorial-2026-07-
     30.md` reports structured plus dense Recall@20 of 0.818 versus 0.732 for
     exact-only on silver labels, with a +0.0859 lift. `codetracebench-e2-
     postgres-joint-retrieval-2026-07-30.md` reports local exact pgvector
     Recall@20 of 0.667 at 3.017 ms p50, while the tested FTS/trigram/vector
     hybrid reached only 0.672 at 256.843 ms p50. The combined evidence matrix
     says custom embedding promotion requires at least +5 absolute Recall@20
     over the general hybrid baseline without RLS, deletion, or latency
     regression.
   - **Reasoning chain:** Dense retrieval meaningfully updates belief that
     semantic candidate generation helps some same-task queries. Silver labels,
     small local cohorts, and lack of human adjudication sharply discount the
     update for collaboration, skill, or enterprise transfer. The latency result
     lowers belief in the tested trigram-heavy fusion, not in all hybrids.
   - **Deployment severity:** Medium-high. A vector neighbor is socially
     tempting to display as a person match.
   - **Confidence:** 0.83.
   - **So what:** Keep exact, structured, lexical, and general dense retrieval
     behind current authority. Train enterprise embeddings or evaluate
     VectorChord, pg_textsearch, pgContext, Turbovec, Turbopuffer, or
     Frankensearch only after a frozen, human-labeled hard slice or Aurora SLO
     failure gives them high expected information value.

6. **§F6 [Kernel Candidate]: NL2SQL is the best first causal testbed, but the
   current posterior on skill benefit is still low.**
   - **Evidence:** `hf-nl2sql-trace-audit-2026-07-30.md` finds WMH BIRD-SQL has
     1,993 real runs and 4,168 tool transitions over 222 traced tasks and 11
     databases, but no full OTel causality or wall-clock timing. `defog-
     governed-sql-replay-conformance-2026-07-30.md` semantically matches all
     95 executable PostgreSQL tasks under hardened policy. `defog-sql-
     factorial-fold0-mechanics-smoke-2026-07-30.md` has every arm solve the
     same 2/4 tasks and fails the protocol gate with 25% to 50% terminal
     protocol failures. `nl2sql-capability-isolation-component-checkpoint-
     2026-07-30.md` passes 61/61 component tests but still leaves P1 and hidden
     families sealed.
   - **Reasoning chain:** SQL traces provide stronger likelihood evidence than
     generic coding chat because database observations, policy denials, SQL
     attempts, and semantic results are observable. But the P0 null and
     protocol failure dominate the current causal posterior. Capability
     isolation raises confidence that a future experiment can be trustworthy,
     not that a procedure already works.
   - **Deployment severity:** High if procedure suggestions are released before
     causal lift; medium if confined to research.
   - **Confidence:** 0.87.
   - **So what:** Make NL2SQL the first intervention gauntlet after protocol
     repair: no artifact, length-matched placebo, and one frozen reviewed
     trace-mined procedure on family-disjoint Defog tasks. Do not unlock
     ReasoningBank, Hermes, GEPA, Trace2Skill, SkillOpt, or RL-history loops
     until they beat controls with sealed inputs.

7. **§F7 [Owner-Acknowledged Limitation]: The highest-value missing evidence is
   label and intervention evidence, not more frameworks or raw corpora.**
   - **Evidence:** `public-native-history-fidelity-2026-07-30.md` finds useful
     native and derivative histories but no valid independent cross-user
     enterprise panel, no complete harness home, and unresolved training rights
     for some sources. `fable5-sensitive-token-scan-2026-07-30.md` blocks raw
     external egress until sanitizer and rescan pass. `LICENSES.md` records
     aggregate-only policies and distinguishes public visibility from
     redistribution or training permission. The combined matrix identifies
     human labels, Aurora/selective-scope scale, evidence validity,
     calibration, privacy, and prospective outcomes as the measured blockers.
   - **Reasoning chain:** More public traces will mostly update parser coverage
     and source-shape priors. The likelihood ratio for enterprise questions is
     higher from blinded same-work labels, decisive-friction labels, influence
     exposures, deletion tests, and randomized or paired outcomes.
   - **Deployment severity:** Medium-high. Dataset accumulation can look like
     progress while leaving the important posterior unchanged.
   - **Confidence:** 0.91.
   - **So what:** Spend the next evidence dollar on internal consented labels,
     random audits, reviewer agreement, protocol repair, and prospective
     interventions. Treat corpus expansion as valuable only when it changes the
     effective independent source-family count or tests a known failure mode.

## Standalone Concept Assessment

| Concept | Bayesian role | Required observations and labels | Current posterior |
|---|---|---|---|
| ATIF | Lossy interchange projection | Mapped event counts, unsupported-field receipts, reimport identity checks | Useful for selected portable tasks/evals; low probability as enterprise authority. |
| OpenTelemetry/OpenInference | Operational topology and timing projection | Expected-count manifests, backend round trip, drop controls, content allowlist | Strong for topology mechanics; weak for authorization, memory, or causality. |
| AgentRx | Invariant and failure-hypothesis generator | Declarative checks, abstention, human decisive-step labels, replay outcomes | Plausible selector; root-cause posterior remains low. |
| Signals | Cheap review-prior over traces | Frozen score, length baseline, random audit, human "informative" labels | Retain as low-cost selector; little evidence of superiority yet. |
| AgentEvals | Stored audit and replay-case proposal | Mutant sensitivity, false-positive rate, changed-system rerun | Useful proposal mechanism; not outcome proof. |
| Phoenix, Opik, Langfuse | Dataset/eval/annotation lifecycle priors | One authoritative release/evaluator schema and deletion closure | Borrow lifecycle concepts; low value as parallel authorities. |
| OpenRCA | Multimodal causal-hypothesis prior | Logs, metrics, topology, trace clocks, alternatives, interventions | Hypothesis only until intervention or quasi-experiment. |
| Graphiti | Temporal fact/entity structure | Entity namespace, valid/system time, contradiction, ACL traversal tests | Relational subset has high support; graph backend is unproven. |
| LangMem | Typed memory extraction/update workflow | Evidence citations, scope, stale/conflict tests, reviewer labels | Proposal generator only; direct mutation unsupported. |
| MemInsight | Typed attributes and ontology hints | Entity/task ontology, calibration, sensitive-attribute tests | Schema inspiration; no independent truth authority. |
| Memory Palace | Verbatim/contextual memory surface | Revision retention, context negatives, deletion and rollback | Useful representation pattern; no utility proof. |
| Temporal evidence | Cutoff-safe online state | Known-at and valid-at separation, interval gaps, future-leak tests | Kernel candidate. |
| `MEMORY.md` | Destination rendering | Signed release refs, source citations, rollback/delete propagation | Destination only, never canonical memory. |
| Cloud dreaming | Query-independent proposal synthesis | Pre-cutoff inputs, independent verifier, partial-output quarantine, utility tests | Experimental arm; automatic release unsupported. |
| ReasoningBank | Procedure lessons from experience | Verified success/failure, family-disjoint holdouts, no self-judge | Plausible candidate generator; untested in Frankengate. |
| Hermes / GEPA / Trace2Skill / SkillOpt | Bounded skill-candidate search | Sealed stages, no-skill/placebo controls, signed releases, rollback | Use behind release lifecycle after NL2SQL gates. |
| Jeopard-style skill learning | Unresolved reference | Pinned project, mechanism, baseline, labels | Do not build until identified. |
| RL environment histories | Resettable state/action evidence | Reset, resources, reward basis, termination, replay divergence | Requires environment attachment; flat traces are insufficient. |
| CASS, Doodlestein/CM, claude-history, Prompt-Scope | Personal history UX and import priors | Import receipts, local rights, deletion path, no cross-user claim | Useful UX/import concepts; weak enterprise inference evidence. |
| Frankensearch | Optional hybrid retrieval sidecar | ACL-before-candidate, tombstones, stale-index tests, license/SBOM, benchmark | Research-only until a named retrieval failure. |
| JSONB/FTS/pgvector in Aurora | Current evidence and candidate-generation authority | Typed authority columns, exact recall oracle, deletion/latency gates | Highest current posterior for initial architecture. |
| VectorChord, pg_textsearch, pgContext | PostgreSQL replacement or extension candidates | Same workload, RLS/deletion proof, HA/ops comparison | Conditional bakeoff arms, not launch requirements. |
| Turbovec, Turbopuffer | Dense retrieval accelerators/services | Authorized candidate allowlists, stale/deletion proof, cost/latency win | Low current posterior as production authority. |
| General embeddings | Semantic candidate generator | Human positives/hard negatives, exact-ID protection, model/index receipts | Conditional dense lane supported for retrieval only. |
| Enterprise-adapted embeddings | Organization-specific retrieval improvement | Rights-cleared labels, train/test by source/time/user/team, +5 Recall@20 gate | Premature. |
| Agentic coding/research traces | Mechanics and candidate substrate | Tool-call fidelity, task labels, outcomes, source rights | Good for adapters and hypotheses, weak for population claims. |
| NL2SQL complete tool traces | Causal skill testbed | DB state, SQL attempts, gold/evaluator separation, policy receipts | Best next deep domain after protocol repair. |

## Composition and Non-Composition Matrix

| Combination | Bayesian composition | Failure mode | Minimum test |
|---|---|---|---|
| Canonical DAG + OTel + ATIF | Canonical store provides prior evidence; projections add transport/topology likelihoods with loss receipts | Projection output is treated as source truth | Source/projection/reimport mutation tests and whole-trace export manifest. |
| Signals + AgentRx + AgentEvals | Signals raise review prior, invariants propose hypotheses, evals create audit/replay candidates | Same label counted as selector, diagnosis, and cause | Random audit, decisive-step labels, changed-system replay. |
| Phoenix/Opik/Langfuse + Frankengate | Lifecycle concepts become native release/evaluator tables | Parallel tools own datasets, feedback, deletion, or eval identity | One deletion/release/evaluator authority test. |
| Graphiti + MemInsight + temporal ledger | Entity/fact candidates are scoped bitemporal rows | Graph proximity or `group_id` substitutes for authority | Cross-scope traversal, alias collision, and interval-gap controls. |
| LangMem + Dreams + `MEMORY.md` | Extractors and dreams emit candidates; releases render destination files | Direct writes generate future evidence that validates themselves | Proposal/release/influence/deletion gauntlet plus memory-on/off outcomes. |
| ReasoningBank + Hermes/GEPA + NL2SQL | Procedure candidates enter sealed family-disjoint causal replay | Generator sees hidden tasks, judges itself, or edits live skills | No-skill/placebo/expert/trace-mined arms with sealed manifests. |
| CASS/Prompt-Scope/claude-history + enterprise search | Local UX informs personal history and import adapters | Single-user local privacy model is assumed enterprise-safe | Authority envelope and destination-transform tests. |
| Frankensearch/Turbopuffer/Turbovec + Aurora | Derived accelerator consumes only eligible IDs or chunks | Search sidecar becomes second policy/cache plane | ACL-before-candidate, tombstone convergence, stale-index fail-closed, PG recheck. |
| General embeddings + structured retrieval | Dense lane adds candidates to exact/structured evidence | Similarity becomes identity, skill, or collaboration | Blinded human task labels and exact-authorized oracle. |
| Enterprise embedding adaptation + feedback | Reviewed labels update a retrieval representation | Clicks, generated memories, or influenced traces become training positives | Frozen hard slice, influence quarantine, memorization and deletion tests. |
| RL histories + trace DAG | Environment evidence is attached as first-class state | Chat transcript is treated as replayable world state | Reset/action/resource/termination negative controls. |

## Enterprise Questions Answered and Not Answered

| Question | Current answer class | Bayesian answer |
|---|---|---|
| Show each user currently authorized history | Mostly deterministic, local mechanics | High posterior for local PostgreSQL mechanics; production Aurora/deletion/failover uncertainty remains. |
| Repeated friction before success | Statistical selector/hypothesis | Candidate review queues are plausible; cause and skill labels remain unsupported. |
| Which evals should be created | Proposal and audit mechanics | Evidence-linked eval candidates are supported; changed-system benefit requires replay. |
| What should become memory or `MEMORY.md` | Proposal only | Temporal candidate mechanics pass; utility and automatic release remain near-prior. |
| Similar work across users | Retrieval hypothesis | Dense/structured retrieval can nominate tasks; named people or collaboration utility is not answered. |
| Missing cloud/domain skills | Causal and social hypothesis | Not supported without capability ontology, confounder labels, exposure, and later outcomes. |
| Who should collaborate | Prospective opt-in product question | Not answerable from traces alone; requires reciprocal consent and utility outcomes. |
| Which prompt, tool, skill, memory, model, or route helps | Causal intervention | Requires randomized, canary, paired, or quasi-experimental exposure registry. |
| Should Frankengate leave Aurora | Future operations question | No current evidence; update only from production-like SLO/cost/deletion/failover failure. |
| Should an enterprise embedding be trained | Future representation question | Premature; update only from frozen hard-slice lift and safety gates. |
| Who is productive, competent, loyal, or likely to leave | Unsafe/refuse | Socially unsafe and not identifiable from intended evidence. |

## Empirical Tests and Falsifiers

1. **Bayesian evidence ledger:** For each claim, record prior, evidence source,
   unit of analysis, dependence cluster, likelihood direction, posterior claim
   class, and calibration notes. Falsifier: a dashboard cannot distinguish a
   deterministic fact, selector, hypothesis, causal effect, and refused claim.

2. **Signal value-of-information test:** Freeze cheap signals, length, random
   audit, and reviewer labels. Falsifier for signals: they do not beat length
   and random on human "worth reviewing" labels after source/task clustering.

3. **Same-work retrieval test:** Human-adjudicate task-family positives and
   hard negatives across exact, structured, FTS, dense, hybrid, reranker, and
   optional sidecar arms under identical authority. Falsifier for dense: no
   material Recall@20/nDCG/MRR lift on cases exact/structured miss.

4. **Memory utility test:** Run corrected v2 memory with blinded arm labels,
   cutoff-safe oracle, real dream treatment, influence exclusion, stale/conflict
   controls, and paired inference. Falsifier for memory utility: no outcome lift
   over no-memory/current-memory/placebo, or stale/anchoring harm increases.

5. **NL2SQL procedure test:** After protocol repair, compare no artifact,
   length-matched placebo, and one frozen reviewed trace-mined procedure on
   schema-family-disjoint Defog tasks. Falsifier: no paired lift in `semantic
   correct AND policy accepted AND no unauthorized observation`, or any security
   violation.

6. **Aurora reversal test:** Run concurrent ingest, history, FTS, pgvector,
   deletion/tombstone, re-embed, aggregate, failover, and RDS Proxy tests.
   Falsifier for Aurora-first: selective authorized recall, p95/p99 latency,
   deletion closure, or inference isolation fails after declared tuning.

7. **Embedding adaptation test:** Train only on rights-cleared reviewed labels
   after general hybrid fails a named slice. Falsifier for adaptation: less than
   +5 absolute Recall@20 over the general hybrid baseline or any exact-ID,
   subgroup, RLS, deletion, latency, memorization, or rollback regression.

8. **Cross-user safety/utility test:** Consented cohort, minimum support,
   reciprocal opt-in, anti-differencing attacks, and objective outcomes.
   Falsifier: privacy controls erase utility or repeated queries recover a
   person, rare project, classified fact, or sensitive task.

## Architecture Consequences

- Keep one governed PostgreSQL/Aurora evidence, candidate, release, influence,
  and experiment authority.
- Store claim class and posterior status as first-class metadata: deterministic,
  statistical, hypothesis, causal, refused, and owner-acknowledged limitation.
- Treat ATIF, OTel/OpenInference, AgentEvals, memory files, external search
  indexes, graph extracts, and learner batches as derived projections with loss
  receipts.
- Maintain source-family, project/task-family, user/team, and intervention
  exposure identifiers for clustered inference.
- Keep exact/structured/lexical retrieval first, with bounded general dense
  retrieval as a candidate lane.
- Make every memory, skill, eval, route, model, prompt, and embedding release
  carry exposure/influence lineage so later traces are not independent evidence
  by default.
- Add no production graph, vector, memory, observability, or lifecycle authority
  until a frozen benchmark shows a high likelihood-ratio gain over the simpler
  baseline under equal authorization and deletion rules.

## Risks Identified

- **Posterior overconfidence:** counting repeated deterministic calls,
  mirrored archives, or same-family tasks as independent samples.
- **Likelihood laundering:** treating projection fidelity, RLS mechanics, or
  mutation sensitivity as evidence of memory utility or causal improvement.
- **Proxy-label drift:** failure, length, incorrect-step labels, and terminal
  success are not the same construct as diagnostic usefulness or skill gap.
- **Future leakage:** later reads, influenced traces, generated memories, or
  released skills can contaminate validation.
- **Similarity/identity conflation:** vector distance may become "same person,
  same work, missing skill, or collaborator."
- **Expensive low-EV signals:** custom embeddings, graph stores, LLM judges, and
  sidecars may add little belief update before labels and causal outcomes exist.
- **Rights and egress uncertainty:** public availability does not imply training
  permission or safe external processing.
- **Aurora dogma risk:** Aurora-first is the current posterior, not a permanent
  axiom; it needs explicit reversal evidence.

## Recommendations

1. Build a Bayesian claims registry for every feature and experiment.
2. Ship personal history and evidence-linked review/proposal workflows first.
3. Keep signals, AgentRx, OpenRCA, and judges as hypothesis generators with
   calibrated abstention and alternatives.
4. Complete the corrected v2 memory run before any automatic memory UX.
5. Repair NL2SQL protocol and run the family-disjoint causal gauntlet before
   releasing learned procedures.
6. Prioritize human labels, random audits, reviewer agreement, and influence
   exposure records over more framework integrations.
7. Keep custom embeddings and external retrieval systems behind preregistered
   hard-slice or operations-failure gates.
8. For team/enterprise features, expose aggregate artifact needs and opt-in
   patterns, not named people or inferred deficits.

## New Ideas and Extensions

- **Expected information gain queue:** Rank next experiments by expected
  posterior movement per dollar, review minute, privacy risk, and engineering
  complexity.
- **Dependence discount field:** Every aggregate result records effective sample
  size after source-family and project/task clustering.
- **Posterior downgrade receipts:** If an artifact influences later traces,
  downstream analyses automatically mark those traces as post-treatment unless
  the model explicitly includes exposure.
- **Counterevidence cards:** For each proposed skill/memory/cause, show the top
  alternative explanations that would lower belief: permission, incident,
  model, missing docs, ambiguous requirements, tool outage, or exploration.
- **Low-EV signal kill switch:** A framework, model, or sidecar remains disabled
  unless its latest frozen benchmark crosses a specified Bayes-factor or utility
  threshold over exact/structured baselines.

## Assumptions Ledger

- Authorized internal users, teams, and admins may see full PII/classified
  content within scope; reusable credentials are excluded from ordinary traces.
- Current project summaries and content-addressed aggregate results are treated
  as primary project evidence.
- Public corpora are useful for parser, representation, retrieval, and protocol
  mechanics, not for employee population inference.
- Several hundred GB does not itself justify leaving Aurora.
- Human review capacity exists for early labels and proposal queues.
- Value means verified outcome improvement, safer evidence review, or lower
  review cost, not merely more traces or richer models.
- Owner-acknowledged limitations are not counted as new discoveries.

## Questions for Project Owner

1. What minimum posterior probability and uncertainty interval is acceptable
   before a hypothesis can appear in user-facing UI?
2. Which claim classes are categorically forbidden for managers even when
   technically authorized?
3. What is the first consented internal cohort that can provide task-similarity,
   friction, skill-opportunity, and outcome labels?
4. What review-minute budget should define value of information for signals and
   LLM judges?
5. What exact Aurora SLO or cost failure would justify a one-database
   replacement study?
6. Which released artifacts make later traces ineligible as independent
   validation by default?
7. What evidence threshold should allow cross-user opt-in introductions around
   an artifact?

## Points of Uncertainty

- Production Aurora behavior under selective RLS, pgvector/FTS, deletion churn,
  failover, and analytics load is untested.
- Corrected v2 memory primitives look much better than the first pilot, but no
  corrected model or human result exists.
- Human label reliability for same work, productive exploration, accidental
  friction, and skill support is unknown.
- General embeddings may fail on internal jargon or exact identifiers more than
  current silver labels reveal.
- NL2SQL may transfer poorly to open-ended coding and research workflows.
- The best user-facing uncertainty language is a product and policy question,
  not just a statistical one.
- Current source reviews of third-party projects may age; production decisions
  need fresh pins and supply-chain checks.

## Agreements and Tensions with Other Perspectives

- **Agreement with B9 Simplicity/MDL:** The current posterior supports one
  governed authority plus projections. B3 adds that the reversal gates should
  be treated as explicit prior-to-posterior update rules, not only simplicity
  discipline.
- **Agreement with L2 Debiasing:** Negative and null results must stay in the
  evidence base. B3 frames them as likelihood updates that prevent posterior
  inflation from mechanics success.
- **Agreement with I4 Perspective-Taking:** Contestability and opt-in are not
  merely social safeguards; they are observation mechanisms that correct false
  labels and improve posterior calibration.
- **Tension with F7 Systems Thinking:** F7 may favor modeling broad feedback
  loops early. B3 favors quarantining loops until influence lineage lets us
  estimate whether feedback is evidence or contamination.
- **Tension with G6 Multi-Criteria Decision:** Weighted matrices can choose a
  component whose evidence barely updates the target claim. B3 asks for
  likelihood ratio and expected information gain before promotion.
- **Agreement with F1 Causal Inference:** Skill, memory, prompt, route, model,
  and embedding benefit require exposure/control and independent outcomes.
  B3 emphasizes how priors should remain conservative until those data exist.

## Confidence

Overall confidence: **0.86**.

Confidence is high that current evidence supports governed personal history,
projection mechanics, temporal provenance, proposal/release lifecycle, and
PostgreSQL/Aurora-first architecture. Confidence is moderate on general dense
retrieval as a candidate lane and on NL2SQL as the best causal testbed. Confidence
is low that current evidence supports automatic memory, root-cause automation,
employee skill inference, collaborator matching, custom embeddings, generator
fine-tuning, or leaving Aurora. The largest future update would come from a
consented internal cohort with reliable labels and randomized or paired
intervention outcomes under complete authority/deletion controls.
