#!/usr/bin/env python3
"""Governed PostgreSQL loader for native Claude Code Wisp trajectories.

Every native JSONL file becomes one canonical trajectory.  The loader stores
typed event semantics and content in the RLS-protected research schema, but it
does not duplicate native records/blocks inside JSONB or place a raw transcript
in ``trajectories.raw_payload``.  Derived eval, fact, and procedure rows are
proposal-only and contain controlled vocabulary plus evidence event IDs; they
are never automatically released.
"""

from __future__ import annotations

import argparse
import collections
import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from psycopg2 import connect
from psycopg2.extras import Json, execute_values

from postgres_loader import (
    assume_application_authority,
    configure_authority,
    vector_literal,
)
from wisp_claude_code_adapter import (
    ADAPTER_VERSION,
    assert_no_silent_drops,
    canonicalize_wisp_file,
)


DERIVATION_REVISION = "wisp-governed-derivation-v1"
DEFAULT_TENANT_ID = "frankengate-private-research"
DEFAULT_SUBJECT_ID = "wisp-public-contributor"
DEFAULT_PURPOSE = "quality-improvement"
DEFAULT_POLICY_REVISION = "private-research-policy-v1"
MAX_EVIDENCE_EVENT_IDS = 32
RECOVERY_MAX_EVENT_DISTANCE = 12

_PAYLOAD_KEYS = (
    "event_id",
    "sequence",
    "kind",
    "observation_status",
    "source_role",
    "parent_event_id",
    "timestamp",
    "session_id",
    "source_uuid",
    "source_parent_uuid",
    "source_record_identity",
    "path_context",
    "session_metadata",
    "system_semantics",
    "compaction",
    "interaction_policy",
    "tool_call_id",
    "function_name",
    "arguments",
    "caller",
    "correlation_status",
    "correlated_tool_proposal_event_id",
    "source_record_parent_event_id",
    "is_error",
    "record_event_id",
    "content_block_index",
    "loss_status",
)


class WispPostgresLoaderError(ValueError):
    """Raised when provenance, authority, or persistence invariants fail."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def source_start_time(trajectory: dict[str, Any]) -> dt.datetime | None:
    """Return the earliest source timestamp, never loader wall-clock time."""
    timestamps = [
        parsed
        for event in trajectory.get("events", [])
        if (parsed := _parse_timestamp(event.get("timestamp"))) is not None
    ]
    return min(timestamps) if timestamps else None


def minimize_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Build content-deduplicated JSONB while preserving typed semantics."""
    payload = {
        key: copy.deepcopy(event[key])
        for key in _PAYLOAD_KEYS
        if key in event
    }
    removed: list[str] = []
    for key in ("native_record", "native_block"):
        if key in event:
            removed.append(key)
    if event.get("content") is not None:
        payload["content_sha256"] = _sha256_value(event["content"])
        removed.append("content")

    if "queue_operation" in event:
        operation = event["queue_operation"]
        minimized = {"operation": copy.deepcopy(operation.get("operation"))}
        if operation.get("content") is not None:
            minimized["content_sha256"] = _sha256_value(operation["content"])
            removed.append("queue_operation.content")
        payload["queue_operation"] = minimized

    if "workspace_snapshot" in event:
        snapshot = event["workspace_snapshot"]
        minimized = {
            "message_id": copy.deepcopy(snapshot.get("message_id")),
            "is_update": copy.deepcopy(snapshot.get("is_update")),
        }
        if snapshot.get("snapshot") is not None:
            minimized["snapshot_sha256"] = _sha256_value(snapshot["snapshot"])
            removed.append("workspace_snapshot.snapshot")
        payload["workspace_snapshot"] = minimized

    if "subagent_workflow" in event:
        workflow = copy.deepcopy(event["subagent_workflow"])
        if workflow.get("result") is not None:
            workflow["result_sha256"] = _sha256_value(workflow["result"])
            del workflow["result"]
            removed.append("subagent_workflow.result")
        payload["subagent_workflow"] = workflow

    payload["persistence_receipt"] = {
        "schema_version": "event-persistence-receipt-v1",
        "removed_redundant_or_large_fields": sorted(removed),
        "content_storage": (
            "content_text_column" if event.get("content") is not None else "none"
        ),
        "native_source_identity_retained": isinstance(
            payload.get("source_record_identity"), dict
        ),
        "tool_arguments_retained": "arguments" in payload,
        "silent_field_drop_count": 0,
    }
    return payload


def _event_tool_fields(event: dict[str, Any]) -> tuple[str | None, str | None]:
    call_id = event.get("tool_call_id")
    tool_name = event.get("function_name")
    return (
        str(call_id) if call_id is not None else None,
        str(tool_name) if tool_name is not None else None,
    )


def _bounded_recovery_transitions(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find same-tool failure-to-success transitions in a fixed event window."""
    by_id = {event["event_id"]: event for event in events}

    def proposal_for(result: dict[str, Any]) -> dict[str, Any] | None:
        parent_id = result.get("correlated_tool_proposal_event_id")
        if not isinstance(parent_id, str):
            parent_id = result.get("parent_event_id")
        proposal = by_id.get(parent_id)
        return proposal if proposal and proposal["kind"] == "tool.proposed" else None

    completed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for event in events:
        if event["kind"] != "tool.completed":
            continue
        proposal = proposal_for(event)
        if proposal is not None and proposal.get("function_name"):
            completed.append((event, proposal))

    transitions: list[dict[str, Any]] = []
    for failed in events:
        if failed["kind"] != "tool.failed":
            continue
        failed_proposal = proposal_for(failed)
        if failed_proposal is None or not failed_proposal.get("function_name"):
            continue
        for succeeded, succeeded_proposal in completed:
            distance = succeeded["sequence"] - failed["sequence"]
            if not 0 < distance <= RECOVERY_MAX_EVENT_DISTANCE:
                continue
            if (
                succeeded_proposal["function_name"]
                != failed_proposal["function_name"]
            ):
                continue
            transitions.append(
                {
                    "failed_event_id": failed["event_id"],
                    "failed_proposal_event_id": failed_proposal["event_id"],
                    "recovery_proposal_event_id": succeeded_proposal["event_id"],
                    "completed_event_id": succeeded["event_id"],
                    "event_distance": distance,
                }
            )
            break
    return transitions


def deterministic_wisp_signals(trajectory: dict[str, Any]) -> dict[str, int]:
    """Compute outcome-blind structural signals from typed events only."""
    events = trajectory["events"]
    kind_counts = collections.Counter(event["kind"] for event in events)
    parent_counts = collections.Counter(
        event["parent_event_id"]
        for event in events
        if event.get("parent_event_id") is not None
    )
    unknown_counts = collections.Counter(
        item["category"]
        for item in trajectory["loss_receipt"].get("unknowns", [])
    )
    recovery_transitions = _bounded_recovery_transitions(events)
    return {
        "source_record_count": int(
            trajectory["loss_receipt"]["source_record_count"]
        ),
        "canonical_event_count": len(events),
        "tool_proposal_count": kind_counts["tool.proposed"],
        "tool_completed_count": kind_counts["tool.completed"],
        "tool_failed_count": kind_counts["tool.failed"],
        "unresolved_tool_result_count": unknown_counts[
            "unresolved_tool_result_correlation"
        ],
        "dangling_parent_count": unknown_counts["dangling_parent_uuid"],
        "branch_point_count": sum(count > 1 for count in parent_counts.values()),
        "compaction_count": sum("compaction" in event for event in events),
        "queue_operation_count": kind_counts["queue.operation"],
        "workspace_snapshot_count": kind_counts[
            "workspace.file_history_snapshot"
        ],
        "subagent_lifecycle_count": (
            kind_counts["subagent.started"] + kind_counts["subagent.result"]
        ),
        "malformed_record_count": kind_counts["source.malformed_record"],
        "recovery_transition_count": len(recovery_transitions),
    }


def signal_vector(signals: dict[str, int]) -> list[float]:
    """Return an eight-dimensional deterministic feature vector."""
    fields = (
        "tool_proposal_count",
        "tool_completed_count",
        "tool_failed_count",
        "unresolved_tool_result_count",
        "dangling_parent_count",
        "branch_point_count",
        "compaction_count",
        "malformed_record_count",
    )
    values = [float(max(0, signals[field])) for field in fields]
    norm = sum(value * value for value in values) ** 0.5
    return [value / norm for value in values] if norm else values


def _evidence(
    events: list[dict[str, Any]],
    kinds: set[str],
    *,
    fallback: bool = True,
) -> tuple[list[str], int]:
    candidates = [
        event["event_id"] for event in events if event["kind"] in kinds
    ]
    if not candidates and fallback:
        candidates = [
            event["event_id"]
            for event in events
            if event["kind"]
            in {"conversation.message", "system.event", "source.malformed_record"}
        ]
    return candidates[:MAX_EVIDENCE_EVENT_IDS], len(candidates)


def _proposal_payload(
    *,
    artifact_kind: str,
    proposal_type: str,
    evidence_event_ids: list[str],
    evidence_total_count: int,
    signals: dict[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": "governed-trace-proposal-v1",
        "lifecycle": "proposal",
        "release_policy": "human_review_required",
        "automatic_release_allowed": False,
        "controlled_vocabulary": {
            "artifact_kind": artifact_kind,
            "proposal_type": proposal_type,
            "evidence_semantics": "typed_canonical_event_ids",
        },
        "evidence_event_ids": evidence_event_ids,
        "evidence_total_count": evidence_total_count,
        "evidence_truncated": evidence_total_count > len(evidence_event_ids),
        "structural_signals": signals,
    }


def build_artifacts(
    trajectory: dict[str, Any],
    *,
    tenant_id: str,
    subject_id: str,
    audience: str,
    team_id: str | None,
    classification: int,
    purpose: str,
    policy_revision: str,
) -> list[dict[str, Any]]:
    """Build one signal and only evidence-supported, unreleased proposals."""
    events = trajectory["events"]
    signals = deterministic_wisp_signals(trajectory)
    source_hash = trajectory["source"]["source_file_sha256"]
    trace_id = trajectory["trace_id"]
    common = {
        "source_trajectory_id": trace_id,
        "tenant_id": tenant_id,
        "owner_subject_id": subject_id,
        "audience": audience,
        "team_id": team_id,
        "classification": classification,
        "allowed_purposes": [purpose],
        "policy_revision": policy_revision,
        "lifecycle": "proposal",
        "source_content_sha256": source_hash,
        "derivation_revision": DERIVATION_REVISION,
    }

    signal_evidence, signal_total = _evidence(
        events,
        {
            "tool.proposed",
            "tool.completed",
            "tool.failed",
            "source.malformed_record",
        },
    )
    signal_payload = _proposal_payload(
        artifact_kind="signal",
        proposal_type="trace_structure_signal",
        evidence_event_ids=signal_evidence,
        evidence_total_count=signal_total,
        signals=signals,
    )
    artifacts = [
        {
            **common,
            "id": f"{trace_id}:signal:{DERIVATION_REVISION}",
            "kind": "signal",
            "content_text": (
                "artifact=deterministic_signal "
                f"tool_proposals={signals['tool_proposal_count']} "
                f"tool_failures={signals['tool_failed_count']} "
                f"unresolved_tool_results={signals['unresolved_tool_result_count']} "
                f"malformed_records={signals['malformed_record_count']}"
            ),
            "payload": signal_payload,
            "embedding": vector_literal(signal_vector(signals)),
        }
    ]

    receipt = trajectory["loss_receipt"]
    failure_categories: list[str] = []
    failure_kinds: set[str] = set()
    if signals["tool_failed_count"]:
        failure_categories.append("tool_failed")
        failure_kinds.add("tool.failed")
    if signals["malformed_record_count"]:
        failure_categories.append("malformed_source_record")
        failure_kinds.add("source.malformed_record")
    if signals["unresolved_tool_result_count"]:
        failure_categories.append("unresolved_tool_result_correlation")
        failure_kinds.update({"tool.completed", "tool.failed"})
    if signals["dangling_parent_count"]:
        failure_categories.append("dangling_parent_uuid")
        failure_kinds.update(
            event["kind"]
            for event in events
            if event.get("source_parent_uuid") and not event.get("parent_event_id")
        )
    additional_conformance = sorted(
        {
            str(item.get("category"))
            for item in receipt.get("losses", []) + receipt.get("unknowns", [])
            if item.get("category")
            not in {
                "malformed_source_bytes_not_retained",
                "unresolved_tool_result_correlation",
                "dangling_parent_uuid",
            }
        }
    )
    if additional_conformance:
        failure_categories.append("other_explicit_conformance_failure")
        failure_kinds.update(
            {
                "source.unknown_record",
                "source.unknown_json_record",
                "content.unknown",
            }
        )

    if failure_categories:
        eval_evidence, eval_total = _evidence(events, failure_kinds)
        eval_type = (
            "trace_conformance_failure_eval"
            if len(failure_categories) > 1
            else {
                "tool_failed": "tool_error_regression_eval",
                "malformed_source_record": "malformed_source_import_eval",
                "unresolved_tool_result_correlation": (
                    "tool_result_correlation_eval"
                ),
                "dangling_parent_uuid": "parent_dag_conformance_eval",
                "other_explicit_conformance_failure": (
                    "schema_conformance_review_eval"
                ),
            }[failure_categories[0]]
        )
        # A receipt category without a canonical evidence event is not enough
        # to create human review work. The signal still records the condition.
        if eval_evidence:
            eval_payload = _proposal_payload(
                artifact_kind="eval_proposal",
                proposal_type=eval_type,
                evidence_event_ids=eval_evidence,
                evidence_total_count=eval_total,
                signals=signals,
            )
            eval_payload["controlled_vocabulary"]["failure_categories"] = (
                failure_categories
            )
            eval_payload["controlled_vocabulary"][
                "additional_conformance_categories"
            ] = additional_conformance
            artifacts.append(
                {
                    **common,
                    "id": f"{trace_id}:eval_proposal:{DERIVATION_REVISION}",
                    "kind": "eval_proposal",
                    "content_text": (
                        f"artifact=eval_proposal proposal_type={eval_type} "
                        f"lifecycle=proposal evidence_count={len(eval_evidence)}"
                    ),
                    "payload": eval_payload,
                    "embedding": None,
                }
            )

    # Structural trace shape cannot establish a durable fact. Fact extraction
    # must separately review content, provenance, temporal validity, and
    # contradictions, so this loader explicitly emits zero fact proposals.

    transitions = _bounded_recovery_transitions(events)
    if transitions:
        evidence_ids: list[str] = []
        for transition in transitions:
            for key in (
                "failed_proposal_event_id",
                "failed_event_id",
                "recovery_proposal_event_id",
                "completed_event_id",
            ):
                event_id = transition[key]
                if event_id not in evidence_ids:
                    evidence_ids.append(event_id)
        evidence_total = len(evidence_ids)
        evidence_ids = evidence_ids[:MAX_EVIDENCE_EVENT_IDS]
        procedure_payload = _proposal_payload(
            artifact_kind="procedure_proposal",
            proposal_type="bounded_same_tool_recovery_review",
            evidence_event_ids=evidence_ids,
            evidence_total_count=evidence_total,
            signals=signals,
        )
        procedure_payload["controlled_vocabulary"].update(
            {
                "recovery_semantics": "same_tool_failure_to_success",
                "maximum_event_distance": RECOVERY_MAX_EVENT_DISTANCE,
            }
        )
        procedure_payload["bounded_transition_count"] = len(transitions)
        artifacts.append(
            {
                **common,
                "id": f"{trace_id}:procedure_proposal:{DERIVATION_REVISION}",
                "kind": "procedure_proposal",
                "content_text": (
                    "artifact=procedure_proposal "
                    "proposal_type=bounded_same_tool_recovery_review "
                    f"lifecycle=proposal evidence_count={len(evidence_ids)}"
                ),
                "payload": procedure_payload,
                "embedding": None,
            }
        )
    return artifacts


def _first_model_name(trajectory: dict[str, Any]) -> str | None:
    for event in trajectory["events"]:
        native = event.get("native_record")
        if not isinstance(native, dict):
            continue
        message = native.get("message")
        if isinstance(message, dict) and isinstance(message.get("model"), str):
            return message["model"]
    return None


def prepare_wisp_rows(
    trajectory: dict[str, Any],
    *,
    created_at: dt.datetime | None = None,
    tenant_id: str = DEFAULT_TENANT_ID,
    subject_id: str = DEFAULT_SUBJECT_ID,
    audience: str = "private",
    team_id: str | None = None,
    classification: int = 0,
    purpose: str = DEFAULT_PURPOSE,
    policy_revision: str = DEFAULT_POLICY_REVISION,
) -> dict[str, Any]:
    """Prepare persistence rows without opening a database connection."""
    assert_no_silent_drops(trajectory)
    if audience == "private" and team_id is not None:
        raise WispPostgresLoaderError("private trajectories cannot have a team_id")
    if audience == "team" and not team_id:
        raise WispPostgresLoaderError("team trajectories require team_id")
    if audience not in {"private", "team"}:
        raise WispPostgresLoaderError("audience must be private or team")

    created_at = created_at or source_start_time(trajectory)
    if created_at is None:
        raise WispPostgresLoaderError(
            "source start time is missing; provide a source-derived workflow start"
        )
    source = trajectory["source"]
    raw_payload = {
        "schema_version": "source-reference-v1",
        "dataset_id": source["dataset_id"],
        "dataset_revision": source["dataset_revision"],
        "relative_path": source["relative_path"],
        "source_file_sha256": source["source_file_sha256"],
        "source_file_byte_length": source["source_file_byte_length"],
        "path_context": copy.deepcopy(source["path_context"]),
        "raw_transcript_embedded": False,
    }
    trajectory_row = {
        "id": trajectory["trace_id"],
        "tenant_id": tenant_id,
        "owner_subject_id": subject_id,
        "audience": audience,
        "team_id": team_id,
        "classification": classification,
        "allowed_purposes": [purpose],
        "policy_revision": policy_revision,
        "source_dataset": source["dataset_id"],
        "source_revision": source["dataset_revision"],
        "adapter_revision": source.get("adapter", ADAPTER_VERSION),
        "task_id": trajectory["task"]["task_id"],
        "harness": "claude-code",
        "model_name": _first_model_name(trajectory),
        "outcome": copy.deepcopy(trajectory["outcome"]),
        "loss_receipt": copy.deepcopy(trajectory["loss_receipt"]),
        "raw_payload": raw_payload,
        "content_sha256": source["source_file_sha256"],
        "created_at": created_at,
    }

    event_rows: list[dict[str, Any]] = []
    for event in trajectory["events"]:
        tool_call_id, tool_name = _event_tool_fields(event)
        event_rows.append(
            {
                "trajectory_id": trajectory["trace_id"],
                "sequence": event["sequence"],
                "event_id": event["event_id"],
                "parent_event_id": event.get("parent_event_id"),
                "kind": event["kind"],
                "observation_status": event["observation_status"],
                "source_role": event["source_role"],
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "content_text": event.get("content"),
                "payload": minimize_event_payload(event),
            }
        )

    artifacts = build_artifacts(
        trajectory,
        tenant_id=tenant_id,
        subject_id=subject_id,
        audience=audience,
        team_id=team_id,
        classification=classification,
        purpose=purpose,
        policy_revision=policy_revision,
    )
    return {
        "trajectory": trajectory_row,
        "events": event_rows,
        "artifacts": artifacts,
    }


def _workflow_key(trajectory: dict[str, Any]) -> tuple[str, str] | None:
    context = trajectory["source"]["path_context"]
    parent = context.get("parent_session_id")
    workflow = context.get("workflow_id")
    if parent and workflow:
        return str(parent), str(workflow)
    return None


def resolve_source_start_times(
    trajectories: list[dict[str, Any]],
) -> dict[str, dt.datetime]:
    """Resolve timestamp-less workflow journals from sibling source events."""
    direct = {
        trajectory["trace_id"]: source_start_time(trajectory)
        for trajectory in trajectories
    }
    workflow_starts: dict[tuple[str, str], dt.datetime] = {}
    for trajectory in trajectories:
        key = _workflow_key(trajectory)
        start = direct[trajectory["trace_id"]]
        if key is not None and start is not None:
            previous = workflow_starts.get(key)
            workflow_starts[key] = min(previous, start) if previous else start

    resolved: dict[str, dt.datetime] = {}
    for trajectory in trajectories:
        start = direct[trajectory["trace_id"]]
        if start is None:
            key = _workflow_key(trajectory)
            start = workflow_starts.get(key) if key is not None else None
        if start is None:
            raise WispPostgresLoaderError(
                "cannot derive source start time for "
                f"{trajectory['source']['relative_path']!r}"
            )
        resolved[trajectory["trace_id"]] = start
    return resolved


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def verify_application_role(connection: Any) -> None:
    """Fail closed unless protected writes execute as the non-bypass app role."""
    with connection.cursor() as cursor:
        cursor.execute("select current_user")
        row = cursor.fetchone()
    if not row or row[0] != "trace_research_app":
        raise WispPostgresLoaderError(
            "protected inserts require current_user=trace_research_app"
        )


def persist_prepared_rows(
    connection: Any, prepared_rows: list[dict[str, Any]]
) -> dict[str, int]:
    """Idempotently insert prepared rows under the verified application role."""
    verify_application_role(connection)
    trajectory_rows = [item["trajectory"] for item in prepared_rows]
    event_rows = [
        event for item in prepared_rows for event in item["events"]
    ]
    artifact_rows = [
        artifact for item in prepared_rows for artifact in item["artifacts"]
    ]
    if not trajectory_rows:
        return {
            "source_trajectories": 0,
            "source_events": 0,
            "signal_artifacts": 0,
            "eval_proposals": 0,
            "fact_proposals": 0,
            "procedure_proposals": 0,
        }

    trajectory_columns = (
        "id",
        "tenant_id",
        "owner_subject_id",
        "audience",
        "team_id",
        "classification",
        "allowed_purposes",
        "policy_revision",
        "source_dataset",
        "source_revision",
        "adapter_revision",
        "task_id",
        "harness",
        "model_name",
        "outcome",
        "loss_receipt",
        "raw_payload",
        "content_sha256",
        "created_at",
    )
    event_columns = (
        "trajectory_id",
        "sequence",
        "event_id",
        "parent_event_id",
        "kind",
        "observation_status",
        "source_role",
        "tool_call_id",
        "tool_name",
        "content_text",
        "payload",
    )
    artifact_columns = (
        "id",
        "source_trajectory_id",
        "tenant_id",
        "owner_subject_id",
        "audience",
        "team_id",
        "classification",
        "allowed_purposes",
        "policy_revision",
        "kind",
        "lifecycle",
        "content_text",
        "payload",
        "embedding",
        "source_content_sha256",
        "derivation_revision",
    )

    with connection.cursor() as cursor:
        # Derived rows are reproducible materializations, not source evidence.
        # Replace this revision's bounded set so a tightened abstention rule
        # removes stale proposals from earlier runs instead of leaving review
        # spam behind under idempotent source/event inserts.
        cursor.execute(
            """
            delete from trace_research.derived_artifacts
            where derivation_revision = %s
              and source_trajectory_id = any(%s)
            """,
            (
                DERIVATION_REVISION,
                [row["id"] for row in trajectory_rows],
            ),
        )
        execute_values(
            cursor,
            """
            insert into trace_research.trajectories (
              id, tenant_id, owner_subject_id, audience, team_id, classification,
              allowed_purposes, policy_revision, source_dataset, source_revision,
              adapter_revision, task_id, harness, model_name, outcome, loss_receipt,
              raw_payload, content_sha256, created_at
            ) values %s
            on conflict (id) do nothing
            """,
            [
                tuple(
                    Json(row[column])
                    if column in {"outcome", "loss_receipt", "raw_payload"}
                    else row[column]
                    for column in trajectory_columns
                )
                for row in trajectory_rows
            ],
            page_size=100,
        )
        for batch in _chunks(event_rows, 1000):
            execute_values(
                cursor,
                """
                insert into trace_research.events (
                  trajectory_id, sequence, event_id, parent_event_id, kind,
                  observation_status, source_role, tool_call_id, tool_name,
                  content_text, payload
                ) values %s
                on conflict do nothing
                """,
                [
                    tuple(
                        Json(row[column]) if column == "payload" else row[column]
                        for column in event_columns
                    )
                    for row in batch
                ],
                page_size=1000,
            )
        execute_values(
            cursor,
            """
            insert into trace_research.derived_artifacts (
              id, source_trajectory_id, tenant_id, owner_subject_id, audience,
              team_id, classification, allowed_purposes, policy_revision, kind,
              lifecycle, content_text, payload, embedding, source_content_sha256,
              derivation_revision
            ) values %s
            on conflict (id) do nothing
            """,
            [
                tuple(
                    Json(row[column]) if column == "payload" else row[column]
                    for column in artifact_columns
                )
                for row in artifact_rows
            ],
            template=(
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s::public.vector,%s,%s)"
            ),
            page_size=100,
        )
    connection.commit()
    artifact_counts = collections.Counter(
        artifact["kind"] for artifact in artifact_rows
    )
    return {
        "source_trajectories": len(trajectory_rows),
        "source_events": len(event_rows),
        "signal_artifacts": artifact_counts["signal"],
        "eval_proposals": artifact_counts["eval_proposal"],
        "fact_proposals": artifact_counts["fact_proposal"],
        "procedure_proposals": artifact_counts["procedure_proposal"],
    }


def load_wisp_corpus(
    connection: Any,
    *,
    corpus_root: Path,
    manifest: dict[str, Any] | Path,
    tenant_id: str = DEFAULT_TENANT_ID,
    subject_id: str = DEFAULT_SUBJECT_ID,
    audience: str = "private",
    team_id: str | None = None,
    classification: int = 0,
    purpose: str = DEFAULT_PURPOSE,
    policy_revision: str = DEFAULT_POLICY_REVISION,
) -> dict[str, int]:
    """Canonicalize every native file, resolve source time, and persist."""
    paths = sorted(corpus_root.resolve().rglob("*.jsonl"))
    trajectories = [
        canonicalize_wisp_file(path, corpus_root, manifest) for path in paths
    ]
    starts = resolve_source_start_times(trajectories)
    prepared = [
        prepare_wisp_rows(
            trajectory,
            created_at=starts[trajectory["trace_id"]],
            tenant_id=tenant_id,
            subject_id=subject_id,
            audience=audience,
            team_id=team_id,
            classification=classification,
            purpose=purpose,
            policy_revision=policy_revision,
        )
        for trajectory in trajectories
    ]
    return persist_prepared_rows(connection, prepared)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--subject-id", default=DEFAULT_SUBJECT_ID)
    parser.add_argument("--authorization-epoch", type=int, default=1)
    parser.add_argument("--classification-ceiling", type=int, default=2)
    parser.add_argument("--classification", type=int, default=0)
    parser.add_argument("--purpose", default=DEFAULT_PURPOSE)
    parser.add_argument("--policy-revision", default=DEFAULT_POLICY_REVISION)
    parser.add_argument("--audience", choices=("private", "team"), default="private")
    parser.add_argument("--team-id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.audience == "private" and args.team_id is not None:
        raise SystemExit("--team-id is only valid with --audience=team")
    if args.audience == "team" and not args.team_id:
        raise SystemExit("--team-id is required with --audience=team")

    connection = connect(args.dsn)
    try:
        # Authority rows are administrative setup.  The transaction is then
        # committed, and every protected data insert below occurs only after
        # assuming the NOSUPERUSER/NOBYPASSRLS trace_research_app role.
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
        counts = load_wisp_corpus(
            connection,
            corpus_root=args.corpus_root,
            manifest=args.manifest,
            tenant_id=args.tenant_id,
            subject_id=args.subject_id,
            audience=args.audience,
            team_id=args.team_id,
            classification=args.classification,
            purpose=args.purpose,
            policy_revision=args.policy_revision,
        )
        print(json.dumps(counts, sort_keys=True))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
