# Trace Intelligence on Aurora: RLS, Scope, and Performance Execution Plan

Status: implementation plan; launch budgets are targets to validate, not measured claims.

## Purpose

FrankenGate must let an individual inspect and mine all of their authorized history,
let teams learn from deliberately shared work, and let an enterprise detect common
friction without turning similarity search into a tenant bypass or employee-surveillance
system. Aurora PostgreSQL remains the evidence, policy, lineage, and deletion authority.
Full-text and pgvector indexes are rebuildable accelerators. Raw or large trace payloads
remain in encrypted object storage behind authorized references.

This plan refines:

- `docs/roadmap/realtime-friction-rag-quality-plane.md`;
- `docs/roadmap/research/trace-intelligence-enterprise-question-composition-audit.md`;
- `docs/roadmap/research/trace-intelligence-composed-feasibility-and-failure-analysis.md`;
- `docs/roadmap/research/log-trace-vector-database-and-reflective-learning-review.md`;
- `docs/roadmap/research/vector-retrieval-storage-architecture-review.md`;
- `docs/roadmap/architecture/outbox-cursor-lifecycle.md`;
- `docs/roadmap/architecture/postgres-authoritative-config-and-mantle-consolidation-plan.md`;
- GitHub epic `pierretokns/frankengate#75`; and
- bead epic `bif-kyy.17.13`.

## JSM analysis kernel

Four reusable reasoning lenses determine the design.

### Identity-chain and surface-transpose

The authenticated Bifrost token identifies a caller, but the identity chain must remain
intact through HTTP, background job, PostgreSQL transaction, RLS policy, ANN query,
reranker, cache, export, eval dataset, memory proposal, replay, migration, and recovery.
Every surface must either carry the same authority envelope or be unable to expose
protected content.

### Fail-open and recovery-path probes

Missing authority context, stale membership, unavailable policy state, a failed RLS
helper, reader-replica lag, index rebuild, cache loss, or analytics-worker failure must
not broaden access. Recovery, import, replay, deletion, backup, and administrative
paths receive the same tests as the normal UI and API.

### Profile-first optimization

Connection pooling, partitioning, HNSW parameters, JSONB indexes, materialized
aggregates, reader endpoints, and specialized retrieval services are hypotheses until a
representative benchmark identifies the bottleneck. Each optimization records its
baseline, query plan, behavior/golden-result proof, resource delta, rollback, and the
specific workload slice it improves.

### Evidence-to-operator workflow

Every surfaced insight must lead to one explicit, auditable action: inspect evidence,
label/dismiss, create an eval, propose memory, open a knowledge/product issue, or request
opt-in collaboration. No insight silently changes routing, memory, permissions,
knowledge, or training eligibility.

## Deployment and threat context

- Internal and potentially internet-reachable gateway and dashboard.
- Kubernetes services with multiple API and worker replicas.
- Aurora PostgreSQL writer is the launch authority.
- Hundreds of gigabytes of logs are plausible, but only a curated subset is eligible
  for text/vector retrieval.
- Users include individuals, teams, enterprise analysts, service workers, migration
  jobs, and narrowly authorized support/security administrators.
- Relevant attackers include an ordinary user probing another user's data, a team
  administrator exceeding team scope, a compromised worker, a stale or confused service,
  and an insider attempting bulk export or cohort differencing.

## Non-negotiable invariants

1. No request, job, or query executes protected SQL without a transaction-local
   authority context.
2. Application roles are `NOSUPERUSER NOBYPASSRLS` and do not own protected tables.
3. Every protected table uses `ENABLE ROW LEVEL SECURITY` and
   `FORCE ROW LEVEL SECURITY`; absence of an applicable policy is default deny.
4. RLS and explicit application predicates both enforce tenant and audience scope.
5. Authorization runs before ANN candidate exposure, distance/count telemetry,
   reranking, snippets, cache, export, or cross-user aggregation.
6. Security dimensions use typed columns. JSONB is not authoritative for tenant,
   subject, audience, purpose, classification, policy, authorization, retention, or
   deletion decisions.
7. A vector or aggregate is a derived object bound to its source and policy/deletion
   epochs. It never becomes independent authority.
8. Protected reads use the writer or a reader proven current enough for the relevant
   authorization/deletion watermark.
9. Heavy parsing, embedding, grouping, judging, index building, and aggregation remain
   outside the inference request path.
10. Enterprise analytics defaults to aggregates; raw trace access is a separate,
    purpose-bound and audited privilege.

PostgreSQL documents that superusers and `BYPASSRLS` roles always bypass RLS, that table
owners normally bypass it unless `FORCE ROW LEVEL SECURITY` is enabled, and that
referential-integrity checks can bypass row security. Those are explicit test cases, not
footnotes:
https://www.postgresql.org/docs/current/ddl-rowsecurity.html

## Scope model

Every trace-derived row has one tenant plus one declared audience mode.

| Audience | Required typed fields | Read rule |
|---|---|---|
| Private user | `owner_subject_id` | Exact authenticated subject and current authorization epoch |
| Project/team | `team_id`, optional `project_id` | Current membership/capability, allowed purpose and classification ceiling |
| Enterprise aggregate | `cohort_policy_id`, no raw-content payload | Explicit analyst purpose plus minimum-cohort and anti-differencing policy |
| Restricted enterprise raw | owner/team plus `case_id` and approval | Separate audited role/capability, time bound, reason bound, never implied by aggregate access |
| System maintenance | job kind plus bounded tenant/shard | Narrow stored operation; no interactive browse/export privilege |

`tenant_id` prevents organization crossing but is not sufficient for user or team
privacy. Team membership does not imply access to private-user rows. Enterprise
administration does not silently imply raw-content access.

### Authority envelope

The gateway resolves its signed/token-backed identity and passes a canonical envelope:

```text
tenant_id
subject_id
principal/capability revision
purpose
classification ceiling
authorization epoch
policy revision
request_id
optional team/project/case scope
```

The envelope is validated once at the service boundary and again by the database access
layer. Arbitrary request headers, UI parameters, job JSON, or model output cannot
construct it.

## Transaction-local database authority

The existing Rust analytics boundary correctly begins a transaction and calls
`set_config('app.tenant_id', ..., true)`. Extend it into the only public database entry
point for protected queries:

1. acquire a pooled connection and begin a short transaction;
2. validate the complete authority envelope and query purpose;
3. apply bounded transaction-local settings with `set_config(..., true)` or equivalent
   `SET LOCAL`;
4. execute an operation whose SQL also contains explicit tenant/audience predicates;
5. normalize authorization-sensitive errors;
6. commit or roll back; transaction-local state expires either way.

PostgreSQL specifies that `SET LOCAL` ends with the transaction and is canceled by
rollback to an earlier savepoint:
https://www.postgresql.org/docs/current/sql-set.html

Never set authority at session scope, in an `after_connect` callback, or on a connection
returned to the pool. Cancellation, panic, timeout, savepoint rollback, and pool reuse
must not retain or widen prior scope.

### RDS Proxy decision

AWS documents that PostgreSQL `SET`/`set_config`, prepared-statement management,
temporary objects, cursors, `LISTEN`, and session-level advisory locks can cause RDS
Proxy pinning:
https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy-pinning.html

Therefore:

- launch with bounded, long-lived application pools directly against the appropriate
  Aurora endpoint unless a measured RDS Proxy experiment proves useful multiplexing for
  the exact transaction-local authority sequence;
- do not claim RDS Proxy capacity benefits from connection-count reduction alone;
  measure `DatabaseConnectionsCurrentlySessionPinned`,
  `DatabaseConnectionsBorrowLatency`, client connections, database connections, and
  failover behavior;
- `LISTEN` uses a dedicated direct/session connection and is never placed behind
  transaction pooling;
- if RDS Proxy pins the normal query path, either accept and capacity-budget that
  behavior or remove it; never weaken transaction-local security state to improve
  multiplexing.

AWS recommends pooling to reduce Aurora PostgreSQL connection churn and identifies
`total_auth_attempts`, `numbackends`, and transaction activity as useful signals:
https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.BestPractices.connection_pooling.html

## Database roles and ownership

Use separate roles:

- `fg_schema_owner NOLOGIN`: owns schemas/tables/functions; never used by services;
- `fg_api NOBYPASSRLS`: short user/team reads and proposal writes;
- `fg_worker NOBYPASSRLS`: leases and processes explicitly assigned tenant/shard jobs;
- `fg_aggregate NOBYPASSRLS`: writes only approved aggregate outputs through bounded
  operations;
- `fg_migrator`: migration-only credentials, unavailable to runtime pods;
- `fg_breakglass`: separately controlled, time-bound and fully audited;
- backup/restore role: verified with `row_security=off` error behavior so a filtered
  backup cannot be mistaken for a complete backup.

Security-definer helpers are exceptional. Each has a fixed `search_path`, typed inputs,
revoked `PUBLIC` execute, narrowly granted callers, no dynamic SQL, no raw-content
return, and adversarial tests. Do not give a general worker role `BYPASSRLS` to simplify
cross-tenant job leasing.

### Worker leasing without cross-tenant browse

Use two stages:

1. a narrow scheduler operation returns only opaque job ID, tenant/shard, kind, lease
   token, and authority revision for an allowed worker class;
2. the worker begins a new tenant-fenced transaction to read or mutate job payload
   references.

The scheduler cannot return user text, embeddings, snippets, or object-store credentials.
Lease renewal and completion require the same tenant, worker, token/fence, attempt, and
authority revision. A stolen job ID alone is useless.

## Policy shape

Prefer simple row-local RLS predicates over repeated joins. PostgreSQL notes that
policies consulting other tables can create race and performance hazards. Use:

- row-local tenant, audience, owner/team/project, classification, purpose, retention,
  and deletion fields;
- a small, indexed, versioned membership/capability table when a lookup is unavoidable;
- a carefully reviewed stable security-definer predicate only to centralize that
  lookup, not to bypass RLS;
- short `READ COMMITTED` transactions and an explicit rule that authorization changes
  fence new queries while already-running bounded reads follow the documented
  non-retroactive policy;
- row and membership authorization epochs so stale contexts fail closed.

Use restrictive policies for universal guards such as tenant, not-deleted, unexpired,
classification, and purpose; add narrowly permissive audience policies for private,
team, and approved enterprise access. Test the effective composition because PostgreSQL
combines permissive policies with `OR` and restrictive policies with `AND`.

Foreign-key and uniqueness errors can reveal that an invisible row exists. Prefer
tenant-scoped composite identities where appropriate and normalize externally visible
conflict/not-found responses.

## Physical data layout

### Deployment boundary

This plan requires one trace-intelligence persistence system: Aurora PostgreSQL.
PostgreSQL owns identity, authorization, searchable metadata, compact evidence,
aggregates, evals, and memory proposals. The existing S3-compatible object path is a
conditional large-blob/cold tier, enabled only for measured payload classes whose
benefit exceeds its outbox, reconciliation, hydration, and deletion complexity. The Go
gateway and background analytics/eval worker are compute clients, not new stores.

ClickHouse, OpenSearch, Qdrant, ParadeDB, VectorChord, pgContext, Turbopuffer, Phoenix,
Langfuse, Opik, and graph databases are not deployment dependencies. If this design
fails a preregistered requirement after hot/cold tiering, sparse embeddings,
preaggregation, and bounded batch analysis, prefer replacing Aurora with one managed
extensible PostgreSQL service before adding a second query database. See the
[minimal architecture decision](../research/log-trace-vector-database-and-reflective-learning-review.md).

### Authoritative compact tables

- `trace_sessions`: conversation/session/task ownership and source lineage;
- `trace_events`: ordered messages, spans, tools, outcomes, feedback and object refs;
- `task_attempts` and `recovery_deltas`;
- `friction_signals` and annotations;
- `trace_documents`: sanitized, purpose-approved retrieval documents plus generated
  `tsvector`;
- `trace_entities` and `trace_edges`;
- `insights`;
- `eval_cases` and dataset memberships;
- `memory_proposals` and temporal fact revisions;
- `cohort_aggregates`;
- `derived_index_releases`, tombstones and deletion receipts.

Raw payload bytes do not live in these tables by default. JSONB retains bounded
provider-specific attributes, evaluator explanations, and provenance extensions.
Frequently filtered JSONB keys are promoted to typed columns before launch.

Tool execution is not stored only as assistant-message JSON. The canonical projection
separates model proposal, authorization/confirmation, actual attempt, observation
delivered to the model, independently verified state delta, and terminal outcome across
MCP, provider-native/hosted, browser, computer, shell, code, file, memory, retrieval and
subagent tools. Existing `MCPToolLog`, model `ToolCalls`, and OTel `mcp.tool` spans are
inputs to that projection, not three independent truths.

### Partitioning

Start with time-range partitioning for append-heavy event/document tables only when the
measured table size, vacuum behavior, retention deletion, or query pruning justifies it.
Use tenant hash subpartitioning only if a representative enterprise distribution shows
hot partitions or unmanageable indexes. Do not create one table or HNSW index per tenant
or team.

All user-history pagination is keyset-based on a stable tuple such as
`(occurred_at DESC, id DESC)`. Required B-tree indexes begin with the enforced equality
scope:

```text
(tenant_id, owner_subject_id, occurred_at DESC, id DESC)
(tenant_id, team_id, occurred_at DESC, id DESC)
(tenant_id, task_fingerprint, occurred_at DESC, id DESC)
(tenant_id, deletion_epoch, policy_revision)
```

GIN indexes serve generated `tsvector` and only demonstrated JSONB containment paths.
Large index creation and backfills run as bounded resumable maintenance jobs, never
startup migrations.

## Hybrid retrieval under RLS

The query planner must see explicit authorization predicates in addition to RLS:

1. apply tenant, audience, purpose, classification, retention, deletion, time and exact
   identifier filters;
2. run lexical and vector candidate searches independently with stable IDs and bounded
   overfetch;
3. fuse/rerank only authorized candidates;
4. reauthorize IDs before snippets or source expansion;
5. bind cache keys to the full authority and retrieval-contract hash.

pgvector documents that ANN filtering is applied after approximate index scanning and
can return too few rows for selective filters. Version 0.8 added iterative scans; exact
search remains the perfect-recall oracle:
https://github.com/pgvector/pgvector

Aurora documents pgvector support and HNSW beginning at extension version 0.5, but the
actual extension version depends on the Aurora engine release:
https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html

Consequently:

- startup records Aurora engine and `vector` extension versions;
- iterative scanning is used only when the installed extension supports it and a query
  plan assertion proves it is active;
- filtered recall is measured by user/team/classification selectivity against exact
  search;
- low-cardinality audience classes may use partial indexes; high-cardinality tenancy
  uses shared indexes plus typed filters, iterative overfetch, or exact search for small
  eligible sets;
- failure to return enough authorized ANN candidates falls back to bounded exact or
  lexical retrieval rather than relaxing security predicates;
- model or dimension changes create immutable parallel index releases.

## Aurora workload isolation and connection budget

Use independently bounded service classes:

| Class | Work | Database behavior |
|---|---|---|
| API/history | short keyset, exact and bounded hybrid reads | small pool, short transaction and statement timeout |
| Worker | leases, signal extraction, embedding manifests | separate pool and concurrency semaphore |
| Aggregation | approved cohort jobs | scheduled quotas and bounded temp/work memory |
| Maintenance | migration, backfill, index build, vacuum support | singleton/fenced job with explicit operator window |
| Listener | outbox notification hint | one direct session per required listener; polling remains correctness path |

Enforce the fleet equation already used by the control-plane plan:

```text
sum(replicas × per-replica pool maxima)
+ dedicated listeners
+ singleton workers/importers/migrations
+ failover and administrative headroom
< writer max_connections × declared safety fraction
```

No component defaults to hundreds or thousands of connections. A deployment renders the
complete connection budget and refuses obviously impossible settings. Reconnect uses
jitter, bounded concurrency, and stable-connection reset thresholds.

Authorization-sensitive queries use the writer by default. A reader endpoint is allowed
only after proving its replay position meets the required policy/deletion watermark;
otherwise the query returns to the writer or fails closed. “Eventual” is not sufficient
for revocation or deletion.

## Latency and capacity method

Establish baselines before choosing indexes or pool sizes. Benchmark at minimum:

- one user with deep history;
- many users in one tenant;
- one user in many teams;
- selective classified scopes;
- large team and enterprise aggregate scopes;
- recent hot data and old cold data;
- exact identifier, lexical, semantic, and hybrid queries;
- simultaneous ingestion, deletion, re-embedding, aggregation and UI traffic;
- Aurora restart/failover, reader lag, pool exhaustion and worker saturation.

Record p50/p95/p99, throughput, returned/eligible candidates, exact-versus-ANN recall,
query plan, buffers/I/O, CPU, memory, WAL, replica lag, pool wait, connection pinning,
timeouts, cancellations and cost. Freeze golden authorized result sets and ordering/tie
rules before each optimization. Only ship an optimization whose measured
impact × confidence / effort clears the project threshold and whose behavior proof
passes.

Initial product targets to validate:

- history first page feels interactive without precomputing a user's entire corpus;
- exact identifier search completes before semantic expansion;
- semantic/group cards may stream progressively;
- heavy insight, eval-suggestion, memory-extraction and enterprise aggregation jobs are
  asynchronous and cancellable;
- analytics saturation cannot measurably alter inference availability or tail latency
  beyond the gateway's declared isolation budget.

## Individual, team, and enterprise workflows

### Individual

- Default filter is `owner_subject_id = authenticated subject`.
- Complete history is paged from authoritative metadata; content is fetched lazily.
- Personal search and suggested questions cite exact source turns.
- Memory and eval creation require preview and approval.

### Team

- Private rows stay private until deliberately shared or derived into an approved team
  artifact.
- Team search uses current membership, purpose and classification; membership changes
  fence new queries through authorization epochs.
- Reusable recovery patterns may become team evals or knowledge issues through an
  audited proposal, not by copying another user's raw conversation.

### Enterprise

- Default views use minimum-cohort aggregates with complementary-cell and repeated-query
  resistance.
- Enterprise analysts see patterns, costs, friction and affected system components, not
  employee rankings.
- Raw evidence escalation requires an approved case, reason, limited time window,
  classification clearance and audit.
- Security/legal holds and incident response use separate workflows and roles.

## Required conformance and adversarial tests

### RLS coverage

- inventory every non-system table and partition;
- assert RLS enabled and forced on every protected relation;
- assert runtime roles are not owner, superuser, or `BYPASSRLS`;
- assert every command has the expected policy and grants;
- create a new protected table fixture without policy and prove CI fails.

### Pool and context isolation

- alternate tenants/users/teams on one reused physical connection;
- missing, empty, malformed, stale and overlong GUC values;
- transaction commit, rollback, savepoint rollback, cancellation, timeout and panic;
- worker lease followed by user query and vice versa;
- connection loss/retry and Aurora failover;
- RDS Proxy pinning and state behavior if the proxy is enabled.

### Scope and derived-data isolation

- private versus team versus aggregate versus restricted-raw access;
- user removed from team during and before a query;
- classification downgrade and purpose change;
- stale policy/authorization/deletion epoch;
- ANN, lexical, entity, reranker, progressive, cache, export and telemetry side channels;
- small-cohort, repeated-query and complementary-cell attacks;
- replay, migration, import, backup/restore, rebuild, tombstone and garbage collection.

### Performance and recall

- exact-search oracle versus ANN by authorization selectivity;
- insufficient ANN results never cause a scope relaxation;
- query-plan assertions for required indexes and iterative scans;
- connection-budget and pool-wait thresholds;
- analytics disabled, saturated, rebuilding and unavailable while inference load runs.

## Implementation order

1. Define the scope lattice, authority-envelope schema, database roles and RLS
   conformance inventory.
2. Replace tenant-only database entry points with one transaction-local full-authority
   wrapper and explicit application predicates.
3. Implement canonical history tables and complete private-user history.
4. Add team-sharing and membership-epoch enforcement.
5. Add curated FTS and pgvector retrieval with exact-recall oracle and deletion
   receipts.
6. Add deterministic signals, attempt/recovery mining, eval and memory workflows.
7. Add aggregate-only enterprise patterns and separately controlled raw-evidence cases.
8. Run the full Aurora capacity, RLS, recall, failover and isolation gauntlet.
9. Promote indexes, pool sizes, reader usage and optional proxy/specialized retrieval
   only from measured evidence.

## Promotion gates

- zero cross-scope rows, IDs, counts, distances, snippets, cache entries, exports or
  telemetry labels in adversarial tests;
- complete RLS coverage and runtime-role proof;
- deletion/revocation propagation within the declared logical SLO;
- exact-versus-ANN recall floors pass for every critical authorization slice;
- connection and worker budgets stay within declared Aurora headroom under failover;
- analytics degradation leaves inference within its isolation SLO;
- every performance claim has a reproducible benchmark artifact and rollback;
- individual, team and enterprise workflows pass mock-free end-to-end tests.
