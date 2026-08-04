# Governed Wisp PostgreSQL benchmark

**Status:** end-to-end local policy and query experiment complete

**Run date:** 2026-07-30

## Question

Can the smallest Frankengate storage architecture—one governed PostgreSQL
schema—serve a user's private longitudinal trace history, structural search,
controlled full-text search, and review proposals while eliminating
unauthorized candidates before ranking?

This is a local PostgreSQL experiment, not an Aurora emulator. It tests SQL
composition, row-level security, proposal lifecycle, lineage, and warm-cache
single-client query behavior.

## Dataset and persisted representation

The pinned Wisp corpus produced:

| Governed object | Count |
| --- | ---: |
| Private trajectories | 104 |
| Canonical events | 17,505 |
| Tool proposals | 2,209 |
| Completed tool results | 2,104 |
| Failed tool results | 103 |
| Malformed-source events | 2 |
| Deterministic signal artifacts | 104 |
| Evidence-backed eval proposals | 11 |
| Fact proposals | 0 |
| Bounded recovery/procedure proposals | 7 |
| All derived artifacts | 122 |

The zero fact count is an intentional abstention. A structural trace summary is
not a durable enterprise fact or user memory. Fact promotion requires scoped
semantic evidence and review that this outcome-free public corpus does not
provide.

The seven procedure proposals contain 89 transitions produced by the same
canonical bounded-recovery constructor used for the independent share-codex
comparison. Each transition requires an explicitly typed error, unique
proposal/result linkage, a newly proposed post-error action in the same
controlled tool family, a successful result within 12 lifecycle events, and
greedy one-to-one assignment. They are review candidates, not claims that the
task recovered or that the procedure is correct.

## Fail-closed authority result

Each denial changed one authority dimension while keeping the query and source
constant. Candidate counts were measured before `ORDER BY`, rank, or `LIMIT`.

| Denial | History | Structural events | Controlled FTS | Proposals |
| --- | ---: | ---: | ---: | ---: |
| Unauthorized subject | 0 | 0 | 0 | 0 |
| Wrong tenant | 0 | 0 | 0 | 0 |
| Stale authorization epoch | 0 | 0 | 0 | 0 |
| Wrong purpose | 0 | 0 | 0 | 0 |
| Insufficient classification | 0 | 0 | 0 | 0 |

The executing application role was verified to be non-superuser,
`NOBYPASSRLS`, unable to create roles, and unable to create databases. Thus the
experiment tests the same fail-closed condition required by Frankengate:
ranking never receives an unauthorized candidate.

## Personal history and review lifecycle

Keyset pagination returned two 20-row pages with zero overlap and serialized no
cursor or trajectory identifier.

There were 18 review proposals: 11 eval and seven procedure. All 18 satisfied:

- database lifecycle is `proposal`;
- payload lifecycle is `proposal`;
- release policy is `human_review_required`;
- no row is reviewed, released, or automatically promoted.

Every proposal has at least one typed evidence event. Every evidence reference
resolves inside its source trajectory, every artifact source hash matches its
trajectory, and the corpus has one pinned source revision and one adapter
revision.

## Corrective experiment

The first end-to-end run failed the lineage invariant. The earlier proposal
generator had created six evidence-empty proposals—two each of eval, fact, and
procedure. The benchmark stopped rather than publishing a partial success.

The loader was then tightened in derivation v1 to:

- emit eval proposals only for explicit errors or conformance failures with
  evidence;
- abstain from structural fact proposals;
- emit procedures only for bounded same-tool failure/completion transitions;
- replace the derivation revision's materialized artifacts on an idempotent
  reload so stale proposals cannot survive a stricter rule.

The second load produced 11 evals, zero facts, and seven procedures. All
lifecycle and lineage assertions then passed. This iteration is evidence that
the benchmark tests a substantive release boundary rather than merely counting
rows.

After the independent Wisp/share-codex replication exposed incomparable
corpus-specific recovery rules, derivation v2 replaced the exact-native-tool
heuristic with the shared controlled-family constructor. The v2 reload
explicitly removed superseded v1 and prior v2 rows before rematerializing 11
eval, zero fact, and seven procedure proposals. The authorization, lifecycle,
and lineage gauntlet passed again against v2.

## Warm-cache latency

One hundred sequential iterations on local PostgreSQL 16.12 with pgvector
0.8.1 produced:

| Query | p50 | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Personal history page | 1.46 ms | 1.68 ms | 1.74 ms |
| Controlled FTS | 2.70 ms | 3.21 ms | 3.43 ms |
| Proposal review queue | 1.41 ms | 1.72 ms | 1.96 ms |
| Structural tool events | 23.29 ms | 24.27 ms | 49.45 ms |

The structural-event plan is the clear first optimization target. It returns
4,416 authorized tool lifecycle events, performs repeated indexed event
lookups for 104 trajectories, touches roughly 12,000 shared buffers, and sorts
before taking 20 rows. A targeted index/query bakeoff around
`(trajectory_id, kind, sequence)` is justified before considering another
database.

The controlled-FTS plan uses a sequential scan over only 122 artifacts rather
than the GIN index. That is rational at this size and not evidence that the GIN
path will or will not win at hundreds of gigabytes.

## What this proves for Frankengate

The combined local system can now demonstrate:

- private “show all my history” pagination;
- structural tool/error retrieval;
- controlled-vocabulary FTS without transcript terms in the result artifact;
- evidence-backed eval and procedure review queues;
- intentional abstention from unsupported facts;
- current-epoch, purpose, classification, tenant, and subject enforcement
  before retrieval ranking;
- content-free aggregate metrics and redacted query-plan diagnostics.

It does not demonstrate:

- Aurora extension compatibility, replicas, failover, parameter groups,
  backup, or storage autoscaling;
- production concurrency, cold-cache latency, or hundreds-of-gigabytes scale;
- that an eval or procedure proposal is correct;
- semantic task similarity, skill gaps, collaboration value, or enterprise
  population effects.

Those remain separate empirical gates. This result supports keeping PostgreSQL
as the first and only persistent system while measuring the actual bottleneck;
it does not justify a second search or vector database.

## Reproduction

```bash
python3 research/trace-intelligence/wisp_postgres_benchmark.py \
  --dsn "$LOCAL_GOVERNED_POSTGRES_DSN" \
  --output research/trace-intelligence/experiments/results/wisp-governed-postgres-benchmark-2026-07-30.json \
  --iterations 100
```

The result serializes aggregate counts, latency distributions, invariant
booleans, and redacted plan nodes only. Authority values, search text,
transcript content, native identifiers, pagination cursors, and plan
predicates are omitted.
