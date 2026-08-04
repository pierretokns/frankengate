# E2 raw CodeTraceBench retrieval factorial

**Run date:** 2026-07-30
**Status:** completed silver-label offline quality pilot; human-label and joint
PostgreSQL/RLS gates remain open
**Dataset:** `NJU-LINK/CodeTraceBench` at
`aa213b84ffb6690fc37ca15766d6ca174ec36d4d`
**Dense model:** `Qwen/Qwen3-Embedding-0.6B` at `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
**Result SHA-256:** `3c6d316ed890e8de40882234e66e57a70679cdaf0bbf13d16677ce510600d6aa`

## Cohort

The frozen raw allowlist contains 145 hash-verified archives,
83 task identities, 37
repeated-task groups, 99 leave-one-trace-out queries,
87 silver positive pairs, and
301 metadata-derived hard-negative
candidate pairs. Raw trace text and embeddings were not committed.

## Factorial result

Every arm retains the exact-identifier channel. `S`, `L`, and `D` switch structured,
lexical, and dense channels. Channels use fixed equal-weight reciprocal-rank fusion.

| Arm | R@1 | R@5 | R@20 | nDCG@20 | MRR | hard negative above positive | exact-ID R@20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0L0D0 | 0.268 | 0.480 | 0.732 | 0.549 | 0.578 | 0.333 | 0.800 |
| S0L0D1 | 0.308 | 0.535 | 0.737 | 0.591 | 0.630 | 0.273 | 0.806 |
| S0L1D0 | 0.278 | 0.515 | 0.677 | 0.551 | 0.593 | 0.303 | 0.739 |
| S0L1D1 | 0.293 | 0.571 | 0.702 | 0.584 | 0.621 | 0.283 | 0.767 |
| S1L0D0 | 0.288 | 0.672 | 0.808 | 0.644 | 0.661 | 0.283 | 0.867 |
| S1L0D1 | 0.333 | 0.641 | 0.818 | 0.666 | 0.687 | 0.263 | 0.894 |
| S1L1D0 | 0.308 | 0.636 | 0.758 | 0.621 | 0.654 | 0.283 | 0.822 |
| S1L1D1 | 0.328 | 0.616 | 0.783 | 0.646 | 0.669 | 0.263 | 0.856 |

The strongest arm by the preregistered lexicographic summary was
`S1L0D1` with Recall@20 0.818. This is not a
production winner: the labels are not human-adjudicated and the quality ranking did
not execute inside PostgreSQL.

## Authorization boundary

The result references the existing forced-RLS PostgreSQL benchmark only as an
independent composition proof. Its denied pre-ranking candidate matrix remained all
zero, but it used a different corpus and deterministic eight-dimensional vectors.
Therefore neither joint quality-plus-RLS nor deletion correctness has passed.

## Claim limits

- task identity is a silver positive, not a blinded human task-family label
- hard negatives are metadata-derived candidates, not adjudicated negatives
- publisher category and tags are available only to structured-on arms
- the raw user objective/prompt is not consistently projected across agents
- offline BM25 is not PostgreSQL FTS or pg_trgm
- offline dense ranking is not pgvector execution
- the independent RLS proof used a different public corpus and deterministic vectors
- no deletion, selective-RLS latency, concurrency, or real-Aurora test ran jointly with quality
- same benchmark work does not imply cross-user collaboration value
- no person-level skill, productivity, enterprise transfer, or causal utility claim is supported

## Required next gates

- blind and independently adjudicate task-family positives and hard negatives
- project provider-neutral objective/environment/failure/recovery views
- load the same candidates and 1024-dimensional vectors into forced-RLS PostgreSQL
- run deletion, stale/missing epoch, purpose, classification, and selective-scope oracles per arm
- measure PostgreSQL FTS, pg_trgm, exact pgvector, p50/p95/p99, bytes, rebuild time, and cost
- test a reranker only after freezing the best dense and non-dense candidate generators
- test domain adaptation only on a named hard slice and require +5 absolute Recall@20
