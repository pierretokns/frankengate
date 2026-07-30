# FrankenGate trace intelligence: composed feasibility and failure analysis

**Status:** architecture decision input, not an implementation claim
**Date:** 2026-07-29
**Scope:** personal/team/enterprise history, retrieval, diagnosis, evals, memory, and pattern mining
**Confidence:** 0.84 for the staged architecture; below 0.60 for unbenchmarked diagnosis,
memory utility, causal recovery, and enterprise-learning claims

This report reconciles the earlier trace-mining, storage, retrieval, embedding,
evaluation, and memory research into one buildable plan. It distinguishes mechanisms
implemented upstream from claims FrankenGate has actually validated.

The question-by-question composition audit in
`docs/roadmap/research/trace-intelligence-enterprise-question-composition-audit.md`
is the normative follow-up for deciding which concepts work together, which claims
need labels or experiments, and whether the combined design answers the intended
enterprise questions.

The database exit-path, canonical tool-call, Anthropic Dreams, and frontier-lab
reflection review is maintained in
`docs/roadmap/research/log-trace-vector-database-and-reflective-learning-review.md`.
That review is normative when selecting a log/trace/vector store or defining a tool
trajectory.

## Decision

Build an authoritative evidence system, not a bundle of observability products:

```text
immutable source event
  -> canonical trajectory DAG plus loss manifest
  -> transaction-local authority and forced RLS
  -> epoch-bound rebuildable projections
  -> authorized exact/lexical/vector retrieval
  -> deterministic signals
  -> evidence-backed diagnosis hypothesis
  -> reviewed eval or memory proposal
  -> privacy-safe team/enterprise aggregate
```

Every arrow is a schema, authorization, deletion, and observability boundary. Aurora
PostgreSQL remains authoritative. Search engines, graphs, caches, datasets, memories,
and exports are derived views with source lineage and current-authorization checks.

Build first: personal history, exact/FTS search, cheap deterministic signals, evidence
previews, and proposal-only eval/memory creation. Filtered ANN, team similarity,
temporal facts, judges, and enterprise patterns graduate independently after their
correctness and privacy gates pass.

Use these evidence labels: **proven upstream**, **implemented upstream without outcome
evidence**, **limited benchmark**, **FrankenGate hypothesis**, and **FrankenGate
validated**. A feature list is not an architecture proof.

## Normative deployment boundary

The architecture for the current several-hundred-GB workload is **Aurora PostgreSQL
first**. Keep normal history, search, analysis metadata, evals, memories, and compact
evidence in that one authority. The existing S3 path is a conditional large-blob/cold
tier enabled only when a measured payload class justifies its additional durability,
reconciliation, hydration, and deletion boundary. The Go gateway and background
analytics/eval worker are compute clients, not additional data systems. All projects
below are sources of algorithms, contracts, tests, and UX concepts—not services to
deploy.

Do not add ClickHouse, OpenSearch, Qdrant, ParadeDB, VectorChord, pgContext,
Turbopuffer, Phoenix, Opik, Langfuse, or a graph database. First use bounded typed
tables, FTS/trigram, sparse task-level pgvector, preaggregates, and bounded asynchronous
jobs. If Aurora still fails a preregistered requirement, evaluate replacing it
with one managed extensible PostgreSQL service. A permanent second query database is
the final escape hatch and requires explicit approval of the duplicated
authorization, deletion, backup, recovery, and operations burden.

The normative decision, cost model, failure gates, and delivery sequence live in
[the minimal architecture review](./log-trace-vector-database-and-reflective-learning-review.md).

## Upstream trace, evaluation, and memory concepts

| Project | Mechanism that makes it useful | Take | Boundary and required gate |
|---|---|---|---|
| [AgentRx](https://github.com/microsoft/AgentRx) | A trajectory projection feeds invariants before a judge localizes and classifies the decisive step. | Canonical projection, revisioned invariants, violation log, taxonomy, evidence-linked diagnosis. | Its IR is simpler/lossier than our DAG and its dynamic checker executes generated Python. Use a declarative DSL or hardened sandbox. Require human-labeled temporal holdout and invariant-only/judge-only/combined ablations. |
| [Signals](https://arxiv.org/abs/2604.00356) | Cheap rephrasing, stagnation, loop, execution, and disengagement features select informative traces before expensive review. | Versioned deterministic detectors over every trace and budgeted selection. | Reported 82% informative yield versus 54% random is one controlled study, not enterprise diagnosis accuracy. Signals are selectors, never labels; retain a stratified random audit sample. |
| [AgentEvals](https://github.com/agentevals-dev/agentevals) | Exact, ordered, unordered, semantic, and custom assertions operate over stored OTel trajectories without rerunning the agent. | Trace-to-regression adapter, matcher semantics, evaluator registry, trace-only assertion class. | A stored trace cannot prove a changed system or external side effect. Separate retrospective audit from sandboxed prospective replay. Test matchers, known mutants, determinism, redaction, and scope. |
| [Phoenix](https://github.com/Arize-ai/phoenix) | Annotation becomes versioned datasets and experiments; OpenInference adds AI semantics to OTel. | Trace -> annotation -> immutable dataset revision -> experiment lifecycle. | Adopt the lifecycle, not Phoenix as our multi-tenant authority. Dataset membership must inherit source authority and deletion lineage; replay side effects must be fenced. |
| [Opik](https://github.com/comet-ml/opik) | Online rules sample/score production traces and connect findings to datasets and experiments. | Rule model, sample/cost budgets, immutable evaluator revisions, calibration sets. | Its ClickHouse/MySQL/Redis/MinIO/Python-service topology is not an Aurora proof. Judges need lag, cost, false-alert, drift, and worker-isolation SLOs. |
| [Langfuse](https://github.com/langfuse/langfuse) | Sessions, feedback scores, datasets, and prompt experiments make production examples reusable. | Feedback provenance, target attribution, reviewed production examples. | Sessions are not necessarily tasks. Feedback may target answer, trajectory, latency, UI, or outcome; never collapse these into one truth label. |
| [Graphiti](https://github.com/getzep/graphiti) | Provenance-bearing episodes create temporally valid entity/fact edges and hybrid retrieval. | Bitemporal facts, contradiction types, source lineage, typed entities, incremental revisions. | It requires a graph backend; `group_id` is not DB-enforced authorization. Benchmark relational facts first and forbid cross-scope traversal/entity merge. |
| [LangMem](https://github.com/langchain-ai/langmem) | Hot-path and background managers extract, consolidate, update, and delete memories. | Candidate extraction and destination adapters. | Namespace templates are not RLS. Automatic update/delete is unsafe here. Ship proposal, preview, edit, reject, expiry, contradiction, and rollback before any injection. |
| [MemInsight](https://github.com/amazon-science/MemInsight) | Entity- and conversation-centric attributes add structured retrieval beyond embeddings. | Versioned attributes for people, systems, tasks, constraints, outcomes, and validity. | Its small research corpus does not establish corporate transfer; licensing needs review. Require corporate ontology, sensitive-attribute, calibration, and entity-resolution tests. |
| [claude-history](https://github.com/raine/claude-history) | Field-aware lexical/fuzzy retrieval blends with embeddings while retaining quoted exact constraints and evidence previews. | Exact-first hybrid ranking, tool-output indexing, compact previews. | A local single-user tool does not prove RLS, enterprise scale, or deletion. Run lexical/vector/hybrid ablations over corporate identifiers and jargon. |
| [Prompt-Scope](https://github.com/monapdx/Prompt-Scope) | Local import, deterministic categories, caching, and lazy analysis support personal reflection. | Private analysis UX, inspectable categories, resumable import. | Local execution supplies its privacy. Truncation/topic rules can bias results; this is not evidence for firmwide mining. |
| [conversation extractor](https://github.com/slyubarskiy/chatgpt-conversation-extractor) | Defensive parsing, schema-evolution/failure logs, and resumable conversion handle messy exports. | Adapter registry, quarantine, import receipt, raw provenance, reconciliation. | It deliberately linearizes the active path and filters hidden/tool/revision data. It does **not** prove branch preservation. Require raw-to-canonical node/edge inventories and loss receipts. |
| [OpenRCA](https://github.com/microsoft/OpenRCA) | KPI time series, dependency graphs, and logs remain distinct retrieval modalities joined for RCA. | Separate metric/log/graph/text evidence joined by IDs, clocks, topology, and uncertainty. | It is a benchmark, not production authorization. Run modality ablations and clock/topology fault injection; call output a hypothesis, not cause. |
| [Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) | An asynchronous synthesis reads an existing memory store and selected sessions, then creates a separate candidate store without modifying the input. | Immutable candidate-memory releases, source-session manifests, diff/review/discard/promote and rollback. | It is a research preview, not a truth engine. “Latest” can incorrectly erase context-specific contradictions; require citations, policy/deletion closure and held-out validation. |
| [ReasoningBank](https://www.research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/) | Successful and failed trajectories are distilled into reusable reasoning strategies, with parallel and sequential trials providing contrast. | Candidate procedural memories from verified outcomes and failure/success contrasts. | Self-judgment and append-only extraction can self-confirm errors. Add provenance, dedupe, contradiction, expiry, independent outcomes and human review. |
| [Bloom](https://www.anthropic.com/research/bloom) | Understanding, scenario ideation, simulated user/tool rollouts, judgment and meta-judgment generate varied behavioral evals from a versioned seed. | Candidate eval variation after a behavior is reviewed; retain seeds, transcripts, model revisions and human calibration. | Synthetic prevalence is not production prevalence. Run in an isolated harness with no real credentials or unrestricted corporate data. |
| [OpenAI self-improving tax agents](https://openai.com/index/building-self-improving-tax-agents-with-codex/) | Full production provenance and expert corrections become structured findings, targeted evals and bounded engineering tasks. | Capture proposed value, source/provenance, expert correction and terminal outcome separately; group only adjudicated recurring failures. | A difference can be preference or workflow noise rather than model error. Do not automate the adjudication step. |

Phoenix, Opik, and Langfuse overlap. FrankenGate owns one lifecycle and exports through
adapters. AgentRx, OpenRCA, and semantic judges likewise remain distinct: deterministic
trajectory diagnosis, cross-modal correlation, and semantic judgment must not each
assign an unqualified final “root cause.”

## Earlier storage, search, and learning concepts

| Concept | What makes it work | Role and decision |
|---|---|---|
| Aurora PostgreSQL | Transactions, relational constraints, typed joins, managed HA and backups. | **Authority foundation.** Isolate inference from ingestion, HNSW, aggregation, deletion, and failover reconnects with separate pools, quotas, and workload gates. |
| PostgreSQL RLS | Policies enforce access at the row boundary; `FORCE RLS` closes ordinary owner bypass. | **Security kernel, not yet complete.** Current `analytics-rs` is tenant-only. Add principal, team, purpose, classification, consent, policy/auth/deletion epochs; test owner roles, savepoints, pool reuse, stale readers, integrity-error channels, and every partition. |
| JSONB | Retains bounded provider-specific long-tail data through schema evolution. | Use only beneath typed authoritative columns. Tenant, principal, scope, classification, purpose, retention, and epochs are never JSONB-only. Promote hot/security fields and avoid unbounded payloads/broad GIN indexes. |
| PostgreSQL FTS/trigram | Transactional lexical indexes preserve IDs, errors, acronyms, tool names, and lineage. | **Build first.** It is exact/lexical fallback and should not be mislabeled BM25. Preserve code/corporate terms with suitable analyzers. |
| [pgvector](https://github.com/pgvector/pgvector) | Co-locates vectors with RLS rows; exact scan supplies an oracle and HNSW/IVFFlat supply ANN. | **Conditional P1.** Aurora supports it, but selective RLS/post-filtering can silently lose recall. Require exact authorized oracles, iterative/overfetch/exact fallback, and capacity tests. |
| [VectorChord](https://github.com/tensorchord/VectorChord) | Native compressed, disk-oriented vector indexing and exact reranking. | **Concept/reference only.** It is a native extension depending on pgvector and is not in Aurora's supported extension set. Consider it only as part of a complete one-database Aurora replacement after a proven failure. |
| [pgContext](https://github.com/Evokoa/pgContext) | New pgrx context engine targets filter-aware ANN, exact MVCC/RLS recheck, hybrid RRF, grouping, and compaction. | **Concept/reference only.** It is very new, PG17/18-oriented, operationally immature, and not Aurora-packaged. Its ideas may inform our SQL and tests; it is not a launch dependency or sidecar. |
| [Turbopuffer](https://turbopuffer.com/docs/architecture) | Object-backed durable search with dense/sparse/text filters and disaggregated compute targets very large corpora. | **Reject for the current architecture.** It is not OSS server infrastructure or an RLS authority and adds network, namespace, branch-deletion, and consistency boundaries. |
| ClickHouse/columnar | Compression and vectorized scans make broad fleet analytics efficient. | **Reject for the current architecture.** Preaggregate in Aurora and run rare bounded scans from S3. A second analytics authority is not justified at this scale. |
| CASS/Doodlestein/CM | Local session discovery, exact/fuzzy recall, bookmarks, compact evidence, and agent-friendly fielded queries. | Adopt query/UX concepts and import adapters, not SQLite/local trust as shared authority. Never assume local raw histories can be uploaded globally. |
| FrankenSearch | Tantivy-style lexical search, dense fusion, reranking, compact local indexes, progressive results. | **Research-only/default-off sidecar.** It receives sanitized authorized chunks and tombstones, never participates in gateway readiness, and must pass auth/deletion/license/failure-isolation gates. |
| Base embeddings | Dense encoders cheaply recover broad semantic paraphrase. | Baseline candidate generator only. MiniLM-class models miss corporate acronyms, IDs, code, tools, and fine distinctions. Vectors are lossy derived sensitive data. |
| Rerankers | Cross-encoders/late interaction reread a bounded query-document set for precision. | Optional second stage over already-authorized candidates. They cannot restore candidates ANN omitted and must never see forbidden text. |
| Domain adaptation | Contrastive positives/hard negatives teach organization-specific vocabulary and task distinctions. | P2 offline research on a consented, purpose-limited, versioned corpus. Split by user/tenant/time; guard sampling bias, false negatives, memorization, drift, and rollback. |
| Clustering | Density/community/topic methods expose recurring tasks and friction without a fixed taxonomy. | Shadow-only candidate insights with exemplars and stability. Labels can hallucinate coherence; small clusters identify people; release changes move clusters. Never employee ranking. |
| `MEMORY.md` | Human-readable durable guidance is portable and editable by a harness. | Approved export destination, never canonical storage. Every proposal needs citations, scope, validity, expiry, destination receipt, and honest deletion semantics for external copies. |

[AWS's Aurora extension matrix](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.Extensions.html)
currently supports pgvector but not pgContext, VectorChord, or the assessed native
columnar extensions. These are backend alternatives, not a stack. Similarly, exactly
one layer owns fusion, pagination, score normalization, and progressive search.

## Canonical contracts and invariants

Keep a raw immutable envelope and a canonical event/edge DAG, then produce versioned
OTel, conversation-branch, request/provider-attempt/fallback, tool trajectory,
metric/log/topology, temporal-fact, and eval projections. Do not flatten unlike
structures into one span table.

The tool trajectory distinguishes a model proposal, authorization/confirmation
decision, execution attempt, observation delivered to the model, independently observed
state delta, and later use or misinterpretation of the result. It covers MCP,
provider-native/hosted, browser, computer, shell, code, file, memory, retrieval and
subagent tools. Rejected, malformed, skipped, timed-out and cancelled calls are evidence
too. A transcript claim that a side effect occurred is never the outcome.

Every canonical or derived object carries typed scope, classification, purpose, source
IDs/hashes, adapter/transform/model/evaluator revision, event/receive/valid/transaction
time, authorization/policy/membership/deletion epochs, and an explicit loss/derivation
manifest.

The core safety theorem is:

```text
Returned(authority, object)
  => trusted(authority)
  && allowed(authority, object)
  && current_epochs(authority, object)
  && all_transitive_sources_not_logically_deleted(object)

scope(derived) <= intersection(scope(source) for every transitive source)
```

Scope broadening requires audited copy-on-promote with a new artifact ID. Generated
memory is a proposal. A trace influenced by that memory cannot independently
corroborate it. A stored-trace eval proves historical captured properties only.
Deletion creates logical non-return over every descendant immediately; physical
erasure follows a declared SLO.

Keep deterministic observations, terminal outcomes, feedback, human annotations,
diagnosis hypotheses, evaluator scores, recovery associations, causal results, and
memory proposals as distinct record types.

## Authorization and retrieval

Every protected operation starts a transaction, installs one server-resolved typed
authority envelope locally, verifies its epochs, performs the operation, and closes the
transaction. Missing/malformed authority fails closed with a distinguishable internal
reason; it must not look like an empty history.

The runtime role is `NOBYPASSRLS`, does not own protected tables, and cannot call
unreviewed `SECURITY DEFINER` code. Reader queries require a policy/deletion watermark
at least as current as the request or fall back to the writer. Savepoint rollback must
not erase the installed scope.

Retrieval is:

```text
typed authorization/classification
  -> quoted/exact constraints
  -> FTS/trigram candidates
  -> optional pgvector candidates
  -> one fusion owner
  -> optional authorized reranker
  -> current-epoch recheck
  -> compact evidence preview
```

Internally distinguish `complete`, `insufficient_authorized_candidates`,
`budget_exhausted`, `index_stale`, and `no_authorized_evidence`. ANN may iterate,
overfetch, or fall back to bounded exact search; it may never relax security filters.
Authorize before exposing IDs, counts, distances, snippets, timing-sensitive
expansion, cache behavior, cluster sizes, exports, or object URLs.

## Questions the product should answer

For an individual:

- What did I ask, and which tools, models, routes, and evidence ran?
- Which of my tasks repeat, stall, loop, rephrase, or need several attempts?
- At the first verified success, what changed from earlier attempts?
- Which real trace should become an eval, and should it be exact, ordered, unordered,
  semantic, snapshot, dry-run, or live?
- What cited guidance is worth proposing to my approved harness memory?

For a team:

- Which explicitly shared/consenting members attempt materially similar tasks?
- Which failures and recoveries recur in a sufficiently large authorized cohort?
- What eval, runbook, prompt, tool, dataset, or memory artifact should be deliberately
  promoted to the team?
- Which apparent pattern disappears when sliced by environment, role, model, or time?

For the enterprise:

- Which privacy-safe task/failure families justify platform investment?
- Which policies, tools, models, routes, or knowledge sources correlate with verified
  outcomes?
- Which candidate evals cover the largest recurring failures?
- Which knowledge gaps can be fixed without exposing or ranking employees?

Aggregate access never implies raw-evidence access. Apply minimum cohorts,
complementary-cell suppression, repeated-query accounting, contribution bounds,
purpose controls, and coarse/noisy release where appropriate.

### Rights, consent, and contestability

“User-owned” is not one permission. A trace may combine the user's prompt, employer
IP, third-party data, tool output, and classified evidence. Model subject visibility,
artifact stewardship, organizational control, export/share rights, and training
permission separately. The right to view never implies the right to export, promote,
or train.

Employment consent alone is structurally weak. Team/enterprise analysis needs a
permitted purpose, non-retaliation/opt-out policy, retention limits, and applicable
legal or employee-representative review. Analytics permission never implies
fine-tuning permission. Ban productivity inference and its proxies—manager drilldown,
rare-cohort counts, friction rates, and team comparisons—not only an explicit
“employee score.”

Cross-user matching is anonymous and brokered by default. Reveal a reusable pattern
first; identify people only through reciprocal opt-in. Users can inspect evidence,
dispute task boundaries and failure labels, correct facts, reject memories/evals, and
observe correction/deletion propagation. Preserve the original claim and the
appeal/adjudication record.

### Temporal and causal semantics

Store at least source occurrence, receipt, fact-valid, transaction, projection
watermark, and policy/auth/deletion time. Historical/as-of analysis selects old facts
by valid/transaction time but always authorizes with current membership, purpose,
classification, and deletion state. Late data produces revisioned `provisional`,
`final_through=<watermark>`, or `revised` outputs; it never silently mutates a promoted
eval or memory.

A usable projection watermark is a tuple—not a timestamp—covering source sequence,
policy epoch, deletion epoch, and model/index release. Long queries, streams, cursors,
exports, and promotions recheck authorization before bytes leave the service. Restored
backups remain quarantined until an independently retained revocation/deletion ledger
has replayed and all projections have rebuilt.

Recovery deltas are observational by default. To call a delta causal, rerun the failed
state unchanged, add only the proposed delta, remove it from the successful state, and
repeat across seeds and relevant releases. Capture model/provider, prompt, route,
fallback, tool/permission, retrieval, governance, deployment, region, time, and incident
state as confounders. Memory utility likewise requires randomized on/off or faithful
counterfactual testing with success, turns, latency, cost, correction, anchoring, stale,
contradictory, and adversarial-memory outcomes.

## Cross-layer FMEA

| Cascade | S / detection difficulty | Required control |
|---|---:|---|
| Import drops/linearizes branches -> wrong trajectory -> wrong diagnosis -> bad eval/memory | 5 / 5 | raw source, adapter fixtures, quarantine, loss receipt |
| OTel drift changes task boundaries without product change | 4 / 5 | retain original attributes and version canonical adapters |
| Fallback pipeline reruns become multiple “user attempts” | 4 / 4 | distinct task/request/agent-attempt/provider-attempt/fallback IDs |
| Missing authority fails open in one worker/cache/export | 5 / 4 | one mandatory typed wrapper, default deny, negative tests |
| Missing authority fails closed but appears as “no results” | 4 / 5 | separate malformed/denied/zero-eligible/zero-hit metrics and canaries |
| Revocation reaches rows but not vectors/caches/facts/evals/memories/URLs | 5 / 5 | source lineage, epochs, query-time reauth, tombstone priority |
| Selective RLS removes ANN neighbors and biases results | 4 / 4 | exact oracle by scope/selectivity; bounded fallback |
| Entity resolver merges similarly named people/repos/systems | 5 / 5 | typed namespaces/stable keys; similarity proposes, never executes |
| Stored prompt injection controls judge/replay/memory worker | 5 / 5 | treat traces as data, strict schemas, no tools/credentials, sandbox, safe rendering |
| Memory extraction creates future traces that self-confirm it | 5 / 4 | proposal-only, intervention lineage, independent corroboration |
| Signal sampling erases quiet cohorts from training/evaluation | 4 / 5 | random baseline and recorded sampling propensity |
| Judge/model revision drifts while dashboards imply continuity | 4 / 5 | immutable revisions, calibration set, bridge studies |
| Cross-user similarity or aggregates enable surveillance/differencing | 5 / 5 | opt-in promotion, cohort/query controls, no employee ranking |
| HNSW/embedding/analysis saturates Aurora, causing more failures and analysis work | 5 / 3 | work credits, quotas, separate pools, dedupe, degrade analytics first |
| Failover reconnect storm violates deletion/revocation SLO | 5 / 4 | bounded jitter, lease fencing, pause noncritical workers |
| Multimodal correlation is reported as root cause | 4 / 4 | alternative hypotheses, counterfactuals, human approval |

## Falsifiable gates

1. **Canonical ingestion:** every expected source node, edge, branch, role, tool result,
   and hash is represented or explicitly quarantined; re-import hashes match.
2. **Authorization:** a separately generated permission oracle equals all rows, IDs,
   counts, distances, snippets, cache/export/object results across pool, savepoint,
   stale-epoch, reader-lag, partition, error, timing, and failover cases.
3. **Derived lifecycle:** one source deletion/reclassification makes every FTS/vector
   entry, cache, fact, insight, eval, memory, aggregate, object, and managed export
   immediately non-returnable, with bounded physical convergence receipts.
4. **Retrieval:** exact identifiers pass 100%; lexical/vector/hybrid/reranked paths run
   on identical authorized queries; ANN meets recall/nDCG/latency floors at the most
   selective scopes or falls back.
5. **Diagnosis/recovery:** two blinded annotators plus adjudication and `insufficient
   evidence` establish temporally held-out task boundaries, decisive steps, categories,
   and recovery associations. Causal wording requires replay/intervention.
6. **Eval/memory:** evals declare audit versus replay semantics and catch known mutants;
   memory remains cited proposal-only, contradiction-aware, editable, expiring, and
   deletion-linked until shadow utility shows no critical harm.
7. **Enterprise privacy:** synthetic cohort and repeated-query attacks cannot recover
   individuals or classified material; no performance-ranking workflow ships.
8. **Aurora operations:** concurrent ingest/history/search/embed/aggregate/delete/
   rebuild/failover stays within connection, inference-p99, recall, queue-age, and epoch
   budgets. Benchmark direct bounded pools against RDS Proxy rather than assuming
   multiplexing; PostgreSQL `SET` behaviors can pin sessions.
9. **Temporal lifecycle:** late-data revision, member removal mid-query/mid-stream,
   stale cursors, deletion during ANN, old-backup restore, stale-index rollback, legal
   hold/release, and model-trained-on-deleted-source cases pass explicit bounded SLOs.
10. **Causal claims:** observational recovery and root-cause labels stay disabled unless
    add/remove interventions, replay-fidelity, propensity/coverage, negative controls,
    and temporal holdouts meet preregistered thresholds.

Pre-register claims, units, primary metrics, critical slices, power, stop rules, and
failure thresholds. Split by user/tenant and time, not turns. Keep one untouched launch
set. Use positive controls (known tool violation, UUID, branch recovery, contradiction,
deleted vector) and negative controls (shuffled order, random embeddings, wrong-time
facts, inaccessible canaries, removed decisive step). Run component ablations before
cross-component experiments.

## Phased build

### P0: authority and personal evidence

- Canonical DAG, adapters, loss manifests, import quarantine.
- Canonical tool proposal/authorization/attempt/observation/state-delta records and
  conformance fixtures for every supported tool family.
- Full authority lattice and RLS oracle; current tenant-only policy is insufficient.
- Personal history, exact/FTS search, deterministic signals, evidence previews.
- Outbox, idempotent projectors, lineage, deletion receipts, work caps.
- Eval and memory proposal schemas; no automatic execution/injection.

### P1: governed intelligence

- pgvector behind exact authorized oracles and selectivity-aware fallback.
- Human annotation, diagnosis hypotheses, failure taxonomy, abstention.
- Retrospective trace audit and separately sandboxed prospective replay.
- Temporal facts and memory proposals with contradiction review.
- Explicit opt-in personal-to-team artifact promotion.

### P2: learning without additional persistent systems

- Keep reranking inside the bounded authorized request path; do not deploy
  FrankenSearch or Turbopuffer.
- Run fleet analytics from Aurora preaggregates and bounded background jobs, reading
  conditionally tiered S3 objects only when present; do not deploy ClickHouse.
- Domain-adaptive embeddings from governed, consented, versioned examples with random
  baselines, hard negatives, privacy tests, immutable releases, and rollback.
- Enterprise patterns only after adversarial differencing and stakeholder-policy gates.

## Reasoning portfolio and kill criteria

The analysis used systems thinking (F7), scientific method (K2), FMEA (F4), dependency
mapping (F2), deductive invariants (A1), adversarial privacy (H2), temporal reasoning
(E3), causal inference and counterfactual reasoning (F1/F3), ethical reasoning (K3),
and stakeholder perspective-taking (I4). Implementation reviews must continue using
information-loss, retrieval, measurement, distributed-systems, lifecycle, capacity,
ethical, and stakeholder reasoning.

Stop or narrow the program if:

- real histories cannot be normalized without material silent loss;
- authority cannot survive pool reuse, savepoints, failover, and stale readers;
- deletion cannot close over all derivatives and managed exports;
- filtered pgvector cannot meet per-scope recall without harming inference;
- diagnosis does not beat deterministic baselines on held-out corporate traces;
- memory proposals miss the required support/scope precision;
- privacy controls remove so much signal that enterprise patterns are not useful; or
- analytics cannot be degraded independently of the inference gateway.

The architecture succeeds by making uncertain intelligence optional and rebuildable
while keeping history, authorization, exact evidence, lineage, and deletion correct
without it.

## Primary sources

- PostgreSQL RLS: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- PostgreSQL `SET`: https://www.postgresql.org/docs/current/sql-set.html
- Aurora extensions:
  https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.Extensions.html
- Aurora vector support:
  https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html
- Aurora pooling:
  https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.BestPractices.connection_pooling.html
- RDS Proxy pinning:
  https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy-pinning.html
- pgvector: https://github.com/pgvector/pgvector
- VectorChord: https://github.com/tensorchord/VectorChord
- pgContext: https://github.com/Evokoa/pgContext
- Turbopuffer: https://turbopuffer.com/docs/architecture
- AgentRx: https://github.com/microsoft/AgentRx
- Signals: https://arxiv.org/abs/2604.00356
- AgentEvals: https://github.com/agentevals-dev/agentevals
- Phoenix: https://github.com/Arize-ai/phoenix
- Opik: https://github.com/comet-ml/opik
- Langfuse: https://github.com/langfuse/langfuse
- Graphiti: https://github.com/getzep/graphiti
- LangMem: https://github.com/langchain-ai/langmem
- MemInsight: https://github.com/amazon-science/MemInsight
- claude-history: https://github.com/raine/claude-history
- Prompt-Scope: https://github.com/monapdx/Prompt-Scope
- conversation extractor:
  https://github.com/slyubarskiy/chatgpt-conversation-extractor
- OpenRCA: https://github.com/microsoft/OpenRCA
- Database/tool/reflection decision:
  `docs/roadmap/research/log-trace-vector-database-and-reflective-learning-review.md`
- Anthropic Dreams: https://platform.claude.com/docs/en/managed-agents/dreams
- Anthropic Bloom: https://www.anthropic.com/research/bloom
- Google ReasoningBank:
  https://www.research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/
- OpenAI self-improving tax agents:
  https://openai.com/index/building-self-improving-tax-agents-with-codex/
