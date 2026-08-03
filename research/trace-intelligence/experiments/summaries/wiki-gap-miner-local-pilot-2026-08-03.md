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

## Verification

```text
uv run pytest -q tests/test_wiki_gap_miner.py \
  tests/test_wiki_gap_clickhouse_contract.py \
  tests/test_wiki_gap_backend_assessment.py
5 tests passed
```

The complete repository suite also ran. It remains green for the new code, but
three pre-existing receipt tests require external `/private/tmp/alfworld-*`
raw artifacts and therefore fail when those artifacts are absent.

## Production next step

Export one governed week of trace events into the canonical schema, run the
miner, and collect the four backend metrics (`event_count`, `source_bytes`,
`p95_scan_seconds`, `daily_gap_scans`). Only then run the same replay cohort
through PostgreSQL and the ClickHouse projection and make the storage decision.
