# FrankenGate Technical Domain Recommendations

Context read: `AGENTS.md`, `README.md`, `docs/roadmap/research/domain-adaptive-embeddings-and-secure-rag.md`, `docs/roadmap/research/bifrost-enterprise-docs-comparison-2026-07-17.md`, `docs/roadmap/research/finance-embedding-candidate-inventory.md`, `docs/roadmap/research/frankensearch-assessment.md`, and the current bead index.

These recommendations focus on the remaining FrankenGate control domains: secure FrankenSearch retrieval, tenant/team/user authorization, embedding adaptation, routing/failover, virtual-key governance, and day-two operational simplicity.

## 1. Make the retrieval authority envelope a shared security primitive

Recommendation: define one authority-owned metadata envelope for every document, chunk, entity, relation, embedding, rerank candidate, semantic-cache entry, and exported retrieval result. It should carry tenant, team/user/principal ownership, classification lattice value, policy version, source ID and source revision, retention, deletion epoch, embedding model, dimensions, chunking/index revision, and provenance signature. The predicate must execute before BM25, ANN, graph traversal, reranking, snippets, progressive `Initial`/`Refined` responses, semantic-cache lookup/write, replay/export, and telemetry labels.

Rationale: the research is explicit that post-filtering is not enough. Unauthorized candidates can leak through scores, counts, cache hits, graph neighborhoods, progressive fast-phase results, and audit metadata. A shared envelope prevents each vector adapter or sidecar path from inventing a slightly different ACL model.

Failure mode: FrankenSearch returns an authorized final answer but exposes unauthorized fast-phase candidates, score distributions, snippets, cache hits, or filtered-count telemetry. A stale policy/index revision silently degrades to permissive retrieval.

Implementation boundary: Aurora/Postgres/configstore owns the canonical envelope and policy versions. `framework/vectorstore`, `plugins/semanticcache`, and any FrankenSearch sidecar receive only authenticated derived copies. Do not put chunk buffers or growing retrieval state in `BifrostContext`; store only small IDs/revisions there.

Bead: yes, but as a child or acceptance split under existing `bif-kyy.17.12.4.1`, not a new epic. The existing bead covers the theme; it should be made executable around one envelope contract shared by vector stores, semantic cache, and FrankenSearch.

## 2. Build an adversarial retrieval authorization oracle before any Helm adoption

Recommendation: create a black-box conformance suite that runs the same tenant/classification/deletion/stale-policy cases against BM25, ANN, hybrid, reranker, semantic cache, progressive FrankenSearch phases, replay/export, and every configured vector adapter. Include cross-tenant near-duplicates, lexically similar hard negatives, stale index revision, deleted source, retained legal hold, wildcard cache key, and adapter filter-fallback cases.

Rationale: the vector-store interface supports multiple backends with different query/filter semantics, and `semanticcache` currently keys mainly by cache key/provider/model/params. Security has to be proven across adapters and cache paths, not reviewed once in a design doc.

Failure mode: Redis, Qdrant, Pinecone, Weaviate, pgvector, or FrankenSearch implements filtering differently; a scan fallback, missing field, cache namespace collision, or progressive refinement path leaks a forbidden candidate.

Implementation boundary: add the oracle around `framework/vectorstore` adapter tests, `plugins/semanticcache` plugin tests, and a future sidecar API harness. Fixtures should avoid raw confidential content and assert stable deny receipts, revision metadata, and no sensitive labels in logs/metrics.

Bead: yes. Add a focused child bead under `bif-kyy.17.12.4.1` or `bif-kyy.10.3` for the cross-adapter adversarial oracle.

## 3. Treat embedding adaptation as a versioned retrieval-contract migration

Recommendation: promote an explicit `RetrievalContract` concept: embedding model, tokenizer, query/document prompt format, chunker, normalization, dimensions, index backend, reranker, ACL policy version, deletion watermark, and evaluation bundle. Domain adaptation should produce a new contract and dual-index shadow/canary it; never patch weights or indexes in place.

Rationale: finance and enterprise jargon need hybrid lexical+dense evaluation, hard negatives, and sliced quality metrics. Adaptation may improve one cohort while harming another, and retrieval quality cannot be separated from authorization/deletion correctness.

Failure mode: an adapted embedder improves aggregate recall but loses ticker/version/policy-ID exact matches, breaks ACL/deletion tests, increases p95 latency, or makes rollback impossible because the old and new vector spaces were mutated in place.

Implementation boundary: keep training/evaluation offline and outside the gateway hot path. Use release-ledger provenance for model cards, tokenizer, weights, licenses, and checksums. Serving should switch by manifest/index revision, with shadow and sticky canary using existing routing/evaluation gates.

Bead: yes if phrased as a concrete `RetrievalContract` manifest child under `bif-kyy.17.12.3`, `bif-kyy.17.11`, or `bif-kyy.17.8`. The existing beads cover adaptation and RAG schemas, but the contract boundary should be explicit.

## 4. Keep FrankenSearch optional, derived, and outside the Go gateway process

Recommendation: prototype FrankenSearch only as an optional sidecar/service with authenticated tenant-scoped ingest/query APIs, bounded queues, explicit model-install lifecycle, and independent health/metrics. Gateway inference should continue without retrieval when the sidecar is unavailable; retrieval itself should fail closed when policy/index provenance is stale.

Rationale: FrankenSearch's Rust/asupersync/model stack is attractive for progressive retrieval, but it adds runtime, model, license, queue, and durability concerns. FrankenGate's core promise depends on the Go gateway staying a simple, low-latency authority membrane.

Failure mode: model downloads, refinement stalls, Rust worker crashes, index rebuilds, or FrankenSQLite durability issues take down inference, block rollout readiness, or force operators to debug an optional retrieval service as part of every gateway incident.

Implementation boundary: Helm values should default it off. Aurora remains authoritative for ownership, policy, retention, tombstones, and manifests. FrankenSearch stores only encrypted/authenticated derived indexes. Go integration should be a narrow client with timeouts, circuit breaker, and metadata-only failure receipts.

Bead: no new bead unless the prototype is approved. Existing `bif-kyy.17.12.4` already asks whether to embed, sidecar, or defer; update its acceptance criteria with this boundary.

## 5. Make tenant/team/user authorization one monotonic evaluator across all surfaces

Recommendation: use a single deny-by-default entitlement evaluator and principal epoch model for model listing, inference, MCP discovery/invocation, semantic cache, FrankenSearch, replay/export, dashboards, and logs. Every decision should return a compact receipt with principal, tenant, policy revision, evaluated scopes, and limiting rule.

Rationale: the README says enterprise governance primitives exist in isolated slices but must be proven in the request path. The research also requires tenant/team/user authorization before retrieval and cache. If these surfaces use separate evaluators, deprovisioning and group changes will drift.

Failure mode: a removed user loses dashboard access but still hits a semantic cache, resumes an MCP connection, queries a stale sidecar index, lists denied models, or exports replay evidence from a previous team membership.

Implementation boundary: `core/authorityepoch`, `plugins/governance`, configstore visibility filters, MCP ownership, and future retrieval APIs should share principal references and policy revisions. Transport handlers should call the same evaluator rather than duplicate team/user checks.

Bead: yes as an integration child under `bif-kyy.2.2`, `bif-kyy.5.6`, and `bif-kyy.21`, scoped to "all derived retrieval/cache/replay surfaces use the same evaluator and receipt."

## 6. Prove routing and fallback monotonicity with budget reservations attached

Recommendation: make routing/fallback transitions carry an explicit candidate-set certificate: authenticated principal, VK, allowed providers/models/keys, policy revision, route rule revision, reservation attempt, and fallback index. Later stages may only narrow the set. Every retry/fallback/shadow/tool turn must reserve, settle, or refund independently and idempotently.

Rationale: Bifrost fallbacks intentionally re-enter plugin hooks, and `AllowFallbacks` defaults to permissive when nil. FrankenGate needs stronger evidence that failover never restores a provider/model/key denied by VK, team/user entitlements, residency, budget, or capability policy.

Failure mode: a primary provider fails and core fallback tries a provider that the VK/team/user could not have selected directly; retries multiply spend without matching reservations; shadow/canary traffic leaks to a disallowed region or model family.

Implementation boundary: `plugins/governance/routing.go` and `core/bifrost.go` fallback loops are the key seam. Pair property tests for candidate-set monotonicity with `core/reservations` and `plugins/governance/admission.go` tests for attempt/lane accounting.

Bead: no new epic, but yes if added as a focused child under existing `bif-kyy.7.8`, `bif-kyy.7.1`, and `bif-kyy.4.9`.

## 7. Extend VK governance to every derived cache, index, and sidecar credential

Recommendation: treat virtual-key revocation/rotation/freshness as a first-class input to semantic cache keys, FrankenSearch sidecar authorization, MCP grants, provider-key selection, and replay/export eligibility. Cache and retrieval keys should include tenant, resolved VK or user authority epoch, policy version, classification scope, and index revision, not only request text/provider/model.

Rationale: upstream-compatible VK headers are retained, but FrankenGate's enterprise contract is stronger: durable fingerprints, cross-pod propagation, readiness fencing, and fail-closed stale authority. Derived data can otherwise outlive the key that created it.

Failure mode: a revoked or rotated VK cannot call the provider but can still receive a cached response, use a stale sidecar session, access an MCP allow-on-all shortcut, or query an index populated under broader authority.

Implementation boundary: `plugins/governance` owns VK evaluation and freshness, configstore owns durable state, `plugins/semanticcache` and FrankenSearch must include authority dimensions in lookup/write keys, and readiness must prove consumers loaded the current snapshot before protected traffic.

Bead: yes, but as a targeted extension to `bif-kyy.3`, `bif-kyy.18`, `bif-kyy.22`, and `bif-kyy.17.12.4.1`, not a separate VK program.

## 8. Design the launch posture around one authority plane and disposable accelerators

Recommendation: keep launch operations boring: Aurora/Postgres is the authority for policy, VKs, budgets, principal epochs, tombstones, manifests, and outbox cursors; Redis/vector stores/FrankenSearch/evaluators/training workers are accelerators or derived services. Each accelerator needs a kill switch, bounded queues, low-cardinality metrics, stale/fail-closed semantics, and a documented degraded mode.

Rationale: the roadmap repeatedly rejects Redis, vector indexes, graph extraction, training, and learning services as mandatory authority. The easiest enterprise system to operate is one where operators know which component is truth and which can be rebuilt or disabled.

Failure mode: optional Redis, vector search, progressive refinement, eval workers, or training pipelines become implicit launch dependencies; outages create split-brain decisions, unbounded queues, readiness confusion, or impossible incident triage.

Implementation boundary: Helm values/schema, health/readiness handlers, governance synchronization metrics, runbooks/doctor output, and release gates. The gateway data plane should expose clear "authority stale", "retrieval unavailable", "accelerator disabled", and "metadata-only" states without coupling inference availability to optional services.

Bead: yes if framed as an operational acceptance bead under `bif-cks.10`, `bif-kyy.6.11`, `bif-kyy.23`, and `bif-kyy.17.12.4`: "operator mode matrix and kill-switch/degraded-mode oracle for all accelerators."

## Suggested Bead Actions

1. Add child under `bif-kyy.17.12.4.1`: shared retrieval authority envelope and enforcement points.
2. Add child under `bif-kyy.17.12.4.1` or `bif-kyy.10.3`: cross-adapter adversarial retrieval authorization oracle.
3. Add child under `bif-kyy.17.12.3`/`bif-kyy.17.8`: immutable retrieval-contract manifest and migration rules.
4. Update `bif-kyy.17.12.4`: FrankenSearch sidecar-only, default-off, no inference dependency.
5. Add integration child under `bif-kyy.2.2`/`bif-kyy.5.6`/`bif-kyy.21`: shared evaluator receipts across retrieval/cache/replay.
6. Add focused child under `bif-kyy.7.8`/`bif-kyy.4.9`: fallback monotonicity plus reservation attempt accounting.
7. Extend VK beads with derived cache/index/sidecar authority invalidation.
8. Add operational-mode oracle under `bif-cks.10`/`bif-kyy.6.11`/`bif-kyy.23`: one authority plane, disposable accelerators, kill switches, and degraded modes.
