#!/usr/bin/env python3
"""Benchmark governed Wisp trace queries in the disposable PostgreSQL lab.

The benchmark assumes ``trace_research`` has been created and a Wisp loader has
inserted one private trajectory per source file plus proposal-only derived
artifacts.  It emits aggregate counts, latency summaries, and redacted query
plan structure only.  It never serializes rows, transcript content, native
identifiers, authority values, search text, or pagination cursors.

This is a local PostgreSQL policy/composition experiment.  It is not an Aurora
emulator and cannot establish Aurora extension compatibility, failover,
replication, storage autoscaling, or production latency.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from psycopg2 import connect


WISP_DATASET = "crispwisp/wisp-claude-code-sessions"
WISP_TOOL_EVENT_KINDS = ("tool.proposed", "tool.completed", "tool.failed")
PROPOSAL_KINDS = ("eval_proposal", "fact_proposal", "procedure_proposal")


class PolicyLeakError(RuntimeError):
    """Raised when a denied authority receives any pre-ranking candidate."""


class BenchmarkInvariantError(RuntimeError):
    """Raised when lifecycle or lineage evidence violates the study contract."""


@dataclasses.dataclass(frozen=True)
class AuthoritySnapshot:
    tenant: str
    subject: str
    epoch: int
    classification_ceiling: int
    purpose: str


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between zero and one")
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def latency_summary(
    run: Callable[[], Any], iterations: int
) -> dict[str, float | int]:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        run()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "iterations": iterations,
        "mean_ms": round(statistics.fmean(samples), 6),
        "p50_ms": round(percentile(samples, 0.50), 6),
        "p95_ms": round(percentile(samples, 0.95), 6),
        "max_ms": round(max(samples), 6),
    }


def denial_scenarios(
    authority: AuthoritySnapshot,
) -> dict[str, AuthoritySnapshot]:
    """Return one-factor authority denials without exposing them in output."""
    stale_epoch = authority.epoch - 1
    return {
        "unauthorized_subject": dataclasses.replace(
            authority, subject=authority.subject + "-denied"
        ),
        "wrong_tenant": dataclasses.replace(
            authority, tenant=authority.tenant + "-denied"
        ),
        "stale_epoch": dataclasses.replace(authority, epoch=stale_epoch),
        "wrong_purpose": dataclasses.replace(
            authority, purpose=authority.purpose + "-denied"
        ),
        "insufficient_classification": dataclasses.replace(
            authority,
            classification_ceiling=authority.classification_ceiling - 1,
        ),
    }


def validate_zero_candidate_matrix(
    matrix: dict[str, dict[str, int]]
) -> dict[str, bool]:
    """Fail closed if any denied scenario obtains a pre-ranking candidate."""
    passed: dict[str, bool] = {}
    for scenario, counts in matrix.items():
        invalid = {
            metric: value
            for metric, value in counts.items()
            if not isinstance(value, int) or value != 0
        }
        if invalid:
            names = ", ".join(sorted(invalid))
            raise PolicyLeakError(
                f"{scenario} returned nonzero pre-ranking candidates: {names}"
            )
        passed[scenario] = True
    return passed


def validate_proposal_lifecycle(
    counts: dict[str, int]
) -> dict[str, bool]:
    checks = {
        "no_nonproposal_database_lifecycle": (
            counts["nonproposal_database_lifecycle"] == 0
        ),
        "payload_lifecycle_matches": (
            counts["payload_lifecycle_mismatches"] == 0
        ),
        "human_review_release_policy": (
            counts["release_policy_mismatches"] == 0
        ),
        "no_released_proposals": counts["released_proposals"] == 0,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise BenchmarkInvariantError(
            "proposal-only lifecycle failed: " + ", ".join(failed)
        )
    return checks


def validate_lineage(counts: dict[str, int]) -> dict[str, bool]:
    checks = {
        "event_sources_exist": counts["events_without_source"] == 0,
        "artifact_sources_exist": counts["artifacts_without_source"] == 0,
        "source_content_hash_matches": (
            counts["source_content_hash_mismatches"] == 0
        ),
        "evidence_events_exist": (
            counts["missing_evidence_event_references"] == 0
        ),
        "proposal_evidence_is_present": (
            counts["proposals_without_evidence"] == 0
        ),
        "single_source_revision": counts["source_revisions"] == 1,
        "single_adapter_revision": counts["adapter_revisions"] == 1,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise BenchmarkInvariantError(
            "source lineage failed: " + ", ".join(failed)
        )
    return checks


_PLAN_FIELDS = {
    "Node Type": "node_type",
    "Join Type": "join_type",
    "Relation Name": "relation",
    "Index Name": "index",
    "Plan Rows": "plan_rows",
    "Actual Rows": "actual_rows",
    "Actual Loops": "actual_loops",
    "Actual Total Time": "actual_total_time_ms",
    "Shared Hit Blocks": "shared_hit_blocks",
    "Shared Read Blocks": "shared_read_blocks",
    "Temp Read Blocks": "temp_read_blocks",
    "Temp Written Blocks": "temp_written_blocks",
}


def summarize_plan(plan_document: dict[str, Any]) -> dict[str, Any]:
    """Keep plan mechanics while dropping predicates, literals, and row data."""
    nodes: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], depth: int) -> None:
        summary = {"depth": depth}
        for source, target in _PLAN_FIELDS.items():
            if source in node:
                summary[target] = node[source]
        nodes.append(summary)
        for child in node.get("Plans", []):
            if isinstance(child, dict):
                visit(child, depth + 1)

    root = plan_document.get("Plan")
    if isinstance(root, dict):
        visit(root, 0)
    return {
        "planning_time_ms": plan_document.get("Planning Time"),
        "execution_time_ms": plan_document.get("Execution Time"),
        "nodes": nodes,
        "predicates_and_literals_emitted": False,
    }


def set_authority(cursor: Any, authority: AuthoritySnapshot) -> None:
    for key, value in (
        ("app.tenant_id", authority.tenant),
        ("app.subject_id", authority.subject),
        ("app.authorization_epoch", str(authority.epoch)),
        (
            "app.classification_ceiling",
            str(authority.classification_ceiling),
        ),
        ("app.purpose", authority.purpose),
    ):
        cursor.execute("select set_config(%s, %s, true)", (key, value))


def fetch_scalar(
    cursor: Any, query: str, parameters: tuple[Any, ...] = ()
) -> int:
    cursor.execute(query, parameters)
    value = cursor.fetchone()[0]
    return int(value)


def authorized_counts(
    cursor: Any, dataset: str, search_query: str
) -> dict[str, int]:
    trajectories = fetch_scalar(
        cursor,
        """
        select count(*)
        from trace_research.trajectories
        where source_dataset = %s
        """,
        (dataset,),
    )
    events = fetch_scalar(
        cursor,
        """
        select count(*)
        from trace_research.events e
        join trace_research.trajectories t on t.id = e.trajectory_id
        where t.source_dataset = %s
        """,
        (dataset,),
    )
    artifacts = fetch_scalar(
        cursor,
        """
        select count(*)
        from trace_research.derived_artifacts a
        join trace_research.trajectories t
          on t.id = a.source_trajectory_id
        where t.source_dataset = %s
        """,
        (dataset,),
    )

    event_counts = {}
    for result_key, event_kind in (
        ("tool_proposals", "tool.proposed"),
        ("tool_completed", "tool.completed"),
        ("tool_errors", "tool.failed"),
        ("malformed_source_events", "source.malformed_record"),
    ):
        event_counts[result_key] = fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.events e
            join trace_research.trajectories t on t.id = e.trajectory_id
            where t.source_dataset = %s and e.kind = %s
            """,
            (dataset, event_kind),
        )

    artifact_counts = {}
    for result_key, artifact_kind in (
        ("signals", "signal"),
        ("eval_proposals", "eval_proposal"),
        ("fact_proposals", "fact_proposal"),
        ("procedure_proposals", "procedure_proposal"),
    ):
        artifact_counts[result_key] = fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            where t.source_dataset = %s and a.kind = %s
            """,
            (dataset, artifact_kind),
        )

    recovery_proposals = fetch_scalar(
        cursor,
        """
        select count(*)
        from trace_research.derived_artifacts a
        join trace_research.trajectories t
          on t.id = a.source_trajectory_id
        where t.source_dataset = %s
          and a.kind = 'procedure_proposal'
          and a.payload #>>
                '{controlled_vocabulary,proposal_type}'
              in (
                'bounded_same_family_recovery_review',
                'tool_error_recovery_review'
              )
        """,
        (dataset,),
    )
    controlled_fts_candidates = fetch_scalar(
        cursor,
        """
        select count(*)
        from trace_research.derived_artifacts a
        join trace_research.trajectories t
          on t.id = a.source_trajectory_id
        where t.source_dataset = %s
          and a.content_tsv @@ websearch_to_tsquery('english', %s)
        """,
        (dataset, search_query),
    )
    return {
        "trajectories": trajectories,
        "events": events,
        "derived_artifacts": artifacts,
        **event_counts,
        "tool_results": (
            event_counts["tool_completed"] + event_counts["tool_errors"]
        ),
        "recovery_proposals": recovery_proposals,
        **artifact_counts,
        "controlled_fts_candidates": controlled_fts_candidates,
    }


def proposal_lifecycle_counts(
    cursor: Any, dataset: str
) -> dict[str, int]:
    base = """
        from trace_research.derived_artifacts a
        join trace_research.trajectories t
          on t.id = a.source_trajectory_id
        where t.source_dataset = %s
          and a.kind = any(%s)
    """
    kinds = list(PROPOSAL_KINDS)
    return {
        "total_proposals": fetch_scalar(
            cursor, "select count(*) " + base, (dataset, kinds)
        ),
        "nonproposal_database_lifecycle": fetch_scalar(
            cursor,
            "select count(*) "
            + base
            + " and a.lifecycle <> 'proposal'",
            (dataset, kinds),
        ),
        "payload_lifecycle_mismatches": fetch_scalar(
            cursor,
            "select count(*) "
            + base
            + """
              and coalesce(a.payload ->> 'lifecycle', '') <> 'proposal'
            """,
            (dataset, kinds),
        ),
        "release_policy_mismatches": fetch_scalar(
            cursor,
            "select count(*) "
            + base
            + """
              and coalesce(a.payload ->> 'release_policy', '')
                    <> 'human_review_required'
            """,
            (dataset, kinds),
        ),
        "released_proposals": fetch_scalar(
            cursor,
            "select count(*) "
            + base
            + """
              and (
                a.lifecycle = 'released'
                or a.payload ->> 'lifecycle' = 'released'
              )
            """,
            (dataset, kinds),
        ),
    }


def lineage_counts(cursor: Any, dataset: str) -> dict[str, int]:
    return {
        "events_without_source": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.events e
            left join trace_research.trajectories t
              on t.id = e.trajectory_id
            where t.id is null
            """,
        ),
        "artifacts_without_source": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            left join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            where t.id is null
            """,
        ),
        "source_content_hash_mismatches": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            where t.source_dataset = %s
              and a.source_content_sha256 <> t.content_sha256
            """,
            (dataset,),
        ),
        "missing_evidence_event_references": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            cross join lateral jsonb_array_elements_text(
              coalesce(a.payload -> 'evidence_event_ids', '[]'::jsonb)
            ) evidence(event_id)
            left join trace_research.events e
              on e.trajectory_id = a.source_trajectory_id
             and e.event_id = evidence.event_id
            where t.source_dataset = %s and e.event_id is null
            """,
            (dataset,),
        ),
        "proposals_without_evidence": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            where t.source_dataset = %s
              and a.kind = any(%s)
              and jsonb_array_length(
                    coalesce(
                      a.payload -> 'evidence_event_ids',
                      '[]'::jsonb
                    )
                  ) = 0
            """,
            (dataset, list(PROPOSAL_KINDS)),
        ),
        "source_revisions": fetch_scalar(
            cursor,
            """
            select count(distinct source_revision)
            from trace_research.trajectories
            where source_dataset = %s
            """,
            (dataset,),
        ),
        "adapter_revisions": fetch_scalar(
            cursor,
            """
            select count(distinct adapter_revision)
            from trace_research.trajectories
            where source_dataset = %s
            """,
            (dataset,),
        ),
    }


def pre_ranking_candidate_counts(
    cursor: Any, dataset: str, search_query: str
) -> dict[str, int]:
    """Count candidates before ORDER BY, distance, rank, or LIMIT."""
    return {
        "history_candidates": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.trajectories
            where source_dataset = %s
            """,
            (dataset,),
        ),
        "structural_event_candidates": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.events e
            join trace_research.trajectories t on t.id = e.trajectory_id
            where t.source_dataset = %s and e.kind = any(%s)
            """,
            (dataset, list(WISP_TOOL_EVENT_KINDS)),
        ),
        "controlled_fts_candidates": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            where t.source_dataset = %s
              and a.content_tsv @@ websearch_to_tsquery('english', %s)
            """,
            (dataset, search_query),
        ),
        "proposal_candidates": fetch_scalar(
            cursor,
            """
            select count(*)
            from trace_research.derived_artifacts a
            join trace_research.trajectories t
              on t.id = a.source_trajectory_id
            where t.source_dataset = %s and a.kind = any(%s)
            """,
            (dataset, list(PROPOSAL_KINDS)),
        ),
    }


def history_pagination(
    cursor: Any, dataset: str, page_size: int
) -> dict[str, int | bool]:
    cursor.execute(
        """
        select created_at, id
        from trace_research.trajectories
        where source_dataset = %s
        order by created_at desc, id desc
        limit %s
        """,
        (dataset, page_size),
    )
    first_page = cursor.fetchall()
    second_page: list[tuple[Any, ...]] = []
    if first_page:
        cursor_time, cursor_identity = first_page[-1]
        cursor.execute(
            """
            select created_at, id
            from trace_research.trajectories
            where source_dataset = %s
              and (created_at, id) < (%s, %s)
            order by created_at desc, id desc
            limit %s
            """,
            (dataset, cursor_time, cursor_identity, page_size),
        )
        second_page = cursor.fetchall()
    first_identities = {row[1] for row in first_page}
    second_identities = {row[1] for row in second_page}
    return {
        "page_size": page_size,
        "first_page_rows": len(first_page),
        "second_page_rows": len(second_page),
        "page_overlap_rows": len(first_identities & second_identities),
        "keyset_cursor_serialized": False,
    }


def role_safety(cursor: Any) -> dict[str, bool]:
    cursor.execute(
        """
        select rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
        from pg_roles
        where rolname = current_user
        """
    )
    row = cursor.fetchone()
    if row is None:
        raise BenchmarkInvariantError("application role metadata unavailable")
    return {
        "not_superuser": not bool(row[0]),
        "cannot_bypass_rls": not bool(row[1]),
        "cannot_create_roles": not bool(row[2]),
        "cannot_create_databases": not bool(row[3]),
    }


def explain_summary(
    cursor: Any, query: str, parameters: tuple[Any, ...]
) -> dict[str, Any]:
    cursor.execute("explain (analyze, buffers, format json) " + query, parameters)
    document = cursor.fetchone()[0][0]
    return summarize_plan(document)


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    authority = AuthoritySnapshot(
        tenant=args.tenant_id,
        subject=args.subject_id,
        epoch=args.authorization_epoch,
        classification_ceiling=args.classification_ceiling,
        purpose=args.purpose,
    )
    connection = connect(args.dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute("set role trace_research_app")
            set_authority(cursor, authority)
            cursor.execute("show server_version")
            server_version = cursor.fetchone()[0]
            cursor.execute(
                """
                select extversion from pg_extension where extname = 'vector'
                """
            )
            vector_row = cursor.fetchone()
            vector_version = vector_row[0] if vector_row else None

            counts = authorized_counts(
                cursor, args.source_dataset, args.search_query
            )
            if counts["trajectories"] == 0:
                raise BenchmarkInvariantError(
                    "authorized Wisp dataset is empty; load it before benchmarking"
                )
            pagination = history_pagination(
                cursor, args.source_dataset, args.page_size
            )
            if pagination["page_overlap_rows"] != 0:
                raise BenchmarkInvariantError(
                    "keyset history pages contain duplicate rows"
                )

            lifecycle_counts = proposal_lifecycle_counts(
                cursor, args.source_dataset
            )
            lifecycle_checks = validate_proposal_lifecycle(lifecycle_counts)
            lineage = lineage_counts(cursor, args.source_dataset)
            lineage_checks = validate_lineage(lineage)
            app_role_safety = role_safety(cursor)
            if not all(app_role_safety.values()):
                raise BenchmarkInvariantError(
                    "application role can bypass a required RLS boundary"
                )

            def history_query() -> None:
                cursor.execute(
                    """
                    select created_at, id
                    from trace_research.trajectories
                    where source_dataset = %s
                    order by created_at desc, id desc
                    limit %s
                    """,
                    (args.source_dataset, args.page_size),
                )
                cursor.fetchall()

            def structural_query() -> None:
                cursor.execute(
                    """
                    select e.trajectory_id, e.sequence
                    from trace_research.events e
                    join trace_research.trajectories t
                      on t.id = e.trajectory_id
                    where t.source_dataset = %s and e.kind = any(%s)
                    order by t.created_at desc, e.sequence
                    limit %s
                    """,
                    (
                        args.source_dataset,
                        list(WISP_TOOL_EVENT_KINDS),
                        args.result_limit,
                    ),
                )
                cursor.fetchall()

            def controlled_fts_query() -> None:
                cursor.execute(
                    """
                    select a.source_trajectory_id,
                           ts_rank_cd(
                             a.content_tsv,
                             websearch_to_tsquery('english', %s)
                           ) as rank
                    from trace_research.derived_artifacts a
                    join trace_research.trajectories t
                      on t.id = a.source_trajectory_id
                    where t.source_dataset = %s
                      and a.content_tsv
                        @@ websearch_to_tsquery('english', %s)
                    order by rank desc, a.created_at desc
                    limit %s
                    """,
                    (
                        args.search_query,
                        args.source_dataset,
                        args.search_query,
                        args.result_limit,
                    ),
                )
                cursor.fetchall()

            def proposal_query() -> None:
                cursor.execute(
                    """
                    select a.source_trajectory_id, a.kind
                    from trace_research.derived_artifacts a
                    join trace_research.trajectories t
                      on t.id = a.source_trajectory_id
                    where t.source_dataset = %s and a.kind = any(%s)
                    order by a.created_at desc
                    limit %s
                    """,
                    (
                        args.source_dataset,
                        list(PROPOSAL_KINDS),
                        args.result_limit,
                    ),
                )
                cursor.fetchall()

            latency = {
                "personal_history_page": latency_summary(
                    history_query, args.iterations
                ),
                "structural_tool_events": latency_summary(
                    structural_query, args.iterations
                ),
                "controlled_fts": latency_summary(
                    controlled_fts_query, args.iterations
                ),
                "proposal_queue": latency_summary(
                    proposal_query, args.iterations
                ),
            }

            history_plan = explain_summary(
                cursor,
                """
                select created_at, id
                from trace_research.trajectories
                where source_dataset = %s
                order by created_at desc, id desc
                limit %s
                """,
                (args.source_dataset, args.page_size),
            )
            structural_plan = explain_summary(
                cursor,
                """
                select e.trajectory_id, e.sequence
                from trace_research.events e
                join trace_research.trajectories t
                  on t.id = e.trajectory_id
                where t.source_dataset = %s and e.kind = any(%s)
                order by t.created_at desc, e.sequence
                limit %s
                """,
                (
                    args.source_dataset,
                    list(WISP_TOOL_EVENT_KINDS),
                    args.result_limit,
                ),
            )
            fts_plan = explain_summary(
                cursor,
                """
                select a.source_trajectory_id
                from trace_research.derived_artifacts a
                join trace_research.trajectories t
                  on t.id = a.source_trajectory_id
                where t.source_dataset = %s
                  and a.content_tsv
                    @@ websearch_to_tsquery('english', %s)
                order by ts_rank_cd(
                  a.content_tsv,
                  websearch_to_tsquery('english', %s)
                ) desc
                limit %s
                """,
                (
                    args.source_dataset,
                    args.search_query,
                    args.search_query,
                    args.result_limit,
                ),
            )

            denial_matrix: dict[str, dict[str, int]] = {}
            for scenario, denied_authority in denial_scenarios(
                authority
            ).items():
                set_authority(cursor, denied_authority)
                denial_matrix[scenario] = pre_ranking_candidate_counts(
                    cursor, args.source_dataset, args.search_query
                )
            denial_checks = validate_zero_candidate_matrix(denial_matrix)

        return {
            "schema_version": "governed-wisp-postgres-benchmark-v1",
            "environment": {
                "database": "local_postgresql",
                "server_version": server_version,
                "vector_extension_version": vector_version,
                "aurora_emulation": False,
                "iterations": args.iterations,
            },
            "source": {
                "dataset": args.source_dataset,
                "authority_values_emitted": False,
                "raw_or_canonical_rows_emitted": False,
            },
            "application_role_safety": app_role_safety,
            "authorized_counts": counts,
            "personal_history_pagination": pagination,
            "proposal_lifecycle": {
                "counts": lifecycle_counts,
                "checks": lifecycle_checks,
            },
            "source_lineage": {
                "counts": lineage,
                "checks": lineage_checks,
            },
            "latency": latency,
            "query_plans": {
                "personal_history": history_plan,
                "structural_tool_events": structural_plan,
                "controlled_fts": fts_plan,
            },
            "denied_pre_ranking_candidate_matrix": {
                "stage": "before_ranking_or_limit",
                "counts": denial_matrix,
                "checks": denial_checks,
                "all_zero": all(denial_checks.values()),
            },
            "privacy_contract": {
                "serialized_granularity": (
                    "aggregate_counts_latency_and_redacted_plan_structure"
                ),
                "content_or_identifiers_emitted": False,
                "search_query_emitted": False,
                "pagination_cursors_emitted": False,
            },
            "claim_limits": [
                (
                    "local PostgreSQL proves SQL composition and fail-closed "
                    "RLS behavior only; it is not an Aurora emulator"
                ),
                (
                    "this run does not test Aurora extension allowlists, "
                    "parameter groups, replicas, failover, backup, or storage "
                    "autoscaling"
                ),
                (
                    "single-node warm-cache latency is not production Aurora "
                    "latency or a concurrency/load result"
                ),
                (
                    "controlled-vocabulary FTS tests structural retrieval, "
                    "not transcript semantic quality"
                ),
                (
                    "proposal counts do not establish eval, fact, procedure, "
                    "or recovery correctness"
                ),
            ],
        }
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-dataset", default=WISP_DATASET)
    parser.add_argument(
        "--tenant-id", default="frankengate-private-research"
    )
    parser.add_argument(
        "--subject-id", default="wisp-public-contributor"
    )
    parser.add_argument("--authorization-epoch", type=int, default=1)
    parser.add_argument("--classification-ceiling", type=int, default=2)
    parser.add_argument("--purpose", default="quality-improvement")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--result-limit", type=int, default=20)
    parser.add_argument(
        "--search-query",
        default=(
            '"bounded_same_family_recovery_review" OR '
            '"tool_error_recovery_review" OR '
            '"tool_error_regression_eval"'
        ),
    )
    args = parser.parse_args()
    if args.authorization_epoch <= 0:
        parser.error("--authorization-epoch must be positive")
    if args.classification_ceiling <= 0:
        parser.error(
            "--classification-ceiling must be positive so a lower denied "
            "scenario can be tested"
        )
    if args.iterations <= 0 or args.page_size <= 0 or args.result_limit <= 0:
        parser.error("iteration and result limits must be positive")
    return args


def main() -> int:
    args = parse_args()
    result = benchmark(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "authorized_counts": result["authorized_counts"],
                "all_denials_zero": result[
                    "denied_pre_ranking_candidate_matrix"
                ]["all_zero"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
