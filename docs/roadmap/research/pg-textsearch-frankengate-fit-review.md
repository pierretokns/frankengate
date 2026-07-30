# pg_textsearch Fit Review for Frankengate

**Date:** 2026-07-29

**Reviewed release:** v1.3.1, commit
[`578ff529`](https://github.com/timescale/pg_textsearch/commit/578ff529894992fb9e67cae4c69424e65c84868e),
released 2026-06-23

**Canonical repository:** [timescale/pg_textsearch](https://github.com/timescale/pg_textsearch)

**Decision:** do not adopt on Aurora; retain as a conditional lexical benchmark
arm if native PostgreSQL search fails a preregistered Frankengate requirement

## Verdict

`pg_textsearch` is a focused, permissively licensed PostgreSQL extension that adds
fast BM25 relevance ranking. It is materially simpler than ParadeDB/`pg_search`,
and its Block-Max WAND implementation is relevant to natural-language trace search.
It does not add vector search, hybrid fusion, fuzzy search, phrase queries, boolean
query semantics, faceting, an authorization model, or any trace/memory intelligence.

It does **not** change the Aurora-first decision:

- Aurora PostgreSQL's current extension catalog does not contain
  `pg_textsearch`.
- The extension is a native C shared library, supports only PostgreSQL 17 and 18,
  installs planner hooks and shared memory, and requires
  `shared_preload_libraries`.
- It therefore cannot be installed by Frankengate on ordinary Aurora PostgreSQL,
  and it is not implementable through Aurora Trusted Language Extensions.
- Native PostgreSQL FTS, `pg_trgm`, typed predicates, JSONB expression indexes, and
  optional `pgvector` remain the deployable Aurora baseline.

The capability is only partly covered by existing plans. Native FTS covers
tokenization, phrase/boolean queries, weights, and transactional lexical recall,
while `pg_trgm` covers typo and substring similarity. Neither supplies corpus-aware
BM25 top-k ranking. ParadeDB/`pg_search` was already retained as an extensible-
PostgreSQL replacement candidate and supplies a much broader search feature set.
`pg_textsearch` should be added only as the **narrow, PostgreSQL-licensed BM25 arm**
of that future bakeoff.

Do not migrate or self-host PostgreSQL merely to obtain it. If a frozen,
RLS-selective Frankengate trace benchmark later proves that native FTS ranking or
latency fails an actual user requirement, compare:

1. native `tsvector`/GIN plus `ts_rank_cd` and `pg_trgm`;
2. `pg_textsearch`;
3. ParadeDB/`pg_search`;
4. lexical plus `pgvector` candidates with one Frankengate-owned RRF/rerank stage.

Advance `pg_textsearch` only if its simpler license and operations win after
correctness, RLS leakage, churn, failover, and recovery tests. Its post-v1.0 issue
history is not yet boring enough for classified production traces.

## pg_textsearch v1.3.1 (2026-06-23)

**Repo:** `github.com/timescale/pg_textsearch @
578ff529894992fb9e67cae4c69424e65c84868e`

The reviewed tag is a non-prerelease
[GitHub release](https://github.com/timescale/pg_textsearch/releases/tag/v1.3.1),
not `main`, which is already labeled `v1.4.0-dev`.

### What it is

The extension defines a custom `bm25` index access method. Documents are tokenized
with PostgreSQL text-search configurations and stored in an inverted LSM-like
structure. A query such as:

```sql
SELECT id, content
FROM trace_documents
ORDER BY content <@> to_bm25query('bedrock timeout', 'trace_content_bm25')
LIMIT 20;
```

returns ascending negative BM25 scores. `k1` and `b` are set per index. Top-k
queries use Block-Max WAND to skip posting blocks that cannot enter the result set.
The v1.3 on-disk memtable uses PostgreSQL buffers and `GenericXLog`; its pages
participate in normal physical WAL replay and streaming replication.

The extension supports:

- `text`, `varchar`, `char`, and corresponding arrays;
- PostgreSQL language configurations and stemming;
- JSONB or transformed text through immutable expression indexes;
- concatenated multi-field expressions;
- partial indexes;
- partitioned tables, with separate corpus statistics per partition;
- parallel index builds, but not parallel index scans;
- inserts, updates, deletes, VACUUM, crash recovery, and physical replication;
- compressed posting segments and an optional derived shared-memory memtable cache.

It is a ranker, not a general search DSL. Stable source explicitly configures the
access method as `ORDER BY` only, single-column, no bitmap scans, no `INCLUDE`
columns, and no parallel scans. See the pinned
[access-method definition](https://github.com/timescale/pg_textsearch/blob/v1.3.1/src/access/handler.c#L55-L116).

### Commands

| Task | Command | Notes |
|---|---|---|
| Build | `PG_CONFIG=/path/to/pg_config make` | PGXS C extension; PG 17 or 18 only |
| Install | `make install` | Requires server filesystem/library access |
| Preload | `shared_preload_libraries = 'pg_textsearch'` | Server restart required |
| Enable | `CREATE EXTENSION pg_textsearch;` | Once per database |
| Create index | `CREATE INDEX idx ON docs USING bm25(content) WITH (text_config='english');` | `text_config` required |
| Search | `ORDER BY content <@> 'terms' LIMIT 10` | Implicit planner-hook form |
| Search explicitly | `ORDER BY content <@> to_bm25query('terms', 'idx') LIMIT 10` | Required in PL/pgSQL and for partial indexes |
| Spill memtable | `SELECT bm25_spill_index('idx');` | Owner/admin operation |
| Force merge | `SELECT bm25_force_merge('idx');` | Synchronous; best after batch load |
| Monitor | Query `pg_stat_user_indexes` | Normal PostgreSQL index counters |
| Test | `make test-all` | SQL, concurrency, recovery, replication suites exist |

### Index config

| Option | Default | Notes |
|---|---:|---|
| `text_config` | required | Standard PostgreSQL text-search configuration |
| `k1` | `1.2` | BM25 term-frequency saturation, range 0.1–10.0 |
| `b` | `0.75` | Length normalization, range 0.0–1.0 |

### Runtime config

| Option | Default | Scope and effect |
|---|---:|---|
| `pg_textsearch.default_limit` | `1000` | User-settable cap when planner finds no SQL `LIMIT`; maximum 100,000 |
| `pg_textsearch.compress_segments` | `on` | User-settable delta/bitpacked new posting segments |
| `pg_textsearch.segments_per_level` | `8` | Superuser; synchronous LSM merge threshold, range 2–64 |
| `pg_textsearch.bulk_load_threshold` | `100000` terms | Superuser; spill at transaction end; zero disables |
| `pg_textsearch.memtable_pages_threshold` | `64` pages | Superuser; roughly 512 KiB before spill; zero disables |
| `pg_textsearch.memtable_cache_enabled` | `on` | Derived shared-memory read cache; on-disk chain remains authority |
| `pg_textsearch.memory_limit` | `2 GiB` | SIGHUP; global cache hard limit, with per-index/global soft limits |
| `pg_textsearch.log_scores` | `off` | Superuser-only score diagnostics |
| `pg_textsearch.log_bmw_stats` | `off` | Superuser-only BMW diagnostics |
| `pg_textsearch.log_cache_state` | `off` | Cache transition diagnostics |

The stable GUC definitions and privilege classes are in
[`src/mod.c`](https://github.com/timescale/pg_textsearch/blob/v1.3.1/src/mod.c#L153-L361);
the 2 GiB cache default is in
[`src/constants.h`](https://github.com/timescale/pg_textsearch/blob/v1.3.1/src/constants.h#L102-L111).

### Environment

| Variable | Purpose |
|---|---|
| `PG_CONFIG` | Select the target PG 17/18 PGXS installation during build |

There is no application service, CLI daemon, external index directory, or runtime
environment-variable surface. PostgreSQL GUCs are the runtime configuration.

## Capability fit

### What it adds beyond the Aurora baseline

The meaningful addition is **fast corpus-aware BM25 ranking**. PostgreSQL's native
search has `ts_rank`/`ts_rank_cd`, positions, weights, phrases, boolean operators,
query rewriting, dictionaries, and GIN/GiST indexes. `pg_trgm` supplies indexed
similarity, `LIKE`/`ILIKE`, and typo-like recall. But native ranking is not BM25 and
can require ranking a large match set after GIN retrieval.

`pg_textsearch` puts term/document statistics and upper bounds in its own index so a
`LIMIT n` query can avoid scoring noncompetitive postings. This can improve:

- free-text prompt-history ranking;
- discovery of traces mentioning several common natural-language concepts;
- lexical candidate generation before a dense reranker;
- ranking long task summaries when exact identifiers alone produce too many hits.

It does **not** help establish task equivalence, skill gaps, causal failure,
memory truth, intervention effects, classification authority, or eval quality.
Those are still data-model, evidence, and experiment problems.

### JSONB

JSONB is supported only through an immutable expression that evaluates to text,
for example `(attributes->>'error_message')`. The query must repeat that exact
expression. `pg_textsearch` does not index arbitrary JSON structure, typed JSON
predicates, nested fields, or faceting. Frankengate's security and hot filter
fields must remain typed columns; bounded provider-specific long-tail fields can
remain JSONB and selected text projections can be indexed.

### Filtering and hybrid retrieval

Filtering is not pushed into the BM25 postings as a general predicate language.
The planner can:

- use a selective B-tree/other path to fetch qualifying rows and invoke standalone
  BM25 scoring; or
- run the BM25 top-k path and apply other conditions afterward.

The second case can silently return fewer than `LIMIT n` rows when a selective
predicate removes top-ranked candidates. The project documents this explicitly
and recommends over-fetching. This is the same class of filtered-retrieval
underfill Frankengate already treats as a correctness problem for pgvector.

There is no vector type, ANN, sparse-vector interface, or built-in RRF. A
single-database hybrid query can independently retrieve authorized BM25 and
pgvector candidates and fuse them in SQL or in one Frankengate-owned stage.
`pg_textsearch` therefore complements rather than replaces pgvector, and does not
overlap with VectorChord or TurboVec's dense-vector acceleration.

## RLS, classified data, and information boundaries

`pg_textsearch` is a PostgreSQL secondary index that emits heap CTIDs. Normal heap
visibility and executor checks still apply, so it does not create an external copy
that bypasses PostgreSQL transactions or table RLS. That is materially safer than
a detached search sidecar.

That does not make the RLS story complete:

- The stable repository has no row-level-security regression suite.
- The BM25 access method cannot produce a bitmap path and cannot combine an
  authorization predicate inside its postings traversal.
- RLS and other selective conditions may therefore turn the fast top-k path into
  post-filtering/underfill or force standalone scoring of all authorized rows.
- BM25 corpus statistics come from the whole index. An authorized row's numeric
  score, ordering, result count, and timing may be influenced by invisible tenants'
  documents. For classified corpora this is a potential statistical side channel
  even though forbidden row content is not returned.
- Partial indexes can isolate a bounded, static scope, but an index per user/team/
  classification combination is not a scalable authorization design and requires
  explicit index names.
- Table owners and `BYPASSRLS` roles still bypass ordinary policies; Frankengate
  needs `FORCE ROW LEVEL SECURITY`, non-owner application roles, and current
  authorization/deletion epoch rechecks regardless of index choice.

The safe conclusion is not “pg_textsearch breaks RLS.” The conclusion is that its
RLS correctness, result completeness, score leakage, and query plans are unproven
for Frankengate. A future bakeoff must run with real forced-RLS policies and
selectivities rather than relying on generic PostgreSQL behavior.

## MVCC, WAL, deletion, and HA

### What integrates correctly in design

- Heap MVCC remains authoritative; the index stores TIDs for row versions and
  PostgreSQL checks heap visibility.
- Inserts and updates are added through the index AM.
- DELETE/UPDATE dead entries are removed or marked through VACUUM, with an alive
  bitset and deferred page reclamation.
- Memtable and segment page mutations are WAL-logged through `GenericXLog`.
- Physical standbys reconstruct pages through the normal WAL stream.
- Transaction and subtransaction callbacks clean backend-local build/cache state.

The stable architecture is described in the pinned
[README](https://github.com/timescale/pg_textsearch/blob/v1.3.1/README.md#memtable-architecture).

### Operational hard edges

- Corpus statistics can remain stale between DELETE and VACUUM even while dead
  tuples are correctly hidden.
- Compaction happens synchronously on foreground spill. There is no background
  compactor, so write-heavy traces can see tail-latency stalls. See
  [issue #313](https://github.com/timescale/pg_textsearch/issues/313).
- Cross-partition BM25 scores are not comparable because every partition has
  separate document counts, average lengths, and IDF.
- `bm25_force_merge` is a manual maintenance operation and rewrites segment pages.
- A binary upgrade requires server library installation/restart and occasionally
  exercises on-disk format compatibility.
- `shared_preload_libraries` is intentionally still required because the restored
  shared-memory cache and planner hooks need early initialization. See
  [issue #377](https://github.com/timescale/pg_textsearch/issues/377).

Most importantly, v1.3.1 itself is a bugfix release dominated by concurrency,
VACUUM, page-reclamation, duplicate-row, standby, and parallel-build correctness
fixes. After the stable release, users reported persistent production index
corruption in:

- [issue #426](https://github.com/timescale/pg_textsearch/issues/426), where a
  large partitioned index's memtable chain points from a regular page to a
  continuation page and repeatedly fails reads/writes; and
- [issue #427](https://github.com/timescale/pg_textsearch/issues/427), where
  multiple v1.3.1 indexes' tombstone chains point to reused/dead memtable pages,
  blocking normal writes and requiring reindex investigation.

[Issue #410](https://github.com/timescale/pg_textsearch/issues/410) also records
v1.2-to-v1.3 persistent page/fragment errors for which `REINDEX` was insufficient
and the user had to drop and recreate the index.

These reports do not prove every v1.3.1 deployment corrupts indexes, and some
state may predate fixes. They do mean that a “production ready” label and clean
microbenchmark cannot yet substitute for months of Frankengate-shaped churn,
crash, VACUUM, failover, and repair testing.

## Aurora compatibility

Aurora currently lists the extensions AWS packages for every supported engine
version. As of this review:

- Aurora supports PostgreSQL 17 and 18 engines;
- the catalog contains no `pg_textsearch` row;
- ordinary Aurora users cannot copy an arbitrary native `.so` into `$libdir`;
- adding a name to `shared_preload_libraries` cannot load a binary AWS has not
  installed; and
- Trusted Language Extensions do not turn this C access method, planner-hook,
  shared-memory, and PGXS codebase into a trusted SQL-language extension.

The authoritative catalog is
[AWS's Aurora PostgreSQL extension matrix](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html).
The absence is a hard deployment blocker, not a tuning concern.

`pg_textsearch` is viable on self-managed PostgreSQL 17/18, Tiger Cloud, or another
managed extensible PostgreSQL service that explicitly packages and preloads it.
That makes it an option **inside** a future one-database Aurora replacement, never
an adjacent search service.

## Benchmark interpretation

The project's reproducible benchmark harness is stronger than a marketing-only
claim:

- 8.8 million MS MARCO passages, 800 queries across 1–8+ token buckets;
- a separate 138 million-passage MS MARCO v2 experiment;
- PostgreSQL 17;
- top-10, warmed-cache Block-Max WAND queries;
- build time, index size, p50/p95/p99, and sequential throughput;
- same runner/configuration for its ParadeDB comparison.

The March snapshot reports a 3.1x sequential throughput advantage over ParadeDB
v0.21.6 on the 8.8M corpus, while ParadeDB built its index 1.7x faster. The
comparison also explains that `pg_textsearch`'s smaller index omits positions, so
the size win is partly a missing-feature tradeoff rather than superior
compression.

The benchmark does not prove Frankengate fit:

- the 8.8M benchmark is single-threaded, warmed, local-socket, and subject to
  roughly 10% GitHub-runner variance;
- it has no forced-RLS/high-selectivity filters, classifications, deletion
  epochs, mixed lexical/vector fusion, tenant concurrency, streaming ingest,
  failover SLO, or repair-time measurement;
- MS MARCO web passages and Bing queries do not resemble corporate traces with
  identifiers, stack traces, code, tool arguments, acronyms, and long outputs;
- the published quality checks validate its BM25 implementation, not whether
  BM25 improves Frankengate task discovery or insight extraction;
- several serious concurrency/recovery bugs were fixed after the benchmark
  snapshot, and open corruption reports postdate v1.3.1.

Use the benchmark as evidence that its algorithm can be fast, not as an adoption
decision.

## Comparison with assessed options

| Option | What it does | Relationship to pg_textsearch | Frankengate decision |
|---|---|---|---|
| Native PostgreSQL FTS | `tsvector`/`tsquery`, GIN/GiST, phrases, boolean/web queries, weights, `ts_rank_cd` | Broader query semantics and Aurora-compatible, but no native BM25 top-k index | Build first |
| `pg_trgm` | Indexed trigram similarity, typo/substrings, `LIKE`/`ILIKE` | Complementary; `pg_textsearch` does not provide fuzzy search | Build first where needed |
| ParadeDB/`pg_search` | Tantivy-backed BM25, phrase/fuzzy search, structured predicates, facets/aggregations, broader DSL | Much broader and more mature feature surface, but heavier and AGPL/commercial licensed | One-database replacement candidate only |
| `pg_textsearch` | Narrow C BM25 index with Block-Max WAND and PostgreSQL tokenizers | Simpler, permissive, fast lexical ranker; fewer features and young storage machinery | Conditional replacement bakeoff arm |
| pgvector | Dense exact/HNSW/IVF semantic similarity | Complementary; fuse separate candidate lists | Aurora conditional baseline |
| VectorChord | Compressed/disk-oriented vector ANN plus reranking | No lexical overlap | Replacement candidate only after vector SLO failure |
| pgContext | Experimental filter-aware vector/context engine with hybrid concepts | Overlaps orchestration/hybrid goals, not mature BM25 lexical breadth | Concept/reference only |
| TurboVec | In-process compressed dense flat scoring | No lexical, SQL, MVCC, WAL, or RLS overlap | Ephemeral benchmark only |
| Frankensearch | External Tantivy/vector/rerank/progressive engine | Broader but creates a second derived authority and synchronization boundary | Default-off research sidecar |

## Missing features that matter for trace search

- No phrase or proximity query. The documented workaround over-fetches BM25
  candidates and post-filters text. See
  [issue #314](https://github.com/timescale/pg_textsearch/issues/314).
- No boolean `AND`/`OR`/`NOT` semantics in the BM25 index. Native `tsquery`/GIN
  remains the recommended workaround. See
  [issue #315](https://github.com/timescale/pg_textsearch/issues/315).
- No fuzzy/typo, prefix, regex, or identifier-aware query DSL.
- No built-in faceting, aggregations, highlighting, snippets, field boosts, or
  per-field BM25F.
- No general multi-column index; concatenation loses field identity/weight.
- No background compaction.
- No predicate pushdown inside the BM25 index for RLS/team/classification filters.
- No vector search or native hybrid fusion.
- No cross-partition global corpus statistics.
- The implicit syntax does not work in PL/pgSQL; explicit index naming is required.
- PostgreSQL token length and large-document tokenization limits still apply.

Several of those features are already covered better by native FTS/`pg_trgm` or
ParadeDB. Frankengate should not recreate them merely to justify this extension.

## Frankengate-specific experiment gate

Do not schedule an infrastructure migration. Add `pg_textsearch` to the existing
retrieval research matrix only after Aurora-native lexical search fails a frozen
acceptance threshold.

The benchmark must use a temporary self-managed PG 17/18 instance and:

1. ingest the same versioned, de-identified trace/task documents into every arm;
2. include exact identifiers, corporate acronyms, tool names, stack traces,
   paraphrased task goals, long tool outputs, and multilingual text;
3. compare Recall@k, nDCG@k, MRR, exact-ID preservation, and downstream grounded
   answer/eval quality, not latency alone;
4. test forced RLS for user, team, enterprise, purpose, classification, retention,
   consent, authorization epoch, and deletion epoch;
5. measure result underfill and timing/score differences at 0.01%, 0.1%, 1%, 10%,
   and 100% authorized selectivity;
6. test whether global corpus statistics leak measurable facts about a hidden
   tenant and whether security-scope partitioning prevents it without exploding
   index count;
7. run concurrent ingest/update/delete/VACUUM/merge/search with crash, promotion,
   replay, PITR, REINDEX, corrupt-index detection, and recovery-time objectives;
8. compare steady-state WAL volume, cache RSS, write p95/p99, index build time,
   query p95/p99, storage, and DBA burden;
9. combine lexical candidates with the same pgvector/reranker arms so BM25's
   incremental contribution is isolated;
10. preregister a kill rule: no replacement if native FTS plus `pg_trgm` and
    pgvector meets quality/SLO, or if the BM25 gain is smaller than the extension,
    upgrade, repair, and HA burden.

## Adopt/test/reject

- **Adopt now:** no.
- **Test now on the production roadmap:** no; native Aurora search is not yet
  disproven.
- **Retain as a conditional experimental arm:** yes.
- **Use as a reason to leave Aurora:** no.
- **Prefer over ParadeDB if a later bakeoff needs only BM25:** possibly; its
  PostgreSQL License and smaller feature/operational surface are attractive.
- **Prefer for classified production traces today:** no; RLS-selective behavior is
  unvalidated and open v1.3.1 corruption reports require resolution and soak time.

The architecture remains one authority. If Frankengate eventually replaces Aurora
with one managed extensible PostgreSQL service for a demonstrated search
requirement, `pg_textsearch` can live in that one database beside pgvector. It
should never be introduced as another persistent sidecar.

## Gotchas

- **Aurora blocker:** the native library is absent from AWS's catalog and requires
  early preload; no SQL-only workaround exists.
- **Filtering underfill:** top-k before selective predicates can return fewer than
  requested. Source:
  [README filtering behavior](https://github.com/timescale/pg_textsearch/blob/v1.3.1/README.md#filtering-with-where-clauses).
- **Global BM25 statistics:** even standalone scoring reads index-wide document
  counts/length/IDF. Source:
  [stable SQL definition](https://github.com/timescale/pg_textsearch/blob/v1.3.1/sql/pg_textsearch--1.3.1.sql#L124-L139).
- **Synchronous compaction:** foreground spills can stall writes. Source:
  [issue #313](https://github.com/timescale/pg_textsearch/issues/313).
- **Partition score mismatch:** scores from different partitions are not directly
  comparable. Source:
  [README limitation](https://github.com/timescale/pg_textsearch/blob/v1.3.1/README.md#partitioned-tables).
- **No phrase/boolean/fuzzy:** native FTS/`pg_trgm` or ParadeDB covers these better.
- **Planner-hook syntax:** use explicit `to_bm25query()` in stored procedures and
  partial-index queries.
- **Recent corruption:** issues
  [#426](https://github.com/timescale/pg_textsearch/issues/426) and
  [#427](https://github.com/timescale/pg_textsearch/issues/427) affect production
  v1.3.1 reports and remain open at review time.
- **Upgrade/restart burden:** installing or changing the native shared library
  requires filesystem control and a server restart.
- **License is favorable, not support:** the
  [PostgreSQL License](https://github.com/timescale/pg_textsearch/blob/v1.3.1/LICENSE)
  is permissive and disclaims maintenance/support obligations.

## Sources

### Primary code and release

- [v1.3.1 release](https://github.com/timescale/pg_textsearch/releases/tag/v1.3.1)
- [Pinned stable source](https://github.com/timescale/pg_textsearch/tree/v1.3.1)
- [README and limitations](https://github.com/timescale/pg_textsearch/blob/v1.3.1/README.md)
- [Access-method capabilities](https://github.com/timescale/pg_textsearch/blob/v1.3.1/src/access/handler.c#L55-L116)
- [GUC and preload implementation](https://github.com/timescale/pg_textsearch/blob/v1.3.1/src/mod.c#L153-L361)
- [SQL operator/function definitions](https://github.com/timescale/pg_textsearch/blob/v1.3.1/sql/pg_textsearch--1.3.1.sql#L124-L233)
- [Benchmark methodology](https://github.com/timescale/pg_textsearch/blob/v1.3.1/benchmarks/gh-pages/methodology.html)
- [PostgreSQL License](https://github.com/timescale/pg_textsearch/blob/v1.3.1/LICENSE)

### Recent PRs and issues

- [v1.3.1 fix set / PR #419](https://github.com/timescale/pg_textsearch/pull/419)
- [Duplicate rows under concurrent writes / PR #417](https://github.com/timescale/pg_textsearch/pull/417)
- [VACUUM page-reclamation race / PR #418](https://github.com/timescale/pg_textsearch/pull/418)
- [Standby-safe deferred reclaim / PR #406](https://github.com/timescale/pg_textsearch/pull/406)
- [Parallel build truncation / PR #416](https://github.com/timescale/pg_textsearch/pull/416)
- [Open memtable-chain corruption / issue #426](https://github.com/timescale/pg_textsearch/issues/426)
- [Open tombstone/page-ownership corruption / issue #427](https://github.com/timescale/pg_textsearch/issues/427)
- [Persistent v1.2→v1.3 page error / issue #410](https://github.com/timescale/pg_textsearch/issues/410)
- [Preload requirement decision / issue #377](https://github.com/timescale/pg_textsearch/issues/377)
- [Phrase-query roadmap / issue #314](https://github.com/timescale/pg_textsearch/issues/314)
- [Boolean-query roadmap / issue #315](https://github.com/timescale/pg_textsearch/issues/315)

### PostgreSQL and Aurora

- [Aurora PostgreSQL supported extensions](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html)
- [PostgreSQL row-security semantics](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL index/MVCC interface](https://www.postgresql.org/docs/current/indexam.html)
- [PostgreSQL text-search functions](https://www.postgresql.org/docs/current/functions-textsearch.html)
- [`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html)
- [ParadeDB repository](https://github.com/paradedb/paradedb)
