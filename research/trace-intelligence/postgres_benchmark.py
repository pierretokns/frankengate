#!/usr/bin/env python3
"""Measure the governed local PostgreSQL pilot without making Aurora claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from psycopg2 import connect


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values must not be empty")
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def latency_summary(run: Callable[[], Any], iterations: int) -> dict[str, float | int]:
    elapsed_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        run()
        elapsed_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "iterations": iterations,
        "mean_ms": statistics.fmean(elapsed_ms),
        "p50_ms": percentile(elapsed_ms, 0.50),
        "p95_ms": percentile(elapsed_ms, 0.95),
        "max_ms": max(elapsed_ms),
    }


def set_authority(
    cursor: Any,
    tenant_id: str,
    subject_id: str,
    authorization_epoch: int,
    classification_ceiling: int,
    purpose: str,
) -> None:
    for key, value in (
        ("app.tenant_id", tenant_id),
        ("app.subject_id", subject_id),
        ("app.authorization_epoch", str(authorization_epoch)),
        ("app.classification_ceiling", str(classification_ceiling)),
        ("app.purpose", purpose),
    ):
        cursor.execute("select set_config(%s, %s, true)", (key, value))


def fetch_scalar(cursor: Any, query: str, parameters: tuple[Any, ...] = ()) -> Any:
    cursor.execute(query, parameters)
    return cursor.fetchone()[0]


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    connection = connect(args.dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute("set role trace_research_app")
            set_authority(
                cursor,
                args.tenant_id,
                args.subject_id,
                args.authorization_epoch,
                args.classification_ceiling,
                args.purpose,
            )

            counts = {
                "trajectories": fetch_scalar(
                    cursor, "select count(*) from trace_research.trajectories"
                ),
                "events": fetch_scalar(
                    cursor, "select count(*) from trace_research.events"
                ),
                "tool_call_proposals": fetch_scalar(
                    cursor,
                    """
                    select count(*) from trace_research.events
                    where kind = 'tool_call_proposal'
                    """,
                ),
                "tool_results": fetch_scalar(
                    cursor,
                    "select count(*) from trace_research.events where kind = 'tool_result'",
                ),
                "reconstructed_events": fetch_scalar(
                    cursor,
                    """
                    select count(*) from trace_research.events
                    where observation_status = 'reconstructed'
                    """,
                ),
                "signal_artifacts": fetch_scalar(
                    cursor,
                    """
                    select count(*) from trace_research.derived_artifacts
                    where kind = 'signal'
                    """,
                ),
            }

            def history_page() -> None:
                cursor.execute(
                    """
                    select id, task_id, model_name, outcome
                    from trace_research.trajectories
                    order by created_at desc, id desc
                    limit 50
                    """
                )
                cursor.fetchall()

            def full_text() -> None:
                cursor.execute(
                    """
                    select trajectory_id, sequence,
                           ts_rank_cd(content_tsv, query) as rank
                    from trace_research.events,
                         websearch_to_tsquery('english', %s) query
                    where content_tsv @@ query
                    order by rank desc, trajectory_id, sequence
                    limit 20
                    """,
                    (args.search_query,),
                )
                cursor.fetchall()

            def vector_search() -> None:
                cursor.execute(
                    """
                    select id, embedding <=> %s::public.vector as distance
                    from trace_research.derived_artifacts
                    where embedding is not null
                    order by embedding <=> %s::public.vector, id
                    limit 20
                    """,
                    (args.query_vector, args.query_vector),
                )
                cursor.fetchall()

            latency = {
                "history_page": latency_summary(history_page, args.iterations),
                "full_text": latency_summary(full_text, args.iterations),
                "vector_search": latency_summary(vector_search, args.iterations),
            }

            cursor.execute(
                """
                explain (analyze, buffers, format json)
                select trajectory_id, sequence
                from trace_research.events
                where content_tsv @@ websearch_to_tsquery('english', %s)
                order by trajectory_id, sequence
                limit 20
                """,
                (args.search_query,),
            )
            full_text_plan = cursor.fetchone()[0][0]

            cursor.execute(
                """
                explain (analyze, buffers, format json)
                select id
                from trace_research.derived_artifacts
                where embedding is not null
                order by embedding <=> %s::public.vector, id
                limit 20
                """,
                (args.query_vector,),
            )
            vector_plan = cursor.fetchone()[0][0]

            set_authority(
                cursor,
                args.tenant_id,
                "unauthorized-subject",
                args.authorization_epoch,
                args.classification_ceiling,
                args.purpose,
            )
            unauthorized_counts = {
                "trajectories": fetch_scalar(
                    cursor, "select count(*) from trace_research.trajectories"
                ),
                "full_text_candidates": fetch_scalar(
                    cursor,
                    """
                    select count(*) from trace_research.events
                    where content_tsv @@ websearch_to_tsquery('english', %s)
                    """,
                    (args.search_query,),
                ),
                "vector_candidates": fetch_scalar(
                    cursor,
                    """
                    select count(*) from trace_research.derived_artifacts
                    where embedding is not null
                    """,
                ),
            }

            set_authority(
                cursor,
                args.tenant_id,
                args.subject_id,
                args.authorization_epoch + 1,
                args.classification_ceiling,
                args.purpose,
            )
            stale_epoch_count = fetch_scalar(
                cursor, "select count(*) from trace_research.trajectories"
            )

        return {
            "schema_version": "governed-postgres-pilot-result-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "database": "local-postgresql-16-pgvector-0.8.1",
                "aurora_emulation": False,
                "iterations": args.iterations,
            },
            "input": {
                "path_name": args.input.name,
                "sha256": sha256_file(args.input),
                "tenant_id": args.tenant_id,
                "subject_id": args.subject_id,
            },
            "authorized_counts": counts,
            "unauthorized_counts": unauthorized_counts,
            "stale_epoch_trajectory_count": stale_epoch_count,
            "latency": latency,
            "plans": {
                "full_text": full_text_plan,
                "vector_search": vector_plan,
            },
            "claim_limits": [
                "single-node local PostgreSQL is not an Aurora emulator",
                "tiny deterministic vectors test composition, not semantic quality",
                "the 300-trace pilot is not a production load test",
            ],
        }
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tenant-id", default="public-research")
    parser.add_argument("--subject-id", default="nebius-researcher")
    parser.add_argument("--authorization-epoch", type=int, default=1)
    parser.add_argument("--classification-ceiling", type=int, default=2)
    parser.add_argument("--purpose", default="quality-improvement")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--search-query", default='"syntax error" OR "failed"')
    parser.add_argument(
        "--query-vector",
        default="[1,0,0,0,0,0,0,0]",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = benchmark(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: result[key] for key in ("authorized_counts", "unauthorized_counts")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
