# Vector retrieval and evidence-storage architecture review

Status: architecture recommendation and experiment plan. This document does not
authorize a production backend, Helm dependency, model promotion, or movement of raw
logs into a vector index.

## Executive decision

Do not put "all logs inside pgvector." A vector index is not a log store, and an
embedding is not the authoritative record. Keep canonical, append-oriented,
retention-governed log/evidence metadata in PostgreSQL and encrypted object storage as
appropriate. Produce privacy-reviewed chunks and embeddings asynchronously as derived,
versioned indexes.

Use one default stack and require evidence before adding anything else:

1. **PostgreSQL is the authority plane.** It owns tenants, principals, teams, policy
   versions, virtual-key epochs, retention, deletion tombstones, evidence manifests,
   source lineage, model/index manifests, and the outbox that drives derived stores.
2. **pgvector is the production default for every initial vector workload.** It keeps
   authorization joins, RLS, transactions, backups, deletion, and index state in the
   database we already operate. Separate schemas, roles, partitions, pools, and capacity
   budgets are cheaper than another database.
3. **PostgreSQL-backed caching is the default too.** First prove that ordinary or
   unlogged tables where acceptable, expiry indexes, batching, and a small bounded
   in-process cache miss the end-to-end SLO before adding Redis/Valkey.
4. **FrankenSearch is research-only retrieval orchestration.** Its
   value is orchestration: two-tier embeddings, BM25, ANN, RRF, reranking, progressive
   results, and graceful refinement failure. It should query an adapter contract or
   maintain a rebuildable local index. The current integration material does not expose
   a ready-made pgvector backend, so "point FrankenSearch at pgvector" requires an
   explicit backend adapter or a service boundary; it is not a configuration switch.
5. **FAISS is an offline benchmark, mining, and training tool by default—not a production
   layer on pgvector.** Both pgvector and FAISS build ANN indexes. Putting FAISS "on
   top" duplicates vector, index, memory, checkpoint, update, delete, authorization and
   failover state. It requires a measured blocker and a passing security benchmark.
6. **LightRAG is a graph-RAG pipeline, not a vector database choice.** Deploy it only for
   evaluated multi-hop/entity-relation workloads. Its graph and vector artifacts are
   additional sensitive derived copies and must obey the same pre-retrieval authorization,
   tombstone, provenance, and model/index revision contract.

Qdrant, Redis/Valkey Search, Weaviate, Pinecone, and a production FrankenSearch service
are escape hatches, not planned components. Admit one only with a written blocker, a
failing Postgres benchmark, a passing replacement benchmark, security conformance, and
an explicit license/update/on-call cost review.

## Why PostgreSQL plus pgvector is compelling

PostgreSQL already participates heavily in the planned architecture. Adding pgvector
can avoid another operational system while retaining transactions, backups, SQL joins,
partitioning, observability, and mature lifecycle tooling. RLS is a material advantage:
when enabled, normal table access is policy-controlled and defaults to deny if no policy
matches. It is not sufficient by itself:

- table owners normally bypass RLS unless `FORCE ROW LEVEL SECURITY` is used;
- superusers and roles with `BYPASSRLS` bypass it;
- connection pooling must set tenant/principal claims transaction-locally and prevent
  session-state bleed;
- background workers, migrations, backups, replicas, and security-definer functions
  need explicit threat treatment;
- ANN filtering behavior still needs a recall and side-channel oracle.

The safe pattern is a least-privileged application role, forced RLS on protected tables,
transaction-local trusted identity, an authority-owned predicate or security-barrier
view, and adversarial tests using the exact production query role. Never accept a
caller-supplied tenant ID as proof of authority.

### Why FAISS on top is not the default

FAISS is an excellent vector-search library for offline mining, evaluation, GPU search,
quantization experiments, and exact-search oracles. It is not a database and does not
inherit PostgreSQL transactions, RLS, WAL, replication, point-in-time recovery,
retention, or deletion semantics.

A production FAISS tier fed from pgvector would make us build and operate a CDC/outbox
consumer, monotonic checkpoint, second index snapshot/restore path, per-tenant
authorization before candidate exposure, tombstone convergence proof, RAM/GPU replicas,
model/index routing, dual-index migrations, readiness fencing, and Go-to-C++ bindings or
a service process. FAISS HNSW also does not directly support vector removal, and its
official index-selection guidance treats indexes as RAM-resident. Those properties are
fine for immutable offline snapshots but expensive for a live deletion-governed corpus.

The minimalist sequence is:

1. pgvector exact search as correctness oracle;
2. pgvector HNSW, with IVFFlat only where benchmarks favor it;
3. tune `halfvec`, binary quantization plus reranking, partitions/partial indexes,
   iterative filtered scans, queries, and Aurora capacity isolation;
4. benchmark FAISS against the same frozen corpus and authorization oracle only if the
   tuned pgvector path misses a named SLO;
5. use production FAISS only for a requirement pgvector cannot satisfy, such as
   GPU-batched offline mining or a proven online scale/latency target.

"FAISS candidate IDs then PostgreSQL post-filter" is not safe for protected online
retrieval: forbidden IDs, distances, counts, and timing have already crossed the
authorization boundary. Pre-authorized shards or selector-aware search would be needed,
which raises the complexity bar further.

### pgvector model and ANN limits

pgvector indexes vectors, not embedding models. Any model can be used if its output can
be represented by the selected type and every indexed/query vector has the expected
dimensions and preprocessing. The retrieval contract must pin model, tokenizer,
query/document prompts, normalization, dimensions, distance metric, chunker, and index
revision.

Current upstream limits and consequences:

- `vector` supports up to 2,000 dimensions; `halfvec` up to 4,000; `bit` up to 64,000;
  `sparsevec` up to 1,000 non-zero elements.
- HNSW and IVFFlat are the built-in ANN index families. HNSW usually has a better
  speed/recall trade-off but higher memory/build cost; IVFFlat requires training and
  careful list/probe tuning.
- ANN indexes are tied to a vector type, distance operator class, and practical model
  dimension. Different models or dimensions should normally use separate columns,
  partitions, tables, or indexes. Never compare vectors from different spaces.
- Filtered ANN can return too few candidates because ordinary filters are applied after
  the approximate scan. Iterative scans improve this, but strict authorization and
  recall must be measured together. Selective tenants may benefit from partitioning or
  partial indexes; high-cardinality tenancy can otherwise multiply indexes or scanning.
- HNSW build, memory, vacuum, WAL, replica lag, backup size, and primary workload
  interference become meaningful at scale. The shared-server choice must be capacity
  isolated and benchmarked under simultaneous governance/log writes and retrieval.
- Exact search remains valuable as the correctness oracle. Every ANN benchmark should
  compare sampled results against exact search and report recall by authorization slice.

Qwen3 0.6B/4B/8B and other 1,024-dimensional candidates fit `vector`; a model above
2,000 dimensions requires `halfvec`, dimensionality reduction, or another backend.
Changing dimensions is a dual-index migration, not an in-place schema edit.

## Why not embed every log

Logs contain prompts, completions, tool arguments/results, customer data, and
high-cardinality identifiers; verified credentials must already have been removed.
Embedding all logs creates a second representation
that is difficult to redact, interpret, delete, or prove non-memorizing. It also spends
database CPU, WAL, storage, backup, and index-build capacity on data that often has no
retrieval value.

Use three explicit layers:

| Layer | Contents | Storage posture |
|---|---|---|
| Canonical evidence | allowlisted metadata, receipts, source/blob references, retention and deletion state | PostgreSQL plus encrypted object storage for approved payloads |
| Curated retrieval corpus | reviewed chunks, provenance, ACL envelope, embedding/retrieval contract | pgvector |
| Ephemeral results | semantic cache entries and bounded working sets | PostgreSQL plus bounded in-process cache initially |

Curated same-scope retrieval corpora may contain authorized full text and embeddings
when every chunk carries source, subject/audience, classification, purpose,
policy/authorization/deletion epochs, and enforced RLS. Curation remains purpose-bound,
sampled or triggered, and independently deletable. An index outside the equivalent
governed scope receives a destination-transformed projection. An embedding never
replaces the source hash or approved source reference.

### Sensitive-content governance is broader than PII redaction

Presidio is useful as one detector for names, contact details, account numbers, and
other recognizable entities. It does not decide whether text is appropriate for a
retrieval corpus. Salary, performance concerns, interpersonal complaints, health or
family context, legal strategy, security incidents, unreleased business plans, customer
confidentiality, and employment allegations may remain highly sensitive even after all
direct identifiers are removed. Conversely, removing every person's identity can make
an approved case unusable or destroy the accountability needed to adjudicate it.

Use a policy pipeline, not a universal redaction pass:

1. **Purpose gate:** state why the source may be used—support, incident response,
   product improvement, skill evaluation, or training are separate purposes.
2. **Detectors:** run Presidio plus domain rules/classifiers for compensation, HR,
   health, legal, security, credentials, customer secrets, harassment/allegation,
   financial and other organization-specific categories. Detectors emit spans,
   categories and confidence; they do not authorize use.
3. **Contextual policy:** combine content categories with source, author/subject roles,
   tenant, audience, consent, region, retention, legal hold and intended cohort.
4. **Transform:** choose exclude, quarantine for review, mask, pseudonymize consistently,
   summarize to an approved abstraction, split the chunk, or retain under a restricted
   classification. Do not assume masking is always the correct transformation.
5. **Human review:** require it for ambiguous/high-impact sources and any training or
   cross-team reuse. Keep reviewer reason codes and policy revision, not sensitive prose
   in audit logs.
6. **Retrieval enforcement:** attach subject and audience scope, purpose, classification,
   policy revision, retention and deletion epoch to every chunk and embedding. RLS and
   query predicates enforce these before ANN candidate exposure.
7. **Evaluation:** maintain a versioned, access-controlled gold set measuring sensitive
   false allows, destructive over-redaction, pseudonym consistency, relationship
   leakage, and inference from neighboring chunks. Never use production sensitive text
   as an unreviewed regression fixture.

Prefer selective curation over embedding every log. Preserve a metadata-only evidence
event when content is ineligible so the flywheel can measure missingness without
retaining the content. Do not destroy useful same-scope evidence merely because it
contains PII; enforce its classification and audience instead.

Contextual sensitive-content model training is explicitly out of scope. FrankenGate
uses conservative source allowlists, purpose restrictions, existing deterministic
redaction where useful, and human approval for corpus admission. Ambiguous logs are not
embedded. This may leave useful evidence unavailable, but it avoids introducing another
model lifecycle and an unreliable authorization dependency.

## Backend comparison

| Capability | pgvector | Qdrant | Redis/Valkey Search | FrankenSearch | LightRAG |
|---|---|---|---|---|---|
| Primary role | relational vector extension | specialized vector engine | hot cache/search engine | hybrid/progressive retrieval orchestrator | graph plus vector RAG pipeline |
| Authority/RLS | strongest fit; native SQL/RLS | application/service policy; payload filters are not identity | application/service policy; query filters are not identity | must be added at service boundary | must be enforced across graph, vector, cache and generation |
| ANN | HNSW, IVFFlat, exact oracle | HNSW, dense/sparse/multivector, quantization | FLAT, HNSW, and newer SVS-VAMANA options | HNSW/local two-tier path documented | delegated to configured vector storage |
| Hybrid lexical+dense | SQL FTS plus application fusion | native query/payload features; validate exact desired fusion | full-text plus vector filters/query syntax | core strength: Tantivy, semantic tiers, RRF/rerank | graph/entity plus vector retrieval modes |
| Model flexibility | type/dimension bound per index | collection/vector configuration bound | schema dimension/type bound | embedder traits/stack; custom model integration required | embedding change can require rebuilding vector tables |
| Scale isolation | shares PostgreSQL unless separated | independent vector cluster | independent memory-centric service | independent process/sidecar | multiple derived services/stores |
| Operational burden | lowest incremental burden, highest contention risk | extra stateful service and shard operations | likely already useful, but memory/cost/eviction semantics | Rust/model/index lifecycle | highest: extraction, graph, vector, LLM and storage lifecycle |
| Best FrankenGate use | secured curated corpora and moderate evidence search | large/high-QPS retrieval corpora | semantic cache and hot disposable recall | optional retrieval API and experimentation | evaluated multi-hop knowledge workflows only |

Weaviate and Pinecone remain valid adapter targets but are not first choices here.
Weaviate adds another broad database/operator surface with overlap against Qdrant.
Pinecone trades operations for external-service cost, region, credential, deletion, and
evidence-control concerns. Keep both behind the conformance contract rather than making
them architectural dependencies.

## Workload-by-workload choice

### 1. Gateway request logs, audit and observability

Store structured, allowlisted log metadata and audit receipts in PostgreSQL. Store
approved large payloads in encrypted object storage with immutable references. Use SQL
FTS and ordinary indexes first. Build a separate curated pgvector table only for a
defined incident/support/evidence-search purpose. Do not synchronously embed on the
request path.

### 2. Semantic response cache

Start with PostgreSQL plus a bounded in-process cache where correctness permits. Keys
must include tenant, principal/virtual-key authority epoch, policy version,
classification scope, provider/model/request contract, and index revision. Add another
cache server only after realistic concurrency, expiry, cleanup and write-amplification
tests show a named SLO cannot be met.

### 3. Enterprise knowledge/RAG and data curation

Use PostgreSQL metadata, pgvector and PostgreSQL lexical search. This gives one
transactional authorization/deletion boundary. A second online engine requires a
written, measured blocker. Keep FrankenSearch offline/research-only until incremental
quality proves worth its complete operational surface.

### 4. Fine-tuning, distillation and evaluation datasets

PostgreSQL stores manifests, lineage, approvals, cohort membership, and pointers;
encrypted object storage stores immutable dataset shards. A vector index is a curation
aid for deduplication, hard-negative mining, clustering, and retrieval—not the dataset
ledger. Offline jobs use pgvector and may use FAISS locally for bounded mining and
evaluation. Promotion consumes immutable dataset/evaluator/model digests, never a live
index.

### 5. Skill reinforcement, ASPIRE-style repair and skill loops

The primary retrieval object is structured trajectory/evidence metadata, not raw chat
similarity. Use PostgreSQL for causal joins, dependency graphs, revision lineage,
promotion receipts, and deletion influence. Use pgvector to retrieve similar reviewed
failure/recovery cases. PostgreSQL FTS plus pgvector provides hybrid recall over skill
text, deterministic tool contracts, goldens, and past cases. Do not let nearest-neighbor similarity publish a skill change;
the existing replay, critical-slice, human approval, canary, and rollback gates remain
decisive.

### 6. NVIDIA-style data flywheel and robotics/multimodal research

Adopt the process pattern—trace serialization, curation, immutable experiments,
evaluation, human-gated promotion—not a single storage product. Large image/video/audio
or trajectory payloads belong in object storage; PostgreSQL owns manifests, temporal
segments, embodiment/task/environment labels, policy and lineage. A specialized vector
store may hold multimodal embeddings, but retrieval contracts must distinguish modality,
encoder, temporal window, dimensions, normalization, and safety/tenant scope. Graph RAG
is justified only if entity/temporal/action relations measurably improve the target
multi-hop task.

## FrankenSearch and pgvector integration boundary

There are three viable shapes, in preference order for experiments:

1. **FrankenSearch owns a derived local index.** PostgreSQL outbox events deliver
   authorized chunks and tombstones. This best exercises FrankenSearch's canonical
   `TwoTierSearcher`, but duplicates embeddings/index state.
2. **FrankenSearch becomes a retrieval orchestrator over backend adapters.** Implement a
   pgvector candidate-source adapter returning stable document IDs, distances,
   provenance and authorization receipts, then use canonical fusion/reranking. This is
   the answer to "point FrankenSearch at pgvector," but it is development work and must
   avoid reimplementing its orchestration.
3. **Gateway composes pgvector and FrankenSearch results.** Avoid this unless the sidecar
   cannot support an adapter: it risks duplicated RRF, score normalization, pagination,
   cancellation and progressive-phase bugs.

Regardless of shape, authorization happens before any candidate, count, distance,
snippet, graph edge, progressive phase, rerank input, cache entry, or telemetry label
crosses the service boundary. Post-filtering the final top-k is not acceptable.

## Shared retrieval contract

Every derived object and query must carry an immutable contract identifier covering:

```text
tenant_id
principal/team/user authority epoch
classification and purpose
policy version
source id, source revision, retention and deletion epoch
embedding model, model digest, tokenizer, prompt format, dimensions, normalization
chunker and chunk revision
lexical schema/analyzer
ANN backend, distance metric and index parameters
reranker and fusion configuration
index revision and tombstone watermark
evaluation bundle and release manifest
```

Unknown, stale, mismatched, deleted, or unprovable values fail closed for protected
retrieval. Contract changes create a new index and use shadow/dual-read/sticky-canary
evaluation with rollback; they never mutate the serving vector space in place.

## Embedding model lifecycle and efficient re-embedding

Treat an embedding model as a small signed release artifact and an embedding index as a
materialized view built from a specific release. Never update model weights or overwrite
vectors in place.

### Immutable objects

- `EmbeddingModelRelease`: base model and revision, adapter/projection weights, tokenizer,
  query/document templates, normalization, dimensions, quantization, license, training
  dataset/evaluator digests, code/container digest, hardware/runtime compatibility,
  security review, checkpoint lineage and signature.
- `ChunkRevision`: source hash/revision, canonical chunk text hash, chunker revision,
  sensitivity decision/policy revision, ACL envelope, retention and deletion epoch.
- `EmbeddingRecord`: chunk revision, model release, vector checksum, created time and
  job/checkpoint ID. Primary key is `(chunk_revision_id, model_release_id)`.
- `IndexRelease`: model release, eligible chunk snapshot/watermark, pgvector table or
  partition, ANN parameters, build statistics, exact-vs-ANN recall, security/evaluation
  bundle, promotion state and rollback parent.

Store each model release in its own vector table/partition or dimension-compatible
column family. A stable catalog/view maps a named retrieval contract to the active index
release. Do not mix scores from model spaces and do not reuse an ANN index across model
releases merely because dimensions match.

### Resumable re-embedding job

1. Freeze an eligible `ChunkRevision` snapshot at a source/deletion/policy watermark.
2. Create a new model/index release in `building`; the current release stays serving.
3. Select only missing `(chunk_revision, model_release)` pairs. Reuse a vector only when
   the complete embedding input contract hash matches—not just source text or dimensions.
4. Batch deterministically by tenant and chunk ID, enforce per-tenant quotas, checkpoint
   last completed ranges plus counts/checksums, and make upserts idempotent.
5. Keep tombstones and policy changes flowing during the build. At catch-up, require the
   new release to reach the authority watermark; otherwise it cannot serve.
6. Build the ANN index after bulk load where appropriate, analyze it, and verify row,
   tenant, classification and deletion counts against the frozen manifest.
7. Run exact-versus-ANN recall, frozen retrieval quality, sensitive-content, RLS,
   deletion, latency/cost and critical-slice gates. Missing or unevaluable cases are
   explicit failures, not dropped rows.
8. Shadow both releases on sampled approved queries. Compare paired results; never merge
   their raw distances. Then sticky-canary the whole retrieval contract.
9. Promote by one transactional catalog-pointer change with an immutable receipt.
   Retain the prior release for the rollback window.
10. Garbage-collect only after retention, rollback, legal-hold, deletion and audit rules
    permit it. Drop the old table/index concurrently and record the destruction receipt.

This supports multiple live versions without doubling forever. Normally keep one active,
one candidate, and one rollback release; cap concurrent builds; prioritize changed/new
chunks; and schedule full re-embedding through bounded workers so it cannot starve the
gateway or control plane.

### Verified fine-tuning loop for tiny embedding models

Fine-tune offline from approved immutable data, never directly from raw production logs:

1. Compile positives, hard negatives and abstention/unauthorized cases from reviewed
   evidence. Split by source/person/thread/time to prevent leakage; freeze a never-train
   holdout and critical security slices.
2. Start with a frozen base and train a small projection, adapter/LoRA where supported,
   or contrastive checkpoint. Record step/epoch checkpoints with optimizer/scheduler,
   RNG seeds, code, config, data manifest, metrics and artifact hashes.
3. Evaluate every candidate against BM25, the unadapted base and the current production
   model on recall@k, nDCG/MRR, exact identifiers, jargon, hard negatives, OOD,
   calibration/abstention, sensitive false allows/denies, deletion, latency, memory and
   cost. Aggregate improvement cannot mask a critical-slice regression.
4. Re-mine hard negatives using the candidate but review and snapshot them before the
   next round. Never let the model train on its own unverified outputs automatically.
5. Package the smallest deployable delta when possible, but sign and promote the entire
   `EmbeddingModelRelease` contract. Model registry states are `candidate`, `validated`,
   `shadow`, `canary`, `active`, `deprecated`, `quarantined`, and `retired`.
6. Promotion requires reproducible rerun, evaluator calibration, human approval, signed
   artifacts, dual-index shadow/canary, and tested rollback. A model checkpoint is not a
   production checkpoint until its corresponding index release and policy watermark are
   also proven.

FAISS is particularly useful inside this offline loop for fast exact/ANN evaluation,
hard-negative mining, clustering, quantizer experiments and GPU batches. That captures
its strengths without turning it into another day-two production database.

## Deployment and Helm recommendation

### Self-service analytics topology

Use one externally visible gateway/API contract but separate Kubernetes workloads:

```text
Dashboard or Claude Code
  -> OIDC session or short-lived device/PKCE grant
  -> FrankenGate analytics API (submit/status/cancel/export/delete)
  -> PostgreSQL report job + authorization/evidence snapshot
  -> bounded analytics worker queue
       -> PostgreSQL aggregates/logstore
       -> optional FrankenSearch authorized derived index
       -> offline embedding/evaluation worker when requested
  -> PostgreSQL result manifest/receipt
  -> analytics API returns citations, coverage, missingness and metrics

Inference clients
  -> gateway inference Deployment and reserved capacity
  -> never execute report, embedding, reindex or mining work
```

Claude Code never receives PostgreSQL, FrankenSearch, provider-key or internal service
credentials. It uses a short-lived audience-bound token with explicit scopes such as
`evidence:write:self`, `analytics:submit:self`, `analytics:read:self`,
`analytics:cancel:self`, `evidence:export:self` and `evidence:delete:self`. Team reports
require a separate grant and aggregation/privacy policy. The dashboard uses the same API
and authorization evaluator, avoiding a privileged UI-only path.

Reports are asynchronous: submission returns `202` plus an idempotent job ID. PostgreSQL
stores job state, frozen evidence/policy watermark, owner, purpose, quotas, progress,
cancellation, result manifest, expiry and audit receipt. Workers claim bounded renewable
leases with `FOR UPDATE SKIP LOCKED` or the existing durable queue pattern. `NOTIFY` is a
wake-up hint; PostgreSQL rows remain durable truth.

FrankenSearch receives only sanitized, authorized, revisioned chunks. Every search is
bound to the server-resolved tenant/principal/policy epoch and index watermark before
candidate generation. It returns IDs/scores/revisions to the worker; PostgreSQL remains
the final authority for result eligibility and citations. Index loss is recoverable and
does not lose report/job/evidence truth.

### Independent scaling and resource isolation

| Workload | Deployment | HPA signals | Isolation requirements |
|---|---|---|---|
| inference | gateway | active requests/streams, provider queue age, latency, CPU | reserved nodes/capacity, database pool and disruption budget; highest priority |
| analytics API | control/API | request concurrency/latency and CPU | lightweight validation/job operations only; no search or embedding execution |
| analytics workers | worker pools by CPU/GPU class | eligible queue depth/age, processing duration, CPU/GPU | tenant-fair admission, bounded leases, separate DB pool/role, cancellation and scale-to-zero where supported |
| FrankenSearch | retrieval service | query concurrency/latency, queue depth, memory/CPU/GPU saturation | default-off, dedicated resources/PDB/topology, no inference readiness dependency |

Use Kubernetes PriorityClasses, ResourceQuotas, LimitRanges, topology/anti-affinity,
separate service accounts and NetworkPolicies. Reserve PostgreSQL connections for
inference/control work; analytics pools have hard lower limits and statement/lock/idle
timeouts. Re-embedding, index rebuild and large reports use explicit per-tenant and
cluster budgets. Backpressure leaves jobs queued or rejects them with a stable retryable
receipt; it never borrows inference pod CPU or its reserved database connections.

The acceptance load test runs peak inference while submitting personal reports,
re-embedding a candidate model and rebuilding an index. It must prove the inference
latency/error budget, connection reservation, fair queueing, cancellation, worker HPA,
FrankenSearch failure isolation, drain and recovery.

- Add pgvector as an optional capability of the external or bundled PostgreSQL profile,
  not as a second mandatory database. Separate schemas, roles, quotas, maintenance
  windows, and preferably storage/IOPS budgets from control-plane tables.
- Keep vector backends behind the existing `framework/vectorstore` contract and Helm
  choice. Add a pgvector adapter only after the security/performance conformance suite.
- Do not add FrankenSearch, Qdrant, Redis/Valkey Search, Weaviate, Pinecone or FAISS to
  the default chart. Customer-supplied external adapters remain compatibility options.
- Expose explicit modes: retrieval disabled, accelerator unavailable, authority stale,
  index rebuilding, metadata-only, and fully ready. Protected retrieval is denied when
  stale; ordinary inference follows its configured no-retrieval behavior.

## Required decision experiments

Do not choose from vendor feature lists. Run one corpus and one security oracle across
the candidates.

1. Build frozen finance/jargon, enterprise-policy, skill-case, and multimodal-manifest
   cohorts with exact-match, semantic, multi-hop, hard-negative, cross-tenant,
   deletion, stale-policy, and OOD slices.
2. Compare lexical, dense, hybrid, hybrid+rereanker, and graph-augmented arms. Report
   recall@k, nDCG, MRR, supportedness, citation precision, ACL false allow/deny,
   deletion SLA, p50/p95/p99, throughput, build time, memory, storage, WAL/replica lag,
   recovery time, and operator steps.
3. Compare pgvector exact versus HNSW/IVFFlat and filtered iterative scans; test shared
   PostgreSQL interference under realistic log/governance writes.
4. If and only if pgvector fails a gate, benchmark FAISS and the smallest relevant
   alternative against that exact failure. Include full day-two and security cost.
5. Add LightRAG only to cohorts with a stated multi-hop hypothesis. Measure extraction
   cost, graph freshness, deletion completeness, unauthorized neighborhood leakage and
   incremental quality over hybrid retrieval.
6. Fault-inject database/vector outage, stale policy, tombstone lag, partial rebuild,
   model mismatch, queue saturation, cancellation and tenant hot-spotting.

## Bead review and proposed graph changes

The current graph already contains the correct epics and should not receive a new
parallel "vector platform" epic. Refine existing work:

- Extend `bif-kyy.17.12.4.1` with the shared retrieval contract, forced-RLS threat model,
  pre-candidate authorization API, and cross-backend adversarial oracle.
- Add a child under `bif-kyy.17.12.4.1` for the pgvector adapter and filtered-ANN/RLS
  benchmark. It depends on the authority envelope and unblocks Helm adoption.
- Add a sibling experiment under `bif-kyy.17.12.4` proving the PostgreSQL-only design.
  Alternative backends are activated only by a recorded failed gate. LightRAG is an
  optional arm gated by a multi-hop cohort.
- Make `bif-kyy.17.12.3` own the immutable retrieval-contract manifest and dual-index
  model migration protocol.
- Link deletion/tombstone acceptance to `bif-kyy.16.7`, entitlement freshness to
  `bif-kyy.5.6`/`bif-kyy.22`, and operational degraded modes to `bif-cks`.
- Reuse `bif-kyy.13` for dataset/model lifecycle and `bif-kyy.15` for skill-loop
  promotion; vector similarity must not create an alternative promotion path.

Before changing the bead graph, finish the requested adversarial duel and planning
review. The live NTM session was busy during this review and the local environment
exposed only one fresh agent launcher, so no new compliant two-model duel was injected.
The existing `WIZARD_IDEAS_CC.md` independently converges on the same authority-plane,
sidecar, retrieval-contract, and cross-adapter-oracle boundaries, but it is not a
completed duel until cross-scoring and reveal artifacts exist.

## Sources

- pgvector upstream README: https://github.com/pgvector/pgvector
- PostgreSQL row security policies: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Qdrant filtering: https://qdrant.tech/documentation/search-precision/filtered-search/
- Qdrant distributed deployment: https://qdrant.tech/documentation/guides/distributed_deployment/
- Redis vector search concepts: https://redis.io/docs/latest/develop/ai/search-and-query/vectors/
- LightRAG upstream repository: https://github.com/HKUDS/LightRAG
- Local FrankenSearch assessment: `docs/roadmap/research/frankensearch-assessment.md`
- Local secure RAG research: `docs/roadmap/research/domain-adaptive-embeddings-and-secure-rag.md`
