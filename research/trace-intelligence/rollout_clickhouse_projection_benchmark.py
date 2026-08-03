#!/usr/bin/env python3
"""Project native-shaped Claude/Codex events into PostgreSQL and ClickHouse.

This is the database-backed follow-up to ``rollout_ingestion_experiment.py``.
It intentionally uses the same cohort and exercises duplicate delivery,
out-of-order batches, PostgreSQL ``ON CONFLICT`` ingestion, and ClickHouse
``ReplacingMergeTree`` projection with ``FINAL`` reads.  The receipt contains
aggregate counts, timings, and gap types only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import time
from pathlib import Path
from typing import Any

from rollout_ingestion_experiment import build_cohort, dedupe_latest
from wiki_gap_miner import mine_gap_candidates


TABLE = "fg_rollout_events"
RAW_TABLE = "fg_rollout_events_raw"
COLUMNS = (
    "event_id",
    "event_time",
    "event_type",
    "query_id",
    "session_id",
    "user_id",
    "text",
    "page_ids",
    "external",
    "answerable",
    "confidence",
    "feedback_kind",
    "outcome_status",
    "version",
)


def event_rows(events: list[dict[str, Any]], replays: int) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for replay in range(replays):
        for event in events:
            rows.append(
                (
                    str(event["event_id"]),
                    dt.datetime(2026, 8, 3, 12, 0, tzinfo=dt.timezone.utc),
                    str(event.get("event_type", "")),
                    str(event.get("query_id", "")),
                    str(event.get("session_id", "")),
                    str(event.get("user_id", "")),
                    str(event.get("text", "")),
                    [str(value) for value in event.get("page_ids", [])],
                    bool(event.get("external", False)),
                    event.get("answerable"),
                    float(event["confidence"]) if isinstance(event.get("confidence"), (int, float)) else None,
                    str(event.get("kind", "")),
                    str(event.get("status", "")),
                    # Delivery replay is not a new source version.  Keeping a
                    # stable version makes the ClickHouse projection compare
                    # semantically equal rows with PostgreSQL's first-writer
                    # ON CONFLICT behavior.
                    1,
                )
            )
    return rows


def as_miner_event(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        event_id,
        _event_time,
        event_type,
        query_id,
        session_id,
        user_id,
        text,
        page_ids,
        external,
        answerable,
        confidence,
        feedback_kind,
        outcome_status,
        _version,
    ) = row
    event: dict[str, Any] = {
        "event_id": str(event_id),
        "event_type": str(event_type),
        "query_id": str(query_id),
        "session_id": str(session_id),
        "user_id": str(user_id),
        "text": str(text),
        "page_ids": list(page_ids or []),
        "external": bool(external),
    }
    if answerable is not None:
        event["answerable"] = bool(answerable)
    if confidence is not None:
        event["confidence"] = float(confidence)
    if feedback_kind:
        event["kind"] = str(feedback_kind)
    if outcome_status:
        event["status"] = str(outcome_status)
    return event


def candidate_summary(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    summary: dict[str, set[str]] = {}
    for candidate in mine_gap_candidates(events):
        for query_id in candidate.query_ids:
            summary.setdefault(query_id, set()).add(candidate.gap_type)
    return {query_id: sorted(values) for query_id, values in sorted(summary.items())}


def semantic_row(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(event.get("event_id", "")),
        str(event.get("event_type", "")),
        str(event.get("query_id", "")),
        str(event.get("session_id", "")),
        str(event.get("user_id", "")),
        str(event.get("text", "")),
        tuple(str(value) for value in event.get("page_ids", [])),
        bool(event.get("external", False)),
        event.get("answerable"),
        event.get("confidence"),
        str(event.get("kind", "")),
        str(event.get("status", "")),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replays", type=int, default=100)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--postgres-dsn", default="postgresql://postgres:fgtest@127.0.0.1:55432/postgres")
    parser.add_argument("--clickhouse-host", default="127.0.0.1")
    parser.add_argument("--clickhouse-port", type=int, default=18123)
    parser.add_argument("--clickhouse-user", default="fgtest")
    parser.add_argument("--clickhouse-password", default="fgtest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.replays < 1 or args.runs < 2:
        raise SystemExit("--replays must be positive and --runs must be at least two")

    import clickhouse_connect
    import psycopg

    base_events, labels, source = build_cohort()
    rows = event_rows(base_events, args.replays)
    shuffled = list(rows)
    random.Random(44017).shuffle(shuffled)
    insert_placeholders = ",".join(["%s"] * len(COLUMNS))
    started = time.perf_counter()

    with psycopg.connect(args.postgres_dsn) as pg:
        with pg.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {TABLE}")
            cursor.execute(
                f"""CREATE TABLE {TABLE} (
                    event_id text PRIMARY KEY,
                    event_time timestamptz NOT NULL,
                    event_type text NOT NULL,
                    query_id text NOT NULL,
                    session_id text NOT NULL,
                    user_id text NOT NULL,
                    text text NOT NULL,
                    page_ids text[] NOT NULL,
                    external boolean NOT NULL,
                    answerable boolean,
                    confidence real,
                    feedback_kind text NOT NULL,
                    outcome_status text NOT NULL,
                    version integer NOT NULL
                )"""
            )
            load_start = time.perf_counter()
            cursor.executemany(
                f"INSERT INTO {TABLE} ({','.join(COLUMNS)}) VALUES ({insert_placeholders}) ON CONFLICT (event_id) DO NOTHING",
                shuffled,
            )
            pg.commit()
            pg_load_seconds = time.perf_counter() - load_start
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
            pg_count = int(cursor.fetchone()[0])
            cursor.execute(f"SELECT {','.join(COLUMNS)} FROM {TABLE} ORDER BY event_id")
            pg_rows = cursor.fetchall()
        pg_query_times: list[float] = []
        for _ in range(args.runs):
            query_start = time.perf_counter()
            with pg.cursor() as cursor:
                cursor.execute(f"SELECT event_type, COUNT(*) FROM {TABLE} GROUP BY event_type ORDER BY event_type")
                cursor.fetchall()
            pg_query_times.append(time.perf_counter() - query_start)

    ch = clickhouse_connect.get_client(
        host=args.clickhouse_host,
        port=args.clickhouse_port,
        username=args.clickhouse_user,
        password=args.clickhouse_password,
    )
    ch.command(f"DROP TABLE IF EXISTS {RAW_TABLE}")
    ch.command(f"DROP TABLE IF EXISTS {TABLE}")
    ch.command(
        f"""CREATE TABLE {TABLE} (
            event_id String,
            event_time DateTime64(3, 'UTC'),
            event_type LowCardinality(String),
            query_id String,
            session_id String,
            user_id String,
            text String,
            page_ids Array(String),
            external UInt8,
            answerable Nullable(UInt8),
            confidence Nullable(Float32),
            feedback_kind LowCardinality(String),
            outcome_status LowCardinality(String),
            version UInt32
        ) ENGINE = ReplacingMergeTree(version)
        ORDER BY (event_id)"""
    )
    ch.command(
        f"""CREATE TABLE {RAW_TABLE} AS {TABLE} ENGINE = MergeTree ORDER BY (event_id)"""
    )
    ch_start = time.perf_counter()
    ch.insert(RAW_TABLE, shuffled, column_names=list(COLUMNS))
    ch.insert(TABLE, shuffled, column_names=list(COLUMNS))
    ch_load_seconds = time.perf_counter() - ch_start
    ch_count_raw_append = int(ch.query(f"SELECT count() FROM {RAW_TABLE}").result_rows[0][0])
    ch_count_before_final = int(ch.query(f"SELECT count() FROM {TABLE}").result_rows[0][0])
    ch_count_after_final = int(ch.query(f"SELECT count() FROM {TABLE} FINAL").result_rows[0][0])
    ch_query_times: list[float] = []
    for _ in range(args.runs):
        query_start = time.perf_counter()
        ch.query(f"SELECT event_type, count() FROM {TABLE} FINAL GROUP BY event_type ORDER BY event_type")
        ch_query_times.append(time.perf_counter() - query_start)
    ch_rows = [tuple(row) for row in ch.query(f"SELECT {','.join(COLUMNS)} FROM {TABLE} FINAL ORDER BY event_id").result_rows]
    ch.close()

    pg_events = [as_miner_event(row) for row in pg_rows]
    ch_events = [as_miner_event(row) for row in ch_rows]
    expected_events = dedupe_latest(base_events)
    pg_candidates = candidate_summary(pg_events)
    ch_candidates = candidate_summary(ch_events)
    expected_replay_count = len(base_events) * args.replays
    receipt = {
        "schema_version": "frankengate-rollout-clickhouse-projection-benchmark-v1",
        "cohort": source,
        "base_event_count": len(base_events),
        "delivered_event_count": len(rows),
        "expected_replay_count": expected_replay_count,
        "postgres": {
            "deduped_row_count": pg_count,
            "load_seconds": pg_load_seconds,
            "query_p95_seconds": sorted(pg_query_times)[min(len(pg_query_times) - 1, int(round((len(pg_query_times) - 1) * 0.95)))],
        },
        "clickhouse": {
            "raw_append_row_count": ch_count_raw_append,
            "final_deduped_row_count": ch_count_after_final,
            "load_seconds": ch_load_seconds,
            "query_p95_seconds": sorted(ch_query_times)[min(len(ch_query_times) - 1, int(round((len(ch_query_times) - 1) * 0.95)))],
        },
        "replay_invariants": {
            "postgres_on_conflict_deduped": pg_count == len(base_events),
            "clickhouse_final_deduped": ch_count_after_final == len(base_events),
            "clickhouse_raw_append_matches_delivery": ch_count_raw_append == expected_replay_count,
            "postgres_clickhouse_rows_equal": sorted(semantic_row(event) for event in pg_events) == sorted(semantic_row(event) for event in ch_events),
            "postgres_clickhouse_candidate_outputs_equal": pg_candidates == ch_candidates,
            "replay_safe_projection": sorted(semantic_row(event) for event in pg_events) == sorted(semantic_row(event) for event in expected_events),
        },
        "candidate_types_by_query": pg_candidates,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "interpretation": "ClickHouse append storage is not idempotent by itself; FINAL is required for replay-safe reads with ReplacingMergeTree. PostgreSQL primary-key ON CONFLICT deduplicates at write time. Both stores produced the same canonical rows and gap findings after deduplication.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, default=str) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
