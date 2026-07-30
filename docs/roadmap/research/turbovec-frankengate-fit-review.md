# TurboVec Fit Review for Frankengate

**Date:** 2026-07-30

**Reviewed release:** Rust crate v0.9.0 / Python package v0.8.0,
commit [`1e7200c`](https://github.com/RyanCodrai/turbovec/commit/1e7200cfd8f26c92ce2855652db64bc7f85bc039)

**Decision:** concept and optional offline experiment only

## Verdict

[TurboVec](https://github.com/RyanCodrai/turbovec) is interesting as a compact,
in-process dense-vector scoring kernel. It is **not** a vector database, PostgreSQL
extension, or Aurora-compatible index. It should not be Frankengate's production
query authority or a persistent global sidecar, and it does not change the
Aurora-first architecture.

The useful concepts are:

- 2-, 3-, or 4-bit vector compression;
- training-free online quantization;
- SIMD flat scanning;
- caller-supplied allowlists enforced inside the scoring kernel, avoiding the
  underfilled results caused by ANN post-filtering;
- a possible memory-efficient reranking path inside an existing Rust analytics job.

The hard boundary is that every authority, durability, and lifecycle guarantee
would remain Frankengate's responsibility. Until vector memory or scoring is a
measured bottleneck, that additional machinery costs more than the library saves.

## What TurboVec is

TurboVec is an MIT-licensed Rust library with Python bindings built around Google
Research's [TurboQuant algorithm](https://arxiv.org/abs/2504.19874). It is an
independent project, not a Google product and not related to Turbopuffer.

The reviewed release is pre-1.0 and the Python package is explicitly classified
as **alpha**, with one listed maintainer. The release and provenance are published
on [PyPI](https://pypi.org/project/turbovec/0.8.0/). There is no Go binding. The
plausible Frankengate integration point is the existing Rust analytics worker.

TurboVec quantizes vectors and performs a SIMD-accelerated flat scan over eligible
32-vector blocks. It is not HNSW, IVF, a graph index, or a distributed search
service. Its search-time pruning comes from a caller-provided mask or allowlist.
See the pinned [search implementation](https://github.com/RyanCodrai/turbovec/blob/v0.9.0/turbovec/src/search.rs#L165-L199).

## What is attractive

- Approximately 8x serialized vector compression at 4-bit or 15–16x at 2-bit
  versus float32 in the project's tests.
- No separate corpus-dependent quantizer training phase.
- Online appends.
- Stable external `u64` IDs and O(1) in-memory removal through `IdMapIndex`.
- Concurrent immutable searches.
- In-kernel allowlists: Aurora SQL/RLS or lexical search can produce eligible IDs,
  then TurboVec scores only those candidates instead of retrieving globally and
  dropping unauthorized results afterward.

This could help an offline job that repeatedly searches millions of already
authorized task/session vectors under a tight memory budget.

## Production incompatibilities

| Frankengate requirement | TurboVec behavior |
|---|---|
| Aurora/PostgreSQL integration | None. TurboVec is not a PostgreSQL extension and is absent from the [Aurora extension catalog](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html). |
| RLS and classified-chunk enforcement | None. An allowlist is an optional function argument; an omitted allowlist performs unrestricted search. |
| MVCC, ACID, and transactions | None. Mutations change an in-memory index under caller coordination. |
| WAL, replication, PITR, HA, or failover | None. |
| Authorization and deletion epochs | None. An index can be stale relative to Aurora. |
| JSONB, joins, typed predicates, FTS, or sparse search | None. Filtering accepts IDs or a boolean mask. Hybrid retrieval must happen outside the library. |
| Multiple embedding releases | One separately built index per model/version/dimension. |
| Distributed scale | No sharding, ownership, replication, or replica coordination. |

For classified data, a global TurboVec index would recreate the same dangerous
pattern as a caller-enforced semantic cache: authorization becomes easy to omit.
A safe wrapper would need mandatory scope-aware APIs, current Aurora-derived
candidate IDs, authorization/deletion watermarks, result reauthorization,
encrypted snapshots, mutation reconciliation, fail-closed behavior, and replica
coordination.

That wrapper would be a new search system even if the library itself is small.

## Durability and lifecycle gaps

The stable v0.9.0 persistence path writes a checkpoint directly and does not supply
database WAL, MVCC, replication, or point-in-time recovery. See the pinned
[persistence implementation](https://github.com/RyanCodrai/turbovec/blob/v0.9.0/turbovec/src/io.rs#L42-L62).
Every append, deletion, or reclassification would have to reach every process and
checkpoint correctly. Main-branch improvements after the stable tag do not change
the production decision until they are released and tested.

The stable implementation also has relevant caveats:

- TQ+ calibration is fixed from the initial ingest. A small first batch can lose
  the calibration benefit for later appends, which is awkward for streaming trace
  ingestion. See the pinned [calibration code](https://github.com/RyanCodrai/turbovec/blob/v0.9.0/turbovec/src/encode.rs#L39-L52).
- The serving process keeps packed codes and a lazily built blocked search layout,
  so serialized index size understates full serving RSS. See the
  [index fields](https://github.com/RyanCodrai/turbovec/blob/v0.9.0/turbovec/src/lib.rs#L105-L150).
- Concurrent reads are supported; mutations need exclusive caller coordination.
  See the [concurrency contract](https://github.com/RyanCodrai/turbovec/blob/v0.9.0/turbovec/src/lib.rs#L22-L35).
- The rapid pre-1.0 changelog includes fixes for malformed-file allocations,
  silently wrong scalar fallback results, partial mutations, orphaned vectors, and
  deletion errors. The audit response is positive, but it is evidence of alpha
  maturity, not yet boring infrastructure.

## Benchmark interpretation

The stable project benchmarks use 100,000 vectors, 1,000 queries, warm in-memory
search, `k=64`, and medians of five batched runs. At 1,536 dimensions and 4-bit,
the pinned x86 benchmark reports high top-1 hit rate and performance near FAISS
FastScan. See the [benchmark harness](https://github.com/RyanCodrai/turbovec/blob/v0.9.0/benchmarks/suite/speed_d1536_4bit_x86_mt.py).

Those results do not establish Frankengate fitness:

- the reported recall measure emphasizes whether exact top-1 appears somewhere in
  the returned set, not enterprise task nDCG or complete Recall@k;
- there is no corporate trace corpus or domain-adapted embedding;
- stable v0.9 lacks a representative multi-tenant filtered benchmark;
- there are no authorization-epoch, deletion-lag, churn, restart, HA, concurrent
  write, or single-query p99 tests;
- the comparison is primarily with FAISS PQ, not Aurora pgvector exact search,
  `halfvec`, pgvector binary quantization plus reranking, HNSW, or VectorChord;
- serialized compression excludes document metadata, policy state, stable-ID map
  overhead, and the additional serving layout.

An independent July 2026 [TurboVec case-study preprint](https://arxiv.org/abs/2607.16973)
reports promising compression and allowlist results, but explicitly limits itself
to one dataset, CPU flat scan, a narrow synthetic privacy model, and no end-to-end
LLM answer-quality evaluation. It is a reason to benchmark, not a production proof.

A PostgreSQL-native TurboQuant proposal in
[pgvector PR #989](https://github.com/pgvector/pgvector/pull/989) was closed. The
maintainer noted missing comparisons with existing `halfvec` and binary
quantization/reranking paths and suggested RaBitQ may be a better direction. There
is no Aurora-compatible TurboVec roadmap to rely on.

## Comparison to the current choices

| Option | Relevance to Frankengate |
|---|---|
| Aurora + pgvector | Less compressed, but preserves SQL, forced RLS, MVCC, WAL, replication, PITR, joins, JSONB, FTS, exact recall, ANN options, and one deletion authority. Default. |
| TurboVec | Compact local dense flat-scoring library. Attractive only as a rebuildable, ephemeral accelerator after authorization. |
| VectorChord | Much closer to a PostgreSQL-native compressed ANN engine, but requires extensible/self-hosted PostgreSQL and a complete one-database migration. |
| Turbopuffer | Managed durable search service with filtering and multiple retrieval modes; a separate authority/operations boundary. Not comparable to an in-process TurboVec kernel. |
| pgContext | Higher-level context/retrieval concepts. TurboVec does not supply provenance, hybrid planning, temporal facts, or memory semantics. |

## Safe optional experiment

Do not add TurboVec to the production plan now. Add it as an arm in the existing
retrieval benchmark only if real measurements show that vector CPU/RAM over large
authorized candidate sets is the bottleneck.

The experiment must:

1. select an authorization-complete, classification-complete snapshot from Aurora;
2. build the TurboVec index inside one ephemeral Rust worker;
3. retain original vectors in Aurora for exact recall and rebuild;
4. pass only mandatory Aurora-authorized candidate IDs;
5. reauthorize returned IDs at the current epoch before exposure;
6. discard the index after the bounded job;
7. compare against exact pgvector, `halfvec`, pgvector binary quantization plus
   reranking, and normal pgvector ANN;
8. use real task/trace embeddings and selective RLS/classification slices;
9. measure full process RSS, build time, single-query p50/p95/p99, throughput,
   recall/nDCG, deletion/reclassification lag, and operational recovery;
10. advance only if the operations-adjusted gain is material.

TurboVec may make dense scoring smaller. It cannot supply task meaning, labels,
skill attribution, causal inference, RLS, temporal memory, or enterprise privacy.
Those remain the actual hard parts of the Frankengate design.
