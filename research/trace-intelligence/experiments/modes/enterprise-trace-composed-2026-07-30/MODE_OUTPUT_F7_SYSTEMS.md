# F7 Systems Thinking Analysis

## Thesis

Frankengate trace intelligence is best modeled as a governed feedback-control system, not as a retrieval stack or memory product. The end-to-end loop is:

```text
capture -> canonicalization -> authority/deletion gate -> signals/retrieval
  -> diagnosis/proposal -> review/release -> exposure/intervention
  -> outcome/evaluation -> withdrawal/learning -> capture
```

The system is viable when every loop has a typed state, source lineage, current authority, deletion behavior, and influence record. It becomes unsafe when outputs flow back into future traces without being marked as interventions. The highest-leverage architecture is therefore one canonical governed evidence authority in Aurora/PostgreSQL, with ATIF, OpenTelemetry/OpenInference, AgentEvals, memories, skills, embeddings, graphs, and sidecars treated as projections or experimental arms until they prove incremental value under the same authority and deletion rules.

## Top Findings

1. **§F1 [Kernel Candidate]: The load-bearing system loop is the governed release cycle, not any one memory, graph, eval, trace, or vector framework.**
   - **Evidence:** The all-together design defines one flow from native/imported trace to canonical DAG, authority gate, deterministic/retrieval planes, independently versioned candidates, human-reviewed copy-on-write release, isolated replay/prospective intervention, outcome, and scoped aggregate release ([trace-intelligence-all-together-system-and-experiment-ladder.md](../../../../../docs/roadmap/research/trace-intelligence-all-together-system-and-experiment-ladder.md)). The memory composition matrix separates observed event, inferred candidate, reviewed release, harness projection, influenced trajectory, and independent held-out evaluation ([memory-skill-replay-evidence-composition-matrix-2026.md](../../../../../docs/roadmap/research/memory-skill-replay-evidence-composition-matrix-2026.md)). The deterministic `dream_release_pipeline_v2.py` enforces citations, authority intersection, independent verification, copy-on-write release, and deletion-aware visibility.
   - **Reasoning chain:** Systems fail at the interfaces between capture, proposal, release, and feedback. If a stochastic analyzer can write directly to `MEMORY.md`, a skill file, an eval suite, a route, or a model, the system loses the distinction between evidence and intervention. Conversely, if each output is a candidate/release with influence lineage, Graphiti, LangMem, Memory Palace, Dreams, ReasoningBank, Hermes-style skill learning, AgentEvals, and OpenRCA can compose as mechanisms over one state machine.
   - **Deployment-calibrated severity:** High. In an internal enterprise tool, authorized users may see full scoped content, but a wrong released artifact can influence work, contaminate later evidence, and spread across team scope.
   - **Confidence:** 0.90.
   - **So what:** Treat the release graph as the kernel. No automatic memory, eval, skill, route, model, or embedding promotion should ship before proposal, review, release, exposure, outcome, withdrawal, and deletion states are represented natively.

2. **§F2 [Kernel Candidate]: Capture and projection are delayed sensors; without expected-count manifests and loss receipts, every downstream loop can optimize against missing reality.**
   - **Evidence:** The canonical projection arm showed ATIF accounted for all 48 governed fixture events but retained 0/48 canonical event identities and 0/34 parent edges after reimport, while OTel/OpenInference retained 48/48 identities and 34/34 parent edges for the operational topology but redacted content/authority fields and reconstructed timestamps ([canonical-projection-e0-conformance-2026-07-30.md](../../summaries/canonical-projection-e0-conformance-2026-07-30.md)). The real OTel SDK/Collector/file-exporter round trip preserved projected spans, but a drop-control demonstrated that storage-to-canonical receipts cannot detect spans discarded before storage; a content-minimized expected manifest is required ([otel-collector-roundtrip-e0-2026-07-30.md](../../summaries/otel-collector-roundtrip-e0-2026-07-30.md)). The public-native-history audit distinguishes byte-native, scrubbed native-graph, record-preserving derivative, merged workflow, and flattened derivative sources ([public-native-history-fidelity-2026-07-30.md](../../summaries/public-native-history-fidelity-2026-07-30.md)).
   - **Reasoning chain:** Feedback systems need sensors with known blind spots. A missing branch, hidden tool denial, dropped parent edge, reconstructed timestamp, or flattened subagent path can later be interpreted as a skill gap, failed tool, successful procedure, or memory fact. Loss is tolerable only if quarantined or carried as machine-readable missingness.
   - **Deployment-calibrated severity:** High for diagnosis, eval, memory, and intervention loops; medium for content-minimized operations telemetry.
   - **Confidence:** 0.88.
   - **So what:** Canonical evidence must remain the source of truth. ATIF, OTel/OpenInference, AgentEvals, AgentRx, Phoenix/Opik/Langfuse datasets, Frankensearch indexes, and `MEMORY.md` outputs need source hashes, expected-count manifests, unsupported-field receipts, and "not canonical" status.

3. **§F3 [Kernel Candidate]: Authority, deletion, exposure, and withdrawal form a shared-state control loop with real concurrency hazards.**
   - **Evidence:** The H5 concurrency PostgreSQL gate passed mechanics but found five hard gaps: exposure can commit after withdrawal unless both operations share a lock; REPEATABLE READ preserves old epoch/membership/deletion visibility until transaction end; governance mutation needs a persistent narrow non-owner writer; provenance deletion needs tombstone/redaction policy; lifecycle event coupling is conventional rather than enforced ([trace-commons-memory-h5-concurrency-postgres-2026-07-30.md](../../summaries/trace-commons-memory-h5-concurrency-postgres-2026-07-30.md)). The all-together design requires RLS and side-channel equality over rows, IDs, counts, snippets, distances, cursors, object refs, caches, timing, and exports. The internal trace-fidelity audit likewise treats RLS and reveal authorization as backend obligations, not UI state ([internal-trace-fidelity-code-audit-2026.md](../../../../../docs/roadmap/research/internal-trace-fidelity-code-audit-2026.md)).
   - **Reasoning chain:** Deletion and revocation are not one-time events; they must propagate through search, vectors, facts, memories, evals, caches, object refs, telemetry, releases, and exports. If a long transaction, sidecar cache, vector index, or exposure row uses an old snapshot, the system can be locally correct and globally stale.
   - **Deployment-calibrated severity:** Critical for cross-scope access and deletion promises; high for memory/skill release correctness.
   - **Confidence:** 0.89.
   - **So what:** Use short current-authority transactions for request-time visibility, shared lifecycle locks/procedures for release/exposure/withdrawal, an explicit tombstone/redaction policy, and a permission oracle that covers every derived path before team or enterprise surfaces launch.

4. **§F4 [Hypothesis with strong negative evidence]: Memory, dreaming, and skill loops are reinforcing loops; without influence quarantine they will self-validate.**
   - **Evidence:** The first 425-call longitudinal local-model pilot produced valid calls but the four evidence-bearing arms had identical aggregate behavior; the "dream" arm did not dream, labels were visible, latest-only retained context, bitemporal semantics were incomplete, and runtime/source launch was not mechanically attested ([longitudinal-memory-local-model-replication-2026-07-30.md](../../summaries/longitudinal-memory-local-model-replication-2026-07-30.md)). The Trace Commons memory composition run retained evidence but had only three online retention queries; latest-only leaked across same-basename placebos in 3/6 while contextual leaked 0/6; comparative quality was not allowed ([trace-commons-memory-composition-2026-07-30.md](../../summaries/trace-commons-memory-composition-2026-07-30.md)). Corrected v2 preregistration now requires query-independent dream release, blinding, credential-only gates, whole-item budgets, and launch attestation ([longitudinal-memory-corrected-replication-v2-2026.json](../../../configs/experiments/longitudinal-memory-corrected-replication-v2-2026.json)).
   - **Reasoning chain:** Once a memory, procedure, retrieval rule, route, prompt, model, or embedding influences a later trace, that trace is no longer independent evidence for the thing that influenced it. Frequency of later repetition is not truth; success after exposure is not clean credit. The loop can amplify stale, overgeneral, or false content unless influence is a first-class state.
   - **Deployment-calibrated severity:** High. Same-scope PII retention is appropriate, but self-confirming memory/skill releases can mislead users and teams inside their authorized scope.
   - **Confidence:** 0.87.
   - **So what:** Add influence quarantine before memory or skill release. Descendant traces should be excluded from independent validation except in explicit exposure/control analyses. Dreams, LangMem, ReasoningBank, Hermes/Jeopard-style skill learning, and RL histories are proposal generators until randomized, replay, or held-out outcome loops prove utility.

5. **§F5 [Owner-Acknowledged Limitation]: Cheap signals and retrieval are balancing loops for review load, not diagnoses; over-weighting them creates selection feedback.**
   - **Evidence:** The combined evidence matrix states structural selection missed the +15-point gate, diagnosis did not beat simple reverse chronology, and memory utility/causal skill benefit remain unproven ([frankengate-combined-evidence-matrix-2026-07-30.md](../../summaries/frankengate-combined-evidence-matrix-2026-07-30.md)). The Defog smoke showed all arms solved the same 2/4 tasks and failed terminal-protocol gates at 25%-50% ([defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md](../../summaries/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md)). The progress ledger records owner-acknowledged limits: semantic similarity alone cannot establish identity, permission, causality, skill deficiency, or intent ([MODES_ANALYSIS_PROGRESS.md](MODES_ANALYSIS_PROGRESS.md)).
   - **Reasoning chain:** Signals such as rephrasing, stagnation, loops, tool failures, cost, and disengagement help route scarce review effort. If review queues feed labels, labels feed skills, and skills feed future review without random audit and sampling propensity, the system will learn the visibility pattern of its own detectors rather than the enterprise's actual failure modes.
   - **Deployment-calibrated severity:** Medium-high. The risk is less credential breach and more slow institutional drift toward false skill/support taxonomies.
   - **Confidence:** 0.86.
   - **So what:** Keep random audit strata, trace-length baselines, and propensity receipts in every review queue. Product copy should say "candidate for review" or "support hypothesis," not root cause, skill gap, or failure label.

6. **§F6 [Kernel Candidate]: A second persistent search, graph, observability, or memory authority is a reinforcing complexity loop unless a native gate fails first.**
   - **Evidence:** The minimal architecture review rejects ClickHouse, OpenSearch, Qdrant, ParadeDB, VectorChord, pgContext, Phoenix, Langfuse, Opik, graph databases, and separate vector databases for the current several-hundred-GB program, with Aurora/PostgreSQL as the only required authority and S3 only as conditional object storage ([log-trace-vector-database-and-reflective-learning-review.md](../../../../../docs/roadmap/research/log-trace-vector-database-and-reflective-learning-review.md)). Same-candidate PostgreSQL retrieval showed exact pgvector at 0.667 Recall@20 and 3.017 ms p50, while the tested FTS/trigram/vector hybrid reached only 0.672 Recall@20 at 256.843 ms p50 and was rejected ([codetracebench-e2-postgres-joint-retrieval-2026-07-30.md](../../summaries/codetracebench-e2-postgres-joint-retrieval-2026-07-30.md)). The Frankensearch assessment calls it an optional sidecar/research service requiring ACL-before-retrieval, tombstones, license review, and fallback ([frankensearch-assessment.md](../../../../../docs/roadmap/research/frankensearch-assessment.md)).
   - **Reasoning chain:** Each new store adds its own ingest lag, cache behavior, deletion convergence, backup/restore state, operator expertise, index revision, and side-channel surface. More systems can improve one query while degrading the global control loop's ability to know what is current and allowed.
   - **Deployment-calibrated severity:** High for production; low for content-free or same-scope experimental arms.
   - **Confidence:** 0.91 for "do not add now"; 0.70 for long-term Aurora sufficiency.
   - **So what:** Keep one fusion owner and one authority. VectorChord, pg_textsearch, pgContext, Turbovec, Turbopuffer, Frankensearch, Qdrant, and graph stores become candidates only after a preregistered Aurora/PostgreSQL failure under equal RLS, deletion, latency, and cost controls.

7. **§F7 [Kernel Testbed]: NL2SQL with complete tool calls is the smallest executable system for testing procedure learning, but the current loop remains blocked.**
   - **Evidence:** Defog governed replay matched all 95 PostgreSQL-executable tasks in conformance but proves the replay/verifier boundary, not model quality or causal skill benefit ([defog-governed-sql-replay-conformance-2026-07-30.md](../../summaries/defog-governed-sql-replay-conformance-2026-07-30.md)). The F0 mechanics smoke had valid authority and zero unauthorized observations, but no arm lift and protocol failure above gate. The capability-isolation checkpoint now passes 61/61 component tests plus one real Linux OCI boundary and one real PostgreSQL role/snapshot slice, yet P1 and hidden remain sealed pending a final minimal image, peer credentials, independent receipts, crash recovery, signed OTel, and the complete 27-gate proof ([nl2sql-capability-isolation-component-checkpoint-2026-07-30.md](../../summaries/nl2sql-capability-isolation-component-checkpoint-2026-07-30.md)).
   - **Reasoning chain:** NL2SQL supplies observable task inputs, schema/tool calls, policy decisions, SQL attempts, terminal submissions, and gold evaluation. That makes it a useful microcosm of capture, diagnosis, skill proposal, intervention, and evaluation. The same observability has already falsified premature benefit claims.
   - **Deployment-calibrated severity:** High if skill learning is productized before the protocol loop is repaired; medium as a research-only sealed benchmark.
   - **Confidence:** 0.84.
   - **So what:** Use NL2SQL as the first causal loop after P0 repair: no artifact, length-matched placebo, expert seed, and frozen trace-mined procedure on family-disjoint tasks. Do not generalize to enterprise skill recommendations until it shows held-out lift.

8. **§F8 [Social System Boundary]: Cross-user and enterprise learning must be artifact-first; person-first similarity is an unsafe reinforcing loop.**
   - **Evidence:** The enterprise composition audit classifies "who is doing the same work?" as anonymous reusable patterns plus reciprocal introduction, not named vector neighbors; it refuses employee skill/productivity claims from trace style, failure counts, or judges ([trace-intelligence-enterprise-question-composition-audit.md](../../../../../docs/roadmap/research/trace-intelligence-enterprise-question-composition-audit.md)). CodeTraceBench retrieval improved silver-label Recall@20 with structured+dense, but the summary explicitly says same benchmark work does not imply collaboration, skill, productivity, enterprise transfer, or causal utility ([codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md](../../summaries/codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md)). Public-history audits found abundant useful mechanics sources but not an independent enterprise panel ([public-local-coding-agent-history-corpus-audit.md](../../../../../docs/roadmap/research/public-local-coding-agent-history-corpus-audit.md)).
   - **Reasoning chain:** In a social system, outputs change behavior and incentives. A "similar work" UI can become a people finder; a "friction" aggregate can become performance surveillance; a skill-support card can become an employee label. The control target should be reusable artifacts, platform fixes, and private support, not people ranking.
   - **Deployment-calibrated severity:** Critical for team/admin surfaces; medium for personal-only candidate cards.
   - **Confidence:** 0.88.
   - **So what:** Cross-user loops should release minimized artifacts, evals, runbooks, aliases, or aggregate demand patterns. Revealing people requires reciprocal opt-in and privacy controls. Some desired questions remain refused even if every technical component works.

## Standalone Concept Assessment

| Concept | System role and interface | Evidence/labels required | F7 verdict |
|---|---|---|---|
| ATIF | Portable conversation/tool/eval projection from the canonical DAG | Source hashes, projection revision, unsupported-field/loss receipt | Use narrowly; never canonical authority. |
| OpenTelemetry/OpenInference | Operational topology, spans, timings, links, low-cardinality tool/model attributes | Expected export manifest, drop controls, backend round trip, content/authority allowlist | Use as telemetry projection; not evidence, authorization, memory, or replay authority. |
| AgentRx | Invariant and failure-hypothesis plane over canonical events | Declarative check inputs, human labels, alternatives, sandboxing | Hypothesis generator; not root-cause proof. |
| Signals | Cheap selector plane for review queues | Random audit, trace-length baseline, sampling propensity | Keep as balancing loop; never diagnosis or skill label. |
| AgentEvals | Stored-trace assertion and replay-fixture projection | Audit vs replay state, evaluator revision, mutants, allowed-variation negatives | Useful proposal mechanism; changed-system claims require replay. |
| Phoenix / Opik / Langfuse | Dataset, annotation, experiment, feedback lifecycle concepts | Native Frankengate tables for evaluator revisions, dataset releases, feedback targets | Borrow concepts; do not deploy as parallel authorities. |
| OpenRCA | Multimodal trace/log/metric/topology RCA hypothesis | Clocks, topology, modality ablations, alternative hypotheses | Hypothesis-only until intervention/counterfactual proof. |
| Graphiti | Temporal entity/fact/episode mechanism | Stable entity keys, valid/system time, contradiction/invalidation, scope tests | Implement relational subset first; graph backend only after relational failure. |
| LangMem | Typed memory create/update/delete workflow | Prompt/model pins, citations, no direct writes, rejection/rollback | Candidate extractor only. |
| MemInsight | Structured attributes over people/tasks/systems/outcomes | Ontology, entity-resolution, sensitive-attribute tests | Useful representation idea; not an enterprise truth engine. |
| Memory Palace / temporal evidence | Verbatim and contextual revision retention | Known-at/valid-at reconstruction, same-name/different-context negatives | Kernel for evidence fidelity. |
| `MEMORY.md` | Harness destination rendering | Release snapshot, citations, expiry, deletion/withdrawal semantics | Destination artifact, never source of truth. |
| Cloud dreaming | Query-independent background synthesis | Input release, generator/verifier separation, partial-output quarantine, held-out utility | Experimental proposal loop; no automatic activation. |
| ReasoningBank | Procedure candidates from success/failure contrast | Verified outcomes, family holdouts, no self-judge, influence records | Candidate mechanism; not product loop yet. |
| Hermes / Jeopard-style skill learning | Protected-write, snapshot, rollback, candidate-search ergonomics | Exact project/protocol definition, hidden tests, placebo/no-skill controls | Use release/replay patterns; do not live-edit skills. |
| RL environment histories | Reset/action/observation/termination/reward/replay attachments | Environment snapshot, resource state, reward basis, divergence record | Add attachments to canonical evidence; flat chat is insufficient. |
| CASS, Doodlestein/CM, claude-history, Prompt-Scope | Local/private history discovery, exact/fuzzy search, bookmarks, reflection UX | Import receipts, credential gates, user consent, no shared raw upload | Adopt UX/import concepts; not shared authority. |
| Frankensearch | Optional hybrid/progressive retrieval sidecar | ACL-before-candidate exposure, tombstones, stale-index tests, license/provenance review | Default-off bakeoff only. |
| Aurora PostgreSQL, JSONB, FTS/trigram, pgvector | One authoritative store plus in-database candidate retrieval | Typed authority columns, exact recall oracle, deletion/failover/concurrency tests | Current minimum architecture. |
| VectorChord, pg_textsearch, pgContext, Turbovec, Turbopuffer | Possible query/index/storage upgrades | Frozen workload failure under equal auth/delete/cost tests | Research/replacement candidates, not launch dependencies. |
| General embeddings | Task/attempt candidate generator | Human task labels, hard negatives, model/chunker/index manifest | Conditional dense lane after exact/structured. |
| Enterprise-adapted embeddings | Organization-specific retrieval improvement | Reviewed pairs/hard negatives, user/team/time split, +5 absolute Recall@20 or equivalent, no deletion/memorization regression | Premature. |
| Agentic coding/research traces | Mechanics, import fidelity, candidate eval/memory/procedure mining | Tool-call completeness, outcomes, task labels, rights | Good substrate for mechanisms; not workforce inference. |
| NL2SQL traces with complete tool calls | Executable procedure-learning and replay testbed | Capability isolation, sealed stages, exact authority, family-disjoint effects | Best first causal lab after protocol repair. |

## Composition and Non-Composition Matrix

| Combination | Composes at this interface | Main feedback hazard | Decision |
|---|---|---|---|
| Canonical DAG + ATIF + OTel/OpenInference | Projection adapters with loss receipts and expected manifests | Projection loss becomes canonical fact | Compose as generated views only. |
| Signals + exact/structured retrieval | Review queue with sampling propensity | Signal-selected examples train future detectors and erase quiet cohorts | Compose with random audit and baselines. |
| Signals + embeddings | Candidate clustering for human task review | Similarity becomes identity, skill, or collaboration | Compose only as triage. |
| AgentRx + OpenRCA + AgentEvals | Hypothesis -> eval proposal -> replay/audit registry | Invariant violation is reported as cause | Compose with alternatives and causal gate. |
| Phoenix + Opik + Langfuse | Dataset/eval lifecycle concepts in native tables | Three products own feedback/datasets/deletes | Do not deploy together or as authorities. |
| Graphiti + MemInsight + temporal facts | Relational fact/edge tables with valid/system time | Entity merge or graph traversal widens scope | Compose relationally first. |
| LangMem + Dreams + Memory Palace + `MEMORY.md` | Untrusted candidate -> verified release -> rendered destination | Automatic memory creates future confirming evidence | Compose only through release/influence lifecycle. |
| ReasoningBank + Hermes + NL2SQL | Frozen procedures tested in sealed family-disjoint tasks | Self-judged procedures or hidden leakage | Compose after P0 protocol repair. |
| RL histories + Agentic traces | Environment/evaluation/replay attachments on canonical events | Transcript mistaken for resettable environment | Compose with replay manifest and divergence records. |
| CASS/Prompt-Scope/claude-history + enterprise history | Local importers feeding governed canonicalization | Local index becomes shared evidence | Compose through credential-clean governed import. |
| Frankensearch + Aurora | Derived index with Aurora-owned envelopes and tombstones | Sidecar returns stale IDs/scores/snippets | Experimental sidecar only after oracle tests. |
| JSONB + typed authority columns | Sparse payload metadata under relational authority | Authority/time/outcome buried in JSONB | Compose with typed security fields. |
| General embeddings + FTS/structured | Optional dense candidate lane under current auth | Whole-trace vector erases distinctions | Compose if human-label lift survives. |
| Custom embeddings + feedback data | Governed training release and frozen holdout | Clicks/success/generated memory become circular labels | Do not build until hard-slice failure. |
| Cross-user similarity + team dashboard | Minimized artifact release, then opt-in introduction | People finder and surveillance | Do not build person-first flow. |

## Enterprise Questions Answered and Not Answered

| Enterprise question | Current answer class | Systems answer |
|---|---:|---|
| Show a user their authorized history, prompts, tool activity, and missingness | Deterministic if L0/L1 pass | Answerable by canonical events, current authority, deletion state, and explicit loss/capture status. |
| Which attempts deserve review? | Statistical selector / hypothesis | Answerable as signal-selected plus random-audit candidates, not failures or skill labels. |
| What repeated friction preceded success? | Hypothesis | Answerable as ordered association if task/outcome lineage exists; causal repair needs replay or exposure. |
| Which tasks are similar? | Hypothesis | Answerable as multi-view task candidates with human/adjudicated labels; vector distance is insufficient. |
| Who is doing related work? | Prospective/social | Only artifact-first, privacy-reviewed, reciprocal opt-in introductions. No named nearest-neighbor people finder. |
| What work are people doing? | Coverage-qualified aggregate | Only gateway-mediated, source-coverage-qualified task families. Not total work, effort, or motivation. |
| What cloud/domain capability might help? | Contestable support hypothesis | Requires ontology, alternatives, environment/permission controls, and prospective outcome. Never "employee X lacks skill" from trace style. |
| What should become an eval? | Proposal | Answerable as cited audit/replay candidate with assertion type and mutation coverage. |
| What should become memory or `MEMORY.md`? | Proposal/release | Answerable as cited, scoped, editable, expiring release candidate; no transcript dump or automatic live mutation. |
| Which prompt, retrieval rule, skill, memory, route, model, or embedding helps? | Causal/prospective | Not answered retrospectively. Requires exposure/control, independent outcomes, and harms/costs. |
| Should Frankengate leave Aurora? | Operations falsifier | No current evidence. Justified only by preregistered failure of auth/delete/latency/failover/cost after mitigations. |
| Should Frankengate train an embedding model? | Retrieval falsifier | No current evidence. Justified only by frozen hard-slice lift over exact/structured/general-hybrid with safety gates. |
| Who is productive, loyal, competent, disengaged, or likely to leave? | Refuse | Socially unsafe and not identifiable from intended evidence. |

## Empirical Tests and Falsifiers

1. **System-loop gauntlet:** Run capture -> canonicalization -> projection -> retrieval -> proposal -> release -> exposure -> withdrawal -> deletion over governed fixtures. Falsifier: any derivative remains visible or any state transition lacks source lineage/current authority.
2. **Sensor loss test:** Mutate traces by dropping roots, branches, tool results, policy denials, fallback attempts, state deltas, and timestamps before ATIF/OTel/AgentEvals projection. Falsifier: downstream consumers can claim completeness without a loss receipt.
3. **Authority concurrency test:** Repeat H5 schedules on the corrected lifecycle procedure and then Aurora/RDS Proxy: exposure vs withdrawal, epoch/membership/deletion during query/stream/object hydration, failover, reader lag, and stale cursor. Falsifier: any stale row, ID, count, distance, snippet, object ref, or active exposure escapes.
4. **Memory feedback test:** Corrected v2 memory replication with latest snapshot, temporal ledger, and temporal plus released dream. Falsifier: future evidence leaks, dream is query-influenced, labels are visible, whole-item budget fails, or memory does not improve verified outcome without stale/anchoring harm.
5. **Skill/procedure loop test:** Repaired NL2SQL P0, then family-disjoint no-skill, length-matched placebo, expert seed, and trace-mined procedure arms. Falsifier: protocol failure above gate, no paired lift, unauthorized observation, or hidden/evaluator leakage.
6. **Retrieval factorial:** Exact/structured/FTS/trigram/general-dense/rerank under identical current authority and deletion oracles. Falsifier for dense/custom: exact/structured/general hybrid already meets target; falsifier for Aurora-first: selective-scope recall/latency cannot meet SLO after bounded tuning.
7. **Cross-user social loop test:** Consented internal cohort with anonymous artifact-first matching, reciprocal opt-in, minimum cohort, complement suppression, and repeated-query attack. Falsifier: people/classified projects can be reconstructed or accepted utility disappears after privacy controls.
8. **Embedding adaptation gate:** Train only on reviewed, purpose-authorized positives/hard negatives split by user/team/time/source and influence exposure. Justify training only with preregistered material lift, for example +5 absolute Recall@20, and no deletion, memorization, identifier, subgroup, or latency regression.

## Architecture Consequences

- **Canonical state:** One governed event/evidence DAG in Aurora/PostgreSQL with typed identities, tool proposal/authorization/execution/observation/state-delta events, task/attempt lineage, source hashes, loss receipts, and content/object manifests.
- **Authority state:** Tenant, subject/team, audience, purpose, classification, consent/training eligibility, authorization epoch, policy revision, retention, deletion/tombstone, and source-use lineage on every source and derivative.
- **Temporal state:** Valid time, known/system time, projection watermark, deletion/auth/policy epoch, interval uncertainty, contradictions, corrections, and appeals.
- **Analysis planes:** Keep selection, retrieval, diagnosis/eval, memory/facts, and procedure/intervention as distinct records joined by evidence IDs, not collapsed into one "insight."
- **Release state:** Candidates, reviews, immutable releases, destination renders, exposures, influences, outcomes, withdrawals, rollbacks, and deletion closure.
- **Retrieval state:** Exact/structured/FTS/trigram/pgvector inside current authority first. Sidecars receive only authorized, credential-clean, rebuildable projections and return opaque IDs for recheck.
- **Operations state:** Analytics, embeddings, evals, memory extraction, exports, and sidecars degrade before gateway inference. Worker queues need age, retries, idempotency, stale-index, and deletion-convergence SLOs.
- **Not in the launch architecture:** Production Graphiti graph store, Phoenix/Opik/Langfuse authority, live LangMem store, automatic `MEMORY.md`/`SKILL.md` writes, custom embeddings, generator fine-tuning, external vector/search authority, named cross-user matching, or manager skill dashboards.

## Risks Identified

- Circular validation: released memories/skills/routes/embeddings create future evidence that appears to validate them.
- Delayed revocation: old transaction snapshots, stale indexes, caches, object refs, and exports outlive current policy.
- Sensor loss: projected traces hide branches, denials, missing tool results, or state deltas.
- Metric laundering: selectors, retrieval recall, and replay mechanics are narrated as diagnosis, skill, or benefit.
- Authority duplication: each extra database or product adds deletion, policy, backup, and incident state.
- Social feedback: team/admin views change incentives and can become surveillance even when raw content is hidden.
- Over-redaction/under-redaction: broad PII stripping harms evidence; credential leakage creates direct operational risk.
- Operational backpressure: embeddings, HNSW, broad analytics, and sidecars can interfere with inference and then create more traces/failures to analyze.

## Recommendations

1. Build the **release/influence/deletion kernel** before advanced intelligence: candidate, review, release, exposure, outcome, withdrawal, rollback, and descendant influence records.
2. Require **expected-count manifests and loss receipts** for every projection, import, dataset, export, and sidecar.
3. Treat all Signals, retrieval, AgentRx, OpenRCA, and judge outputs as **hypotheses with alternatives**, not labels.
4. Make **current-authority and deletion oracles** shared infrastructure for SQL, FTS, vector, graph, cache, memory, eval, export, telemetry, and object hydration.
5. Keep **Aurora/PostgreSQL first but falsifiable** with explicit reversal thresholds for selective-RLS recall/latency, failover, deletion closure, and analytics isolation.
6. Keep **general task-level embeddings conditional** and defer custom embeddings until a frozen hard-slice failure proves they are necessary.
7. Use **NL2SQL as the first causal procedure lab** only after terminal protocol and capability-isolation gates pass.
8. Launch **personal history and proposal queues first**; team/enterprise output should be artifact-first, aggregate, contestable, and opt-in for identity reveal.

## New Ideas and Extensions

- **Control-loop ledger:** Every feature declares its loop inputs, outputs, delays, feedback path, failure mode, and rollback.
- **Influence quarantine service:** A shared API that marks traces exposed to releases, memory, skills, prompts, routes, models, embedding/index revisions, evals, and search results.
- **Projection loss scoreboard:** A visible compatibility matrix for ATIF, OTel, AgentEvals, AgentRx, Frankensearch, Graphiti, and memory destinations showing retained identities, branches, auth, time, deletion, and missingness.
- **Revocation drill mode:** A deterministic internal drill that revokes membership/deletes source evidence mid-query, mid-stream, mid-rerank, mid-export, and mid-release.
- **Artifact-first broker:** Cross-user similarity produces a reviewed reusable artifact first; people are revealed only through reciprocal opt-in.
- **Negative-result dashboard:** Keep latest-only leakage, no-memory abstention artifact, rejected hybrid RRF latency, Defog protocol failure, and underpowered memory gates visible as active constraints.
- **Claim-class field on every result:** Deterministic, statistical, causal, hypothesis, owner-acknowledged limitation, or refused.

## Assumptions Ledger

- The deployment remains an internal enterprise tool; authorized users/admins may see full scoped PII/classified content.
- Reusable credentials are excluded from ordinary trace capture and every model/evaluator/index/replay/export boundary.
- Several hundred GB is the current workload order, so capacity alone does not justify another persistent store.
- Local project summaries and configs are treated as primary project evidence for this pane.
- Public traces are useful for parser/mechanics/retrieval experiments but not workforce or enterprise-population claims.
- Human review capacity exists for early proposal queues, label creation, and contested releases.
- Aurora-first is a starting constraint, not a belief that PostgreSQL can satisfy every future workload.

## Questions for Project Owner

1. Which outputs are categorically forbidden even for admins: named skill gaps, manager drilldown, productivity inference, cross-user people search, rare-cohort exploration, or inferred intent?
2. What exact Aurora/RDS Proxy failure would justify leaving Aurora or adding a sidecar?
3. What deletion operations must be synchronous non-return versus asynchronous physical erasure?
4. Which memory and skill destinations can receive releases, and what withdrawal notice is acceptable for exported files?
5. Who adjudicates contested task boundaries, skill/support hypotheses, memory facts, and cross-scope source conflicts?
6. What reviewer budget is acceptable per proposed eval, memory, skill, or artifact?
7. What enterprise cohort can support prospective intervention labels without creating surveillance pressure?
8. Which outcome metric is primary for "helped": verified task success, fewer turns, lower latency/cost, fewer corrections, user-rated usefulness, or business outcome?

## Points of Uncertainty

- Corrected v2 memory primitives remove several confounds, but no corrected model result exists yet.
- Aurora selective-RLS, vector/FTS, failover, RDS Proxy, deletion, and concurrent analytics behavior remain unproven at production scale.
- Human label reliability for same work, productive exploration, accidental friction, recovery, and support opportunity is unknown.
- General embeddings may underperform or overperform public/silver tests on enterprise jargon and exact identifiers.
- The final utility of team/enterprise artifacts after privacy controls is unknown.
- NL2SQL may be an excellent causal microcosm but may transfer poorly to coding/research traces.
- External product capabilities may have changed; this analysis relies on the project-recorded source pins and summaries rather than new browsing.

## Agreements and Tensions with Other Perspectives

- **Agreement with B9 Simplicity/MDL:** One governed authority plus rebuildable projections is the smallest coherent system. F7 adds that this is not only simpler; it is the control structure that prevents delayed feedback and shared-state drift.
- **Agreement with H2 Adversarial:** Similarity-to-identity, authorization side channels, projection loss, and circular memory/skill loops are realistic attacks. F7 frames them as system feedback failures that will emerge even without a malicious actor.
- **Agreement with I4 Perspective-Taking:** Personal-first, artifact-first, contestable workflows are adoption controls. F7 adds that contestability is also a feedback correction mechanism, not just UX.
- **Agreement with L2 Debiasing:** Public-corpus, metric, status-quo, and framework-collection biases are feedback distortions. F7 treats random audit, influence quarantine, and claim-class fields as system-level debiasing controls.
- **Expected agreement with K2 and F1:** Standalone and factorial experiments must separate selection, retrieval, diagnosis, memory, procedure, and intervention effects. F7 emphasizes staged loops because a full everything-at-once factorial would be underpowered and uninterpretable.
- **Tension with G6 Multi-Criteria:** A weighted matrix may select a high-utility component before shared-state hazards are solved. F7 would veto any component that cannot participate in the authority/deletion/influence control loop, even if its isolated score is strong.
- **Tension with B3 Bayesian:** Sequential weak evidence is useful for internal prioritization, but showing low-certainty skill or collaboration posteriors can alter behavior and contaminate future evidence. F7 prefers private/shadow updates until exposure is modeled.

## Confidence

Overall confidence: **0.87**. Confidence is high that the release/influence/deletion control loop is the kernel, that ATIF/OTel/memory/search systems should remain projections until native gates fail, and that current evidence does not support automatic memory, skill-gap inference, collaborator matching, custom embeddings, or leaving Aurora. Confidence is lower on the ultimate retrieval/storage choice and memory/procedure utility because corrected v2 model results, production Aurora gauntlets, human labels, and prospective enterprise outcomes remain unrun.
