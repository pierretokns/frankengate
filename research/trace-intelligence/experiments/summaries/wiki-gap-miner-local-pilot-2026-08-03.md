# Wiki-gap miner local pilot — 2026-08-03

## What was built

`wiki_gap_miner.py` consumes governed canonical trace events and versioned wiki
pages. It emits evidence-backed candidates for:

* absent or undiscoverable knowledge;
* missing operational knowledge when an external tool was required;
* incomplete procedures after a failed or rolled-back outcome;
* incorrect or stale answers after user correction;
* stale pages corroborated by a correction or failed outcome; and
* recurring demand across distinct users without requiring embeddings.

`sql/clickhouse_wiki_gap_mining.sql` defines an optional ClickHouse analytical
projection with a query rollup and candidate queries. PostgreSQL remains the
authority store for users, permissions, wiki versions, and candidate approval.

`wiki_gap_backend_assessment.py` is the explicit promotion gate. It recommends
ClickHouse only when measured p95 scan latency, source volume, or daily scan
pressure crosses configured thresholds; it does not assume that a database
change is needed.

## Local result

The six-event fixture produced five review candidates, including recurring
cross-user demand, missing operational knowledge, failed procedure, and
absent/undiscoverable evidence. The successful-lookup control produced no
candidate.

The 12-file governed Frankengate conformance cohort was then adapted through
`canonical_governed_to_wiki_gap.py`. It contains four user requests and
outcomes, but **zero explicit wiki-search or retrieval events**. The miner
returned zero gap candidates and a `wiki_observation_coverage` of `0.0`; this
is the correct fail-closed result, not evidence that the wiki is complete.

The actual database rollup was run in disposable PostgreSQL 16 and ClickHouse
26.3 containers. On a deterministic 950,000-row expansion of those governed
fixtures, both databases returned identical 600,000-row rollups:

| backend | load | query p50 | query p95 |
| --- | ---: | ---: | ---: |
| PostgreSQL | 16.00 s | 1.919 s | 2.095 s |
| ClickHouse | 4.20 s | 0.428 s | 0.440 s |

This is a storage-mechanics result only: the source cohort has no wiki
observations, so it cannot estimate real gap prevalence. It does show that the
ClickHouse projection is materially faster for repeated analytical rollups at
this expanded volume, while PostgreSQL remains sufficient for the tiny source
cohort and authoritative workflow state.

## Verification

```text
uv run pytest -q tests/test_wiki_gap_miner.py \
  tests/test_wiki_gap_clickhouse_contract.py \
  tests/test_wiki_gap_backend_assessment.py \
  tests/test_canonical_governed_to_wiki_gap.py
9 tests passed
```

The database benchmark is reproducible with:

```text
uv run --with 'psycopg[binary]' --with clickhouse-connect \
  python wiki_gap_db_benchmark.py --fixture-root fixtures/governed-v1 \
  --scale 50000 --runs 3 \
  --output experiments/results/wiki-gap-db-benchmark-governed-50000-2026-08-03.json
```

The complete repository suite also ran. It remains green for the new code, but
three pre-existing receipt tests require external `/private/tmp/alfworld-*`
raw artifacts and therefore fail when those artifacts are absent.

## Production next step

Export one governed week of trace events into the canonical schema, run the
miner, and collect the four backend metrics (`event_count`, `source_bytes`,
`p95_scan_seconds`, `daily_gap_scans`). Only then run the same replay cohort
through PostgreSQL and the ClickHouse projection and make the storage decision.
The immediate product requirement is to emit explicit `wiki_search`,
`retrieval`, answer-evidence, and citation events; without those, the detector
must remain silent.
