# H2 Adversarial Review Analysis

## Thesis

The combined trace-intelligence program is viable only if it behaves as a governed evidence and proposal system. The adversarial failure mode is not mainly that an outsider sees private content; in this deployment, authorized users may see full PII/classified material inside scope and credentials are excluded from the ordinary trace plane. The sharper risks are that the system turns partial traces into confident organizational conclusions, leaks scope through retrieval side channels, validates memories and skills against evidence they caused, and gives managers a polished vocabulary for surveillance.

The smallest defensible kernel is one canonical evidence DAG, transaction-local authority, exact temporal/provenance/deletion semantics, candidate-only retrieval and memory generation, and independently measured intervention effects. Everything else - ATIF, OTel/OpenInference, AgentRx, Signals, AgentEvals, Phoenix, Opik, Langfuse, OpenRCA, Graphiti, LangMem, Memory Palace, Dreams, ReasoningBank, Hermes-style skill learning, RL histories, Frankensearch, custom embeddings, and external vector stores - should be treated as an adapter, projection, or experimental arm until it survives adversarial tests.

## Top Findings

1. §F1 - Similarity can be weaponized into a people finder and false skill-gap engine.
   - Evidence: The dispatch explicitly asks which combinations "conflate identity with similarity" and which questions remain socially unsafe (`MODE_AGENT_DISPATCH.md:41-46`). The project progress ledger records an owner-acknowledged limitation: semantic similarity alone cannot establish identity, permission, causality, skill deficiency, or intent (`MODES_ANALYSIS_PROGRESS.md:95-99`). The composition audit refuses named people from vector proximity, employee skill claims from failure/judge labels, and manager people-finder workflows (`trace-intelligence-enterprise-question-composition-audit.md:297-309`). CodeTraceBench retrieval improved silver Recall@20, but its summary states that same benchmark work does not imply person-level skill, productivity, collaboration, enterprise transfer, or causal benefit (`codetracebench-e2-authorized-retrieval-factorial-2026-07-30.md:48-59`).
   - Attack/failure: A manager searches "who keeps failing Aurora failover" or a rare project acronym, repeats slightly varied queries, and uses nearest neighbors, counts, snippets, or timing to identify a person, then labels them as lacking skill. Even if every individual row is technically within admin scope, the product has converted retrieval into an organizational accusation.
   - Reasoning chain: Dense retrieval and Signals can nominate related traces. Related trace does not imply same task, same cause, same capability gap, or consent to introduce people. Rare terms and repeated query complements can de-anonymize aggregates. Once the UI names people or ranks friction, users and managers will read it as institutional truth.
   - Severity: Critical for team/admin surfaces; high for personal-only surfaces if outputs are exportable or copied into reviews.
   - Confidence: 0.91.
   - So what: Ban named cross-user matches, skill-gap labels, productivity labels, and manager drilldown from vector/Signals outputs. Require artifact-first aggregation, minimum cohorts, repeated-query accounting, reciprocal opt-in before naming people, and a red-team reconstruction suite using rare clusters, exact identifiers, complements, snippets, distances, cursors, and timing.
   - Status: Kernel candidate plus owner-acknowledged limitation.

2. §F2 - Authorization side channels can leak before content is displayed.
   - Evidence: The Aurora RLS plan requires authorization before ANN exposure, distance/counts, reranking, snippets, cache, export, and aggregation, and requires roles without `BYPASSRLS` plus `FORCE RLS` (`trace-intelligence-aurora-rls-execution-plan.md:73-93`). The vector backend decision makes the authorization envelope authoritative and treats vector/lexical indexes as untrusted candidate generators whose IDs must be intersected before ranking, snippets, caches, replay, telemetry, or learning sinks (`vector-retrieval-backend-decision.md:5-11`). The secure RAG note warns that post-filtering is insufficient because scores, counts, neighborhoods, and caches can leak (`domain-adaptive-embeddings-and-secure-rag.md:73-83`). The all-together system doc requires permission-oracle equality across rows, IDs, counts, snippets, distances, cursors, object refs, cache, timing, and exports (`trace-intelligence-all-together-system-and-experiment-ladder.md:236-253`).
   - Attack/failure: A user without access probes a deleted project name through ANN, FTS, graph traversal, autocomplete, cache keys, aggregate counts, or latency. The system returns zero snippets but different distances, result counts, cursor lengths, cache-hit timing, or "unavailable" versus "no match," proving the project or person exists.
   - Reasoning chain: In retrieval systems, hidden rows can still affect candidate generation, ranking, cache behavior, aggregation thresholds, object references, and response timing. Stale authority epochs, reader lag, cache loss of envelope fields, and sidecars with weaker filters all broaden access without showing raw text.
   - Severity: Critical. Internal deployment reduces public exposure but not cross-scope leakage among users, teams, admins, workers, and compromised services.
   - Confidence: 0.88.
   - So what: Make the adversarial permission oracle a launch blocker. Every retrieval backend, graph/materialized view, cache, export, evaluation, memory, and telemetry path must be tested against malformed authority, stale epoch, withdrawal, deletion, reader lag, revoked membership, unauthorized exact term, unauthorized vector neighbor, aggregate differencing, and timing comparison. Denied, zero, malformed, and unavailable must have deliberate, audited semantics.
   - Status: Kernel candidate.

3. §F3 - Lossy trace projections can fabricate tool side effects and causal stories.
   - Evidence: ATIF is adopted only as import/export, not canonical evidence, because it lacks tenant/team/classification/purpose/policy/auth epoch, uses limited time semantics, and packages LLM/tool proposals/observations in a way that is insufficient for enterprise evidence (`atif-trace-schema-crosswalk-and-gap-analysis.md:6-17`, `atif-trace-schema-crosswalk-and-gap-analysis.md:19-33`). The same crosswalk says tool calls are proposals, not proof of authorization, dispatch, completion, or side effect (`atif-trace-schema-crosswalk-and-gap-analysis.md:106-128`), and no compared projection supplies full tool authorization semantics (`atif-trace-schema-crosswalk-and-gap-analysis.md:161-189`). The all-together failure table names "tool proposal as execution" and "silent linearization" as failure modes (`trace-intelligence-all-together-system-and-experiment-ladder.md:639-645`).
   - Attack/failure: An attacker or careless integration exports to ATIF/OTel/AgentEvals, drops failed branches or post-auth denial, then imports the projection as canonical. A later report says "the agent executed tool X, caused Y, and then recovered," when the trace only shows a proposed call, an unauthorized attempt, or a hidden failed branch.
   - Reasoning chain: Projection loss is not neutral in a system that diagnoses work. Missing branch, auth, proposal/execution, observation, state-delta, and valid/system time fields can invert conclusions. A parent-child span tree or task-step list is useful operationally but cannot be the evidence source for who did what, what was authorized, or what caused the outcome.
   - Severity: High for eval, RCA, memory, and audit features; medium for pure observability dashboards with content minimized.
   - Confidence: 0.86.
   - So what: Require projection loss receipts and round-trip manifests. Canonical records must distinguish proposal, authorization, dispatch, execution, observation, durable side effect, terminal submission, rollback, and missingness. Any projected trace used for RCA, AgentEvals, memory, or skill learning must carry a "not canonical" receipt unless every load-bearing field survives.
   - Status: Kernel candidate.

4. §F4 - Memory and skill loops can validate themselves.
   - Evidence: The evidence composition matrix warns that observed event, inferred candidate, reviewed release, harness projection, influenced trajectory, and independent held-out eval are distinct states (`memory-skill-replay-evidence-composition-matrix-2026.md:21-35`). It also says ReasoningBank/skill evolution fails if a generator judges itself, retrieves its own candidate, or trains/tests on related traces (`memory-skill-replay-evidence-composition-matrix-2026.md:99-110`). The all-together system rejects automatic Dream/LangMem writes and requires governed release graphs rather than stochastic analyzer writes (`trace-intelligence-all-together-system-and-experiment-ladder.md:160-186`, `trace-intelligence-all-together-system-and-experiment-ladder.md:255-274`). The longitudinal pilot found identical evidence-bearing arms and important confounds rather than memory benefit (`longitudinal-memory-local-model-replication-2026-07-30.md:16-31`, `longitudinal-memory-local-model-replication-2026-07-30.md:66-75`).
   - Attack/failure: A generated `MEMORY.md`, LangMem update, ReasoningBank procedure, dream artifact, or Hermes-style skill is exposed to users. Later traces improve or merely repeat the artifact's wording. The system retrieves those later traces as "independent evidence" that the memory/skill was correct, trains an embedding or procedure on them, and promotes the artifact.
   - Reasoning chain: Once a trace is influenced by a memory, route, skill, prompt, model, or retrieval release, it is no longer independent evidence for that release. Self-judged loops amplify fluent but wrong explanations and bury negative controls. Future leakage is especially easy in longitudinal histories where later reads reveal what was missing earlier.
   - Severity: High. This can produce confident but wrong memories, skills, and papers while every local receipt appears valid.
   - Confidence: 0.90.
   - So what: Introduce an influence quarantine ledger. Any artifact exposure, retrieval release, memory, skill, prompt, model, eval, or index version must mark downstream traces. Descendant traces cannot validate ancestors except in explicitly modeled exposure/control analyses. Ban automatic memory/procedure promotion; require independent verification, no-skill/placebo controls, held-out family splits, rollback, and deletion closure.
   - Status: Kernel candidate plus owner-acknowledged limitation.

5. §F5 - False causal skill-gap stories are the easiest organizational harm to ship.
   - Evidence: The composition audit says repeated symptoms cannot distinguish skill, documentation, permission, tool, model, retrieval, policy, incident, quota, environment, or exploration, and calls "skill gap" a contestable intervention hypothesis (`trace-intelligence-enterprise-question-composition-audit.md:229-248`). The all-together doc classifies skill support only as a hypothesis and says never assert a named employee lacks skill from prose, retries, judge labels, or failure counts (`trace-intelligence-all-together-system-and-experiment-ladder.md:73-83`). The Defog mechanics smoke showed every arm passed the same two of four tasks, no paired pass discordances, and protocol gate failure rates of 25-50 percent (`defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md:11-20`, `defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.md:74-86`). The README states no public corpus supplies a gold enterprise skill-gap label (`README.md:479-497`).
   - Attack/failure: A dashboard turns "repeated SQL retries" into "missing NL2SQL skill," turns "looped tool calls" into "needs training," or turns "used memory proposal" into "skill improved," without testing permission, protocol, stale docs, model/tool route, hidden schema, environment, or exploration alternatives.
   - Reasoning chain: Failures in agentic traces are often overdetermined. A trace can show where work got stuck, but not why in the causal sense. Skill is a person-level latent trait; the available evidence is task/session-level and affected by tools, policy, model, budget, instructions, and data access.
   - Severity: Critical if tied to employee review, staffing, compensation, performance management, or manager dashboards; medium if kept as private optional support hypotheses.
   - Confidence: 0.92.
   - So what: Product copy and APIs must use "support opportunity" or "artifact/procedure candidate," never "employee skill gap," unless a dedicated causal study exists. Every diagnosis card must list non-skill alternatives and the reversible intervention ladder: permission fix, docs fix, tool fix, retrieval fix, prompt/procedure, memory, route/model, embedding, fine-tune. Use randomized or stepped-wedge interventions with contestable labels before causal wording.
   - Status: Kernel candidate plus owner-acknowledged limitation.

6. §F6 - Credentials and prompt-injected outputs are the sharpest boundary failures.
   - Evidence: The privacy boundary document states credentials never belong in the content plane and must be stripped before capture, index, replay, eval, model input, export, or durable storage (`privacy-redaction-and-learning-boundaries.md:46-53`). It also says every boundary needs scanning and safe input does not imply safe output (`privacy-redaction-and-learning-boundaries.md:57-71`). Fable expansion found 11 bearer-token-shaped candidates and blocked third-party egress pending sanitizer proof (`README.md:383-390`). The same privacy doc requires adversarial tests for cross-tenant token collision, failed deletion, chunk splits, homoglyphs, base64, prompt injection, and other formats (`privacy-redaction-and-learning-boundaries.md:172-181`).
   - Attack/failure: A user or tool result embeds a secret across chunk boundaries, base64, homoglyphs, markdown links, SQL comments, or generated patches. The capture path strips request headers but not model outputs or tool observations. A judge, memory extractor, embedding worker, public dataset exporter, or third-party model then ingests a reusable credential or a prompt-injected instruction that poisons memory/eval output.
   - Reasoning chain: Authorized PII and classified content can remain inside scope, but reusable credentials create direct account compromise. Boundary control must be destination-specific and bidirectional: model/tool outputs can introduce secrets even when inputs are clean.
   - Severity: Critical for credential leakage; high for poisoned memories/evals crossing into releases.
   - Confidence: 0.87.
   - So what: Make the credential-only gate mandatory before every durable capture, model/evaluator/index input, replay artifact, output patch, export, sidecar, and egress. Scan both inputs and outputs. Require typed secret fingerprints rather than raw secrets, adversarial encoding tests, fail-closed sanitizer receipts, and quarantine for any candidate artifact with unresolved secret or injection markers.
   - Status: Kernel candidate.

7. §F7 - Stacking observability, graph, memory, vector, and search products creates a second authority by accident.
   - Evidence: The memory composition matrix says reviewed projects are not stackable production services and recommends one governed relational evidence plane with upstream stores/files as non-authoritative projections (`memory-skill-replay-evidence-composition-matrix-2026.md:9-19`). The architecture review rejects Phoenix/Opik/Langfuse duplication and says Graphiti group keys are not authorization (`trace-intelligence-enterprise-question-composition-audit.md:250-264`). The vector backend decision says external stores such as Redis/Qdrant are not authoritative and must return opaque IDs plus scores only, with stale epoch rejection and revision attachments (`vector-retrieval-backend-decision.md:31-46`). The flywheel archaeology warns generic plugin errors fail open and are unacceptable for auth, privacy, and invocation authorization (`flywheel-gauntlet-codebase-archaeology.md:41-45`).
   - Attack/failure: The team adds Langfuse for evals, Phoenix for datasets, Graphiti for entity memory, Frankensearch/Turbopuffer for retrieval, and a memory service for extraction. Each one has its own IDs, retention, permissions, retries, caches, backups, and deletes. One stale sidecar returns a withdrawn snippet or trains on a deleted trace even though Aurora is correct.
   - Reasoning chain: The adversary does not need a vulnerability if the architecture has many semi-trusted copies. Duplicated lifecycle planes make current authority, deletion, object storage, cache invalidation, and audit receipts combinatorially hard. Operational failure then becomes policy failure.
   - Severity: High for production; medium for isolated offline experiments with content-free or same-scope transformed data.
   - Confidence: 0.84.
   - So what: Adopt external products as concepts, adapters, and test arms, not systems of record. Any sidecar must receive only authorized, credential-clean, scoped chunks or opaque IDs; return opaque IDs/scores only; recheck in Aurora before snippets/ranking/cache; prove tombstone propagation; and degrade before inference. No second authority without a preregistered Aurora/native benchmark failure.
   - Status: Kernel candidate.

8. §F8 - Aggregate analytics can become surveillance even when raw content is hidden.
   - Evidence: The all-together system bans no individual productivity score, hidden manager search, and cross-user private recall (`flywheel-gauntlet-codebase-archaeology.md:88-99`). It requires team and enterprise views to avoid named friction lists, raw nearest-neighbor drilldowns, and one-person-complement aggregates (`trace-intelligence-all-together-system-and-experiment-ladder.md:204-235`). The privacy boundary says derived friction should improve interaction, not infer emotion, health, protected class, or unrelated employee performance (`privacy-redaction-and-learning-boundaries.md:124-132`).
   - Attack/failure: An enterprise admin cannot see raw traces, but can filter by team, project, time window, model, error class, and skill label until the remaining cohort is one person. Repeated exports reveal who worked late, who used a given tool, who failed a task, or which confidential project had an incident.
   - Reasoning chain: Aggregates leak through small cells, complements, longitudinal deltas, and rich filters. Internal admin authority does not automatically create a legitimate purpose for workforce profiling. The more useful the analytics, the easier it is to use as an employee monitoring interface.
   - Severity: High. It can undermine adoption and create legal/HR exposure even if no external breach occurs.
   - Confidence: 0.86.
   - So what: Add an aggregate privacy budget, cohort thresholds, complement suppression, repeated-query ledger, purpose tags, export review, and explicit feature bans. Treat "manager can infer a person from aggregate controls" as a failed release gate.
   - Status: Kernel candidate.

## Standalone Concept Assessment

| Concept | Adversarial use | Defensible role |
| --- | --- | --- |
| ATIF | Launder lossy task steps into canonical evidence; hide auth, branches, and side effects. | Import/export projection with loss receipts and source hashes. |
| OpenTelemetry/OpenInference | Treat span trees as complete evidence or leak content/authority through telemetry backends. | Content-minimized operational projection, latency/topology/debugging, expected-count manifests. |
| AgentRx | Convert invariant violations into confident root-cause or skill diagnoses. | Hypothesis generator and checker proposal framework with sandboxing and alternatives. |
| Signals | Relabel cheap friction selectors as skill, productivity, intent, or morale. | Review queue selector with random audit strata and construct labels. |
| AgentEvals | Treat retrospective stored-trace assertions as proof a changed system will work. | Audit and replay candidate generation, separated from prospective intervention evidence. |
| Phoenix / Opik / Langfuse | Create duplicate dataset/eval/feedback authorities with stale deletion and divergent policy. | Lifecycle inspiration or adapters around Frankengate-owned records. |
| OpenRCA | Narrate causal incidents from correlated traces/logs/metrics without interventions. | RCA hypothesis engine with modality ablations and non-causal wording. |
| Graphiti / MemInsight | Use graph proximity, `group_id`, or entity merge as authorization or identity proof. | Relational/bitemporal fact pattern first; graph backend only after relational benchmark failure. |
| LangMem / Memory Palace / `MEMORY.md` | Mutate live memory silently; export stale or cross-scope memories as personal truth. | Reviewed, cited, scoped, rollbackable memory proposals or destinations. |
| Temporal evidence | If absent, enables future leakage, stale authority, and latest-wins contamination. | Load-bearing canonical valid/system/observed/release/deletion/influence semantics. |
| Cloud dreaming | Generate plausible but unsupported memories, evals, or skills and self-promote them. | Background candidate synthesis with pre-cutoff inputs, independent verification, and rollback. |
| ReasoningBank / Hermes / Jeopard-style skill learning | Train on successes/failures and judge itself, creating self-confirming procedures. | Procedure candidates tested against sealed family-disjoint no-skill/placebo controls. |
| RL environment histories | Pretend flat chat traces are replayable environment state and reward. | Valid only with reset/action/observation/resource/reward attachments and divergence tests. |
| CASS / Doodlestein/CM / claude-history / Prompt-Scope | Import personal/local histories into shared enterprise memory without rights, receipts, or scope. | UX and import ideas for personal exact/fuzzy search, with governed transforms. |
| Frankensearch | Become a shadow search authority with raw content, stale tombstones, or weaker auth. | Default-off sidecar returning authorized opaque IDs/scores only, rechecked by Aurora. |
| Aurora PostgreSQL JSONB/FTS/pgvector | Overtrust local mechanics as proof of production Aurora scale/failover. | Current minimum authority and retrieval substrate, with reversal criteria. |
| VectorChord / pg_textsearch / pgContext / Turbovec / Turbopuffer | Architecture shopping before labels, authority, and deletion are solved. | Replacement candidates only after equal-scope benchmark and operations failure. |
| General embeddings | Hide exact identifiers and policy facts behind semantic similarity. | Candidate lane after exact/structured channels, never identity/cause/skill proof. |
| Enterprise-adapted embeddings | Memorize sensitive traces, learn generated artifacts, and resist deletion. | Later research arm requiring governed labels, hard negatives, deletion/memorization tests, and rollback. |
| Agentic coding/research traces | Infer workforce capability from public/survivor traces or incomplete outcomes. | Parser, replay, retrieval, review-selection, and proposal mechanics substrate. |
| NL2SQL traces | Mistake protocol/tool failure for SQL skill, or let gold/evaluator paths leak. | Strong causal testbed after capability isolation, sealed stages, and protocol remediation. |

## Composition and Non-Composition Matrix

| Composition | Works if | Adversarial failure | Test or containment |
| --- | --- | --- | --- |
| Canonical DAG + OTel/OpenInference | OTel is a content-minimized projection with loss receipts. | Span tree becomes canonical, drops branches, or leaks content/authority. | Expected-trace manifest, drop/duplicate/schema-evolution round trip, content allowlist. |
| Canonical DAG + ATIF | ATIF is export/import only and unsupported fields are explicit. | ATIF reimport erases auth, proposal/execution, valid time, or missingness. | Projection-diff suite and "not canonical" receipt on every imported object. |
| Signals + embeddings | Both are candidate selectors. | Nearest neighbors become "same work," "same person," "same skill gap," or collaboration recommendation. | Human task labels, cohort thresholds, reciprocal opt-in, no named people from vectors. |
| AgentRx + AgentEvals + OpenRCA | Invariants produce hypotheses, evals audit claims, RCA lists alternatives. | A checker violation becomes a causal root-cause label. | Negative controls, modality ablation, intervention/replay requirement for causal wording. |
| Phoenix/Opik/Langfuse concepts + Aurora | Lifecycle concepts are implemented in one authority. | Multiple products own datasets, feedback, evaluator state, or deletes. | One release/deletion ledger; sidecar must be rebuildable projection. |
| Graphiti + temporal evidence | Graph facts are relational, scoped, cited, and bitemporal. | Entity merge or graph proximity leaks cross-scope facts or overwrites contradictions. | Cross-scope traversal, entity-collision, stale-edge, and latest-wins tests. |
| LangMem/Dreams/Memory Palace + `MEMORY.md` | Outputs are reviewed proposals with citations, release, influence, rollback. | Silent memory write influences traces and validates itself. | Influence quarantine, no self-verification, exposure/control, deletion closure. |
| ReasoningBank/Hermes + NL2SQL replay | Procedures are frozen and tested on family-disjoint sealed tasks. | Generator sees hidden/gold data or judges its own procedures. | Capability isolation, no-skill/placebo/expert/trace-mined arms, hidden broker, canaries. |
| RL histories + canonical traces | Environment state and reward basis are first-class. | Flat transcript is treated as replayable state. | Reset/resource/action/observation/reward divergence tests. |
| CASS/Prompt-Scope/Frankensearch + enterprise search | Personal UX runs behind the same authority envelope. | Local/imported index becomes shared evidence or skips deletion. | Import rights manifest, credential transform, tombstone propagation, scope oracle. |
| Aurora + pgvector/FTS | Authority and retrieval remain in one transactionally governed plane. | Local Postgres result is overclaimed as Aurora production proof. | Aurora/RDS Proxy/failover/selective-RLS/concurrency gauntlet. |
| Aurora + external vector/search DB | Sidecar is untrusted, opaque-ID-only, and rechecked. | Sidecar returns snippets/counts/distances or stale deleted vectors. | Stale-epoch rejection, auth-before-distance, tombstone, object-ref, cache, and timing tests. |
| General embeddings + enterprise adaptation | Adaptation is gated by frozen human-labeled hard slices. | Fine-tune learns unreviewed generated memories or private success/failure traces. | Train/test by user/tenant/time, memorization audit, deletion/unlearning plan, rollback. |
| Aggregate analytics + admin views | Purpose, cohort, complement, and query budgets are enforced. | Hidden manager search reconstructs individuals or classified project activity. | Rare-cohort and repeated-query red team, export review, minimum cohorts. |

## Enterprise Questions Answered and Not Answered

- "What happened in my authorized work?" Answerable as deterministic evidence if canonical trace, tool lifecycle, authority, object refs, and deletion state are present.
- "Where did this task get stuck?" Answerable as a trace-local selector or hypothesis. Not answerable as root cause without alternatives, labels, and intervention/replay.
- "What should I review or improve?" Partially answerable as personal/private proposals with citations, status, and contestability.
- "What reusable artifact should this team fund?" Partially answerable as aggregate candidate families after cohort thresholds, purpose limits, human review, and no person drilldown.
- "Who is doing the same work?" Not answerable as named people from similarity. It can become anonymous artifact matching plus reciprocal opt-in.
- "Who lacks a cloud/domain/SQL skill?" Not answerable from traces, retries, failures, judges, or embeddings. It is at most a contestable support-intervention hypothesis.
- "Did a memory, skill, model, prompt, route, or embedding help?" Not answerable from retrospective traces influenced by the artifact. Requires exposure/control and independent outcomes.
- "Should we fine-tune or train enterprise embeddings?" Not currently answered. Requires a frozen failure of exact/structured/general-dense baselines, governed labels, deletion/memorization tests, and measured lift.
- "Can admins inspect full evidence?" Yes inside authorized scope and purpose, with credentials excluded. That does not imply permission for employee scoring, hidden search, raw cross-user recall, or export.

## Empirical Tests and Falsifiers

1. Permission-oracle gauntlet: For every retrieval, cache, graph, memory, eval, export, and telemetry path, compare authorized versus unauthorized outputs over IDs, counts, distances, snippets, cursors, object refs, cache hits, errors, and timing. Falsifier: any distinguishable cross-scope signal not explicitly allowed by policy.
2. Rare-cohort analytics attack: Seed rare terms, one-person complements, deleted projects, classified labels, and repeated-query variants. Falsifier: an analyst can reconstruct a person, project, or restricted trace from aggregates or exports.
3. Projection-loss attack: Round-trip traces with denied tool calls, hidden branches, fallback attempts, failed side effects, delayed observations, and missing events through ATIF/OTel/AgentEvals. Falsifier: any downstream consumer can assert execution, causality, or completeness without a loss receipt.
4. Memory poisoning and self-validation test: Inject a plausible but wrong memory/procedure/dream with valid-looking citations, expose it to a subset, and verify descendant traces are excluded from independent validation. Falsifier: the artifact promotes itself through influenced evidence or judge agreement alone.
5. Skill-gap causal negative control: Construct tasks where failure is caused by permission, stale docs, model/tool protocol, hidden schema, quota, or environment, not skill. Falsifier: any dashboard labels a person/team skill gap without abstention and alternatives.
6. Credential boundary suite: Use authorization headers, virtual keys, DSNs, signed URLs, provider tokens, private keys, chunks, base64/base64url, hex, homoglyphs, markdown links, SQL comments, model outputs, and generated patches. Falsifier: any reusable secret enters durable trace, model, evaluator, index, replay, memory, export, or sidecar input.
7. Sidecar stale-delete test: Populate a sidecar, delete/withdraw/reclassify source evidence, revoke membership, and query during reader lag and rebuild. Falsifier: sidecar returns stale IDs, snippets, counts, vectors, distances, or cache hits.
8. NL2SQL intervention test: After protocol remediation, run no-skill, length-matched placebo, expert seed, and trace-mined procedure on family-disjoint tasks with sealed stages. Falsifier: no paired lift, protocol failure above gate, security violation, or effect only after future/hidden leakage.
9. Aurora reversal test: Run concurrent ingest, personal history, selective RLS search, embedding, deletion, aggregate, failover, and analytics isolation on Aurora/RDS Proxy. Falsifier for Aurora-first: preregistered recall/latency/deletion/isolation SLO failure after bounded mitigations.
10. Embedding adaptation test: Freeze human-labeled positives/hard negatives by user, tenant, time, project, and influence exposure. Falsifier for adaptation: general hybrid meets target, adapted model memorizes private content, regresses exact identifiers, violates deletion, or lacks meaningful lift.

## Architecture Consequences

- Keep one canonical governed evidence DAG. ATIF, OTel/OpenInference, AgentEvals datasets, `MEMORY.md`, Frankensearch indexes, graph projections, and vector stores are not authority.
- Every derived artifact carries source IDs, authority envelope, purpose, classification, privacy receipt, deletion lineage, valid/system time, release version, and influence exposure.
- Authorize before candidate exposure: no IDs, counts, distances, snippets, graph neighborhoods, reranker inputs, cache keys, object refs, telemetry, aggregates, or exports before current authority is established.
- Treat memory, skill, dream, procedure, route, model, embedding, and eval outputs as proposals until reviewed, independently verified, exposed under control, and rollbackable.
- Separate inference from flywheel work. Analytics, embedding, eval, memory extraction, sidecars, and export workers must degrade or drop metadata before they impair request serving.
- Implement contestability as data model, not copy. Trace labels need `candidate`, `insufficient`, `contested`, `corrected`, `verified`, `released`, `withdrawn`, `deleted-source-blocked`, and adjudication lineage.
- New persistent systems require reversal evidence. A graph DB, vector DB, search sidecar, observability product, or custom embedding is justified only after the one-authority architecture fails a named benchmark under equal authority/deletion controls.

## Risks Identified

- Critical: Person-level skill, productivity, collaboration, or performance conclusions from similarity, Signals, judge labels, retries, or failures.
- Critical: Credential leakage into durable traces, embeddings, model/evaluator inputs, replays, memories, exports, or sidecars.
- Critical: Cross-scope side channels through ANN/FTS/graph/cache/counts/distances/timing/object refs before authorization.
- High: Circular validation where memories, skills, prompts, routes, or embeddings influence traces that later validate them.
- High: Projection loss turning tool proposals, denials, fallback attempts, or missing branches into completed side effects and causal narratives.
- High: Aggregate analytics enabling hidden manager search, rare-cohort reconstruction, classified-project discovery, or one-person complements.
- High: Duplicate authorities across Phoenix/Opik/Langfuse/Graphiti/LangMem/search/vector systems causing stale deletion and inconsistent policy.
- Medium-high: Overclaiming local PostgreSQL, synthetic, public, or mechanics results as Aurora production, enterprise transfer, or outcome benefit.
- Medium-high: Custom embeddings or fine-tunes learning unreviewed generated artifacts, stale memories, or private traces without deletion closure.

## Recommendations

1. P0: Install a forbidden-inference gate in product, API, exports, and documentation: no person-level skill, productivity, collaboration, loyalty, morale, or performance claims from trace intelligence.
2. P0: Build the permission-oracle and rare-cohort attack suites before any team/admin retrieval, graph, aggregate, memory, or export release.
3. P0: Make credential-only transformation and output rescanning mandatory at every capture, durable storage, model/evaluator/index, replay, memory, export, and sidecar boundary.
4. P0: Require projection loss receipts for ATIF, OTel/OpenInference, AgentEvals, datasets, `MEMORY.md`, and any external tool output. No projected object can be promoted to canonical evidence.
5. P1: Add influence quarantine to the schema before releasing memories, skills, dreams, procedures, route changes, model changes, embeddings, or rerankers.
6. P1: Launch personal history, exact/structured search, deterministic trace-local Signals, and cited proposal queues before team dashboards.
7. P1: Keep Phoenix, Opik, Langfuse, Graphiti, LangMem, external vector/search systems, custom embeddings, and fine-tuning as experimental arms until a preregistered native failure exists.
8. P1: Repair NL2SQL protocol failure before running skill-learning claims. Preserve the null/mechanics result as a blocker, not a footnote.
9. P2: Run a consented enterprise adjudication study for same-task, friction type, environmental blocker, support opportunity, and verified outcome labels before cross-user features.

## New Ideas and Extensions

- Adversarial insight card: Every insight shows its claim class, allowed action, disallowed interpretations, source count, cohort floor, authority scope, deletion status, influence exposure, and nearest alternative explanations.
- Influence quarantine ledger: A built-in table marking every trace touched by a memory, skill, dream, route, model, prompt, embedding, eval, or retrieval release, automatically excluding descendants from naive validation.
- Permission-oracle diff harness: A synthetic and live-safe suite that compares unauthorized and authorized queries over rows, scores, snippets, counts, cursors, caches, object refs, exports, and timing.
- Collaboration escrow: Cross-user "same work" never names people directly. It creates a reusable artifact first, then supports reciprocal opt-in introductions with source redaction and contestability.
- Cause-card negative controls: Every root-cause or support hypothesis must list and test non-skill causes: permission, docs, model, route, tool, protocol, quota, environment, incident, stale schema, and exploration.
- Projection-loss scoreboard: Each external format or product gets a visible score for identities, branches, auth, tool lifecycle, side effects, time, deletion, and missingness retained.
- Aggregate attack budget: Team/admin analytics maintain repeated-query ledgers, complement suppression, and red-team canaries that block releases when inference risk accumulates.
- Secret-poison quarantine: Candidate memories/evals/patches/procedures with unresolved prompt-injection or secret markers are stored only in a quarantined review lane, never in ordinary search or training.

## Assumptions Ledger

- Assumption: The deployment remains an internal enterprise tool where authorized users, teams, and admins may inspect full PII/classified content inside scope, while reusable credentials are excluded from the ordinary trace plane.
- Assumption: Several-hundred-GB scale and Aurora-first are current constraints, not proof that Aurora can satisfy every future workload.
- Assumption: Project documents and summaries are treated as primary project evidence; many limitations are owner-acknowledged and not rediscovered here.
- Assumption questioned: A vector neighbor is the same work, same identity, same skill need, or socially useful collaborator.
- Assumption questioned: A failed or long trace means low skill rather than permission, tooling, protocol, model, incident, or exploration.
- Assumption questioned: A memory or skill validated by later traces is independent of its own exposure.
- Assumption questioned: Hiding raw content is enough to prevent surveillance if aggregates, counts, distances, and repeated filters remain available.
- Assumption questioned: Adding a specialized memory/graph/vector/eval product increases safety or quality without creating another authority.

## Questions for Project Owner

1. Which outputs are categorically forbidden even for enterprise admins: named skill gaps, productivity scores, hidden manager search, rare-cohort exploration, collaboration matching, or inferred morale/intent?
2. What cohort floors, complement suppression rules, and repeated-query budgets will apply to team and enterprise aggregates?
3. Who adjudicates contested task boundaries, support hypotheses, memory proposals, skill labels, and source-deletion conflicts?
4. Is reciprocal opt-in mandatory before revealing a person behind a cross-user pattern?
5. Which side channels count as unauthorized disclosure for this organization: distances, counts, latency, object refs, cache hit/miss, cursor length, or "unavailable" errors?
6. What is the exact reversal threshold for leaving Aurora, adding a graph/vector/search sidecar, or training enterprise embeddings?
7. What memory/procedure destinations are allowed after source deletion or reclassification, especially for exported `MEMORY.md` files?
8. What outcome would justify a causal "helped" claim: task success, fewer turns, lower cost, shorter latency, fewer corrections, user-rated usefulness, reviewer agreement, or downstream business result?

## Points of Uncertainty

- I did not browse external current product docs; assessment of third-party systems is based on project records and the dispatch scope, not fresh vendor capability claims.
- The true private enterprise distribution, legal constraints, employee-representative requirements, and organization culture are unknown; these can change severity and launch policy.
- Current experiments are mostly public, synthetic, gated, local, or mechanics-oriented. Live enterprise labels and prospective outcomes remain the biggest unknown.
- Aurora/RDS Proxy/failover/selective-RLS behavior under production concurrency remains unproven in the evidence read here.
- Corrected v2 memory primitives may remove several pilot confounds, but there is no corrected model-quality or utility result yet.
- Human label reliability for "same work," "productive exploration," "support opportunity," and "root cause" may be lower than product expectations.

## Agreements and Tensions with Other Perspectives

- Agreement with I4 Perspective-Taking: The I4 output argues that adoption depends on personal-first, artifact-first, contestable workflows and that manager views need artifact funding rather than "who is deficient" claims (`MODE_OUTPUT_I4_PERSPECTIVES.md:3-21`). H2 strengthens this into an adversarial rule: if a manager can convert a trace insight into a person label, assume it will happen and test/block it.
- Agreement with L2 Debiasing: The L2 output identifies framework collection bias, metric relabeling, public-corpus survival bias, and circular feedback as the main bias traps (`MODE_OUTPUT_L2_DEBIASING.md:18-34`, `MODE_OUTPUT_L2_DEBIASING.md:63-70`). H2 treats the same traps as attack surfaces: a biased metric or duplicate framework becomes a practical path to false conclusions or stale access.
- Expected agreement with A1 Deductive: Proposal is not execution, retrieval is not identity, association is not cause, and authorization must be a premise for every derivative. H2 supplies the abuse cases when those implications are blurred.
- Expected agreement with F1 Causal: Skill, memory, route, model, and prompt benefits are intervention hypotheses, not retrospective trace facts. H2 emphasizes that confident causal wording is itself a product vulnerability.
- Tension with F7 Systems Thinking: F7 may value richer loops and leverage points. H2 accepts loops only after influence quarantine, deletion closure, and exposure/control gates exist; otherwise every loop is a self-validation attack.
- Tension with G6 Multi-Criteria: A weighted decision matrix may prefer a feature with high utility and moderate risk. H2 would veto features whose failure modes create employee surveillance, credential leakage, or cross-scope disclosure, even if expected utility is high.
- Tension with B3 Bayesian: Bayesian incremental evidence can be useful, but showing weak posterior skill/support hints to managers can operationalize them as facts. H2 prefers withholding socially dangerous low-certainty inferences.

## Confidence

Overall confidence: 0.87. Confidence is high that similarity-to-identity, authorization side channels, projection loss, circular memory/skill loops, credential leakage, and surveillance aggregates are realistic failure modes because the project documents repeatedly identify the same boundaries and negative results. Confidence is lower on likelihood in the actual enterprise deployment because live policy, UI, organization culture, and production workloads are not yet known. The analysis would change most if a prospective enterprise study showed safe, contestable, non-surveillance cross-user utility under strict privacy budgets, or if Aurora/native retrieval failed a frozen equal-authority benchmark badly enough to justify a sidecar without weakening deletion and scope.
