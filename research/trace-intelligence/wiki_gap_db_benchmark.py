#!/usr/bin/env python3
"""Benchmark the wiki-gap analytical rollup in PostgreSQL and ClickHouse.

The benchmark uses the governed Frankengate conformance fixtures as a source
cohort and a deterministic multiplier only to expose scan/aggregation costs.
The receipt keeps source content out of the result; it records row counts,
timings, and equality of the rollup outputs.

Run with the disposable services from the research worktree:

    uv run --with psycopg[binary] --with clickhouse-connect \
      python wiki_gap_db_benchmark.py --fixture-root fixtures/governed-v1 \
      --scale 10000 --output experiments/results/wiki-gap-db-benchmark.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from canonical_governed_to_wiki_gap import adapt_trace


PG_TABLE = "fg_wiki_gap_events"
CH_TABLE = "fg_wiki_gap_events"
COLUMNS = (
    "tenant_id",
    "event_time",
    "event_id",
    "event_type",
    "query_id",
    "session_id",
    "user_id",
    "text",
    "page_ids",
    "tool",
    "external",
    "answerable",
    "confidence",
    "feedback_kind",
    "outcome_status",
    "payload",
)


def events_to_rows(base: Sequence[dict[str, Any]], scale: int) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for repeat in range(scale):
        tenant = f"governed-fixture-{repeat % 16:02d}"
        for index, event in enumerate(base):
            event_time = dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=repeat)
            page_ids = event.get("page_ids") if isinstance(event.get("page_ids"), list) else []
            rows.append(
                (
                    tenant,
                    event_time,
                    f"{event.get('event_id', index)}:{repeat}",
                    str(event.get("event_type", "")),
                    f"{event.get('query_id', 'query')}:{repeat}",
                    f"{event.get('session_id', 'session')}:{repeat}",
                    str(event.get("user_id", "")),
                    str(event.get("text", "")),
                    [str(value) for value in page_ids],
                    str(event.get("tool", "")),
                    bool(event.get("external", False)),
                    event.get("answerable"),
                    float(event["confidence"]) if isinstance(event.get("confidence"), (int, float)) else None,
                    str(event.get("kind", "")),
                    str(event.get("status", "")),
                    json.dumps({"source": "governed-v1", "repeat": repeat}, separators=(",", ":")),
                )
            )
    return rows


def fixture_rows(root: Path, scale: int) -> list[tuple[Any, ...]]:
    base: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        trace = json.loads(path.read_text(encoding="utf-8"))
        events, _ = adapt_trace(trace)
        base.extend(events)
    return events_to_rows(base, scale)


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def summarize_times(values: Sequence[float]) -> dict[str, float]:
    return {
        "runs": len(values),
        "p50_seconds": percentile(values, 0.50),
        "p95_seconds": percentile(values, 0.95),
        "max_seconds": max(values) if values else 0.0,
    }


def postgres_query(connection: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, query_id,
               COUNT(*) FILTER (WHERE event_type = 'retrieval') AS retrieval_events,
               COUNT(*) FILTER (WHERE event_type = 'retrieval' AND cardinality(page_ids) > 0) AS useful_retrieval_events,
               COUNT(*) FILTER (WHERE event_type = 'tool_call' AND external) AS external_tool_calls,
               COUNT(*) FILTER (WHERE feedback_kind IN ('correction', 'wrong', 'stale')) AS corrections,
               COUNT(*) FILTER (WHERE outcome_status IN ('failure', 'failed', 'rollback')) AS failed_outcomes
        FROM {PG_TABLE}
        GROUP BY tenant_id, query_id
        ORDER BY tenant_id, query_id
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def clickhouse_query(client: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, query_id,
               countIf(event_type = 'retrieval') AS retrieval_events,
               countIf(event_type = 'retrieval' AND length(page_ids) > 0) AS useful_retrieval_events,
               countIf(event_type = 'tool_call' AND external = 1) AS external_tool_calls,
               countIf(feedback_kind IN ('correction', 'wrong', 'stale')) AS corrections,
               countIf(outcome_status IN ('failure', 'failed', 'rollback')) AS failed_outcomes
        FROM {CH_TABLE}
        GROUP BY tenant_id, query_id
        ORDER BY tenant_id, query_id
    """
    return [tuple(row) for row in client.query(query).result_rows]


def postgres_session_query(connection: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, lower(text) AS normalized_text,
               COUNT(DISTINCT user_id) AS distinct_users,
               COUNT(DISTINCT session_id) AS distinct_sessions,
               COUNT(*) AS demand_count
        FROM {PG_TABLE}
        WHERE text <> ''
        GROUP BY tenant_id, normalized_text
        HAVING COUNT(DISTINCT user_id) >= 2
        ORDER BY tenant_id, normalized_text
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def clickhouse_session_query(client: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, lowerUTF8(text) AS normalized_text,
               uniqExact(user_id) AS distinct_users,
               uniqExact(session_id) AS distinct_sessions,
               count() AS demand_count
        FROM {CH_TABLE}
        WHERE text != ''
        GROUP BY tenant_id, normalized_text
        HAVING distinct_users >= 2
        ORDER BY tenant_id, normalized_text
    """
    return [tuple(row) for row in client.query(query).result_rows]


def postgres_failure_query(connection: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, to_char(date_trunc('hour', event_time), 'YYYY-MM-DD HH24:MI:SS') AS event_hour,
               COUNT(*) FILTER (WHERE outcome_status IN ('failure', 'failed', 'rollback')) AS failed,
               COUNT(*) FILTER (WHERE feedback_kind IN ('correction', 'wrong', 'stale')) AS corrected
        FROM {PG_TABLE}
        GROUP BY tenant_id, event_hour
        ORDER BY tenant_id, event_hour
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def clickhouse_failure_query(client: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, formatDateTime(toStartOfHour(event_time), '%Y-%m-%d %H:%i:%S') AS event_hour,
               countIf(outcome_status IN ('failure', 'failed', 'rollback')) AS failed,
               countIf(feedback_kind IN ('correction', 'wrong', 'stale')) AS corrected
        FROM {CH_TABLE}
        GROUP BY tenant_id, event_hour
        ORDER BY tenant_id, event_hour
    """
    return [tuple(row) for row in client.query(query).result_rows]


def postgres_keyword_query(connection: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, COUNT(*) AS keyword_hits
        FROM {PG_TABLE}
        WHERE text ILIKE '%mantle%'
        GROUP BY tenant_id
        ORDER BY tenant_id
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def clickhouse_keyword_query(client: Any) -> list[tuple[Any, ...]]:
    query = f"""
        SELECT tenant_id, count() AS keyword_hits
        FROM {CH_TABLE}
        WHERE positionCaseInsensitive(text, 'mantle') > 0
        GROUP BY tenant_id
        ORDER BY tenant_id
    """
    return [tuple(row) for row in client.query(query).result_rows]


def run_repeated(fn: Any, runs: int) -> tuple[list[tuple[Any, ...]], list[float]]:
    times: list[float] = []
    result: list[tuple[Any, ...]] = []
    for _ in range(runs):
        started = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - started)
    return result, times


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--cohort", choices=("governed", "labeled"), default="governed")
    parser.add_argument("--scale", type=int, default=1000)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--postgres-dsn", default="postgresql://postgres:fgtest@127.0.0.1:55432/postgres")
    parser.add_argument("--clickhouse-host", default="127.0.0.1")
    parser.add_argument("--clickhouse-port", type=int, default=18123)
    parser.add_argument("--clickhouse-user", default="fgtest")
    parser.add_argument("--clickhouse-password", default="fgtest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.scale < 1 or args.runs < 2:
        raise SystemExit("--scale must be positive and --runs must be at least 2")

    import clickhouse_connect
    import psycopg

    if args.cohort == "labeled":
        from wiki_gap_labeled_experiment import build_cohort

        base_events, _, _ = build_cohort(20)
        source_name = "wiki-gap-labeled-experiment-v1"
    else:
        base_events = []
        for path in sorted(args.fixture_root.glob("*.json")):
            trace = json.loads(path.read_text(encoding="utf-8"))
            adapted, _ = adapt_trace(trace)
            base_events.extend(adapted)
        source_name = "fixtures/governed-v1"
    rows = events_to_rows(base_events, args.scale)
    with psycopg.connect(args.postgres_dsn) as pg:
        with pg.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {PG_TABLE}")
            cursor.execute(
                f"""CREATE TABLE {PG_TABLE} (
                    tenant_id text NOT NULL, event_time timestamptz NOT NULL,
                    event_id text NOT NULL, event_type text NOT NULL,
                    query_id text NOT NULL, session_id text NOT NULL,
                    user_id text NOT NULL, text text NOT NULL, page_ids text[] NOT NULL,
                    tool text NOT NULL, external boolean NOT NULL,
                    answerable boolean, confidence real, feedback_kind text NOT NULL,
                    outcome_status text NOT NULL, payload jsonb NOT NULL
                )"""
            )
            started = time.perf_counter()
            cursor.executemany(
                f"INSERT INTO {PG_TABLE} ({','.join(COLUMNS)}) VALUES ({','.join(['%s'] * len(COLUMNS))})",
                rows,
            )
            pg.commit()
            pg_load_seconds = time.perf_counter() - started
        pg_result, pg_times = run_repeated(lambda: postgres_query(pg), args.runs)
        pg_session_result, pg_session_times = run_repeated(lambda: postgres_session_query(pg), args.runs)
        pg_failure_result, pg_failure_times = run_repeated(lambda: postgres_failure_query(pg), args.runs)
        pg_keyword_result, pg_keyword_times = run_repeated(lambda: postgres_keyword_query(pg), args.runs)

    ch = clickhouse_connect.get_client(
        host=args.clickhouse_host,
        port=args.clickhouse_port,
        username=args.clickhouse_user,
        password=args.clickhouse_password,
    )
    ch.command(f"DROP TABLE IF EXISTS {CH_TABLE}")
    ch.command(
        f"""CREATE TABLE {CH_TABLE} (
            tenant_id LowCardinality(String), event_time DateTime64(3, 'UTC'),
            event_id String, event_type LowCardinality(String), query_id String,
            session_id String, user_id String, text String, page_ids Array(String),
            tool String, external UInt8, answerable Nullable(UInt8), confidence Nullable(Float32),
            feedback_kind LowCardinality(String), outcome_status LowCardinality(String), payload JSON
        ) ENGINE = MergeTree ORDER BY (tenant_id, session_id, event_time, event_id)"""
    )
    ch_rows = [
        row[:-1] + (json.loads(row[-1]),)
        for row in rows
    ]
    started = time.perf_counter()
    ch.insert(CH_TABLE, ch_rows, column_names=list(COLUMNS))
    ch_load_seconds = time.perf_counter() - started
    ch_result, ch_times = run_repeated(lambda: clickhouse_query(ch), args.runs)
    ch_session_result, ch_session_times = run_repeated(lambda: clickhouse_session_query(ch), args.runs)
    ch_failure_result, ch_failure_times = run_repeated(lambda: clickhouse_failure_query(ch), args.runs)
    ch_keyword_result, ch_keyword_times = run_repeated(lambda: clickhouse_keyword_query(ch), args.runs)
    ch.close()

    receipt = {
        "schema_version": "frankengate-wiki-gap-db-benchmark-v1",
        "source": source_name,
        "base_event_count": len(base_events),
        "expanded_event_count": len(rows),
        "scale": args.scale,
        "runs": args.runs,
        "rollup_rows": {"postgres": len(pg_result), "clickhouse": len(ch_result)},
        "rollup_outputs_equal": [list(row) for row in pg_result] == [list(row) for row in ch_result],
        "postgres": {
            "load_seconds": pg_load_seconds,
            "queries": {
                "query_rollup": {"rows": len(pg_result), "equal_to_clickhouse": [list(row) for row in pg_result] == [list(row) for row in ch_result], "timing": summarize_times(pg_times)},
                "session_demand": {"rows": len(pg_session_result), "equal_to_clickhouse": [list(row) for row in pg_session_result] == [list(row) for row in ch_session_result], "timing": summarize_times(pg_session_times)},
                "failure_window": {"rows": len(pg_failure_result), "equal_to_clickhouse": [list(row) for row in pg_failure_result] == [list(row) for row in ch_failure_result], "timing": summarize_times(pg_failure_times)},
                "keyword_search": {"rows": len(pg_keyword_result), "equal_to_clickhouse": [list(row) for row in pg_keyword_result] == [list(row) for row in ch_keyword_result], "timing": summarize_times(pg_keyword_times)},
            },
        },
        "clickhouse": {
            "load_seconds": ch_load_seconds,
            "queries": {
                "query_rollup": {"rows": len(ch_result), "timing": summarize_times(ch_times)},
                "session_demand": {"rows": len(ch_session_result), "timing": summarize_times(ch_session_times)},
                "failure_window": {"rows": len(ch_failure_result), "timing": summarize_times(ch_failure_times)},
                "keyword_search": {"rows": len(ch_keyword_result), "timing": summarize_times(ch_keyword_times)},
            },
        },
        "interpretation": "This measures analytical rollup mechanics on governed fixtures; it does not establish production-scale cost or wiki-gap prevalence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
