#!/usr/bin/env python3
"""Load canonical public trajectories into the disposable governed PostgreSQL lab.

Raw datasets remain outside Git. The loader connects with fixture-administrator
credentials only to seed the authority epoch, then performs every protected insert
after ``SET ROLE trace_research_app`` with transaction-local authority settings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from psycopg2 import connect
from psycopg2.extras import Json, execute_values

from tracebench import canonicalize_nebius, deterministic_signals, sha256_text, stable_json


def chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def signal_vector(signals: dict[str, float]) -> list[float]:
    """Return a deterministic test vector, not a semantic embedding."""

    fields = (
        "friction_score",
        "tool_action_count",
        "syntax_error_count",
        "not_found_count",
        "permission_error_count",
        "test_failure_count",
        "repeated_action_count",
        "edit_rejection_count",
    )
    raw = [max(0.0, float(signals[name])) for name in fields]
    norm = sum(value * value for value in raw) ** 0.5
    return [value / norm for value in raw] if norm else raw


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.12g}" for value in values) + "]"


def event_tool_fields(event: dict[str, Any]) -> tuple[str | None, str | None]:
    if event["kind"] != "tool_call_proposal" or not event.get("command"):
        return None, None
    command = str(event["command"]).strip()
    name = command.split(maxsplit=1)[0] if command else None
    return event["event_id"], name


def configure_authority(
    connection: Any,
    tenant_id: str,
    subject_id: str,
    authorization_epoch: int,
    classification_ceiling: int,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into trace_research.authority_epochs (
              tenant_id,
              subject_id,
              authorization_epoch,
              classification_ceiling,
              active,
              updated_at
            )
            values (%s, %s, %s, %s, true, now())
            on conflict (tenant_id, subject_id)
            do update set
              authorization_epoch = excluded.authorization_epoch,
              classification_ceiling = excluded.classification_ceiling,
              active = true,
              updated_at = now()
            """,
            (tenant_id, subject_id, authorization_epoch, classification_ceiling),
        )
    connection.commit()


def assume_application_authority(
    connection: Any,
    tenant_id: str,
    subject_id: str,
    authorization_epoch: int,
    classification_ceiling: int,
    purpose: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute("set role trace_research_app")
        for key, value in (
            ("app.tenant_id", tenant_id),
            ("app.subject_id", subject_id),
            ("app.authorization_epoch", str(authorization_epoch)),
            ("app.classification_ceiling", str(classification_ceiling)),
            ("app.purpose", purpose),
        ):
            cursor.execute("select set_config(%s, %s, true)", (key, value))


def load_nebius(
    connection: Any,
    input_path: Path,
    tenant_id: str,
    subject_id: str,
    audience: str,
    team_id: str | None,
    classification: int,
    purpose: str,
    policy_revision: str,
) -> dict[str, int]:
    trajectory_rows: list[tuple[Any, ...]] = []
    event_rows: list[tuple[Any, ...]] = []
    artifact_rows: list[tuple[Any, ...]] = []

    with input_path.open(encoding="utf-8") as source:
        for line in source:
            source_row = json.loads(line)
            trace = canonicalize_nebius(source_row)
            content_sha256 = sha256_text(stable_json(trace))
            signals = deterministic_signals(trace)

            trajectory_rows.append(
                (
                    trace["trace_id"],
                    tenant_id,
                    subject_id,
                    audience,
                    team_id,
                    classification,
                    [purpose],
                    policy_revision,
                    trace["source"]["dataset_id"],
                    trace["source"]["dataset_revision"],
                    trace["source"]["adapter"],
                    trace["task"]["task_id"],
                    "swe-agent",
                    trace["source"].get("model_name"),
                    Json(trace["outcome"]),
                    Json(trace["loss_receipt"]),
                    Json(source_row),
                    content_sha256,
                )
            )

            for event in trace["events"]:
                tool_call_id, tool_name = event_tool_fields(event)
                event_rows.append(
                    (
                        trace["trace_id"],
                        event["sequence"],
                        event["event_id"],
                        event.get("parent_event_id"),
                        event["kind"],
                        event["observation_status"],
                        event["source_role"],
                        tool_call_id,
                        tool_name,
                        event.get("content"),
                        Json(event),
                    )
                )

            artifact_rows.append(
                (
                    trace["trace_id"] + ":signals-v1",
                    trace["trace_id"],
                    tenant_id,
                    subject_id,
                    audience,
                    team_id,
                    classification,
                    [purpose],
                    policy_revision,
                    "signal",
                    (
                        f"task={trace['task']['task_id']} "
                        f"model={trace['source'].get('model_name')} "
                        f"friction={signals['friction_score']:.3f} "
                        f"repeated_actions={signals['repeated_action_count']:.0f} "
                        f"test_failures={signals['test_failure_count']:.0f}"
                    ),
                    Json(signals),
                    vector_literal(signal_vector(signals)),
                    content_sha256,
                    "deterministic-signals-v1",
                )
            )

    with connection.cursor() as cursor:
        execute_values(
            cursor,
            """
            insert into trace_research.trajectories (
              id, tenant_id, owner_subject_id, audience, team_id, classification,
              allowed_purposes, policy_revision, source_dataset, source_revision,
              adapter_revision, task_id, harness, model_name, outcome, loss_receipt,
              raw_payload, content_sha256
            ) values %s
            on conflict (id) do nothing
            """,
            trajectory_rows,
            page_size=100,
        )
        for batch in chunks(event_rows, 1000):
            execute_values(
                cursor,
                """
                insert into trace_research.events (
                  trajectory_id, sequence, event_id, parent_event_id, kind,
                  observation_status, source_role, tool_call_id, tool_name,
                  content_text, payload
                ) values %s
                on conflict (trajectory_id, sequence) do nothing
                """,
                batch,
                page_size=1000,
            )
        execute_values(
            cursor,
            """
            insert into trace_research.derived_artifacts (
              id, source_trajectory_id, tenant_id, owner_subject_id, audience,
              team_id, classification, allowed_purposes, policy_revision, kind,
              content_text, payload, embedding, source_content_sha256,
              derivation_revision
            ) values %s
            on conflict (id) do nothing
            """,
            artifact_rows,
            template=(
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s::public.vector,%s,%s)"
            ),
            page_size=100,
        )
    connection.commit()
    return {
        "source_trajectories": len(trajectory_rows),
        "source_events": len(event_rows),
        "signal_artifacts": len(artifact_rows),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--tenant-id", default="public-research")
    parser.add_argument("--subject-id", default="researcher")
    parser.add_argument("--authorization-epoch", type=int, default=1)
    parser.add_argument("--classification-ceiling", type=int, default=2)
    parser.add_argument("--classification", type=int, default=0)
    parser.add_argument("--purpose", default="quality-improvement")
    parser.add_argument("--policy-revision", default="research-policy-v1")
    parser.add_argument("--audience", choices=("private", "team"), default="private")
    parser.add_argument("--team-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.audience == "private" and args.team_id is not None:
        raise SystemExit("--team-id is only valid with --audience=team")
    if args.audience == "team" and not args.team_id:
        raise SystemExit("--team-id is required with --audience=team")

    connection = connect(args.dsn)
    try:
        configure_authority(
            connection,
            args.tenant_id,
            args.subject_id,
            args.authorization_epoch,
            args.classification_ceiling,
        )
        assume_application_authority(
            connection,
            args.tenant_id,
            args.subject_id,
            args.authorization_epoch,
            args.classification_ceiling,
            args.purpose,
        )
        counts = load_nebius(
            connection,
            args.input,
            args.tenant_id,
            args.subject_id,
            args.audience,
            args.team_id,
            args.classification,
            args.purpose,
            args.policy_revision,
        )
        print(json.dumps(counts, sort_keys=True))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
