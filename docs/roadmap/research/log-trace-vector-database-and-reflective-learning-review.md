# Frankengate minimal log, trace, vector, and reflective-learning architecture

**Status:** corrected normative decision and implementation plan
**Date:** 2026-07-29
**Scale assumption:** several hundred GB of retained raw logs and traces
**Primary constraint:** smallest possible set of persistent systems that safely supports
personal history, tool trajectories, search, trace mining, evals, and memory proposals

## Correction

The previous version optimized for optionality and proposed several independent
database experiments. That was the wrong objective. Every additional database duplicates
data, authorization, deletion, backup, monitoring, migrations, incident response and
operator knowledge.

The decision is:

```text
Required trace-intelligence persistence
  1. Aurora PostgreSQL

Conditional existing storage path
  - S3-compatible object storage only for measured large-blob/cold-retention needs

Existing compute
  - Go Frankengate gateway/API
  - background analytics/eval worker only for isolated asynchronous jobs
```

Do **not** deploy ClickHouse, OpenSearch, Qdrant, ParadeDB, VectorChord, pgContext,
Phoenix, Langfuse, Opik, a graph database, or a separate vector database for this
program.

OpenTelemetry remains an interchange format. PostgreSQL FTS/trigram and pgvector remain
indexes inside the existing authority. The Frankengate UI and API own the personal
history, trace analysis, eval and memory workflows. Compact prompt, response and tool
evidence stays in Aurora initially. The existing S3 path is enabled only for payloads
whose measured storage, I/O or retention cost justifies its outbox, reconciliation and
hydration complexity; it is never a query authority.

If this architecture fails a preregistered requirement after the optimizations in this
plan, the first alternative is to **replace Aurora with one managed extensible
PostgreSQL service**, preserving one database and at most one commodity object tier.
Adding a specialized database is a last resort, not the next phase.

## Why this is sufficient at current scale

Several hundred GB is not a database-capacity problem. Aurora PostgreSQL storage
automatically grows to 256 TiB on current supported releases:
https://docs.aws.amazon.com/rds/latest/auroraextendedcontent/aurora-faq-scalability.html

The real constraints are:

- how much raw content is duplicated into heap, FTS and vector indexes;
- how many embeddings are created;
- broad scans and group-bys over raw events;
- I/O pricing, cache hit rate, vacuum and index maintenance;
- connection and worker concurrency;
- deletion and retention churn.

All six can be controlled without introducing another persistent database.

Aurora already supplies managed multi-AZ storage, backup, failover, replicas, SQL,
transactions, JSONB, FTS, trigram search, RLS and pgvector. AWS currently publishes
pgvector 0.8.x for current Aurora PostgreSQL releases:
https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html

If a measured payload class is cheaper or operationally safer outside Aurora, S3
supplies low-cost, independently durable object storage and lifecycle transitions. Its
cost surface is storage class, requests, retrieval and transfer:
https://aws.amazon.com/s3/pricing/

## Decision criteria

Rank complete architectures, not individual product features.

| Criterion | Weight | Meaning |
|---|---:|---|
| Persistent system count | 5 | Databases/object stores with their own data lifecycle |
| Authorization correctness | 5 | RLS, classifications, purpose and current epochs |
| Deletion correctness | 5 | One source deletion closes every searchable derivative |
| Operational burden | 5 | HA, backup, upgrades, monitoring, incidents and expertise |
| Total cost | 4 | Infrastructure, duplicate storage, network and people |
| Current-scale fit | 4 | Hundreds of GB, not hypothetical petabytes |
| Personal query fit | 4 | History, exact/lexical search, evidence expansion |
| Analytics fit | 3 | Recurrence, failure, tool and cohort aggregate jobs |
| Vector fit | 2 | Authorized candidate generation, not a product by itself |
| Migration/rollback risk | 4 | Amount of new code/data/security boundary |

Security and simplicity outweigh maximum single-query throughput. A system that is
faster but creates another authorization and deletion plane is worse until the existing
system demonstrably cannot meet the requirement.

## Complete architecture comparison

Scores are relative architectural judgments from 1 (poor) to 5 (strong), not benchmark
results.

| Complete architecture | Persistent systems | Simplicity | Security/deletion | Current-scale fit | Cost shape | Decision |
|---|---:|---:|---:|---:|---:|---|
| **Aurora only** | 1 | 5 | 5 | 5 | 4 | **Build first.** Keep compact searchable evidence transactionally colocated until measurements justify tiering. |
| **Aurora + conditional S3 blob tier** | 1 required + 1 conditional | 4 | 4 | 5 | 5 | **Enable by measured payload class only.** S3 never becomes searchable authority. |
| Managed extensible PostgreSQL + S3 | 2 | 4 | 5 | 5 | 4 | **Only replacement candidate.** Consider if Aurora's extension limits cause a proven failure. |
| Self-hosted PostgreSQL + S3 | 2 | 2 | 5 | 5 | 2 | Same logical simplicity but high human/HA/upgrade cost. Use only with an existing database SRE capability. |
| Aurora + ClickHouse + S3 | 3 | 2 | 3 | 5 | 2 | Reject now. Excellent scans do not justify a second query/security/deletion plane at hundreds of GB. |
| Aurora + OpenSearch + S3 | 3 | 2 | 3 | 5 | 2 | Reject now. Search features duplicate PostgreSQL authority and indexes. |
| Aurora + Qdrant + S3 | 3 | 2 | 3 | 4 | 2 | Reject. It solves only vectors and leaves text, logs and trace analytics elsewhere. |
| Aurora + Turbopuffer + S3 | 3 | 2 | 3 | 5 | 2 | Reject. It is another external retrieval authority for a scale not presently needed. |
| ClickHouse as sole database + S3 | 2 | 3 | 2 | 5 | 4 | Reject as governance authority: transactional RLS/relational policy and mutation semantics are the wrong fit. |
| OpenSearch as sole database + S3 | 2 | 3 | 2 | 5 | 3 | Reject as governance authority: document security does not replace transactional policy, joins and approvals. |

This matrix does not recommend running a bakeoff across all candidates. It eliminates
architectures before implementation. The only active proof is Aurora first, with the
existing S3 path activated only where its measured benefit exceeds its consistency and
operations cost.

## Minimal production architecture

```text
request, response, routing, governance and tool events
  -> canonical typed event/trajectory
  -> one Aurora transaction
       authoritative row + compact evidence
       optional durable object intent for a measured large-payload class
  -> optional asynchronous object writer
       selected large payload to S3 with digest and receipt
  -> bounded Aurora projectors
       personal history
       exact/FTS/trigram search
       sparse task-level pgvector
       deterministic signals
       daily/team/enterprise aggregates
       eval and memory proposals
  -> UI/API
       RLS-authorized rows first
       optional authorized S3 hydration only for tiered evidence
```

### Aurora owns

- principal, tenant, team/project and audience ownership;
- classification, purpose, retention, consent and training eligibility;
- policy, authorization, membership and deletion epochs;
- request/session/task/attempt/branch/event identity;
- canonical tool proposal, authorization, execution, observation and outcome records;
- keyset history indexes and searchable text;
- a deliberately small set of task/recovery embeddings;
- deterministic friction signals and compact aggregate tables;
- eval/dataset/memory proposal state, review and promotion receipts;
- object manifests, digests, lineage, tombstones and deletion receipts;
- durable analytics job leases and projection watermarks.

### Conditional S3 tier owns

- only payload classes that cross a measured size, I/O, cost or retention threshold;
- full raw request/response or provider envelopes selected by that policy;
- large tool arguments/results and streaming fragments;
- immutable import/source envelopes and replay fixtures;
- evaluation datasets and generated artifacts too large for PostgreSQL;
- cold Parquet/JSON evidence for bounded offline analysis;
- versioned exports and candidate memory release files.

Do not tier an object merely because it can be tiered. S3 object keys are never bearer
capabilities. Aurora owns the authorized manifest and current epochs. A client receives
bytes only after an authorized manifest lookup.

### Existing compute owns

- the Go gateway emits canonical events and serves short interactive queries;
- asynchronous work uses the smallest deployable worker shape that remains isolated
  from inference. Reuse the existing Rust worker initially rather than adding another
  service, but do not treat its separate runtime as permanent without measuring its
  maintenance and throughput benefit;
- rare broad historical jobs read bounded Aurora ranges or, when tiering is enabled,
  S3 objects with ephemeral worker-local compute. They write compact results to
  PostgreSQL and introduce no persistent query authority.

## Hot/cold layout

The system must not store every raw byte three times.

### Always in Aurora

- the complete history index needed to list every authorized prompt/session;
- prompt/user text required for exact/lexical history search, subject to redaction and
  retention policy;
- compact answer/tool/evidence previews;
- typed routing, model, latency, cost, status, error and outcome fields;
- canonical tool metadata and object payload references;
- source hashes, lineage and deletion state.

### Tiered to S3 only after the gate

- selected full provider envelopes;
- verbose intermediate reasoning/stream chunks where collection is permitted;
- large tool arguments/results;
- attachments, screenshots, files and replay environments;
- large evaluator explanations and export artifacts.

The UI pages all history from Aurora using stable keyset pagination. Opening a detail
hydrates only the authorized objects for that item. A missing cold object is a typed
evidence error, never a silent empty response.

## Search with no extra engine

Use an exact-first retrieval ladder:

1. typed scope, classification, purpose, retention and epoch predicates;
2. exact IDs, quoted strings, tool/model/error codes and normalized corporate terms;
3. PostgreSQL `tsvector` FTS and `pg_trgm`;
4. optional task-level pgvector candidates;
5. reciprocal-rank or deterministic score fusion in one implementation;
6. current-epoch recheck;
7. authorized preview/object expansion.

Native FTS is not BM25, but it is adequate for personal history and candidate generation
when exact corporate identifiers are preserved. Do not pay for a new search cluster
until a user-relevant quality benchmark proves that ranking, highlighting, faceting or
latency is inadequate.

JSONB stores bounded provider-specific long-tail data. Ownership, authorization,
classification, time, status, tool identity and frequently filtered fields remain typed
columns. Avoid broad GIN indexes over unbounded raw JSON.

## Sparse vector strategy

Vector count, not raw-log bytes, determines pgvector cost.

Do not embed:

- every span;
- every tool result;
- every message turn;
- raw duplicated chunks;
- records that deterministic exact/lexical search already resolves.

Initially embed:

- one task/session representation;
- optionally one verified failure-to-success recovery delta;
- approved memory/eval evidence that needs semantic retrieval.

For `N` vectors of dimension `d`, raw float storage begins near `4 * N * d` bytes before
row and index overhead. Embedding ten million 1,024-dimensional tasks is roughly 41 GB
of raw vector values; embedding hundreds of millions of turns would be a self-created
scale problem. Cardinality budgets and per-purpose vector manifests are therefore
architecture controls.

Start with exact vector search on authorized candidate sets. Add HNSW only when the
exact path misses latency SLOs. Measure filtered ANN against exact authorized results;
pgvector documents that filtering interacts with approximate scans and supplies
iterative scans in newer versions:
https://github.com/pgvector/pgvector

## Analytics with no ClickHouse

Avoid repeated scans over raw event payloads:

- compute cheap deterministic features once at ingestion/projector time;
- partition append-heavy event tables by time only when measured;
- maintain compact daily/hourly aggregates for tool, task, error, route, model and
  outcome dimensions;
- retain exemplars by ID rather than copying payloads into aggregates;
- use bounded Rust jobs for clustering, evaluator and memory work;
- run rare deep historical jobs over S3 source files and persist only versioned results;
- expire/rebuild derived tables independently.

The dashboard reads compact PostgreSQL tables. It does not run arbitrary group-bys over
hundreds of GB on every page load.

ClickHouse is reconsidered only if broad aggregate workloads remain the named bottleneck
after these controls and their business value justifies a permanent third data system.
The existence of a tested optional ClickHouse logstore lowers future switching cost; it
does not justify deploying it.

## Cost model and controls

The minimal architecture has four cost categories:

```text
monthly cost
  = Aurora compute
  + Aurora storage/indexes/I/O
  + S3 storage/requests/retrieval
  + embedding/judge compute
```

There is no second database cluster, duplicated index fleet, cross-database replication
service, or second on-call specialty.

Controls:

- keep compact evidence in Aurora; offload only payload classes that pass the measured
  tiering gate, then compact many tiny cold records into sensible objects/Parquet
  batches;
- use S3 lifecycle transitions only when access frequency and minimum-duration charges
  justify them:
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html
- keep one searchable text representation and one bounded preview, not several full
  copies;
- cap embeddings by purpose and task, deduplicate by content/model hash, and batch them;
- run deterministic detectors before LLM judges;
- materialize common aggregates once;
- bound every worker, query, statement, connection and index-build class;
- compare Aurora Standard and I/O-Optimized from actual bills. AWS states I/O-Optimized
  can save when I/O exceeds 25% of total Aurora database spend:
  https://aws.amazon.com/rds/aurora/pricing/
- use separate but bounded connection pools for interactive reads, projectors,
  analytics and maintenance—these are pools, not new systems;
- keep experiments and optional intelligence degradable without affecting inference.

### Current hybrid-offload gap

The present `HybridLogStore` uses an in-memory upload queue and intentionally drops an
S3 upload when the `Put` fails. That is acceptable for optional payload offload but not
for canonical evidence required by history, evals or memory.

Before relying on S3 as the cold evidence tier:

- commit a durable outbox/object-intent row with the authoritative event;
- lease and retry uploads from the analytics worker;
- verify digest/size and write a receipt before setting `has_object`;
- expose failed/pending evidence status in history;
- reconcile orphaned objects and missing objects;
- prioritize deletion/tombstone jobs;
- alert on oldest pending age and permanent failure.

Fixing this durability boundary is substantially simpler than adding another database.

## Canonical tool calling

All tool families share one model:

```text
ToolProposal
  -> ToolAuthorizationDecision
  -> ToolAttempt
  -> ToolObservation
  -> ToolStateDelta
  -> ToolUseInReasoning
  -> terminal outcome
```

Cover MCP, provider-native/hosted, Responses API, browser, computer, shell, code, file,
memory, retrieval and subagent tools.

Every record includes stable task/attempt/event/parent/span/invocation IDs, ordering and
parallel group, tool family/name/schema hash, proposed arguments, authorization and
confirmation, execution/retry/idempotency, result/error, side-effect class,
before/after evidence, latency/cost, payload digest/object reference, redaction, typed
scope/classification and current epochs.

Record malformed, denied, skipped, timed-out, cancelled and failed attempts. A model
claim that a tool ran is not an execution fact; a successful API response is not proof
of the intended side effect; a delivered result is not proof that the model used it
correctly.

This schema lives in Aurora. Full tool payloads live in S3. No trace database is needed.

## Reflective learning with no external platform

Use upstream systems as design references, not deployed dependencies:

| Concept | Take into Frankengate | Do not deploy/infer |
|---|---|---|
| [Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) | Separate immutable candidate memory release from selected sessions; input never modified; review/discard/promote. | No Anthropic managed memory dependency and no in-place `MEMORY.md` edit. “Latest” is not automatically true. |
| [Anthropic Reflect](https://www.anthropic.com/news/reflect-with-claude) | Private user-facing task/topic/friction reflection with evidence and correction. | No manager view, employee score or psychological inference. |
| [Anthropic agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Complete tool trajectory, environment outcome, multiple trials, deterministic/model/human graders. | No brittle single prescribed path when alternatives are valid. |
| [Anthropic Bloom](https://www.anthropic.com/research/bloom) | Generate varied candidate eval scenarios from a reviewed behavior and versioned seed in an isolated job. | No separate Bloom service and no production credentials or secrets in simulators. |
| [OpenAI self-improving tax agents](https://openai.com/index/building-self-improving-tax-agents-with-codex/) | Correction -> structured finding -> targeted eval -> bounded engineering task, with full provenance. | A difference is not automatically an error; experts adjudicate workflow noise/preferences. |
| [OpenAI in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/) | Layer schema, lineage, code, human annotation, institutional knowledge and scoped memory; compare outcomes. | Historical queries and retrieved documents are not permission-free truth. |
| [OpenAI GPT-Red](https://openai.com/index/unlocking-self-improvement-gpt-red/) | Isolated prompt-injection generation against tool, retrieval and memory pipelines. | No attacker access to production tools, credentials or unrestricted network. |
| [Google ReasoningBank](https://www.research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/) | Candidate procedural memories from independently verified successful and failed trajectories. | No self-judge auto-promotion or append-only uncurated memory. |
| [Google AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | Immutable candidate archive and hard evaluators where outcomes are executable. | Do not apply evolutionary self-modification to subjective employee insights. |
| [Meta HyperAgents](https://ai.meta.com/research/publications/hyperagents/) | Separate proposal, evaluation and archive roles in a sandbox. | No autonomous production code/prompt/policy self-modification. |
| [Microsoft AgentRx](https://www.microsoft.com/en-us/research/blog/systematic-debugging-for-ai-agents-introducing-the-agentrx-framework/) | Common trajectory IR, deterministic guarded invariants, evidence log, failure taxonomy and abstention. | No unrestricted generated checker execution or unqualified “root cause.” |
| [Microsoft LEGOMem](https://www.microsoft.com/en-us/research/publication/legomem-modular-procedural-memory-for-multi-agent-llm-systems-for-workflow-automation/) | Separate orchestrator/decomposition guidance from executor/tool guidance. | No cross-user procedural leakage or assumed transfer across environments. |
| [Microsoft ACE](https://www.microsoft.com/en-us/research/publication/agentic-context-engineering-evolving-contexts-for-self-improving-language-models/) | Versioned candidate playbooks, compact deltas, held-out eval and rollback. | No policy/prompt ownership bypass. |

Implement these concepts with Aurora tables and bounded background jobs. Use S3
artifacts only for payload classes that pass the tiering gate. They do not require
Phoenix, Langfuse, Opik, Graphiti or another memory database.

## The only migration ladder

### State A — build and operate

**Aurora only for normal history, search, analysis metadata, evals and memories.**

This is the only required production target. Existing S3 is a conditional blob/cold
tier, not a prerequisite or a query system.

### State B — replace Aurora, keep one database

Enter only if State A fails a named SLO after hot/cold tiering, bounded vectors,
partitioning, pre-aggregation, query/index tuning and appropriate Aurora pricing mode.

Evaluate one managed extensible PostgreSQL offering capable of the missing feature, for
example Postgres with `pg_search`/ParadeDB and pgvector. Neon documents managed
`pg_search` availability:
https://neon.com/blog/pgsearch-on-neon

The goal is still one PostgreSQL authority, with at most one conditional object tier.
Do not retain Aurora as a permanent second source after cutover.

### State C — self-host the same one-database design

Use only when no managed provider meets security/extension requirements and the
organization accepts database SRE ownership. CloudNativePG documents automated and
quorum failover, including the durability/availability tradeoff:
https://cloudnative-pg.io/documentation/current/failover/

ParadeDB, VectorChord and pgContext are extension candidates inside this replacement,
not additional production services. ParadeDB community documentation currently
distinguishes logical replication from physical HA support for its custom index:
https://github.com/paradedb/paradedb/blob/v0.25.0/docs/welcome/guarantees.mdx

### State D — split databases only after PostgreSQL is disproven

This is an exception requiring a new architecture decision.

- ClickHouse is the candidate only if broad append-heavy analytics is the proven
  irreducible workload.
- OpenSearch is the candidate only if interactive lexical/hybrid search is the proven
  irreducible workload.
- Qdrant is not selected merely because vectors exist.

The evidence must show that replacing PostgreSQL cannot solve the bottleneck more simply
and that the value exceeds a permanent second authorization/deletion/operations plane.

## Promotion and kill gates

Stay on Aurora unless all are true:

1. a user-facing SLO or cost budget fails for at least two representative periods;
2. data tiering, cardinality reduction, indexes, plans, pooling, partitioning,
   pre-aggregation and pricing mode have been tried and measured;
3. the failing workload has a frozen authorized corpus and exact result oracle;
4. the replacement meets equal RLS, deletion, classification, backup and restore gates;
5. total cost includes people, duplicated storage, network, monitoring and incidents;
6. migration, shadowing, rollback and old-system retirement are demonstrated;
7. one replacement wins as a complete architecture, not because of one feature.

Do not add a system when:

- it only improves an optional or unmeasured feature;
- the same result can be computed asynchronously;
- reducing embedding/index cardinality closes the gap;
- a materialized aggregate closes the gap;
- an occasional S3 batch job closes the gap;
- the team cannot own its failure and deletion semantics;
- it would remain after its supposed source system is never retired.

## Delivery sequence

### P0 — make Aurora sufficient

- Canonical tool trajectory and complete personal history in Aurora.
- Exact/FTS/trigram history search and keyset pagination.
- One task embedding only where semantic retrieval has a defined purpose.
- Typed authorization/classification/epochs on every row.

### P1 — make it inexpensive

- Measure heap/index/WAL/I/O cost and payload-size distribution.
- Enable S3 only for a payload class whose measured savings exceed the outbox,
  reconciliation, hydration, deletion and incident burden.
- If enabled, add durable object outbox, retries, receipts, reconciliation and deletion
  closure before removing the authoritative bytes from Aurora.
- Deduplicate searchable text and embeddings by content/revision hash.
- Add retention/lifecycle, partitions only when measured, and common aggregates.
- Choose Aurora Standard or I/O-Optimized from real cost attribution.

### P2 — add intelligence without systems

- Deterministic trace and tool signals.
- Bounded asynchronous mining over Aurora ranges and optional tiered S3 objects.
- Tool-aware eval proposals and immutable memory candidate releases.
- Personal Reflect-style UI and privacy-safe team/enterprise aggregates.

### P3 — prove the current architecture

- Concurrent history/search/ingest/delete/eval/failover benchmark.
- Exact authorized vector oracle and selective-scope recall.
- Monthly cost attribution by workload and derivative.
- Restore, deletion, stale-reader, object-missing and worker-death tests.

### P4 — replacement decision only after failure

- Produce a short decision record naming the failed SLO and why State A cannot meet it.
- Compare complete one-database replacements.
- Split databases only with explicit approval of the permanent complexity.

## Tracking corrections

- Canonical tool trajectories remain:
  https://github.com/pierretokns/frankengate/issues/88 and bead
  `bif-kyy.17.13.1.5`.
- The former multi-database bakeoff item is corrected to an Aurora-first proof and
  single-replacement gate:
  https://github.com/pierretokns/frankengate/issues/89 and bead
  `bif-kyy.17.13.3.4`.
- Immutable memory candidates remain:
  https://github.com/pierretokns/frankengate/issues/83 and bead
  `bif-kyy.17.13.2.2`.
- Tool-aware eval proposals remain:
  https://github.com/pierretokns/frankengate/issues/82 and bead
  `bif-kyy.17.13.2.1`.

## Acceptance criteria

1. A user can page, search and open all authorized history from Aurora; optional S3
   hydration is required only for payload classes that passed the tiering gate.
2. Every supported tool proposal, authorization, attempt, result and observed side
   effect is represented or has a loss receipt.
3. If S3 tiering is enabled, object upload failure is durable/retryable and visible; no
   required evidence is removed from Aurora before a verified receipt.
4. Exact/lexical/vector/history queries fail closed under missing/stale authority and
   meet the declared SLO on the representative corpus.
5. Revocation/deletion prevents all Aurora, cache and conditionally tiered S3 return
   within the declared SLO.
6. Daily and interactive dashboards read bounded tables/indexes rather than scanning
   raw history.
7. Embedding cardinality and index storage remain within explicit budgets.
8. Analytics/eval/memory workers can saturate or fail without harming inference.
9. Monthly cost attributes Aurora compute, storage/index/WAL/I/O, conditional S3 and
   model work to named product workloads.
10. No additional persistent query system is introduced without the State A failure
    evidence and replacement/split decision described above.
