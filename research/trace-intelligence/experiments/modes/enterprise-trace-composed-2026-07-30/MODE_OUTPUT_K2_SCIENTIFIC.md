# K2 Scientific Reasoning Analysis

## Thesis

Frankengate's trace-intelligence program is scientifically viable if it treats every proposed mechanism as a falsifiable claim about a named construct, unit, label source, control condition, and deployment scope. The current evidence supports an internal governed evidence-and-proposal product: personal history, exact/structured/lexical retrieval, deterministic review selectors, projection loss receipts, local RLS mechanics, and cited eval/memory/procedure proposal workflows. It does not yet support automatic memory, root-cause automation, employee skill inference, named collaborator matching, causal intervention benefit, custom embeddings, or leaving Aurora. The next program should be a staged empirical ladder, not an everything-stack: first prove representation and authority, then labels, then candidate generation, then controlled intervention effects, while treating repeated deterministic model calls as repeatability checks rather than independent samples.

## Top Findings

1. **§F1 [Kernel Candidate]: The load-bearing scientific invariant is claim-class separation, not framework coverage.**
   - **Evidence:** `research/trace-intelligence/configs/experiments/enterprise-question-composed-factorial-v3-2026.json` says public trace mechanism validation is not enterprise validity, retrieval similarity is not identity, prediction is not causation, model judgment is not a human or executable outcome, repeat invocations are not independent samples, and null results are publishable. `research/trace-intelligence/experiments/summaries/frankengate-combined-evidence-matrix-2026-07-30.md` reports partial mechanics passes but explicitly rejects root-cause automation, employee skill inference, automatic memory writes, collaborator matching, and embedding fine-tuning.
   - **Reasoning chain:** K2 asks what each component predicts and how it can be wrong. ATIF, OTel, Signals, AgentRx, AgentEvals, Phoenix/Opik/Langfuse, Graphiti, LangMem, Dreams, ReasoningBank, Hermes, CASS-style tools, dense retrieval, and NL2SQL replay do not answer the same construct. Some measure representation fidelity, some candidate recall, some review precision, some intervention utility, and some only source availability. A system that reports them as one "insight" fabricates construct validity.
   - **Deployment-calibrated severity:** High. In an internal enterprise deployment, authorized users may see scoped sensitive content, but unsupported claim upgrades can still drive bad product decisions and socially unsafe team/admin conclusions.
   - **Confidence:** 0.92. Multiple independent project artifacts repeat this claim boundary and several experiments already show metric-to-claim failures.
   - **So what:** Add a mandatory `claim_class` and `construct` to every experiment result, API response, dashboard card, proposal, and release: deterministic evidence, statistical selector, hypothesis, causal intervention result, proposal, refused, or unknown.

2. **§F2 [Kernel Candidate]: The independent unit is the task/query/source cluster, not the model invocation, turn, or repeated run.**
   - **Evidence:** `longitudinal-memory-corrected-replication-v2-2026.json` defines the experimental unit as one pre-cutoff online state query, marks repeat invocations as non-independent, pairs interventions on the same query, uses source-family fixed strata, and uses project-cluster bootstrap. `longitudinal-memory-local-model-replication-2026-07-30.md` reports 17 units and 425 attempts but states the five deterministic invocations are repeatability checks, not five independent samples. `tests/test_composed_system_factorial_v3.py` verifies `repeats_are_precision_only`, and `composed_system_factorial_v3.py` collapses repeats inside unit-by-arm cells before estimating effects.
   - **Reasoning chain:** Model calls share source traces, prompts, runtime, task, evaluator, and often deterministic decoding. Treating them as independent samples inflates precision, hides source concentration, and can turn a 17-unit memory pilot into a fake 425-observation study. The same issue applies to trace turns, tool calls, and multiple proposed assertions derived from one episode.
   - **Deployment-calibrated severity:** High for scientific and product decisions; medium for pure engineering conformance.
   - **Confidence:** 0.95. The corrected configs and tests directly encode the rule.
   - **So what:** Report `independent_unit_n`, source-family count, project/task-family clusters, repeat count, and cluster-level intervals beside every metric. Do not run significance tests over invocations unless the estimand is explicitly invocation reliability.

3. **§F3 [Kernel Candidate]: Projection fidelity is a prerequisite experiment, not evidence of memory, skill, or root-cause truth.**
   - **Evidence:** `canonical-projection-e0-conformance-2026-07-30.md` shows ATIF accounted for 48 source events but retained 0/48 canonical event IDs and 0/34 parent edges in the enterprise stress corpus, while OpenInference/OTel retained 48/48 IDs and 34/34 parent edges after deterministic reimport but redacted/normalized/unsupported many fields. `otel-collector-roundtrip-e0-2026-07-30.md` shows the SDK/Collector/file-export path retained all projected span identities and links, yet a Collector-side drop control proved downstream receipts cannot detect a wholly missing trace without an external source/export manifest.
   - **Reasoning chain:** A lossy projection can be a valid arm for operations or interchange only after its losses are measured. It cannot become the source truth for another component because missing authorization decisions, branches, proposal/execution distinctions, or environment state can invert the downstream conclusion.
   - **Deployment-calibrated severity:** High. Projection loss can create false audit, RCA, eval, memory, or skill claims even when no unauthorized user sees data.
   - **Confidence:** 0.90. The E0 fixtures directly test projection behavior and source documents describe the gaps.
   - **So what:** Keep one canonical governed event DAG as the experimental substrate. ATIF, OTel/OpenInference, AgentEvals, AgentRx, OCEL, and RL records are projections with loss receipts and cannot be chained as canonical inputs while the DAG exists.

4. **§F4 [Owner-Acknowledged Limitation / Kernel Candidate]: Public and synthetic corpora are good mechanism fixtures but weak external-validity evidence.**
   - **Evidence:** `longitudinal-memory-cohort-expansion-2026-07-30.md` passes smaller count gates with 17 online queries, 10 changed cases, and 5 exact cross-session transitions, but fails confirmatory diversity at two source families versus three required and three exact-transition project contexts versus five required. `public-native-history-fidelity-2026-07-30.md` finds mirrored, scrubbed, flattened, merged, and incomplete histories. `wisp-governed-postgres-benchmark-2026-07-30.md` is a single public contributor/local PostgreSQL mechanics result. `codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md` uses silver task labels and metadata hard negatives, not blinded enterprise labels.
   - **Reasoning chain:** Source availability and parser fidelity are not population inference. Public traces are selected by publication, redaction, mirror practices, benchmark curation, and harness-specific logging. A mechanism can pass on these sources and still fail on internal jargon, policy, tools, team structure, or delayed outcomes.
   - **Deployment-calibrated severity:** Medium-high. The internal deployment lowers public-disclosure risk, but false generalization into team/admin intelligence is still harmful.
   - **Confidence:** 0.89. The limitation is repeatedly owner-documented and empirically visible in source concentration.
   - **So what:** Use public data for representation, leakage, parser, and negative-control work. Require a consented internal cohort with adjudicated labels before cross-user similarity, skill support, collaboration, or enterprise-transfer claims.

5. **§F5 [Hypothesis with Strong Negative Result]: Dense retrieval is a useful candidate generator, but custom embeddings and external vector/search stores have not earned promotion.**
   - **Evidence:** `codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md` finds structured+dense at 0.818 Recall@20 versus 0.732 exact-only on silver labels, but warns the result is not PostgreSQL/RLS/human-label proof. `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` then loads the same 145 documents and 1,024-dimensional vectors into local forced-RLS PostgreSQL: exact pgvector reaches 0.667 Recall@20 at 3.017 ms p50, while the tested FTS/trigram/vector RRF reaches only 0.672 at 256.843 ms p50. `domain-adaptive-embeddings-and-secure-rag.md` requires governed judgments, hard negatives, deletion tests, and baseline comparison before adaptation.
   - **Reasoning chain:** The mechanism claim is not "vectors help." It is "a specific retrieval lane improves human-labeled authorized retrieval enough to justify cost, latency, deletion, and lifecycle burden." Current data supports keeping a bounded general dense lane under authority; it falsifies the tested trigram-heavy hybrid for this workload and does not justify a custom model.
   - **Deployment-calibrated severity:** Medium. Premature embeddings mainly add cost and stale-index risk now; the risk becomes high if distance is used as identity, skill, or collaboration evidence.
   - **Confidence:** 0.86 for "no custom embedding now"; 0.70 for the eventual best retrieval stack because internal labels and Aurora operations remain unrun.
   - **So what:** Freeze exact/structured/FTS/general-dense/reranker baselines before any adaptation. Promote an enterprise embedding only on a rights-cleared hard slice with at least +0.05 absolute Recall@20, no exact-ID regression, no RLS/deletion regression, and held-out private terminology transfer.

6. **§F6 [Kernel Candidate]: Memory, Dreams, Graphiti, LangMem, MemInsight, Memory Palace, and `MEMORY.md` must be tested as separate stages: retrieval, temporal truth, proposal support, release safety, influence, and utility.**
   - **Evidence:** `longitudinal-memory-local-model-replication-2026-07-30.md` reports identical aggregate results for evidence-bearing memory arms, a `no_memory` abstention artifact, visible arm labels, a non-dreaming dream arm, incomplete bitemporality, latest-only context retention, unattested runtime/source state, and deterministic repeats. `longitudinal-memory-corrected-replication-v2-2026.json` adds blinding, query-independent Dream release, credential gates, future-evidence exclusion, whole-item budgets, native-tool-only output, paired contrasts, and hard failure gates. `trace-commons-memory-h5-postgres-2026-07-30.md` passes 26 forced-RLS/release/exposure assertions, while `trace-commons-memory-h5-concurrency-postgres-2026-07-30.md` finds exposure/withdrawal atomicity, REPEATABLE READ revocation, governance writer, provenance deletion, and lifecycle-event coupling gaps.
   - **Reasoning chain:** A memory system can preserve revisions yet fail to improve later work; it can generate plausible candidates yet fail entailment; it can improve one metric while causing stale or cross-scope harm. Conflating these stages is the classic self-confirming memory loop.
   - **Deployment-calibrated severity:** High. Memory artifacts influence future traces and can later appear to validate themselves.
   - **Confidence:** 0.91 that automatic memory is unsupported; 0.73 that proposal-only memory will become useful after corrected trials.
   - **So what:** Run the corrected v2 memory experiment before any live memory promotion. Keep Dreams/LangMem/Graphiti-like extraction as untrusted proposal arms; render `MEMORY.md` only from reviewed releases with influence quarantine and deletion closure.

7. **§F7 [Hypothesis / Best Causal Testbed]: NL2SQL is the strongest first skill-learning domain, but the current evidence is mechanics and protocol repair, not skill benefit.**
   - **Evidence:** `defog-governed-sql-replay-conformance-2026-07-30.md` semantically matched 95 executable tasks through the verifier/security boundary but states this is not a model factorial. `defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md` completed 12 episodes with zero unauthorized observations, but all arms passed the same 2/4 tasks and protocol failure was 25%, 50%, and 25%, failing the preregistered under-10% gate. `nl2sql-capability-isolation-component-checkpoint-2026-07-30.md` passes 61/61 component tests plus one Linux/runc and PostgreSQL role slice, but P1 remains blocked pending final minimal image, per-episode identities, OS peer credentials, signed receipts, crash recovery, and the full 27-gate proof.
   - **Reasoning chain:** NL2SQL has better labels than general coding: questions, schemas, SQL attempts, observations, terminal submissions, policy checks, and executable outcomes. That makes it scientifically attractive, not production-ready. The visible P0 null/protocol failure should block hidden effect screens until the protocol is repaired arm-independently.
   - **Deployment-calibrated severity:** Medium-high. Research investment is justified; shipping a skill flywheel would create circular and unsafe claims.
   - **Confidence:** 0.84. The domain is strong, but the effect is currently untested.
   - **So what:** Rerun P0 after protocol repair under new hashes. Then compare no artifact, length/vocabulary-matched placebo, expert seed, and evidence-mined procedure on family-disjoint tasks with sealed evaluator/broker isolation.

8. **§F8 [Kernel Candidate / Negative Result]: Person-level skill, productivity, and collaborator claims currently lack valid labels and remain socially unsafe even inside authorized scope.**
   - **Evidence:** `trace-intelligence-all-together-system-and-experiment-ladder.md` classifies "who is productive, loyal, competent, or likely to leave" as refused and says skill/collaboration questions require prospective evidence, consent, minimum cohorts, and anti-differencing tests. `frankengate-combined-evidence-matrix-2026-07-30.md` marks missing skills and collaborator matching as not supported. `trace-intelligence-enterprise-question-composition-audit.md` states Signals plus embeddings cannot distinguish skill from permission, tool, model, docs, incident, quota, environment, or exploration.
   - **Reasoning chain:** A trace is a task/session artifact under changing tools and policies, not a direct measurement of a person's latent capability or social usefulness. Similarity and repeated friction can generate artifact proposals; they do not establish identity, competence, intent, or collaboration value.
   - **Deployment-calibrated severity:** High to critical for team/admin surfaces. Authorized visibility does not make weak personnel inference scientifically valid or socially safe.
   - **Confidence:** 0.93.
   - **So what:** Ban employee skill-gap, productivity, loyalty, and named collaborator conclusions from trace-intelligence outputs. Future experiments may test private support opportunities or reciprocal opt-in artifact introductions, not people rankings.

## Standalone Concept Assessment

| Concept or family | Enterprise question it can test | Required evidence and labels | Current answer class |
|---|---|---|---|
| ATIF | Can selected task/eval trajectories be exported portably? | Field-loss receipts, source hashes, unsupported-field manifest, reimport diff | Deterministic projection with known loss; not canonical authority. |
| OpenTelemetry/OpenInference | What operational topology, timing, span links, and tool lifecycle occurred? | Expected source/export manifest, backend round trip, content allowlist, loss receipt | Deterministic operational projection; not replay, memory, or authorization proof. |
| AgentRx | Which invariant violations nominate candidate failure points? | Declarative invariant set, temporal holdout, human decisive-step labels, ablations | Hypothesis generator only. |
| Signals | Which traces deserve review for friction/recovery? | Random audit stratum, length/stage baselines, human informative-case labels | Statistical selector; not cause, skill, or productivity. |
| AgentEvals | Which stored traces can become regression/eval proposals? | Assertion semantics, known mutants, changed-system replay, scope-safe fixtures | Retrospective audit/proposal; not changed-system proof. |
| Phoenix / Opik / Langfuse | How should datasets, annotations, evaluators, experiments, and releases be governed? | One authoritative native lifecycle, evaluator revisions, deletion lineage | Lifecycle concepts, not production authorities. |
| OpenRCA | Which multimodal incident hypotheses fit traces/logs/metrics/topology? | Synchronized modalities, alternatives, negative controls, intervention evidence | RCA hypothesis; causal only after intervention/replay. |
| Graphiti | Can temporal facts/entities/contradictions improve evidence retrieval? | Entity namespace, valid/system time, scope edges, deletion, relational baseline | Ephemeral ablation; relational subset first. |
| LangMem | Can memory candidates be extracted with useful schema discipline? | Evidence citations, entailment labels, scope, review, rollback, deletion lineage | Proposal generator only. |
| MemInsight | Can typed entity/task/outcome attributes improve retrieval or review? | Ontology, sensitive-attribute policy, entity-resolution tests, calibration | Schema inspiration; not independent inference authority. |
| Memory Palace / MemPalace | Can verbatim/bitemporal evidence preserve contextual state? | Revision retention, context identity, same-name/different-project negatives | Representation mechanism; utility unproven. |
| Temporal evidence oracle | What was known and valid at cutoff? | Valid-time, known-time, interval gaps, conflict handling, lineage exclusion | Kernel deterministic mechanism. |
| `MEMORY.md` | What released memory should be rendered to a harness? | Reviewed release, citations, expiry, withdrawal, deletion communication | Destination artifact, never source of truth. |
| Cloud dreaming / Dreams | Can query-independent background synthesis propose useful memory/evals? | Pre-cutoff input release, independent verification, partial-output quarantine, exposure controls | Experimental proposal arm; no automatic writes. |
| ReasoningBank | Can success/failure contrast produce reusable procedural lessons? | Verified outcomes, family-disjoint holdouts, no-skill/placebo controls, influence lineage | Candidate mechanism; no Frankengate effect yet. |
| Hermes / GEPA / Trace2Skill / SkillOpt | Can bounded skill candidates improve future tasks? | Frozen splits, hidden tests, mutation proof, verifier, rollback, human approval | Research arms; direct live mutation rejected. |
| Jeopard-style skill learning | Which concrete system/protocol is meant? | Repository/source pin and operational definition | Unresolved; do not build or attribute results. |
| RL environment histories | Can replay or reward support policy/skill learning? | Reset/action/observation/state/reward/termination/resource manifests | Needs environment attachment; flat traces insufficient. |
| CASS / Doodlestein/CM / claude-history / Prompt-Scope | Can personal/local exact and fuzzy history UX help users inspect work? | Import receipts, local rights, parser fidelity, deletion/export semantics | UX/import concepts, not enterprise authority. |
| Frankensearch | Can a sidecar improve authorized retrieval enough to justify another stateful path? | ACL-before-candidate, tombstones, stale-index tests, license/SBOM, bakeoff | Default-off experiment only. |
| Aurora PostgreSQL + JSONB / FTS / pgvector | Can one authority answer history, search, proposals, and experiments? | Production workload, RLS oracle, deletion, failover, concurrency, recall/latency | Current smallest architecture; local mechanics only so far. |
| VectorChord / pg_textsearch / pgContext / Turbovec / Turbopuffer | Can another engine beat Aurora/native Postgres under equal authority? | Same authorized corpus, same deletion/RLS, p95/p99/cost/ops comparison | Reversal candidates after a named failure, not launch dependencies. |
| General embeddings | Can semantic candidates improve retrieval after exact/structured channels? | Human positives/hard negatives, exact-ID protection, RLS/deletion tests | Conditional candidate lane. |
| Enterprise-adapted embeddings | Can an adapted retriever fix a frozen hard slice? | Governed labels, train/test by source/team/time, memorization/deletion/rollback tests | Premature. |
| Agentic coding/research traces | Can tool-call-complete histories test mechanics and proposal mining? | Rights, task segmentation, outcome labels, tool fidelity | Strong mechanics substrate, weak population inference. |
| NL2SQL complete tool traces | Can procedure/skill interventions be causally tested? | DB state, schema/tool calls, gold/evaluator separation, sealed families | Best first causal domain after P0 repair. |

## Composition and Non-Composition Matrix

| Combination | Scientific composition | Failure mode | Required test |
|---|---|---|---|
| Canonical DAG + ATIF + OTel/OpenInference | DAG is source; projections carry loss receipts and role-specific metrics | Projection loss becomes source truth | Source/canonical/projection/reimport diff over branches, tools, auth, timing, environment, and loss receipts. |
| Signals + AgentRx + AgentEvals | Signals select, invariants hypothesize, evals audit/replay | Selector or invariant violation becomes cause | Random audit, decisive-step labels, invariant-only/judge-only/combined ablations, changed-system replay. |
| Phoenix/Opik/Langfuse concepts + native lifecycle | One release/evaluator/dataset model in Aurora | Duplicate dataset/delete/eval authorities | Native lifecycle conformance and deletion closure; no separate product as authority. |
| Graphiti + temporal oracle + LangMem | Extracted facts/memories are scoped, bitemporal, cited candidates | Entity merge/proximity/latest-wins bypasses scope or contradiction | Same-name negatives, cross-scope traversal, interval-censored gap, relational-vs-graph ablation. |
| Dreams + `MEMORY.md` | Dream emits pre-cutoff proposals; reviewed release renders destination | Query-influenced dream or silent file mutation self-validates | Query-independent release, independent verification, influence quarantine, memory-on/off utility. |
| ReasoningBank/Hermes/SkillOpt + NL2SQL | Candidate procedures tested on sealed family-disjoint tasks | Generator sees hidden/gold outcomes or judges itself | No-skill/placebo/expert/evidence-mined arms, broker/evaluator isolation, paired family effects. |
| CASS/Prompt-Scope/Frankensearch + enterprise search | UX/query ideas run behind current authority | Local/shared index becomes second evidence plane | Import rights, credential transform, tombstone propagation, current-authority oracle. |
| General embeddings + structured retrieval | Dense adds candidates after exact and structured features | Similarity becomes identity, skill, or collaboration | Human same-task labels, hard negatives, exact-ID regression guard. |
| Enterprise embeddings + feedback | Reviewed labels and influence-separated holdouts train a bounded retriever | Clicks, generated memories, or success traces become unreviewed positives | Frozen hard slice, train/test by source/time/user/team, memorization and deletion tests. |
| RL histories + canonical traces | Environment/reward attachments are first-class | Chat or ATIF transcript treated as resettable state | Reset/resource/action/observation/reward divergence tests. |
| Full everything factorial | Useful only after block validation and power planning | Underpowered interactions and uninterpretable double-counting | Staged factorials over few mechanisms at a time, with interaction estimands. |

## Enterprise Questions Answered and Not Answered

| Question | Current K2 answer | Evidence status |
|---|---|---|
| Show a user their authorized history | Deterministically answerable after production authority/deletion/failover gates | Local Wisp/PostgreSQL mechanics pass; Aurora ops untested. |
| Which attempts deserve review? | Statistical selector/hypothesis | Signals and structural features can select; need random audit and labels. |
| Where did repeated friction precede success? | Candidate episode, not cause | Needs task identity, outcome labels, environment/permission controls, and replay/intervention for causality. |
| Which traces should become evals? | Proposal/audit | Mutation/assertion mechanics exist; changed-system replay still required. |
| What should become memory? | Cited proposal only | Temporal/RLS mechanics pass partially; utility and corrected model results absent. |
| Which prior work is similar? | Candidate retrieval | Structured+dense promising on silver labels; human task labels and privacy gates missing. |
| Which prompt/skill/tool/memory/model helps? | Prospective causal question | Requires exposure/control, independent outcomes, influence lineage, and rollback. |
| What skill is missing for a person/team? | Not currently answerable as a trait | Needs capability ontology, alternatives, labels, and prospective benefit; person-level trait claims refused. |
| Who should collaborate? | Not answerable from similarity | Requires reciprocal opt-in and measured outcome around an artifact. |
| Should Frankengate train an embedding? | No current justification | Only after a frozen baseline failure and safety/utility gate. |
| Should Frankengate leave Aurora? | No current justification | Only after representative selective-RLS/retrieval/delete/failover workload failure after tuning. |
| Can admins see full scoped content? | Yes by deployment context, credentials excluded | This is an authorization policy fact, not permission for workforce inference. |

## Empirical Tests and Falsifiers

1. **E0 representation and authority gate.** Test source/canonical/projection round trips over branches, retries, fallbacks, tool proposal/authorization/execution/result/state-delta, deletion, classification, and replay. Falsifier: any silent loss of an expected node/edge/authority field or any derived path that can answer without the canonical receipt.

2. **E1 friction-selector labels.** On Wisp/share-codex/CodeTraceBench/NL2SQL episodes, compare cheap Signals, deterministic invariants, and AgentRx-style reasoners against random and length/stage-count baselines. Labels: informative trace, accidental friction, productive exploration, environment blocker, missing permission, tool/model/harness failure, and insufficient evidence. Falsifier: selectors do not beat random/length at a fixed review budget or reviewers cannot reliably label constructs.

3. **E2 same-work retrieval factorial.** Use exact, structured, FTS, generic dense, reranker, and bounded hybrid arms against blinded human task-family positives and hard negatives, split by source/project/time. Include unauthorized nearest neighbors and same-vocabulary/different-objective negatives. Falsifier for dense: exact/structured/FTS match or beat dense on target slices; falsifier for custom embeddings: general hybrid reaches target or adaptation regresses exact identifiers/RLS/deletion.

4. **E3 eval/diagnosis proposal test.** Generate AgentEvals-style exact/ordered/semantic/invariant proposals from Signals+AgentRx/OpenRCA hypotheses. Evaluate against known mutants and changed-system replay where feasible. Falsifier: high allowed-variation false positives, poor citation precision, or no changed-system bug catch.

5. **E4 corrected memory/Dream experiment.** Run the v2 protocol: latest snapshot, temporal ledger, temporal plus released Dream; paired on 17+ cutoff-safe queries but analyzed by source/project cluster. Add human entailment labels, conflict/stale/deletion harms, and later-task utility as secondary. Falsifier: no lift over temporal ledger, future/context leakage, harmful selection, review burden too high, or utility only in influenced traces.

6. **E5 NL2SQL procedure gauntlet.** After protocol repair and full isolation gates, compare no artifact, length/vocabulary placebo, expert seed, single-trace reflection, pooled success/failure procedure, and bounded search+release. Use family-disjoint tasks, identical model/tool/budget, sealed hidden outcomes, and paired exact tests. Falsifier: protocol failure above gate, zero paired lift, family regression, policy violation, or effect disappearing under placebo.

7. **E6 prospective skill-support pilot.** In a consented internal cohort, randomize no suggestion, generic tip, evidence-matched support, and unrelated placebo for task opportunities. Labels must separate skill, permission, docs, tool, model, incident, environment, and exploration. Falsifier: false-deficit rate high, user harm/unwanted inference, no objective later outcome lift, or low reviewer agreement.

8. **E7 reciprocal collaboration pilot.** Only after same-work retrieval passes: artifact-first anonymous pattern, no introduction, task-similarity-only opt-in, and similarity plus reciprocal need/availability. Falsifier: privacy controls remove utility, unwanted contact rises, or reidentification attacks recover people/classified projects.

9. **E8 Aurora and retrieval operations gauntlet.** Run representative concurrent ingest, history, exact/FTS/vector retrieval, deletion/revocation, re-embedding, aggregates, reader lag, failover, RDS Proxy, worker saturation, and inference isolation. Falsifier for Aurora-first: preregistered p95/p99, recall, deletion, failover, or cost SLO failure after bounded mitigations.

## Architecture Consequences

- Keep the canonical governed evidence DAG and proposal/release/evaluation/influence records in Aurora/PostgreSQL as the only production authority until E8 fails.
- Store typed authority, subject/team/project, purpose, classification, policy epoch, deletion epoch, valid time, known time, source revision, claim class, and influence exposure as first-class fields, not JSONB-only metadata.
- Treat ATIF, OTel/OpenInference, AgentEvals fixtures, `MEMORY.md`, graph extracts, search indexes, learner batches, and sidecars as rebuildable projections with loss receipts.
- Implement every insight as an experiment record with construct, unit, arm, control, labels, source-family, cluster key, model/runtime/index revisions, missingness, and falsifier.
- Build deterministic exact/structured/FTS retrieval first, add bounded general dense retrieval under current authority, and keep adaptation/sidecars behind frozen reversal gates.
- Keep memories, skills, dreams, evals, route/model/index changes, and prompt updates in a proposal/release/influence lifecycle with exposure controls and rollback.
- Design dashboards to show deterministic evidence and hypothesis/proposal queues before team/admin inference surfaces.

## Risks Identified

- **High:** Construct drift from selector/retrieval metrics into skill, cause, or productivity labels.
- **High:** Pseudoreplication from model invocations, turns, or multiple candidates derived from one episode.
- **High:** Future leakage and circular validation from memory/skill/retrieval releases influencing traces that later validate them.
- **High:** Projection loss converting proposals, denials, missing branches, or failed side effects into completed actions.
- **High:** Cross-scope side channels through counts, distances, snippets, caches, graph neighborhoods, and aggregate differencing.
- **Medium-high:** Public corpus survival and mirror bias masquerading as enterprise generality.
- **Medium-high:** Premature vector/search/graph frameworks duplicating authority and deletion without improving measured outcomes.
- **Medium:** Aurora-first could become unfalsifiable unless production operations gates are written and run.
- **Medium:** Over-redacting PII would damage authorized internal construct validity; under-stripping credentials is a hard boundary failure.

## Recommendations

1. **P0: Create a claims registry.** Every feature and experiment declares construct, claim class, unit, label source, controls, known confounders, falsifier, and owner. Reject UI/API copy that upgrades the claim.
2. **P0: Enforce independent-unit accounting.** Report task/query/source-cluster `n` separately from invocation, turn, proposal, and repeat counts.
3. **P0: Preserve negative results as gates.** The no-memory abstention artifact, latest-only/context confounds, CodeTraceBench gate miss, hybrid latency rejection, and Defog protocol failure should remain blockers, not footnotes.
4. **P1: Run E1 and E2 before team surfaces.** Human labels for friction and same-work retrieval are prerequisites for cross-user or team aggregation.
5. **P1: Finish corrected v2 memory and NL2SQL P0 before memory/skill products.** Proposal-only UX can proceed; automatic release cannot.
6. **P1: Build the Aurora operations gauntlet before sidecars.** Only a frozen equal-authority failure should trigger Frankensearch, Turbopuffer, VectorChord, pg_textsearch, pgContext, or another backend.
7. **P2: Delay enterprise embedding adaptation.** Train only after an authorized hard slice proves general baselines fail and the adapted model passes deletion/memorization/rollback tests.
8. **P2: Require prospective consent for support/collaboration studies.** Anonymous artifact-first workflows are the first admissible cross-user experiments.

## New Ideas and Extensions

- **Falsifier cards:** Every proposed mechanism gets a small card: "What would make us remove this?" surfaced beside the roadmap item.
- **Construct linting:** A CI-style checker for experiment summaries that flags forbidden wording such as "skill gap" when the metric is selector precision or retrieval recall.
- **Pseudoreplication receipt:** Automatic reporting of independent units, clusters, repeated invocations, candidates per source, and effective sample warnings.
- **Influence exclusion query:** A standard query that removes traces descended from a memory/skill/model/index release before validation.
- **Negative-control library:** Canonical episodes where failure is caused by permission, stale docs, tool outage, hidden schema, model route, environment drift, or deliberate exploration rather than skill.
- **Projection-loss scoreboard:** A per-format matrix for ATIF, OTel/OpenInference, AgentEvals, AgentRx, OCEL, and RLDS showing which constructs each can and cannot support.
- **Architecture reversal board:** A live decision table for Aurora, graph, sidecar search, custom embeddings, memory promotion, and skill release with current evidence and next falsifier.
- **Human-label calibration set:** Small blinded packs that measure reviewer agreement on same-work, friction, environment blocker, support opportunity, and memory entailment before model metrics are trusted.

## Assumptions Ledger

- The deployment is an internal enterprise tool; authorized users, teams, and admins may inspect full PII/classified content inside scope.
- Reusable credentials are excluded from the ordinary trace plane and from model/evaluator/index/replay/export boundaries.
- Existing project docs and summaries are treated as primary project evidence for this pane; many limitations are owner-acknowledged.
- Aurora/PostgreSQL is the starting authority, but not an article of faith; it must be falsifiable under representative workload.
- Public traces are mechanism fixtures, not employee or enterprise population samples.
- Human review capacity exists for early labels and proposal queues, but should be measured as a cost.
- A useful enterprise answer must be cited, contestable, scoped, and honest about whether it is deterministic, statistical, causal, or hypothesis-grade.

## Questions for Project Owner

1. What are the minimum independent-unit and source-family thresholds before any team/enterprise claim can leave exploratory status?
2. Which constructs are worth paying human label cost for first: same work, friction type, environment blocker, memory entailment, or support opportunity?
3. What reviewer agreement threshold blocks a feature from launch?
4. Which outcome is primary for "helped": task success, fewer turns, lower cost, latency, fewer corrections, user-rated usefulness, or downstream business result?
5. What production SLOs would falsify Aurora-first: p95/p99 latency, recall, deletion closure, failover recovery, cost, or connection headroom?
6. What cross-user outputs are categorically refused even if technically authorized and consented?
7. Who adjudicates when scientific utility conflicts with social risk in memory, skill, or collaboration experiments?
8. What is the maximum acceptable false-deficit rate for private skill-support suggestions?

## Points of Uncertainty

- The true enterprise trace distribution may differ materially from the public coding/NL2SQL corpora.
- Human label reliability for same-work, productive exploration, friction, cause, and support opportunity is unknown.
- Corrected v2 memory primitives are stronger than the pilot, but no corrected model or human result exists.
- Aurora selective-RLS/vector/FTS behavior under production concurrency and failover remains unmeasured.
- General embeddings may underperform internal jargon more than CodeTraceBench suggests, or exact/structured fields may dominate more than expected.
- The best external sidecar or PostgreSQL replacement could change quickly; this analysis uses project-recorded evidence and did not perform fresh vendor research.
- Prospective enterprise interventions may be limited by policy, consent, review capacity, or adoption even if scientifically desirable.

## Agreements and Tensions with Other Perspectives

- **Agreement with B9 Simplicity/MDL:** K2 agrees that the current smallest defensible production architecture is one governed authority plus projections and proposal workflows. K2's reason is experimental control: fewer authorities make units, labels, deletion, and intervention exposure measurable.
- **Agreement with G6 Multi-Criteria:** K2 agrees that Aurora-first and proposal-only score best now. K2 would make G6's reversal thresholds preregistered experiments rather than decision preferences.
- **Agreement with L2 Debiasing:** K2 shares L2's concern that mechanics success and public-corpus availability can be over-weighted. K2 adds the concrete sampling and unit-of-analysis controls.
- **Agreement with F1 Causal:** K2 expects F1 to reject memory/skill/prompt/model benefit claims without exposure/control and independent outcomes. K2 supplies the staged empirical ladder before those causal tests.
- **Agreement with A1 Deductive:** K2 expects A1 to formalize the invalid implications: retrieval is not identity, association is not cause, proposal is not release, projection is not authority.
- **Tension with F7 Systems Thinking:** F7 may want to model rich feedback loops early. K2 treats feedback loops as experimental hazards until influence lineage and holdouts are in place.
- **Tension with I4 Perspective-Taking:** I4 may prioritize trust and adoption by suppressing low-certainty signals. K2 allows low-certainty signals in private experiments if their construct, uncertainty, and disallowed interpretations are explicit.
- **Tension with H2 Adversarial Review:** H2 may veto some socially risky studies outright. K2 would permit only those that are consented, artifact-first, privacy-tested, and designed to falsify utility before product exposure.

## Confidence

Overall confidence: **0.88**.

Confidence is high that the current evidence supports a governed evidence/proposal kernel and does not support automatic memory, causal skill benefit, employee skill inference, collaborator matching, custom embeddings, or leaving Aurora. Confidence is lower on the eventual value of semantic retrieval, memory, and NL2SQL procedures because the decisive internal labels, corrected v2 memory results, repaired NL2SQL P0, and production Aurora gauntlet remain unrun. The fastest way to change this analysis is a preregistered, authority-complete benchmark where a non-minimal component beats the minimal baseline on human/executable outcomes while preserving RLS, deletion, provenance, latency, and influence controls.
