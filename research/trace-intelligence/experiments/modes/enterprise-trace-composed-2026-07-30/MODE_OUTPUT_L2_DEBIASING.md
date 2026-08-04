# L2 Debiasing Analysis

## Thesis

The Frankengate trace-intelligence program is unusually well documented about its own limits, which is a strength and also a bias hazard: the architecture can start mistaking well-instrumented mechanics for validated enterprise intelligence. The current Aurora-first, proposal-only, evidence-linked path is the best supported default, but it must stay reversible. The debiasing rule is: every advanced component remains an experimental arm until it beats exact/structured baselines, survives current-authority/deletion gates, and improves a prospectively measured outcome without turning trace evidence into employee surveillance.

## Top Findings

1. **§F1: Aurora-first is justified, but can become status-quo bias.**
   - **Evidence:** `trace-intelligence-enterprise-question-composition-audit.md` says Aurora remains the only required authority; `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` shows exact pgvector at `0.667` Recall@20 and `3.017 ms` p50 locally, while the tested hybrid reached only `0.672` Recall@20 at `256.843 ms`; `log-trace-vector-database-and-reflective-learning-review.md` admits Aurora has not passed failover, RDS Proxy, selective-RLS scale, or production workload gates.
   - **Reasoning chain:** The evidence rejects "add another database now," not "Aurora can do everything forever." A local rollback-only PostgreSQL run is a mechanism gate, not an Aurora operations proof.
   - **Severity:** Medium for the internal deployment: a premature second system creates duplicated authorization/deletion risk, but a dogmatic Aurora stance could hide real scale or extension failures.
   - **Confidence:** 0.84.
   - **So what:** Keep Aurora as P0, but write explicit reversal criteria: leave or replace it if selective authorized recall/latency, deletion closure, failover/reconnect, or analytics isolation fail after bounded vector cardinality, exact fallback, partitioning, pooling, and preaggregation.
   - **Bias audited:** Confirmation/status-quo bias.
   - **Status:** Kernel candidate, because it is supported by architecture docs plus measured retrieval results.

2. **§F2: Framework collection bias is the main product-shape risk.**
   - **Evidence:** `memory-skill-replay-evidence-composition-matrix-2026.md` lists Dreams, Graphiti, LangMem, MemPalace, ReasoningBank, Hermes, GEPA/Trace2Skill, and RL episodes, but repeatedly maps them to Frankengate-native records rather than deployed services; `trace-intelligence-composed-feasibility-and-failure-analysis.md` says Phoenix, Opik, and Langfuse overlap and should contribute lifecycle ideas, not become separate authorities.
   - **Reasoning chain:** The upstream projects are attractive because each names a missing capability. Stacking them would double-count ingestion, identity, retention, release, and deletion semantics while making authority harder, not easier.
   - **Severity:** High: in an internal multi-tenant tool, duplicate data planes are a realistic source of cross-scope leakage and stale deletion, even without public exposure.
   - **Confidence:** 0.87.
   - **So what:** Adopt concepts as schemas, tests, and adapters. Do not deploy Phoenix, Opik, Langfuse, Graphiti, LangMem, or memory services as independent systems of record unless a specific Frankengate-native benchmark fails.
   - **Bias audited:** Availability and framework-collection bias.
   - **Status:** Kernel candidate.

3. **§F3: Several metrics are useful selectors but invalid labels.**
   - **Evidence:** `nebius-matched-pilot-2026-07-30.md` reports deterministic friction precision at 20 percent budget of `73.3%`, while trace length reached `76.7%`; `codetracebench-manifest-e1-e3-e4-2026-07-30.md` reports structural review selection precision `0.567`, below the preregistered +15 point gate and tied with length/stage count; `longitudinal-memory-local-model-replication-2026-07-30.md` shows `no_memory` at 100% exact-decision correctness due to abstention, a control artifact.
   - **Reasoning chain:** Selection, localization, abstention, exact match, and successful terminal output are different constructs. Optimizing one and narrating another is metric bias.
   - **Severity:** High: the system could produce confident but wrong "skill gap," root-cause, or memory-benefit claims for employees if selector metrics are relabeled as diagnoses.
   - **Confidence:** 0.90.
   - **So what:** Every dashboard and experiment must label whether a number is selector precision, retrospective audit match, retrieval quality, replay success, causal intervention effect, or human outcome.
   - **Bias audited:** Metric/construct bias and automation bias.
   - **Status:** Kernel candidate.

4. **§F4: Public corpora are survival-biased and should not simulate an enterprise.**
   - **Evidence:** `public-native-history-fidelity-2026-07-30.md` finds mirrored, scrubbed, flattened, and merged histories, not an independent enterprise panel; `longitudinal-memory-cohort-expansion-2026-07-30.md` reports Fable added reads but failed a confirmatory diversity gate because the Glint archive is a byte-exact mirror and transitions are concentrated in two source families; `codetracebench-manifest-e1-e3-e4-2026-07-30.md` notes CodeTraceBench is curated and filtered.
   - **Reasoning chain:** A public corpus that preserves tool calls is valuable for parser and mechanics tests. It is not evidence about employee prevalence, collaboration opportunities, or enterprise transfer.
   - **Severity:** Medium-high: internal deployment lowers public privacy risk, but false organizational conclusions are still costly and socially unsafe.
   - **Confidence:** 0.88.
   - **So what:** Use public traces for adapters, negative controls, and candidate experimental designs; require a consented, prospective, within-enterprise cohort before cross-user similarity, skill support, or collaboration recommendations.
   - **Bias audited:** Survivorship, selection, and external-validity bias.
   - **Status:** Owner-acknowledged limitation, confirmed.

5. **§F5: Mechanics success is being overweighted relative to intervention benefit.**
   - **Evidence:** `bitemporal-memory-conformance-2026-07-30.md` passes 15/15 synthetic assertions but states it does not establish memory benefit; `trace-commons-memory-composition-2026-07-30.md` has only three retention queries and no comparative quality claim; `defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md` shows all arms passed the same 2/4 tasks and protocol failures were 25-50%; `frankengate-combined-evidence-matrix-2026-07-30.md` classifies memory utility, causal skill benefit, and enterprise utility as unproven or gated.
   - **Reasoning chain:** Authority, RLS, sealed stages, proposal release, and replay receipts are necessary substrate. They do not imply that memories, skills, evals, dreams, or model changes help.
   - **Severity:** High: an internal tool can safely store evidence but still cause harm by automatically promoting ineffective guidance or skills.
   - **Confidence:** 0.91.
   - **So what:** Treat every memory, skill, prompt, routing, model, and fine-tune suggestion as a reversible intervention with no-skill/placebo/current-control arms and independent outcome measurement.
   - **Bias audited:** Sunk-cost and automation bias.
   - **Status:** Kernel candidate.

6. **§F6: Similarity is being correctly demoted, and that demotion should be enforced.**
   - **Evidence:** `codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md` shows structured+dense improves silver Recall@20 by `+0.0859`, but labels are silver and not human adjudicated; `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` says same benchmark task does not imply cross-user collaboration value; `trace-intelligence-enterprise-question-composition-audit.md` requires reciprocal opt-in for introductions.
   - **Reasoning chain:** Dense retrieval can nominate candidates, but identity, same work, permission to introduce people, and shared capability gaps require adjudicated task signatures and policy.
   - **Severity:** High for team/enterprise views: vector-neighbor outputs can become a people-finder if UI language is careless.
   - **Confidence:** 0.86.
   - **So what:** Keep embeddings as candidate generators. Never display named cross-user matches from vector distance alone; route through anonymous reusable patterns and reciprocal opt-in.
   - **Bias audited:** Similarity/identity conflation and automation bias.
   - **Status:** Kernel candidate.

7. **§F7: Temporal leakage and circular feedback are the hard-to-see failure modes.**
   - **Evidence:** `trace-commons-memory-composition-2026-07-30.md` says version gaps became known only from later read results and could not legitimately drive pre-read abstention; `bitemporal-memory-conformance-2026-07-30.md` marks influenced traces ineligible as independent validation; `memory-skill-replay-evidence-composition-matrix-2026.md` warns that a generated memory influencing future traces cannot independently corroborate itself.
   - **Reasoning chain:** Longitudinal trace intelligence creates feedback: retrieval changes behavior, memories change traces, skills change task attempts, and later observations tempt evaluators to score earlier decisions with future information.
   - **Severity:** High: the system could train on or validate against its own outputs while appearing statistically rigorous.
   - **Confidence:** 0.89.
   - **So what:** Make influence lineage mandatory for memories, skills, evals, retrieval releases, and model/index releases; hold out traces that were influenced by the artifact being validated.
   - **Bias audited:** Future-leakage, circular-feedback, and confirmation bias.
   - **Status:** Kernel candidate.

## Standalone Concept Assessment

| Concept | Enterprise question it can answer | Evidence/labels required | Debiasing verdict |
|---|---|---|---|
| ATIF | Portable task/eval export for selected conversations and tools | Loss receipt, source/projection hashes, explicit unsupported fields | Useful projection, not canonical evidence or authority. |
| OpenTelemetry/OpenInference | Operational topology, latency, span navigation, tool lifecycle projection | Expected span manifest, backend round trip, content/authority allowlist | Strong operational projection; not a memory, replay, or authorization store. |
| AgentRx | Candidate failure localization and invariant violations | Declarative invariants, temporal holdout, human labels, checker sandbox | Candidate diagnosis only; "root cause" needs intervention/replay. |
| Signals | Cheap review-queue selection | Frozen score, random audit stratum, diagnostically-informative labels | Selector, not diagnosis or skill label. |
| AgentEvals | Stored-trace audits and replay fixture candidates | Assertion semantics, mutant tests, changed-system replay boundary | Useful if audit vs replay is explicit. |
| Phoenix / Opik / Langfuse | Dataset, annotation, experiment, feedback lifecycle | One authoritative dataset/release model and evaluator revisions | Import lifecycle concepts, not services. |
| OpenRCA | Multimodal RCA hypotheses | Metrics/logs/topology clocks, modality ablations, alternatives | Hypothesis generator, not causal proof. |
| Graphiti / MemInsight | Entity/fact/episode and bitemporal retrieval | Entity namespace, valid/system time, contradiction and scope rules | Relational subset first; graph backend only after relational failure. |
| LangMem / Memory Palace / `MEMORY.md` | Candidate memory extraction and destination rendering | Evidence citations, review, release, rollback, deletion lineage | Proposal/destination only; never live authority. |
| Cloud dreaming | Background candidate synthesis | Input release, model/job pins, partial-output quarantine, held-out utility | Experimental arm; no automatic promotion. |
| ReasoningBank / Hermes / Jeopard-style skills | Procedural candidates from success/failure contrast | Hidden-family eval, no-skill/placebo controls, influence receipts | Useful only with independent evaluation and rollback. Unknown "Jeopard" must stay unresolved, not renamed. |
| RL environment histories | Replay/divergence and reward-linked episodes | Reset/action/observation/termination/resource state | Needs environment attachment; flat trace is insufficient. |
| CASS / Doodlestein / CM / claude-history / Prompt-Scope / Frankensearch | Personal/local exact and fuzzy history UX | Import receipts, local privacy, fielded query evidence | Adopt UX/query ideas; not shared enterprise authority. |
| JSONB / FTS / pgvector in Aurora | Authority, exact/lexical/vector candidate retrieval | Typed authority columns, exact recall oracle, deletion/latency gates | Best current minimum. Do not hide authority in JSONB. |
| VectorChord / pg_textsearch / pgContext / Turbovec / Turbopuffer | Potential performance or feature upgrade | Frozen failed workload, equal RLS/deletion, cost/ops comparison | Research/replacement candidates, not launch requirements. |
| General embeddings | Semantic candidate generation | Human task labels, hard negatives, RLS and deletion tests | Conditional candidate lane. |
| Enterprise-adapted embeddings | Organization-specific jargon/task retrieval | Governed labels, train/test by user/tenant/time, +5 absolute Recall@20 and no safety regressions | Premature until general hybrid fails on a named slice. |
| Agentic coding/research traces | Parser, review queues, eval/memory/procedure candidates | Tool-call fidelity, outcomes, task labels, source rights | Strong mechanics substrate, weak population inference. |
| NL2SQL traces | Capability-isolated procedural replay and skill tests | Complete tool calls, databases, gold/evaluator separation, hidden families | Best causal testbed so far, but P0 protocol failed. |

## Composition and Non-Composition Matrix

| Combination | Composes when | Fails when | Debiasing test |
|---|---|---|---|
| Canonical DAG + OTel/OpenInference | OTel is a content-minimized projection with expected-count manifests | Spans become the canonical evidence or policy plane | Drop/duplication/backend-evolution round trips. |
| Signals + AgentRx + AgentEvals | Signals select, invariants hypothesize, evals audit or replay | Selector, hypothesis, and cause collapse into one label | Random audit plus human/adjudicated decisive-step labels. |
| Phoenix/Opik/Langfuse lifecycle + Aurora | Dataset and evaluator concepts are implemented as Frankengate records | Each product owns its own dataset/delete identity | One authoritative release and deletion closure test. |
| Graphiti + temporal memory | Edges/facts are relational, scoped, bitemporal, and cited | Graph proximity or `group_id` substitutes for authorization | Cross-scope traversal and entity-merge negative controls. |
| LangMem/Dreams + `MEMORY.md` | Extracted memories are untrusted candidates and rendered files are destinations | In-place memory updates become evidence | Proposal review, influence lineage, rollback, and deletion tests. |
| ReasoningBank/Hermes + NL2SQL replay | Candidate procedures are frozen and tested on family-disjoint tasks | Generator judges itself or sees hidden families | No-skill/placebo/expert/trace-mined arms with sealed stages. |
| CASS/Frankensearch + enterprise search | Local UX/query primitives run behind the same authority envelope | Local index is uploaded or shared as trusted global evidence | Destination transform, tombstone, RLS-equivalent sidecar gate. |
| General embeddings + structured retrieval | Dense lane only adds candidates after exact/structured filters | One whole-trace vector becomes identity, skill, or collaboration | Blinded task labels and exact authorized oracle. |
| Enterprise embedding adaptation + feedback | Training data has reviewed labels, influence/deletion receipts, and holdouts | Clicks, success traces, or generated memories become unreviewed positives | Frozen hard slice, memorization/deletion tests, rollback. |
| RL histories + canonical traces | Environment state and reward basis are first-class attachments | Chat transcript or ATIF export is treated as replay state | Reset/resource/divergence negative controls. |

## Enterprise Questions Answered and Not Answered

| Enterprise question | Current debiased answer |
|---|---|
| Show each user their own history | Supported locally as a mechanics goal; production authority/deletion/failover gates remain. |
| Find repeated friction/recovery | Supported as review candidates; not yet verified as accidental friction, correct recovery, or cause. |
| Suggest evals | Supported as proposal/audit mechanics; changed-system replay benefit remains untested. |
| Suggest memory / `MEMORY.md` | Not supported as automatic memory; supported as cited proposal mechanics. |
| Similar work across users | Not supported as named matches; possible as anonymous, consented, human-confirmed patterns. |
| Missing cloud/domain skills | Not supported. Requires capability ontology, environmental alternatives, and prospective outcome evidence. |
| Who should collaborate | Not supported except reciprocal opt-in around a reviewed artifact. |
| Custom embedding or generator fine-tune | Premature. Requires a frozen failure of general hybrid plus safety and deletion gates. |
| Root-cause automation | Not supported. Hypothesis generation is feasible; causal wording requires intervention/replay. |

## Empirical Tests and Falsifiers

1. **Aurora reversal test:** Run concurrent ingest/search/delete/re-embed/aggregate/failover through Aurora and RDS Proxy with selective RLS. Falsifies Aurora-first if exact authorized recall, p95/p99 latency, deletion SLO, or inference isolation fails after the documented mitigations.
2. **Embedding adaptation test:** Freeze human-adjudicated positives/hard negatives by user/tenant/time. Train only after baseline exact/structured/general-dense/hybrid fails a named slice. Promote only with at least +5 absolute Recall@20 and no RLS, deletion, latency, memorization, or hard-negative regression.
3. **Signals diagnostic test:** Freeze each deterministic signal and a random audit stratum. Falsifies Signals-as-review-selector if it does not beat length and random on human "informative trace" labels.
4. **Memory utility test:** Randomized or stepped-wedge memory on/off with stale, contradiction, anchoring, and deletion harms. Falsifies memory benefit if proposal arms do not improve verified outcomes versus no-memory/current-memory controls.
5. **Skill/procedure test:** No-skill, length-matched placebo, expert seed, and trace-mined procedure on sealed family-disjoint NL2SQL tasks. Falsifies skill-learning value if paired wins do not exceed controls after protocol failure is repaired.
6. **Graph backend test:** A bounded, authorized multi-hop temporal-fact benchmark must fail relational recursive SQL before Graphiti-like service deployment is justified.
7. **Cross-user collaboration test:** Consented users, blinded same-task adjudication, reciprocal opt-in, minimum cohorts, and measured outcomes. Falsifies collaboration feature if privacy controls erase utility or re-identification attacks recover people.
8. **OTel backend test:** Repeat SDK/Collector round trip against the production backend, including whole-trace drop and schema evolution. Falsifies telemetry-as-loss-detected unless an out-of-band expected-trace manifest catches missing traces.

## Architecture Consequences

- Keep one governed PostgreSQL/Aurora evidence and proposal authority for P0.
- Keep ATIF and OTel/OpenInference as projections with loss receipts, not as evidence stores.
- Keep advanced memory, graph, skill-learning, reranking, and embedding systems as isolated experimental arms.
- Keep exact/structured/lexical retrieval and sparse task-level general embeddings before custom models.
- Keep every derived artifact rebuildable, scoped by source intersection, and invalidated by current deletion/auth/policy epochs.
- Keep proposal, release, influence, evaluation, and destination-rendering records distinct.
- Add no production graph, vector, analytics, memory, or observability authority until a preregistered failure names the missing capability.

## Risks Identified

- **High:** Selector metrics become employee skill or productivity labels.
- **High:** Memory/skill artifacts influence future traces and then self-corroborate.
- **High:** A second database or platform creates stale deletion and cross-scope leakage paths.
- **Medium-high:** Public corpora overfit the research agenda toward available coding/NL2SQL traces and away from enterprise work diversity.
- **Medium:** Aurora-first becomes unfalsifiable and delays a needed one-database replacement.
- **Medium:** Local model/runtime pilots overstate independence when repeated deterministic calls are treated like samples.
- **Medium:** Exact/structured success underweights semantic cases that need human-labeled task similarity.

## Recommendations

1. **P0:** Maintain a claims registry beside each feature: deterministic, statistical, causal, hypothesis, or unsafe. Refuse UI copy that upgrades the claim class.
2. **P0:** Add reversal thresholds for Aurora, general embeddings, graph service, sidecar search, and model fine-tuning before the next implementation phase.
3. **P0:** Require random audit strata in every signal-selected review queue.
4. **P1:** Build a small enterprise adjudication study for task similarity, friction type, environmental blocker, and verified outcome before cross-user features.
5. **P1:** Treat all memories and skills as interventions with exposure/control/influence receipts, not content objects.
6. **P1:** Preserve negative results as release blockers, especially Defog P0 protocol failure and the no-memory scoring artifact.
7. **P2:** Evaluate domain-adapted embeddings only on hard slices where exact/structured/general hybrid demonstrably fails.

## New Ideas and Extensions

- **Bias ledger per artifact:** Attach fields for `source_selection_bias`, `label_source`, `influence_exposure`, `future_information_used`, and `claim_class` to every result/release.
- **Architecture reversal board:** A live table of "what would make us leave Aurora/add graph/train embedding" with current evidence and missing evidence.
- **Counter-label dashboard:** Show why a trace was *not* labeled as skill gap, cause, memory-worthy, or collaboration-worthy.
- **Negative-control gallery:** Curate examples where length beats signals, no-memory wins by abstention, latest-only leaks same-basename context, and hybrid RRF loses latency.
- **Influence quarantine:** Any trace touched by a released memory/skill/retrieval model is automatically excluded from independent validation unless the analysis explicitly models exposure.

## Assumptions Ledger

- Internal authorized users may inspect full PII/classified content within scope; this analysis assumes credentials remain excluded from ordinary capture.
- The current several-hundred-GB scale assumption is accurate enough that capacity alone does not justify another database.
- Existing project documents are treated as primary project evidence; many limitations are owner-acknowledged, not new discoveries.
- Public traces are useful for mechanics and parser coverage but not a stand-in for an enterprise population.
- "User benefit" means verified task/outcome improvement, not just better retrieval score or shorter trace.
- Authorization, deletion, provenance, and temporal correctness are core substrate, not optional governance wrappers.

## Questions for Project Owner

1. What is the first enterprise cohort where prospective consent and outcome labels are realistically obtainable?
2. Which user-facing SLO would justify replacing Aurora with one managed extensible PostgreSQL service?
3. What minimum reviewer agreement is required before a task-family or skill-support label can influence recommendations?
4. Which cross-user outputs are categorically banned even with opt-in?
5. Which memory destinations are allowed to receive rendered artifacts, and how will external deletion/withdrawal be communicated?
6. What cost/latency budget should cap embedding and judge work per trace?
7. Who has authority to promote a memory, eval, or skill when evidence is strong but social risk is high?

## Points of Uncertainty

- The true enterprise trace distribution may differ materially from public coding and NL2SQL corpora.
- Aurora selective-RLS/vector behavior under concurrent production load remains untested.
- Human label reliability for "same work," "productive exploration," and "skill support opportunity" is unknown.
- General embedding performance on company jargon and exact identifiers may be better or worse than CodeTraceBench suggests.
- The corrected v2 memory replication primitives may remove several pilot confounds, but no corrected model result exists yet.
- The best "smallest architecture" may change after object-tier and failover tests.

## Agreements and Tensions with Other Perspectives

- **Agreement with K2 Scientific:** Every component should be treated as a falsifiable claim; L2 adds that preregistered negative results must be protected from narrative override.
- **Agreement with A1 Deductive:** Claim-class invariants are mandatory: retrieval does not imply identity, association does not imply cause, and proposal does not imply release.
- **Agreement with F1 Causal:** Memory, skill, prompt, model, and routing benefit require exposure/control and independent outcome; L2 emphasizes that automation will otherwise manufacture self-confirming evidence.
- **Agreement with B9 Simplicity/MDL:** The smallest architecture is currently one governed PostgreSQL authority plus projections. L2 disagrees only if simplicity becomes unfalsifiable status-quo bias.
- **Tension with F7 Systems Thinking:** F7 may see many interacting components as necessary leverage points; L2 treats each added loop as a bias amplifier unless influence and deletion are first-class.
- **Tension with G6 Multi-Criteria:** Decision matrices can launder subjective weights. L2 asks for reversal evidence, not just weighted preference.
- **Agreement with H2 Adversarial Review:** The most dangerous failures are confident organizational conclusions, cross-scope contamination, and circular training data. L2 frames these as bias traps as well as attacks.
- **Agreement with I4 Perspective-Taking:** Contestability and non-retaliation are not ethics decoration; they are measurement controls against false labels.

## Confidence

Overall confidence: **0.86**. Confidence is high that current evidence supports an Aurora-first, proposal-only, evidence-linked product and does not support automatic memory, skill-gap inference, collaborator matching, root-cause automation, or custom embeddings. Confidence is lower on the ultimate storage and embedding decisions because production Aurora operations, human enterprise labels, and corrected v2 memory/model results remain unrun. The main update that would lower this analysis is a frozen enterprise benchmark where Aurora/exact/structured/general-hybrid fails under equal authority/deletion controls and an advanced component produces durable, audited outcome lift.
