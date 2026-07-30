# G6 Multi-Criteria Decision Analysis

## Thesis

The decision-dominant architecture is a single governed Aurora/PostgreSQL evidence and proposal authority, with exact/structured/lexical retrieval first, pgvector as a bounded accelerator, and ATIF/OTel/OpenInference as lossy projections with receipts. The current evidence supports an internal product that answers personal history, authorized evidence search, review queues, cited eval/memory/procedure proposals, and aggregate artifact backlogs. It does not support automatic memory writes, root-cause automation, employee skill inference, named collaboration matching, custom embeddings, external vector/search authorities, or generator/skill fine-tuning.

G6 scoring is intentionally conservative: authority, deletion, temporal correctness, and operational reversibility are weighted higher than framework coverage. The best near-term program is L0-L3 plus proposal-only L5, with NL2SQL as the first controlled intervention lab after protocol repair. Every heavier architecture is an experimental arm until it beats the minimal one under the same RLS, deletion, provenance, latency, and outcome tests.

Decision weights used below:

| Criterion | Weight | What it means here |
|---|---:|---|
| Answer quality and actionability | 14 | Produces useful, cited, contestable answers to original enterprise questions. |
| Exact-term fidelity | 8 | Preserves identifiers, paths, schema names, versions, prompts, tool names, and quoted terms. |
| Temporal and authority correctness | 15 | Respects known-at, valid-at, policy epoch, source revision, purpose, and current authorization. |
| Deletion and RLS closure | 14 | Prevents protected rows, IDs, counts, distances, snippets, caches, exports, or telemetry leaks. |
| Latency and query cost | 9 | Meets interactive history/search targets and keeps heavy work asynchronous. |
| Ingest and storage cost | 7 | Avoids embedding/indexing every log and limits WAL, backup, object, and rebuild growth. |
| Operational burden | 10 | Minimizes new stateful systems, migrations, on-call paths, licenses, and recovery procedures. |
| Aurora compatibility | 7 | Works on managed Aurora PostgreSQL without unapproved extensions or privileged server hooks. |
| Scale and isolation readiness | 6 | Can survive hundreds of GB, worker saturation, failover, and inference isolation requirements. |
| Scientific usefulness | 10 | Supports falsifiable experiments, controls, labels, holdouts, and negative results. |

## Top Findings

1. **§F1: Kernel candidate - one Aurora authority is the highest-scoring default.**
   - **Evidence:** `trace-intelligence-aurora-rls-execution-plan.md` states Aurora remains the evidence, policy, lineage, and deletion authority while FTS and pgvector are rebuildable accelerators. `trace-intelligence-composed-feasibility-and-failure-analysis.md` rejects ClickHouse, OpenSearch, Qdrant, VectorChord, pgContext, Turbopuffer, Phoenix, Opik, Langfuse, and graph DBs as initial dependencies. `canonical-projection-e0-conformance-2026-07-30.md` shows ATIF and OTel/OpenInference are projections, not complete authorities.
   - **Reasoning chain:** The enterprise problem is not just "find similar traces." It is "find authorized, current, provenance-preserving evidence and know what claim class it supports." A single transactional authority scores best on authority, deletion, exact fields, and operational burden. Projections can serve interoperability and observability only if they carry loss receipts back to the canonical DAG.
   - **Severity:** High. A premature second authority creates stale deletion, policy, identity, and provenance divergence in an internal classified/PII system.
   - **Confidence:** 0.89.
   - **So what:** Build the first product and research ladder on Aurora/PostgreSQL canonical tables, typed authority fields, RLS, deletion epochs, release/proposal records, FTS, and optional pgvector. Treat every sidecar as derived and disposable.

2. **§F2: Kernel candidate - exact, structured, and lexical retrieval should gate dense/hybrid retrieval.**
   - **Evidence:** `codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md` found structured+dense best offline at `0.818` Recall@20 on silver labels. `codetracebench-e2-postgres-joint-retrieval-2026-07-30.md` then showed local forced-RLS exact pgvector at `0.667` Recall@20 and `3.017 ms` p50, while the tested hybrid reached only `0.672` Recall@20 at `256.843 ms` p50. The README explicitly rejects the tested hybrid and says this is not an Aurora/concurrency/scale result.
   - **Reasoning chain:** Dense retrieval has value as a candidate generator, but the measured local hybrid is a bad quality-latency trade. Exact identifiers, schemas, paths, errors, tools, and structured task fields remain load-bearing for coding and NL2SQL traces. A single fusion owner with reauthorization is preferable to stacking BM25, ANN, rerankers, and framework-specific score blending.
   - **Severity:** Medium-high. Bad retrieval design can both miss evidence and overload the authority database or sidecar, but the immediate product can degrade safely to exact/FTS.
   - **Confidence:** 0.83.
   - **So what:** Ship exact/structured/FTS first. Add pgvector behind an explicit capability and exact-search oracle. Reject trigram-heavy or RRF-heavy hybrids until a frozen benchmark shows material recall gain at acceptable p95/p99 and no RLS/deletion regression.

3. **§F3: Owner-acknowledged limitation - current memory, Dream, LangMem, and Graphiti evidence supports proposals, not automatic memory.**
   - **Evidence:** `longitudinal-memory-local-model-replication-2026-07-30.md` reports identical aggregate results for evidence-bearing memory arms and exposed confounds. `trace-commons-memory-composition-2026-07-30.md` found latest-only same-basename leakage in `3/6` cases and contextual `0/6`, but was underpowered. `dream_release_pipeline_v2.py` requires query-independent proposals, independent verification, copy-on-write release, and deletion-aware visibility.
   - **Reasoning chain:** Temporal facts, bitemporal oracles, and Dream release records are valuable because they prevent future leakage and make proposals auditable. They do not prove that memory improves future work. Automatic `MEMORY.md`, LangMem, Graphiti, or Memory Palace updates would score poorly on deletion, influence control, and scientific usefulness because later traces may be caused by the generated memory.
   - **Severity:** High. Silent memory mutation can create stale guidance, circular validation, and cross-scope leakage.
   - **Confidence:** 0.88.
   - **So what:** Keep memory/Dream/Graphiti/LangMem as cited proposal and review infrastructure only. No automatic prompt, memory, route, procedure, or model update should occur until exposure/control outcomes and deletion closure pass.

4. **§F4: Hypothesis - NL2SQL is the best first causal skill-learning lab, but not yet a deployable skill flywheel.**
   - **Evidence:** `nl2sql-enterprise-skill-domain-assessment-2026-07-30.md` identifies NL2SQL as a strong domain because traces contain typed questions, schema inspection, SQL attempts, database observations, and executable outcomes. `nl2sql-capability-isolation-component-checkpoint-2026-07-30.md` reports `61/61` component tests passing, real Linux `runc` checks, and PostgreSQL role audit. `defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md` shows all arms passed the same `2/4` tasks and protocol failure was `25-50%`.
   - **Reasoning chain:** NL2SQL has unusually clear labels and tool effects, so it scores high on scientific usefulness. It scores lower on production readiness because terminal protocol failure dominated the first smoke and several isolation receipts remain incomplete. Skill-learning should be tested as an intervention registry, not as an autonomous learning loop.
   - **Severity:** Medium. Research investment is justified; production claims would be premature.
   - **Confidence:** 0.79.
   - **So what:** Fund protocol repair, complete the 27-gate isolation proof, rerun P0, then compare no-skill, placebo, expert seed, and evidence-mined procedure on family-disjoint Defog/BIRD-style tasks.

5. **§F5: Kernel candidate - observability and eval products should contribute schemas and projections, not become authorities.**
   - **Evidence:** `otel-collector-roundtrip-e0-2026-07-30.md` preserved all projected span identities, parent edges, links, timestamps, status, attributes, tool lifecycle classification, resource/scope, and receipt pointers for 48 spans/12 traces, but collector-side drops required an out-of-band source/export manifest. The composed feasibility docs say Phoenix, Opik, Langfuse, AgentEvals, AgentRx, and OpenRCA are useful concepts but should not own lifecycle/deletion identity.
   - **Reasoning chain:** OTel/OpenInference is excellent for operator navigation, spans, topology, and content-minimized telemetry. ATIF is useful for task/eval interchange. Phoenix/Opik/Langfuse offer dataset/evaluator lifecycle ideas. AgentRx/OpenRCA can express hypotheses. None of these solve Frankengate authority, source intersection, deletion, or intervention causality if deployed as parallel systems.
   - **Severity:** Medium-high. Duplicate lifecycle systems are easy to install and hard to delete correctly.
   - **Confidence:** 0.81.
   - **So what:** Implement native lifecycle tables and export adapters. Use content-minimized OTLP and selected ATIF projections with loss manifests. Do not deploy Phoenix/Opik/Langfuse/Graphiti as systems of record.

6. **§F6: Owner-acknowledged limitation - custom embeddings and external vector/search services fail the current decision threshold.**
   - **Evidence:** `domain-adaptive-embeddings-and-secure-rag.md` says adaptation begins only after governed judgments and baselines. `trace-intelligence-all-together-system-and-experiment-ladder.md` sets L9 to require at least `+5` absolute Recall@20 on a frozen hard slice with no exact-ID, subgroup, deletion, latency, or rollback regression. `pg-textsearch-frankengate-fit-review.md` says `pg_textsearch` is not Aurora-installable and should be a conditional benchmark arm. `turbovec-frankengate-fit-review.md` says TurboVec is concept/offline only, not Aurora-compatible authority. `frankensearch-assessment.md` keeps FrankenSearch default-off and license/security pending.
   - **Reasoning chain:** Domain embeddings and sidecars may improve hard cases, but they add model lifecycle, index release, license, rollback, deletion, and side-channel burden. Current bottlenecks are labels, authority proofs, protocol failures, and Aurora operations, not absent vector features.
   - **Severity:** Medium. Premature adoption increases day-two risk; delayed adoption is acceptable if reversal thresholds are explicit.
   - **Confidence:** 0.84.
   - **So what:** Train no enterprise embedding and deploy no external vector/search authority until exact/structured/FTS/general-dense/reranker baselines fail a named, frozen, authorized slice and the candidate passes the same RLS/deletion/latency gates.

7. **§F7: Kernel candidate - the first product should answer deterministic and hypothesis questions, and refuse socially unsafe people analytics.**
   - **Evidence:** `frankengate-combined-evidence-matrix-2026-07-30.md` says personal history, structural review queues, and evidence-linked eval/procedure proposals are supported or partially supported, while memory utility, causal skill benefit, cross-user learning, collaborator matching, and embedding fine-tuning are not. `MODE_OUTPUT_I4_PERSPECTIVES.md` and `MODE_OUTPUT_L2_DEBIASING.md` independently warn against person-level skill, productivity, and collaboration claims.
   - **Reasoning chain:** A decision model must include adoption and misuse costs. Similarity, repeated friction, recovery deltas, and selector scores can nominate artifacts for review. They cannot identify employee competence, intent, effort, loyalty, or who should work together without consent and prospective outcome evidence.
   - **Severity:** High in the internal deployment because authorized access still can be socially unsafe.
   - **Confidence:** 0.87.
   - **So what:** Product copy, APIs, and dashboards should label each insight as deterministic, statistical, causal, hypothesis, or refused. Named cross-user recommendations and skill gaps stay disabled unless an opt-in, artifact-first experiment passes.

8. **§F8: Hypothesis - upgrade thresholds are more important than feature completeness.**
   - **Evidence:** The Aurora execution plan requires exact-vs-ANN recall floors, deletion SLOs, connection budgets, failover behavior, analytics isolation, and reproducible benchmark artifacts. The corrected memory v2 config defines hard failure gates for credentials, future evidence, hidden labels, Dream release, attestation, truncation, and pooling. The vector architecture docs require same-corpus security oracle comparisons before enabling pgvector or FrankenSearch.
   - **Reasoning chain:** A matrix can become framework theater if every component gets a low-confidence score and then slips into the roadmap. The right decision mechanism is a reversible ladder: add an advanced component only when the simpler architecture fails a preregistered gate and the component passes the same authority/deletion/science tests.
   - **Severity:** Medium-high. Without explicit reversal criteria, either Aurora-first becomes dogma or framework collection becomes architecture.
   - **Confidence:** 0.80.
   - **So what:** Maintain an architecture reversal board with thresholds for Aurora replacement, external sidecars, graph service, memory promotion, NL2SQL skill release, and embedding adaptation.

## Standalone Concept Assessment

| Concept | Best enterprise answer | Evidence and labels required | G6 decision |
|---|---|---|---|
| ATIF | Portable selected task/eval trajectories | Source hashes, field mapping, loss receipts, unsupported field inventory | Use as narrow export only. E0 showed enterprise stress events lose IDs/edges in ATIF reimport. |
| OpenTelemetry/OpenInference | Span topology, timings, tool lifecycle, operational navigation | Expected source/export manifest, content allowlist, backend round trip | Use as content-minimized projection. Not authority or full replay. |
| AgentRx | Invariant violations and failure hypotheses | Declarative checks, sandbox, human decisive-step labels, ablations | Implement concepts for hypotheses. Do not emit root-cause truth. |
| Signals | Cheap review selectors and friction candidates | Random/length audit strata, precision labels, missingness labels | Use before judges/embeddings. Never relabel as skill or cause. |
| AgentEvals | Stored trace assertions and eval proposals | Assertion semantics, mutant tests, prospective replay boundary | Use as Frankengate eval records. Audit != changed-system proof. |
| Phoenix, Opik, Langfuse | Dataset, annotation, evaluator, experiment lifecycle | One release/deletion identity, evaluator revision, import/export receipts | Adopt lifecycle ideas; do not deploy as parallel authorities. |
| OpenRCA | Multimodal incident and topology hypotheses | Logs/metrics/topology clocks, alternative causes, intervention evidence | Hypothesis engine only. Causal RCA remains gated. |
| Graphiti | Bitemporal facts, contradiction/source lineage | Entity resolution, valid/system time, scoped edges, deletion tests | Test relational facts/edges first; graph backend only after relational failure. |
| LangMem | Memory extraction/update/delete workflow | Citations, destination scope, review, rollback, deletion lineage | Proposal extractor only; no automatic memory mutation. |
| MemInsight | Typed attributes over tasks/entities/outcomes | Ontology, calibration, entity-resolution, sensitive-attribute tests | Useful schema inspiration; not a separate inference authority. |
| Memory Palace | Personal navigation and recall UX | Cited, scoped evidence cards, contestability | UX metaphor only. Avoid hidden cognitive profiling. |
| Temporal evidence | Known-at/valid-at/source/deletion correctness | Bitemporal oracle, lineage, cutoff proofs, future-leak tests | Load-bearing kernel mechanism. |
| `MEMORY.md` | Rendered destination artifact | Release receipt, citations, expiry, deletion/withdrawal semantics | Destination only. Canonical truth remains in Aurora. |
| Cloud dreaming | Query-independent candidate synthesis | Pre-cutoff inputs, verifier packet, independent verification, release receipts | Use for proposals only. No direct write to memory/skills. |
| ReasoningBank | Procedural memories from success/failure contrast | Hidden-family controls, no-skill/placebo arms, influence lineage | Research arm after NL2SQL protocol repair. |
| Hermes/Jeopard-style skill learning | Candidate skills/procedures from trajectories | Resettable environments, evaluator separation, held-out families | Useful idea; unsafe without prospective controls and rollback. |
| RL environment histories | Reward-linked action/observation episodes | Environment state, reset, action, reward, termination, resource receipts | Valuable if attached to canonical evidence; flat chat logs are insufficient. |
| CASS | Local multi-agent history ingestion/search | Import receipts, license review, connector fidelity | Adopt connector/UX ideas; not enterprise authority. |
| Doodlestein/CM | Personal/local memory and compact review workflows | Local trust boundary, source rights, deletion path | Use UX/import concepts only. |
| claude-history | Exact-first personal history search | Native history fidelity, local privacy, fielded query tests | Use for personal UX patterns; no RLS/scale claim. |
| Prompt-Scope | Private prompt reflection | Source-local evidence, user consent | Personal reflection only, not firmwide mining. |
| Frankensearch | Hybrid/progressive lexical+dense search | ACL-before-candidate, tombstones, stale-index tests, license/SBOM, p95 benchmarks | Default-off sidecar experiment, not launch dependency. |
| Aurora JSONB | Bounded provider-specific metadata | Typed authority columns beside JSONB, promoted hot keys | Use only for long-tail attributes; not security decisions. |
| PostgreSQL FTS/trigram | Exact/lexical fallback and quoted-term search | Generated tsvector, query plans, RLS selectivity, typo tests | Launch baseline. Avoid expensive hybrid unless benchmarked. |
| pgvector | Generic dense candidate lane and exact vector oracle | Model/index contract, exact-vs-ANN recall, deletion and RLS tests | Conditional accelerator inside Aurora/Postgres. |
| VectorChord | Compressed PostgreSQL-native ANN candidate | Managed/extensible PostgreSQL migration proof, equal RLS/deletion | Replacement candidate only if Aurora/pgvector fails. |
| pg_textsearch | BM25 PostgreSQL ranking | Self-hosted PG17/18 extension, RLS side-channel tests, ranking benchmark | Not Aurora-adoptable now; conditional bakeoff arm. |
| pgContext | Higher-level retrieval/context concepts | Provenance, authority, temporal and deletion mapping | Concept watchlist; not a storage decision. |
| Turbovec | Compact in-process dense flat scoring | Aurora-authorized candidate allowlists, ephemeral worker benchmark | Offline/ephemeral experiment only. Not authority or sidecar. |
| Turbopuffer | Managed durable vector/search service | Equivalent auth, region, deletion, outage, cost, and side-channel tests | Escape hatch only after Aurora failure. |
| General embeddings | Candidate generation for semantic similarity | Human/silver labels, hard negatives, exact-ID tests, RLS/deletion | Use as baseline and optional lane. |
| Enterprise-adapted embeddings | Jargon/task hard-slice recall | Reviewed positives/hard negatives, train/test by person/time/tenant, holdout | Late conditional. Require +5 absolute Recall@20 and no regressions. |
| Agentic coding/research traces | Personal history, review queues, eval/memory/procedure candidates | Tool-call fidelity, task boundaries, outcomes, rights | Good mechanics substrate; weak population/skill inference. |
| NL2SQL complete tool traces | Controlled skill/procedure experiments | SQL attempts, DB observations, gold separation, hidden families, sandbox receipts | Highest-priority causal testbed after protocol gates. |

## Composition and Non-Composition Matrix

| Composition | Decision | Interface | Main double-count/leak risk | Required control |
|---|---|---|---|---|
| Canonical DAG + OTel/OpenInference | Compose | OTLP spans with receipt pointers | OTel becomes trusted evidence or misses upstream drops | Source/export manifest, content minimization, loss receipts. |
| Canonical DAG + ATIF | Compose narrowly | Selected task/eval trajectory export | ATIF loss treated as complete evidence | Explicit loss manifest and reimport conformance. |
| Aurora + exact/FTS + deterministic Signals | Compose | SQL tables, tsvector, signal tables | Signals become labels | Random/length audit and claim-class tags. |
| Aurora + pgvector + generic embeddings | Compose conditionally | Authorized candidate IDs, exact oracle, one fusion owner | ANN underfill, distance/count side channels | Pre-candidate authorization, overfetch/exact fallback, reauth before snippets. |
| Signals + AgentRx + AgentEvals | Compose as triage | Selector -> hypothesis -> eval proposal | Selector/hypothesis/eval collapse into "cause" | Separate tables and evidence states. |
| OpenRCA + metrics/logs/topology + trace DAG | Compose as hypothesis | Joined IDs/clocks/topology | Correlation narrated as cause | Alternative explanations and intervention requirement. |
| Temporal oracle + Dream pipeline + `MEMORY.md` | Compose as proposal | Verified proposal release rendered to destination | Future leakage and self-verification | Cutoff, independent verifier, copy-on-write release, influence lineage. |
| Graphiti + MemInsight + Aurora facts | Compose only relational-first | Bitemporal fact/edge tables | Graph proximity/group key substitutes for authority | Scope intersection, entity-merge negatives, relational ablation. |
| ReasoningBank/Hermes/RL histories + NL2SQL | Compose after gates | Frozen procedure candidate into intervention registry | Successful trace becomes "good skill" | No-skill/placebo/expert controls, sealed hidden families. |
| CASS/claude-history/Prompt-Scope + personal UX | Compose | Import adapters and fielded personal search | Local privacy model assumed enterprise-safe | Destination transform and authority envelope. |
| Frankensearch + Aurora | Compose only as default-off sidecar | Derived authorized chunks and tombstone outbox | Progressive phase leaks unauthorized candidates | ACL-before-candidate, stale-index fail-closed, PostgreSQL recheck. |
| Phoenix + Opik + Langfuse as deployed stack | Do not compose | N/A | Duplicate datasets, evals, feedback, deletion identities | Implement native lifecycle records instead. |
| ATIF + OTel as two canonical stores | Reject | N/A | Split truth and conflicting loss semantics | Canonical DAG remains source. |
| Signals + whole-trace embeddings = diagnosis | Reject | N/A | Identity/cause inferred from selectors | Human decisive-step labels and intervention tests. |
| Automatic LangMem/Dream/Memory Palace writes | Reject | N/A | Circular validation and stale/future leakage | Proposal-only release path. |
| Semantic similarity = collaboration/person finder | Reject | N/A | Similarity becomes identity/social recommendation | Anonymous pattern plus reciprocal opt-in only. |
| Custom embedding before frozen benchmark | Reject | N/A | Training/deletion burden without known failure | +5 Recall@20 hard-slice gate and safety tests. |
| Full "everything factorial" | Reject | N/A | Cost explosion and uninterpretable effects | Laddered ablations with one added mechanism at a time. |

## Enterprise Questions Answered and Not Answered

| Enterprise question | Current decision status | Why |
|---|---|---|
| "Show me all my authorized history." | Build first | Deterministic history, exact search, tool-call evidence, and lazy content fetch are within the Aurora authority model. Production still needs deletion/failover gauntlets. |
| "What tools/prompts/models did I use and what happened?" | Build first | Complete tool-call canonicalization and OTel projections support this descriptively. |
| "Which traces deserve review?" | Build as hypothesis/selector | Signals and retrieval can nominate candidates. They require random audit and should not be labels. |
| "What repeated friction/recovery patterns exist?" | Build as review queue | Supported as aggregate/artifact candidates, not root cause or person skill. |
| "Which evals should we create?" | Build as proposal | AgentEvals-style records and governed release mechanics support cited proposals. Changed-system value remains prospective. |
| "Which memories or `MEMORY.md` entries should exist?" | Proposal only | Temporal/Dream release primitives support reviewable candidates. Automatic writes are unsupported. |
| "Which prior work is similar?" | Conditional | Exact/structured/FTS and generic dense can find candidates under authority. Human labels and consent are needed for cross-user meaning. |
| "Who should collaborate?" | Refuse for now | Similarity is not social usefulness. Reciprocal opt-in around an artifact is the minimum future path. |
| "What skills are missing?" | Refuse as people claim | Current evidence cannot separate skill from protocol, permission, model, tool, environment, or task design. |
| "What caused this failure?" | Hypothesis only | OpenRCA/AgentRx can propose alternatives. Causal claims need intervention/replay. |
| "Should we train an embedding?" | Not yet | Requires a frozen hard-slice failure of exact/structured/general baselines and +5 absolute Recall@20 with no safety regressions. |
| "Should we leave Aurora?" | Not yet | Requires representative Aurora workload failure after tuning, not vendor feature desire. |
| "Can traces train skills or policies automatically?" | No | Needs prospective controls, influence lineage, human approval, and rollback. |
| "How productive or loyal is an employee?" | Refuse | Socially unsafe and unsupported by trace evidence. |

## Empirical Tests and Falsifiers

Upgrade thresholds I would preregister:

1. **Aurora replacement or second query store threshold.** Consider leaving Aurora or adding a permanent query store only if a representative workload with concurrent ingest, history, exact/FTS, pgvector, deletion, re-embedding, aggregation, and failover fails a declared p95/p99, recall, deletion, connection-headroom, or inference-isolation SLO after bounded pools, typed predicates, partitioning where justified, preaggregation, sparse embeddings, exact fallback, and worker quotas. The replacement must pass the same RLS/deletion/failover/backup tests and have lower total operational risk.

2. **External vector/search sidecar threshold.** A sidecar such as FrankenSearch, Qdrant, Turbopuffer, or similar must show at least one material, named improvement: for example >= +0.05 absolute Recall@20 on a frozen hard slice, or >= 2x p95 latency/cost improvement on an otherwise failing authorized retrieval workload. It must also prove ACL-before-candidate, tombstone convergence, stale-index fail-closed behavior, content-free telemetry, SBOM/license closure, and PostgreSQL reauthorization before snippets.

3. **pgvector ANN threshold.** HNSW/IVFFlat/iterative scan paths promote only if they meet exact-search recall floors for every critical authorization slice and never underfill by relaxing predicates. Small authorized candidate sets must fall back to exact or lexical search.

4. **Custom embedding threshold.** Train or deploy enterprise-adapted embeddings only after exact, structured, FTS, general dense, and reranker baselines fail a frozen, reviewed hard slice. Promotion requires >= +5 absolute Recall@20, no exact identifier or hard-negative regression, no subgroup regression, no ACL/deletion/memorization leak, no p95/p99 or rollback regression, signed model/index releases, and reviewed data rights.

5. **Memory/Dream threshold.** Promote memory only from reviewed proposals with source citations, authority-envelope intersection, independent verification, cutoff proof, zero credential or future evidence leak, deletion closure, and measured later-task utility over no-memory/current-memory/placebo. Any generated memory-influenced trace is excluded from independent validation unless explicitly modeled as exposed.

6. **Signals threshold.** A signal remains a selector if it beats random and length/stage-count baselines on human "informative trace" labels. A diagnostic label requires decisive-step labels and an intervention or replay test. The earlier +15 point structural-selection gate is a useful minimum reference.

7. **NL2SQL skill threshold.** Before hidden or production-like claims, protocol failure must drop below 10%, unauthorized observations must remain zero, and evidence-mined procedures must beat no-skill and length-matched placebo on family-disjoint tasks. Expert seed is an upper reference, not proof of mined skill value.

8. **Graph service threshold.** A Graphiti-like backend is justified only after a bounded multi-hop temporal-fact benchmark fails relational recursive SQL/materialized edges under equal authority/deletion controls and the graph improves answer quality enough to cover extraction and entity-resolution burden.

9. **AgentRx/OpenRCA threshold.** Root-cause language requires prospective replay, counterfactual intervention, or a randomized/quasi-experimental design. Without that, outputs are hypotheses with alternatives and confidence only.

10. **OTel/ATIF projection threshold.** A projection is acceptable if it preserves the fields claimed for its role and emits explicit losses for the rest. Telemetry cannot claim drop detection without an expected source/export manifest.

Hard falsifiers for any architecture:

- Any unauthorized row, ID, candidate count, distance, snippet, cache hit, export, or telemetry label crosses scope.
- Any credential reaches model input/output, evaluator, index, replay, tool IO, or egress.
- A deleted or revoked source remains visible beyond the declared logical SLO.
- An insight loses source citations, authority epoch, policy/deletion epoch, or claim class.
- Analytics or indexing measurably degrades inference beyond the gateway isolation budget.
- A memory/skill/model trains on or validates against its own unmarked influence.

## Architecture Consequences

Ranked minimal architectures:

| Rank | Architecture | Score / 100 | Decision |
|---:|---|---:|---|
| 1 | **A0: Governed Aurora kernel.** Canonical event DAG, typed authority/time/deletion columns, bounded JSONB, RLS, object refs, exact history, FTS, deterministic Signals, proposal/release tables, content-minimized OTel and selected ATIF exports. | 87 | Build first. Best combined authority, deletion, exactness, cost, and operations score. |
| 2 | **A1: A0 + generic pgvector lane.** Curated retrieval corpus, model/index contract, exact vector oracle, optional ANN, one fusion owner, reauth before snippets. | 80 | Conditional P1. Good semantic recall potential, but no Aurora/concurrency proof yet. |
| 3 | **A2: A0 + temporal memory/Dream proposal graph.** Bitemporal oracle, Dream proposal verifier, copy-on-write release, `MEMORY.md` renderer. | 76 | Build as proposal/review workflow only. No automatic live memory. |
| 4 | **A3: A0 + NL2SQL intervention lab.** Broker/evaluator isolation, sealed folds, procedure registry, no-skill/placebo/expert/evidence-mined arms. | 73 | Highest scientific ROI research arm after protocol repair. |
| 5 | **A4: A0 + optional FrankenSearch sidecar.** Authorized derived index, progressive hybrid search, tombstone outbox, PostgreSQL recheck. | 58 now, up to 75 after gates | Default-off experiment. Security/license/benchmark work required. |
| 6 | **A5: A0 + external vector/search service as permanent store.** Qdrant/Turbopuffer/OpenSearch-like online store. | 45 now | Escape hatch only after Aurora failure and equal authority proof. |
| 7 | **A6: A0 + Graphiti/LangMem/Memory Palace as deployed memory stack.** | 43 | Reject now. Use concepts inside native proposal records. |
| 8 | **A7: A0 + Phoenix/Opik/Langfuse as separate lifecycle authorities.** | 39 | Reject now. Duplicate release/deletion/eval truth. |
| 9 | **A8: Custom embeddings or generator/skill fine-tuning loop.** | 42 now | Late conditional. Requires frozen hard-slice and intervention lift. |
| 10 | **A9: Full RL/ReasoningBank/Hermes auto-skill flywheel.** | 38 now | Research only. Too much causal, feedback, and rollback risk. |

Implementation implications:

- The launch data model should make `source_id`, `source_revision`, `known_at`, `valid_at`, `policy_revision`, `authorization_epoch`, `deletion_epoch`, `classification`, `purpose`, `owner/team/project`, `derivation_manifest`, and `claim_class` first-class fields.
- JSONB is long-tail metadata, not authority. Any field used for tenant, subject, audience, purpose, classification, policy, retention, or deletion must be typed.
- Every derived object is rebuildable from source and invalidated by current source/policy/deletion epochs.
- The retrieval API should expose degraded states: `exact_only`, `lexical_only`, `semantic_unavailable`, `index_stale`, `budget_exhausted`, `insufficient_authorized_evidence`, and `metadata_only`.
- Heavy parsing, embedding, judging, aggregation, and replay remain worker jobs with separate pools and quotas. The inference path must not wait on them.
- A sidecar cannot return raw content. It returns opaque IDs, scores, index revision, and receipts; Aurora decides current visibility and citations.

## Risks Identified

| Risk | Severity | Decision impact |
|---|---|---|
| Cross-scope leakage through ANN, BM25, graph neighborhoods, counts, distances, snippets, cache, or telemetry | High | Forces pre-candidate auth, exact oracle, reauth, and zero-leak gates before advanced retrieval. |
| Stale deletion or policy in derived indexes, memories, datasets, or sidecars | High | Keeps one authority and requires tombstone/rebuild/readback receipts. |
| Selector metrics becoming employee skill, productivity, or root-cause labels | High | Requires claim-class tags and refusal of person analytics. |
| Memory/skill/model circular feedback | High | Requires influence lineage, exposure controls, and holdouts. |
| Aurora-first status-quo bias | Medium | Requires explicit reversal board and production gauntlet. |
| Framework-collection bias | Medium-high | Scores separate products low until they prove unique value under same controls. |
| Over-embedding sensitive traces | Medium-high | Favors curated retrieval corpus over embedding every log. |
| Hybrid retrieval latency/cost blowup | Medium | Exact/FTS first, measured fusion only. |
| Public corpus overgeneralization | Medium | Public traces are mechanics evidence, not enterprise population evidence. |
| License/model supply-chain surprises in sidecars and embeddings | Medium | Sidecars and custom models require SBOM, model-card, and pinned asset approvals. |

## Recommendations

1. **P0 - Adopt A0 as the baseline architecture.** Build canonical Aurora evidence/proposal authority, personal history, exact search, FTS, deterministic Signals, proposal queues, RLS/deletion receipts, and OTel/ATIF projections with loss manifests.

2. **P0 - Publish the G6 reversal board.** For Aurora, pgvector, sidecars, graph, memory, NL2SQL skill release, custom embeddings, and generator fine-tuning, record the current decision, trigger threshold, required experiment, owner, and rollback.

3. **P0 - Enforce claim classes in product and API.** Values should include deterministic, statistical, hypothesis, causal, proposal, refused, and unknown. Do not allow UI copy to upgrade retrieval or selector outputs into cause or skill.

4. **P1 - Run the Aurora operations gauntlet.** Include selective RLS, deletion/revocation, exact/FTS/vector queries, worker saturation, re-embedding, aggregation, failover, reader lag, pool exhaustion, and inference isolation.

5. **P1 - Promote pgvector only as a measured retrieval lane.** Use exact pgvector as the oracle, test ANN under selective authorization, and keep lexical fallback.

6. **P1 - Repair and rerun NL2SQL P0 before skill claims.** Complete missing broker/evaluator receipts, reduce protocol failure, then run no-skill/placebo/expert/evidence-mined comparisons.

7. **P1 - Build proposal-only memory/Dream lifecycle.** Cited proposal, review, release, exposure, rollback, and deletion closure are valuable even if memory utility remains unproven.

8. **P2 - Evaluate sidecars and custom embeddings only after a named failure.** FrankenSearch, pg_textsearch, VectorChord, Turbovec, Turbopuffer, and enterprise embeddings belong in bakeoffs, not the launch chart.

9. **P2 - Add stakeholder and label studies before team intelligence.** Task similarity, friction type, environmental blockers, outcome usefulness, and contestability need human adjudication before cross-user features.

## New Ideas and Extensions

- **Architecture reversal board:** A live table with threshold, current evidence, last benchmark, next experiment, and "what would change our mind" for every non-minimal component.
- **Decision receipt per insight:** Store the criterion scores that allowed an insight to be shown: authority pass, deletion watermark, evidence count, claim class, support type, and missingness.
- **Costed claim ladder:** Every enterprise card picks the lowest-cost reversible action first: inspect evidence, label, create eval, propose memory, open docs issue, run intervention, then consider model/index change.
- **Negative-result gallery:** Preserve examples where length beat Signals, latest-only leaked, no-memory won by abstention artifact, hybrid RRF lost on latency, and Defog protocol dominated task success.
- **Retrieval stress dashboard:** Track exact, FTS, dense, hybrid, reranker, and sidecar lanes under the same authorized corpus with p50/p95/p99, Recall@20, denied-candidate counts, and deletion lag.
- **Influence quarantine ledger:** Any trace exposed to a memory, skill, retrieval model, evaluator, or route change is tagged so it cannot later be counted as independent validation without adjustment.
- **Artifact-first team broker:** Similar cross-user work becomes an anonymous reusable artifact proposal first; naming people requires reciprocal opt-in and evidence of benefit.

## Assumptions Ledger

- Internal authorized users may inspect full PII/classified content inside scope; credentials are excluded from the ordinary trace plane.
- Aurora PostgreSQL is the starting managed authority, and several hundred GB of traces is not by itself an exit trigger.
- The current local PostgreSQL 16/pgvector evidence is a mechanics and retrieval benchmark, not an Aurora operations proof.
- Public agent histories are useful for adapters, parsers, and candidate experiments, not for enterprise workforce claims.
- The correct first product is evidence/proposal workflow, not autonomous optimization.
- A lower weighted score does not mean a concept is useless; it means it is not a launch dependency under current evidence.
- Exact identifiers and typed fields matter at least as much as semantic similarity for coding and NL2SQL traces.
- Human review capacity is limited, so proposal precision and burden are real architecture criteria.

## Questions for Project Owner

1. What user-facing SLOs define failure for personal history, exact search, lexical search, and semantic expansion?
2. What deletion/revocation logical SLO should all derived indexes, memories, datasets, and projections meet?
3. What Recall@20, nDCG, or supportedness floor is required before semantic retrieval is considered product-useful?
4. Which cross-user outputs are categorically banned even if technically authorized?
5. What minimum cohort threshold and repeated-query policy should enterprise aggregate views enforce?
6. What reviewer agreement is required before a task-family, friction, or skill-support label can influence recommendations?
7. Who can approve release of a memory, eval, skill, embedding, or sidecar index when technical metrics pass but social risk remains?
8. What is the maximum acceptable operational budget for a second stateful retrieval system?
9. Which Aurora engine and pgvector versions are target launch constraints?
10. What is the first real enterprise domain after NL2SQL where prospective outcome labels are feasible?

## Points of Uncertainty

- Aurora selective-RLS/vector behavior under representative concurrent production load remains unmeasured.
- The true enterprise trace distribution may contain more exact identifiers, more sensitive content, or more semantically ambiguous tasks than public coding/NL2SQL corpora.
- Human label reliability for "same work," "friction," "cause," "useful recovery," and "skill support" is unknown.
- General embeddings may underperform or outperform current silver-label results on internal jargon; both directions remain plausible.
- Corrected v2 memory primitives are stronger than the pilot, but no corrected model result exists yet.
- The best sidecar or PostgreSQL replacement candidate could change quickly; this analysis uses project-recorded evidence, not a fresh market scan.
- We do not yet know whether enterprise users will tolerate proposal volume, contestability burden, or opt-in collaboration workflows.

## Agreements and Tensions with Other Perspectives

- **Agreement with K2 Scientific:** G6 agrees that every advanced component is a falsifiable claim. The matrix ranks mechanisms by current evidence and gives falsifiers rather than treating feature count as value.
- **Agreement with A1 Deductive:** Retrieval does not imply identity, association does not imply cause, proposal does not imply release, and projection does not imply authority. These invariants dominate the scoring.
- **Agreement with F1 Causal:** Memory, skill, prompt, route, model, and embedding benefit require interventions and outcome controls. G6 assigns high scientific value to NL2SQL precisely because it can support that structure.
- **Agreement with B9 Simplicity/MDL and L2 Debiasing:** The smallest coherent architecture is one governed PostgreSQL/Aurora authority plus projections and bounded accelerators. Simplicity remains a default, not a religion, because reversal thresholds are explicit.
- **Agreement with I4 Perspective-Taking:** Person-level analytics has high social cost even when authorized. Artifact-first, proposal-only, contestable workflows score higher than dashboards that feel powerful but cannot be trusted.
- **Tension with F7 Systems Thinking:** F7 may favor modeling many feedback loops early. G6 treats most loops as low-scoring until influence, deletion, and intervention accounting exist.
- **Tension with H2 Adversarial Review:** H2 may recommend stronger categorical bans. G6 leaves some features as conditional because decision analysis can admit them after strict evidence, but the initial score is still reject or research-only.
- **Tension with L2 Debiasing:** L2 warns that matrices can launder subjective weights. G6 mitigates this by making upgrade thresholds and hard falsifiers more important than the exact weighted scores.

## Confidence

Overall confidence: **0.84**.

Confidence is high that the current evidence supports an Aurora-first, evidence-linked, proposal-only baseline and does not support automatic memory, employee skill inference, collaborator matching, custom embeddings, or external retrieval authorities. Confidence is lower on the ultimate storage and embedding decisions because real Aurora failover/concurrency/selective-RLS tests, corrected v2 memory outcomes, and human enterprise labels remain unrun. The evidence most likely to change this decision would be a frozen, authority-complete benchmark where the minimal Aurora/exact/structured/FTS/general-dense design fails a declared user SLO and a sidecar, graph service, or adapted embedding passes the same deletion, RLS, provenance, latency, and outcome gates.
