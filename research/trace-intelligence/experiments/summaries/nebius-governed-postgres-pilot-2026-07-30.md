# Nebius governed PostgreSQL pilot

**Run date:** 2026-07-30
**Status:** completed local composition test; not an Aurora or production-scale result
**Input SHA-256:** `6d1f9fcd171f036e37a486fd5eeff68fd06f2c4ccef96cc60d20049b2535219e`
**Result:** `experiments/results/nebius-governed-postgres-pilot-2026-07-30.json`

## Question

Can the smallest proposed persistence system—one PostgreSQL 16 database with JSONB,
native full-text search, pgvector, typed authority columns, and forced RLS—store the
frozen public pilot and prevent unauthorized rows from becoming text or vector
candidates?

This run does not test semantic embeddings, multi-node Aurora, RDS Proxy, failover,
reader lag, hundreds of gigabytes, or enterprise intervention quality.

## Loaded evidence

| Item | Count |
|---|---:|
| Canonical trajectories | 300 |
| Source events | 11,490 |
| Reconstructed tool-call proposals | 5,595 |
| Reconstructed tool results | 5,295 |
| All reconstructed events | 10,890 |
| Deterministic signal artifacts | 300 |

Every source message remains present. The SWE-agent source does not contain native tool
spans, call authorization, or execution IDs. Tool semantics are therefore explicitly
`reconstructed`; the counts must not be described as observed executions.

## Authority result

All protected queries ran after `SET ROLE trace_research_app`. That role is a table
non-owner and is `NOSUPERUSER NOBYPASSRLS`. The transaction-local authority envelope
included tenant, subject, authorization epoch, classification ceiling, and purpose.

| Probe | Visible rows |
|---|---:|
| Authorized subject trajectories | 300 |
| Unauthorized subject trajectories | 0 |
| Unauthorized subject FTS candidates | 0 |
| Unauthorized subject vector candidates | 0 |
| Authorized subject with stale epoch | 0 |

The separate adversarial SQL fixture also passed private-user, team, cross-tenant,
classification, unapproved-purpose, missing-epoch, and stale-epoch assertions. This is
evidence that RLS can compose with both retrieval paths in the local fixture. It is not
evidence that every future query will do so; query conformance must remain mandatory.

## Local timings

One hundred warm iterations ran against the single-node Colima PostgreSQL fixture.
These values are diagnostic baselines, not service-level objectives.

| Query | mean | p50 | p95 | maximum |
|---|---:|---:|---:|---:|
| 50-row history page | 2.64 ms | 2.59 ms | 3.08 ms | 3.38 ms |
| FTS top 20 | 25.31 ms | 25.01 ms | 27.15 ms | 47.51 ms |
| deterministic-vector top 20 | 4.08 ms | 4.06 ms | 4.56 ms | 4.66 ms |

The analyzed FTS plan used an index scan. The vector query sorted the 300 authorized
artifacts instead of using HNSW, which is appropriate at this size and is a reminder
not to infer ANN behavior from a tiny corpus.

## What this changes

The experiment supports keeping one PostgreSQL authority for the next ladder stage.
It does not justify another search or vector system. The next storage experiment should
increase authorized and unauthorized candidate cardinality, preserve the same query
contract, and test selective RLS, deletion/epoch churn, top-k underfill, partitioning,
and concurrent ingestion before evaluating any external database.

The first real semantic test must use frozen relevance labels and compare exact
identifiers, structured task signatures, PostgreSQL FTS/trigram, dense retrieval, and
hybrid retrieval over exactly the same authorized candidates. These deterministic
eight-dimensional signal vectors are not a substitute.
