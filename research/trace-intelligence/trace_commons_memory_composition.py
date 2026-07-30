#!/usr/bin/env python3
"""Deterministic, content-minimized Trace Commons memory composition.

The runner compares evidence retention and lifecycle mechanics. It never treats
later alignment as memory correctness or utility, never emits native content or
identifiers, and never activates dream proposals.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional, Sequence, Union

import bitemporal_memory_conformance as temporal
import trace_commons_memory_conformance as native


SCHEMA_VERSION = "trace-commons-memory-composition-result-v4"
ANALYSIS_VERSION = "deterministic-full-cohort-composition-preflight-v4"
REAL_DATASET_ID = (
    "trace-commons/agent-traces-full-claude-memory-composition"
)
REAL_DATASET_REVISION = "112ebd4d03ce852b00e935d523107c3d0c9a65bf"
DIRECT_TOOLS = {"read", "write", "edit", "grep"}
SHELL_TOOLS = {"bash", "powershell"}
STATE_TOOLS = {"read", "write", "edit"}
CONTEXT_NAMES = {"memory.md", "claude.md", "agents.md", "project.md"}
CONTEXT_COMMAND_RE = re.compile(
    r"(^|[/\s'\"`])(?:memory|claude|agents|project)\.md"
    r"(?=$|[/\s'\"`])",
    re.IGNORECASE,
)
FIXED_IMPORT_AUTHORITY = native.AuthorityEnvelope(
    tenant_id="trace-commons-public-research",
    owner_subject_id="trace-commons-composition-cohort",
    team_id="trace-intelligence-study",
    classification=1,
    purpose="trace-memory-research",
    authorization_epoch=1,
)


class CompositionError(ValueError):
    """Raised when the frozen deterministic composition contract is violated."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def keyed_digest(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "rate": (
            round(float(numerator) / float(denominator), 12)
            if denominator
            else None
        ),
    }


def admitted_context_path(path: str) -> bool:
    normalized = native.normalize_path(path)
    basename = PurePosixPath(normalized).name
    return (
        basename in CONTEXT_NAMES
        or "/memory/" in normalized
        or "/skills/" in normalized
    )


def admitted_shell_command(command: str) -> bool:
    normalized = native.normalize_path(command)
    return (
        "/memory/" in normalized
        or "/skills/" in normalized
        or CONTEXT_COMMAND_RE.search(normalized) is not None
    )


@dataclass(frozen=True)
class QualifiedInteraction:
    call: native.ToolCall
    result: native.ToolResult
    tool_kind: str
    path: Optional[str]
    project_source: str
    event_key: str
    artifact_key: Optional[str]
    artifact_name_key: Optional[str]
    project_key: str
    session_key: str
    call_order: tuple[Any, ...]
    result_order: tuple[Any, ...]


@dataclass(frozen=True)
class StateObservation:
    event_key: str
    artifact_key: str
    artifact_name_key: str
    project_key: str
    session_key: str
    session_id: str
    call_record_uuid: str
    result_record_uuid: str
    call_order: tuple[Any, ...]
    result_order: tuple[Any, ...]
    observed_at: datetime
    source_kind: str
    content_sha256: str
    content_bytes: int
    canonical_content: str
    interval_censored_change: bool


def normalize_project_source(value: str) -> str:
    """Normalize a cwd with the frozen platform-aware project join rule."""

    normalized = re.sub(r"/+", "/", value.replace("\\", "/"))
    if re.match(r"^[A-Za-z]:/", normalized):
        normalized = normalized.casefold()
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized


def _initial_project_sources(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """Return each session's first nonempty normalized cwd.

    Exact normalized equality is the only cross-session project grouping rule.
    """

    result: dict[str, str] = {}
    for record in sorted(
        records,
        key=lambda item: (
            str(item["_source_file"]),
            int(item["_source_line"]),
        ),
    ):
        session_id = str(record.get("sessionId", ""))
        cwd = record.get("cwd")
        if (
            session_id
            and session_id not in result
            and isinstance(cwd, str)
            and cwd
        ):
            result[session_id] = normalize_project_source(cwd)
    return result


def _project_inventory(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    initial = _initial_project_sources(records)
    sessions_by_project: dict[str, set[str]] = defaultdict(set)
    for session_id, project in initial.items():
        sessions_by_project[project].add(session_id)
    return {
        "apparent_projects": len(sessions_by_project),
        "multi_session_project_groups": sum(
            len(sessions) > 1 for sessions in sessions_by_project.values()
        ),
        "sessions_missing_initial_cwd": len(
            {
                str(record.get("sessionId"))
                for record in records
                if record.get("sessionId")
            }
        )
        - len(initial),
    }


def _serial_session_pairs(
    records: Sequence[Mapping[str, Any]],
) -> set[tuple[str, str]]:
    """Return strictly non-overlapping same-project session orderings."""

    projects = _initial_project_sources(records)
    bounds: dict[str, tuple[datetime, datetime]] = {}
    for record in records:
        session_id = str(record.get("sessionId", ""))
        timestamp = record.get("timestamp")
        if not session_id or not isinstance(timestamp, str):
            continue
        observed = native.instant(timestamp)
        current = bounds.get(session_id)
        bounds[session_id] = (
            min(current[0], observed) if current else observed,
            max(current[1], observed) if current else observed,
        )
    pairs: set[tuple[str, str]] = set()
    sessions = sorted(bounds)
    for earlier in sessions:
        for later in sessions:
            if (
                earlier != later
                and projects.get(earlier)
                and projects.get(earlier) == projects.get(later)
                and bounds[earlier][1] < bounds[later][0]
            ):
                pairs.add((earlier, later))
    return pairs


def _source_order(
    observed_at: datetime,
    source_receipt_order: int,
    source_line: int,
    tool_id: str,
) -> tuple[Any, ...]:
    return (
        observed_at,
        int(source_receipt_order),
        int(source_line),
        sha256_bytes(tool_id.encode("utf-8")),
    )


def _join_result(
    call: native.ToolCall,
    results: Mapping[tuple[str, str], native.ToolResult],
) -> Optional[native.ToolResult]:
    result = results.get((call.session_id, call.tool_id))
    if result is None:
        return None
    if (
        result.source_assistant_uuid
        and result.source_assistant_uuid != call.record_uuid
    ):
        return None
    if result.observed_at < call.observed_at:
        return None
    return result


def _receipt_root(
    receipts: Sequence[Mapping[str, Any]],
) -> str:
    normalized = [
        {
            "path": str(item["path"]),
            "bytes": int(item["bytes"]),
            "sha256": str(item["sha256"]),
            "records": int(item["records"]),
        }
        for item in receipts
    ]
    return sha256_value(sorted(normalized, key=lambda item: item["path"]))


def _manifest_receipt(
    manifest: Mapping[str, Any],
) -> str:
    cohort = manifest.get("cohort")
    source_files = (
        cohort.get("source_files")
        if isinstance(cohort, dict)
        else manifest.get("source_files")
    )
    if not isinstance(source_files, list) or not source_files:
        raise CompositionError("manifest source_files are required")
    calculated = sha256_value(source_files)
    declared = manifest.get("cohort_receipt_sha256")
    if declared is not None and str(declared) != calculated:
        raise CompositionError("manifest cohort receipt does not match")
    return calculated


def _load_experiment_config(
    path: Union[Path, str],
    dataset_manifest_path: Union[Path, str],
) -> tuple[dict[str, Any], str]:
    config_path = Path(path)
    try:
        raw = config_path.read_bytes()
        config = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise CompositionError(
            f"cannot load experiment configuration: {exc}"
        ) from exc
    if not isinstance(config, dict):
        raise CompositionError("experiment configuration must be an object")
    if (
        config.get("schema_version")
        != "trace-memory-composition-experiment-v1"
    ):
        raise CompositionError("unexpected experiment configuration schema")
    dataset = config.get("dataset")
    if not isinstance(dataset, dict):
        raise CompositionError("experiment dataset binding is required")
    bound_manifest = (config_path.parent / str(dataset.get("manifest", ""))).resolve()
    actual_manifest = Path(dataset_manifest_path).resolve()
    if bound_manifest != actual_manifest:
        raise CompositionError("experiment binds a different dataset manifest")
    try:
        manifest_raw = actual_manifest.read_bytes()
    except OSError as exc:
        raise CompositionError("cannot hash bound dataset manifest") from exc
    if sha256_bytes(manifest_raw) != dataset.get("manifest_sha256"):
        raise CompositionError("bound dataset manifest SHA-256 mismatch")
    if dataset.get("revision") != REAL_DATASET_REVISION:
        raise CompositionError("experiment binds a different dataset revision")
    model = config.get("model_phase")
    if not isinstance(model, dict):
        raise CompositionError("model phase configuration is required")
    for prompt_name in (
        "atomic_extractor_system_prompt",
        "dream_system_prompt",
    ):
        prompt = model.get(prompt_name)
        declared = model.get(prompt_name + "_sha256")
        if not isinstance(prompt, str) or sha256_bytes(
            prompt.encode("utf-8")
        ) != declared:
            raise CompositionError(
                f"{prompt_name} receipt does not match"
            )
    mechanics = config.get("mechanics_phase")
    if not isinstance(mechanics, dict):
        raise CompositionError("mechanics phase configuration is required")
    if mechanics.get("latest_only_identity") != [
        "normalized_artifact_basename"
    ]:
        raise CompositionError("unexpected latest-only identity")
    if mechanics.get("bitemporal_identity") != [
        "authority_subject",
        "project_context_key",
        "artifact_key",
    ]:
        raise CompositionError("unexpected bitemporal identity")
    deterministic_contract = {
        "phase_status": {
            "deterministic_mechanics_preflight": "enabled",
            "postgresql_ranker": "not_run",
            "model_quality": "not_run",
            "human_review": "not_run",
        },
        "project_identity": {
            "source": "initial_nonempty_cwd_in_each_native_history",
            "normalization": [
                "replace_backslash_with_slash",
                "collapse_repeated_slashes",
                "casefold_windows_drive_paths_only",
                "remove_trailing_slash_except_root",
            ],
            "join_rule": "exact_normalized_initial_cwd_equality",
            "filename_join_forbidden": True,
            "branch_join_forbidden": True,
            "expected_apparent_projects": 21,
            "expected_multi_session_groups": 6,
            "ambiguous_groups": [
                "overlapping_sessions_remain_same_project_but_not_serial_continuations"
            ],
        },
        "cutoffs": {
            "position": "strictly_before_each_qualifying_native_operation",
            "same_branch_evidence": True,
            "earlier_same_project_sessions": True,
            "future_events_or_sessions": False,
            "target_call_result_and_descendants": False,
            "failed_or_unjoined_operations_advance_state": False,
        },
        "mechanics_phase": {
            "content_match": "sha256_of_canonical_exact_content",
            "verbatim_identity": [
                "authority_subject",
                "project_context_key",
                "artifact_key",
                "revision_digest",
            ],
            "latest_only_identity": ["normalized_artifact_basename"],
            "latest_only_context_fields": [],
            "latest_only_overwrite_order": [
                "observed_at_utc",
                "source_receipt_order",
                "source_line",
                "tool_use_digest",
            ],
            "bitemporal_identity": [
                "authority_subject",
                "project_context_key",
                "artifact_key",
            ],
            "valid_time_semantics": (
                "observed_boundary_with_interval_censored_unknown_gaps"
            ),
            "dream_active_mutations_without_release": 0,
            "no_memory_sanity_control": "not_run",
        },
        "common_state_reducer": {
            "applies_to": [
                "verbatim",
                "latest_only",
                "contextual_bitemporal",
            ],
            "procedure": [
                "discard_ineligible_authority_or_post_cutoff_items",
                "abstain_on_known_interval_gap",
                "abstain_when_top_eligible_states_conflict_at_the_same_observation_boundary",
                "otherwise_return_the_highest_ranked_exact_state_digest",
            ],
            "known_interval_gap_definition": (
                "open_gap_marker_observed_strictly_before_query_cutoff"
            ),
            "dream_scored_separately": True,
        },
        "dream_policy": {
            "unsupported_active_promotions_allowed": 0,
            "unsupported_proposals_allowed": True,
            "unsupported_proposal_disposition": "reject_or_quarantine",
            "automatic_promotion_allowed": False,
            "promotion_requires_independent_release_decision": True,
        },
        "durable_output": {
            "raw_arm_outputs_committed": False,
            "authorized_quarantine_outputs_allowed": True,
            "aggregate_content_allowed": False,
            "raw_paths_allowed": False,
            "raw_identifiers_allowed": False,
            "per_artifact_digests_allowed": False,
            "cohort_receipt_digest_allowed": True,
        },
    }
    mismatches = [
        name
        for name, expected in deterministic_contract.items()
        if config.get(name) != expected
    ]
    if mismatches:
        raise CompositionError(
            "deterministic experiment contract mismatch: "
            + ", ".join(sorted(mismatches))
        )
    return config, sha256_bytes(raw)


def _validate_expected_inventory(
    manifest: Mapping[str, Any],
    actual: Mapping[str, int],
) -> None:
    expected = manifest.get("expected_inventory")
    if expected is None:
        return
    if not isinstance(expected, dict):
        raise CompositionError("expected_inventory must be an object")
    if manifest.get("frozen_source_identity") is True:
        identity_mismatches = []
        if manifest.get("dataset_id") != REAL_DATASET_ID:
            identity_mismatches.append("dataset_id")
        if manifest.get("dataset_revision") != REAL_DATASET_REVISION:
            identity_mismatches.append("dataset_revision")
        if manifest.get("adapter") != native.ADAPTER_VERSION:
            identity_mismatches.append("adapter")
        if manifest.get("harness") != "claude_code":
            identity_mismatches.append("harness")
        if identity_mismatches:
            raise CompositionError(
                "frozen source identity mismatch: "
                + ", ".join(sorted(identity_mismatches))
            )
    mismatches = []
    for name, expected_value in expected.items():
        if name not in actual:
            mismatches.append(name)
            continue
        if int(actual[name]) != int(expected_value):
            mismatches.append(name)
    if mismatches:
        raise CompositionError(
            "frozen inventory mismatch: " + ", ".join(sorted(mismatches))
        )


def _qualifying_interactions(
    cohort: native.VerifiedMemoryCohort,
    identity_key: bytes,
    source_receipt_order: Mapping[str, int],
) -> tuple[list[QualifiedInteraction], dict[str, int]]:
    initial_projects = _initial_project_sources(cohort.records)
    interactions: list[QualifiedInteraction] = []
    metrics = {
        "qualifying_candidate_calls": 0,
        "qualifying_interactions": 0,
        "qualifying_failures": 0,
        "qualifying_unmatched_calls": 0,
        "explicit_reads": 0,
        "writes_or_edits": 0,
        "shell_search_or_other": 0,
    }
    for call in cohort.calls:
        tool_kind = call.tool_name.casefold()
        path: Optional[str] = None
        qualifies = False
        if tool_kind in DIRECT_TOOLS:
            path = call.path
            qualifies = bool(path and admitted_context_path(path))
        elif tool_kind in SHELL_TOOLS:
            command = call.tool_input.get("command")
            qualifies = isinstance(command, str) and admitted_shell_command(command)
        if not qualifies:
            continue
        metrics["qualifying_candidate_calls"] += 1
        result = _join_result(call, cohort.results)
        if result is None:
            metrics["qualifying_unmatched_calls"] += 1
            continue
        metrics["qualifying_interactions"] += 1
        if result.is_error:
            metrics["qualifying_failures"] += 1
        if tool_kind == "read":
            metrics["explicit_reads"] += 1
        elif tool_kind in {"write", "edit"}:
            metrics["writes_or_edits"] += 1
        else:
            metrics["shell_search_or_other"] += 1

        project_source = initial_projects.get(call.session_id, "")
        project_identity = (
            project_source
            if project_source
            else "missing-session-project:" + call.session_id
        )
        artifact = (
            keyed_digest(identity_key, native.normalize_path(path))
            if path
            else None
        )
        artifact_name = (
            keyed_digest(
                identity_key,
                PurePosixPath(native.normalize_path(path)).name,
            )
            if path
            else None
        )
        interactions.append(
            QualifiedInteraction(
                call=call,
                result=result,
                tool_kind=tool_kind,
                path=path,
                project_source=project_source,
                event_key=keyed_digest(
                    identity_key,
                    f"{call.source_file}:{call.source_line}:{call.tool_id}",
                ),
                artifact_key=artifact,
                artifact_name_key=artifact_name,
                project_key=keyed_digest(identity_key, project_identity),
                session_key=keyed_digest(identity_key, call.session_id),
                call_order=_source_order(
                    call.observed_at,
                    source_receipt_order[call.source_file],
                    call.source_line,
                    call.tool_id,
                ),
                result_order=_source_order(
                    result.observed_at,
                    source_receipt_order[call.source_file],
                    call.source_line,
                    call.tool_id,
                ),
            )
        )
    interactions.sort(key=lambda item: item.call_order)
    return interactions, metrics


def _parent_maps(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Optional[str]]]:
    result: dict[str, dict[str, Optional[str]]] = defaultdict(dict)
    for record in records:
        session_id = str(record.get("sessionId", ""))
        uuid = str(record.get("uuid", ""))
        if not session_id or not uuid:
            continue
        parent = record.get("parentUuid")
        result[session_id][uuid] = str(parent) if parent is not None else None
    return result


def _is_ancestor(
    parents: Mapping[str, Optional[str]],
    ancestor_uuid: str,
    descendant_uuid: str,
) -> bool:
    current = parents.get(descendant_uuid)
    seen: set[str] = set()
    while current is not None and current not in seen:
        if current == ancestor_uuid:
            return True
        seen.add(current)
        current = parents.get(current)
    return False


def _branch_eligible(
    observation: StateObservation,
    target: QualifiedInteraction,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
) -> bool:
    if observation.session_id != target.call.session_id:
        return (
            (
                observation.session_id,
                target.call.session_id,
            )
            in serial_session_pairs
            and observation.result_order < target.call_order
        )
    parents = parents_by_session.get(target.call.session_id, {})
    return (
        observation.result_order < target.call_order
        and (
            _is_ancestor(
                parents,
                observation.result_record_uuid,
                target.call.record_uuid,
            )
            or _is_ancestor(
                parents,
                observation.call_record_uuid,
                target.call.record_uuid,
            )
        )
    )


def _latest_eligible(
    observations: Sequence[StateObservation],
    target: QualifiedInteraction,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
) -> Optional[StateObservation]:
    eligible = [
        item
        for item in observations
        if item.artifact_key == target.artifact_key
        and item.project_key == target.project_key
        and _branch_eligible(
            item,
            target,
            parents_by_session,
            serial_session_pairs,
        )
    ]
    return max(eligible, key=lambda item: item.result_order) if eligible else None


def _state_observations(
    interactions: Sequence[QualifiedInteraction],
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
) -> tuple[list[StateObservation], dict[str, int]]:
    observations: list[StateObservation] = []
    metrics = {
        "supported_observations": 0,
        "ambiguous_transitions": 0,
        "interval_censored_changes": 0,
        "failed_operation_promotions": 0,
    }
    for item in interactions:
        if (
            item.tool_kind not in STATE_TOOLS
            or item.path is None
            or item.artifact_key is None
            or item.artifact_name_key is None
            or item.result.is_error
        ):
            continue
        content: Optional[str] = None
        if item.tool_kind == "read":
            if not isinstance(item.result.content, str):
                metrics["ambiguous_transitions"] += 1
                continue
            content = native.canonicalize_read_content(item.result.content)
        elif item.tool_kind == "write":
            raw = item.call.tool_input.get("content")
            if not isinstance(raw, str):
                metrics["ambiguous_transitions"] += 1
                continue
            content = native.canonicalize_write_content(raw)
        else:
            previous = _latest_eligible(
                observations,
                item,
                parents_by_session,
                serial_session_pairs,
            )
            old = item.call.tool_input.get("old_string")
            new = item.call.tool_input.get("new_string")
            replace_all = bool(item.call.tool_input.get("replace_all", False))
            if (
                previous is None
                or not isinstance(old, str)
                or not isinstance(new, str)
            ):
                metrics["ambiguous_transitions"] += 1
                continue
            occurrences = previous.canonical_content.count(old)
            if occurrences == 0 or (not replace_all and occurrences != 1):
                metrics["ambiguous_transitions"] += 1
                continue
            content = (
                previous.canonical_content.replace(old, new)
                if replace_all
                else previous.canonical_content.replace(old, new, 1)
            )

        previous = _latest_eligible(
            observations,
            item,
            parents_by_session,
            serial_session_pairs,
        )
        changed_after_gap = (
            item.tool_kind == "read"
            and previous is not None
            and sha256_bytes(content.encode("utf-8"))
            != previous.content_sha256
        )
        if changed_after_gap:
            metrics["interval_censored_changes"] += 1
        observation = StateObservation(
            event_key=item.event_key,
            artifact_key=item.artifact_key,
            artifact_name_key=item.artifact_name_key,
            project_key=item.project_key,
            session_key=item.session_key,
            session_id=item.call.session_id,
            call_record_uuid=item.call.record_uuid,
            result_record_uuid=item.result.record_uuid,
            call_order=item.call_order,
            result_order=item.result_order,
            observed_at=item.result.observed_at,
            source_kind=item.tool_kind,
            content_sha256=sha256_bytes(content.encode("utf-8")),
            content_bytes=len(content.encode("utf-8")),
            canonical_content=content,
            interval_censored_change=changed_after_gap,
        )
        observations.append(observation)
        metrics["supported_observations"] += 1
    return observations, metrics


def _same_context(
    observation: StateObservation,
    target: StateObservation,
) -> bool:
    return (
        observation.artifact_key == target.artifact_key
        and observation.project_key == target.project_key
    )


def _online_candidates(
    observations: Sequence[StateObservation],
    target: StateObservation,
    target_interaction: QualifiedInteraction,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
    *,
    contextual: bool,
) -> list[StateObservation]:
    def eligible(item: StateObservation) -> bool:
        if contextual:
            return _branch_eligible(
                item,
                target_interaction,
                parents_by_session,
                serial_session_pairs,
            )
        if item.session_id != target_interaction.call.session_id:
            return item.result_order < target_interaction.call_order
        return _branch_eligible(
            item,
            target_interaction,
            parents_by_session,
            serial_session_pairs,
        )

    return sorted(
        (
            item
            for item in observations
            if (
                _same_context(item, target)
                if contextual
                else item.artifact_name_key == target.artifact_name_key
            )
            and eligible(item)
        ),
        key=lambda item: item.result_order,
        reverse=True,
    )


def _retrospective_candidate(
    observations: Sequence[StateObservation],
    target: StateObservation,
    *,
    latest_only: bool,
) -> Optional[StateObservation]:
    same = [
        item
        for item in observations
        if (
            item.artifact_name_key == target.artifact_name_key
            if latest_only
            else _same_context(item, target)
        )
    ]
    if not same:
        return None
    if latest_only:
        return max(same, key=lambda item: item.result_order)
    eligible = [
        item for item in same if item.result_order <= target.result_order
    ]
    return max(eligible, key=lambda item: item.result_order) if eligible else None


def _reduced_online_outcome(
    target: StateObservation,
    candidates: Sequence[StateObservation],
) -> str:
    """Select from pre-cutoff evidence, then score against the later result.

    The target content and its post-result interval-censoring label may score a
    selected state as exact or stale, but must never cause an online
    abstention. This corpus has no pre-cutoff open-gap marker.
    """

    if not candidates:
        return "abstention"
    top_boundary = candidates[0].observed_at
    boundary_values = {
        item.content_sha256
        for item in candidates
        if item.observed_at == top_boundary
    }
    if len(boundary_values) > 1:
        return "abstention"
    return (
        "exact"
        if candidates[0].content_sha256 == target.content_sha256
        else "stale"
    )


def _future_continuation(
    target: StateObservation,
    candidate: StateObservation,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
) -> bool:
    if candidate.result_order <= target.result_order:
        return False
    if candidate.session_id != target.session_id:
        return (
            target.session_id,
            candidate.session_id,
        ) in serial_session_pairs
    parents = parents_by_session.get(target.session_id, {})
    return _is_ancestor(
        parents,
        target.result_record_uuid,
        candidate.call_record_uuid,
    ) or _is_ancestor(
        parents,
        target.call_record_uuid,
        candidate.call_record_uuid,
    )


def _dream_metrics(
    observations: Sequence[StateObservation],
    authority: native.AuthorityEnvelope,
) -> dict[str, Any]:
    ledger = temporal.MemoryLedger()
    envelope = temporal.Envelope(
        tenant_id=authority.tenant_id,
        owner_subject_id=authority.owner_subject_id,
        audience="private",
        team_id=None,
        classification=authority.classification,
        purposes=(authority.purpose,),
        authorization_epoch=authority.authorization_epoch,
        policy_revision="trace-commons-import-v1",
    )
    proposed_revisions: set[tuple[str, str, str]] = set()
    for item in observations:
        evidence = temporal.Evidence(
            evidence_id=item.event_key,
            fact_key=item.artifact_key,
            context=(("project", item.project_key),),
            value=item.content_sha256,
            valid_from=item.observed_at,
            observed_at=item.observed_at,
            envelope=envelope,
        )
        ledger.add_evidence(evidence)
        revision_key = (
            item.artifact_key,
            item.project_key,
            item.content_sha256,
        )
        if revision_key in proposed_revisions:
            continue
        proposed_revisions.add(revision_key)
        ledger.propose(
            fact_key=item.artifact_key,
            context={"project": item.project_key},
            value=item.content_sha256,
            valid_from=item.observed_at,
            evidence_ids=(item.event_key,),
            derivation_revision=ANALYSIS_VERSION,
        )
    return {
        "proposed_changes": len(ledger.candidates),
        "evidence_linked_proposals": len(ledger.candidates),
        "automatically_active_changes": 0,
        "rejected_or_quarantined_proposals": 0,
        "review_burden_proxy": len(ledger.candidates),
        "active_release_count": len(ledger.releases),
        "failed_job_atomicity_control": {
            "status": "not_run",
            "exposed_proposals": None,
            "quarantined_proposals": None,
        },
    }


def _mechanism_metrics(
    interactions: Sequence[QualifiedInteraction],
    observations: Sequence[StateObservation],
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
    authority: native.AuthorityEnvelope,
) -> tuple[dict[str, Any], dict[str, int]]:
    interactions_by_event = {item.event_key: item for item in interactions}
    read_targets: list[
        tuple[
            StateObservation,
            QualifiedInteraction,
            list[StateObservation],
            list[StateObservation],
        ]
    ] = []
    for target in observations:
        if target.source_kind != "read":
            continue
        interaction = interactions_by_event[target.event_key]
        contextual_candidates = _online_candidates(
            observations,
            target,
            interaction,
            parents_by_session,
            serial_session_pairs,
            contextual=True,
        )
        if contextual_candidates:
            latest_candidates = _online_candidates(
                observations,
                target,
                interaction,
                parents_by_session,
                serial_session_pairs,
                contextual=False,
            )
            read_targets.append(
                (
                    target,
                    interaction,
                    contextual_candidates,
                    latest_candidates,
                )
            )

    online_denominator = len(read_targets)
    contextual_outcomes = [
        _reduced_online_outcome(target, candidates)
        for target, _, candidates, _ in read_targets
    ]
    latest_outcomes = [
        _reduced_online_outcome(target, candidates)
        for target, _, _, candidates in read_targets
    ]
    contextual_online_exact = contextual_outcomes.count("exact")
    contextual_online_stale = contextual_outcomes.count("stale")
    contextual_online_abstentions = contextual_outcomes.count("abstention")
    latest_online_exact = latest_outcomes.count("exact")
    latest_online_stale = latest_outcomes.count("stale")
    latest_online_abstentions = latest_outcomes.count("abstention")
    latest_cross_project_returns = sum(
        bool(candidates)
        and outcome != "abstention"
        and candidates[0].project_key != target.project_key
        for (target, _, _, candidates), outcome in zip(
            read_targets, latest_outcomes
        )
    )
    exact_cross_session_write_to_read = sum(
        candidates[0].source_kind in {"write", "edit"}
        and outcome == "exact"
        and candidates[0].session_id != target.session_id
        for (target, _, candidates, _), outcome in zip(
            read_targets, contextual_outcomes
        )
    )

    post_observation_denominator = len(read_targets)
    latest_post_observation_exact = 0
    history_post_observation_exact = 0
    changed_retrospective = 0
    for target, _, _, _ in read_targets:
        latest = _retrospective_candidate(
            observations, target, latest_only=True
        )
        historical = _retrospective_candidate(
            observations, target, latest_only=False
        )
        latest_post_observation_exact += (
            latest is not None
            and latest.content_sha256 == target.content_sha256
        )
        history_post_observation_exact += (
            historical is not None
            and historical.content_sha256 == target.content_sha256
        )
        later = [
            item
            for item in observations
            if _same_context(item, target)
            and _future_continuation(
                target,
                item,
                parents_by_session,
                serial_session_pairs,
            )
            and item.content_sha256 != target.content_sha256
        ]
        changed_retrospective += bool(later)

    unique_revision_keys = {
        (item.artifact_key, item.project_key, item.content_sha256)
        for item in observations
    }
    latest_by_name: dict[str, StateObservation] = {}
    for item in observations:
        current = latest_by_name.get(item.artifact_name_key)
        if current is None or item.result_order > current.result_order:
            latest_by_name[item.artifact_name_key] = item
    latest_retained_revision_keys = {
        (item.artifact_key, item.project_key, item.content_sha256)
        for item in latest_by_name.values()
    }
    supported_observations = len(observations)
    supported_unique_revisions = len(unique_revision_keys)
    latest_retained = len(latest_retained_revision_keys)
    latest_overwritten = len(
        unique_revision_keys - latest_retained_revision_keys
    )
    contextual_online = {
        "online_exact": rate(
            contextual_online_exact, online_denominator
        ),
        "online_stale_returns": rate(
            contextual_online_stale, online_denominator
        ),
        "online_abstentions": rate(
            contextual_online_abstentions, online_denominator
        ),
    }
    dream = _dream_metrics(observations, authority)
    mechanisms = {
        "verbatim": {
            **contextual_online,
            "post_observation_retention_exact": rate(
                history_post_observation_exact,
                post_observation_denominator,
            ),
            "retained_revisions": supported_unique_revisions,
            "source_observations": supported_observations,
            "overwritten_revisions": 0,
        },
        "latest_only": {
            "online_exact": rate(
                latest_online_exact, online_denominator
            ),
            "online_stale_returns": rate(
                latest_online_stale, online_denominator
            ),
            "online_abstentions": rate(
                latest_online_abstentions, online_denominator
            ),
            "online_cross_project_returns": rate(
                latest_cross_project_returns, online_denominator
            ),
            "post_observation_retention_exact": rate(
                latest_post_observation_exact,
                post_observation_denominator,
            ),
            "retained_revisions": latest_retained,
            "source_observations": supported_observations,
            "overwritten_revisions": latest_overwritten,
        },
        "contextual_bitemporal": {
            **contextual_online,
            "post_observation_retention_exact": rate(
                history_post_observation_exact,
                post_observation_denominator,
            ),
            "retained_revisions": supported_unique_revisions,
            "source_observations": supported_observations,
            "overwritten_revisions": 0,
            "interval_uncertainties": sum(
                item.interval_censored_change for item in observations
            ),
        },
        "proposal_only_dream": dream,
    }
    evaluation = {
        "online_queries": online_denominator,
        "post_observation_retention_queries": post_observation_denominator,
        "changed_artifact_post_observation_cases": changed_retrospective,
        "exact_cross_session_write_to_later_read": (
            exact_cross_session_write_to_read
        ),
        "latest_only_cross_project_returns": (
            latest_cross_project_returns
        ),
    }
    return mechanisms, evaluation


def _branch_points(records: Sequence[Mapping[str, Any]]) -> int:
    child_counts: Counter[tuple[str, str]] = Counter()
    for record in records:
        parent = record.get("parentUuid")
        if parent is not None:
            child_counts[
                (str(record.get("sessionId", "")), str(parent))
            ] += 1
    return sum(count > 1 for count in child_counts.values())


def _negative_control_metrics(
    interactions: Sequence[QualifiedInteraction],
    observations: Sequence[StateObservation],
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    serial_session_pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    projects_by_name: dict[str, set[str]] = defaultdict(set)
    for item in observations:
        projects_by_name[item.artifact_name_key].add(item.project_key)
    collisions = sum(
        len(projects) - 1
        for projects in projects_by_name.values()
        if len(projects) > 1
    )
    interaction_by_event = {item.event_key: item for item in interactions}
    placebo_cases = 0
    contextual_placebo_leaks = 0
    latest_placebo_leaks = 0
    future_positive_cases = 0
    future_positive_detected = 0
    contextual_future_filter_leaks = 0
    latest_future_filter_leaks = 0
    for target in observations:
        if target.source_kind != "read":
            continue
        interaction = interaction_by_event[target.event_key]
        foreign_same_name = [
            item
            for item in observations
            if item.artifact_name_key == target.artifact_name_key
            and item.project_key != target.project_key
        ]
        if foreign_same_name:
            placebo_cases += 1
            contextual_selected = _online_candidates(
                observations,
                target,
                interaction,
                parents_by_session,
                serial_session_pairs,
                contextual=True,
            )
            latest_selected = _online_candidates(
                observations,
                target,
                interaction,
                parents_by_session,
                serial_session_pairs,
                contextual=False,
            )
            contextual_placebo_leaks += any(
                item.project_key != target.project_key
                for item in contextual_selected
            )
            latest_placebo_leaks += any(
                item.project_key != target.project_key
                for item in latest_selected
            )

        future_positive_cases += 1
        if not _branch_eligible(
            target,
            interaction,
            parents_by_session,
            serial_session_pairs,
        ):
            future_positive_detected += 1
        contextual_selected = _online_candidates(
            observations,
            target,
            interaction,
            parents_by_session,
            serial_session_pairs,
            contextual=True,
        )
        latest_selected = _online_candidates(
            observations,
            target,
            interaction,
            parents_by_session,
            serial_session_pairs,
            contextual=False,
        )
        contextual_future_filter_leaks += any(
            item.result_order >= interaction.call_order
            for item in contextual_selected
        )
        latest_future_filter_leaks += any(
            item.result_order >= interaction.call_order
            for item in latest_selected
        )

    def zero_leak_status(cases: int, leaks: int) -> str:
        if cases == 0:
            return "not_run"
        return "passed" if leaks == 0 else "failed"

    def combined_status(statuses: Sequence[str]) -> str:
        if "failed" in statuses:
            return "failed"
        if "not_run" in statuses:
            return "not_run"
        return "passed"

    contextual_placebo_status = zero_leak_status(
        placebo_cases, contextual_placebo_leaks
    )
    latest_placebo_status = zero_leak_status(
        placebo_cases, latest_placebo_leaks
    )
    contextual_future_status = zero_leak_status(
        future_positive_cases, contextual_future_filter_leaks
    )
    latest_future_status = zero_leak_status(
        future_positive_cases, latest_future_filter_leaks
    )
    positive_status = (
        "not_run"
        if future_positive_cases == 0
        else (
            "passed"
            if future_positive_detected == future_positive_cases
            else "failed"
        )
    )
    return {
        "same_name_cross_project_collisions": collisions,
        "same_basename_different_project_placebo": {
            "cases": placebo_cases,
            "contextual_bitemporal": {
                "leaks": contextual_placebo_leaks,
                "status": contextual_placebo_status,
            },
            "latest_only": {
                "leaks": latest_placebo_leaks,
                "status": latest_placebo_status,
            },
            "status": combined_status(
                [contextual_placebo_status, latest_placebo_status]
            ),
        },
        "future_contaminated_positive_control": {
            "cases": future_positive_cases,
            "detected": future_positive_detected,
            "status": positive_status,
        },
        "future_filter": {
            "cases": future_positive_cases,
            "contextual_bitemporal": {
                "leaks": contextual_future_filter_leaks,
                "status": contextual_future_status,
            },
            "latest_only": {
                "leaks": latest_future_filter_leaks,
                "status": latest_future_status,
            },
            "status": combined_status(
                [contextual_future_status, latest_future_status]
            ),
        },
    }


def _decision_status(
    evaluation: Mapping[str, int],
    mechanisms: Mapping[str, Mapping[str, Any]],
    negative_controls: Mapping[str, Any],
    *,
    deterministic_contract_enforced: bool,
) -> dict[str, Any]:
    underpowered = []
    if int(evaluation["online_queries"]) < 10:
        underpowered.append("fewer_than_10_reconstructable_read_cutoffs")
    if int(evaluation["changed_artifact_post_observation_cases"]) < 5:
        underpowered.append(
            "fewer_than_5_changed_post_observation_cases"
        )
    if int(evaluation["exact_cross_session_write_to_later_read"]) < 2:
        underpowered.append("fewer_than_2_exact_cross_session_transitions")
    latest = mechanisms["latest_only"]
    temporal_arm = mechanisms["contextual_bitemporal"]
    retention_passed = (
        int(evaluation["changed_artifact_post_observation_cases"]) > 0
        and int(latest["overwritten_revisions"]) > 0
        and int(temporal_arm["overwritten_revisions"]) == 0
        and int(
            temporal_arm["post_observation_retention_exact"]["numerator"]
        )
        > int(latest["post_observation_retention_exact"]["numerator"])
    )
    placebo = negative_controls[
        "same_basename_different_project_placebo"
    ]
    future_positive = negative_controls[
        "future_contaminated_positive_control"
    ]
    future_filter = negative_controls["future_filter"]
    all_controls_passed = all(
        item["status"] == "passed"
        for item in (placebo, future_positive, future_filter)
    )
    return {
        "source_fidelity_h1": "passed",
        "evidence_retention_h2": (
            "passed_mechanics_only" if retention_passed else "not_demonstrated"
        ),
        "temporal_answerability_h3": (
            "underpowered" if underpowered else "eligible_for_comparison"
        ),
        "proposal_isolation_h4": (
            "partial_active_isolation_only_failed_job_control_not_run"
        ),
        "governed_postgresql_h5": "not_run",
        "comparative_quality_claim_allowed": False,
        "deterministic_contract_enforced": (
            deterministic_contract_enforced
        ),
        "negative_controls_all_passed": all_controls_passed,
        "latest_only_context_isolation": placebo["latest_only"]["status"],
        "contextual_bitemporal_context_isolation": (
            placebo["contextual_bitemporal"]["status"]
        ),
        "analysis_scope": "deterministic_mechanics_preflight",
        "underpowered_reasons": underpowered,
        "model_quality_phase": "not_run",
        "human_review_phase": "not_run",
    }


def analyze_manifest(
    manifest_path: Union[Path, str],
    source_root: Union[Path, str],
    experiment_config_path: Optional[Union[Path, str]] = None,
) -> dict[str, Any]:
    experiment_config_sha256: Optional[str] = None
    if experiment_config_path is not None:
        _, experiment_config_sha256 = _load_experiment_config(
            experiment_config_path,
            manifest_path,
        )
    cohort = native.load_verified_memory_cohort(
        manifest_path,
        source_root,
        default_authority=FIXED_IMPORT_AUTHORITY,
    )
    manifest_receipt = _manifest_receipt(cohort.manifest)
    verified_receipt = _receipt_root(cohort.receipts)
    identity_key = hashlib.sha256(
        (verified_receipt + ":" + ANALYSIS_VERSION).encode("utf-8")
    ).digest()
    source_receipt_order = {
        str(receipt["path"]): index
        for index, receipt in enumerate(cohort.receipts)
    }
    interactions, interaction_metrics = _qualifying_interactions(
        cohort, identity_key, source_receipt_order
    )
    project_inventory = _project_inventory(cohort.records)
    histories = len(
        {
            str(record.get("sessionId"))
            for record in cohort.records
            if record.get("sessionId")
        }
    )
    inventory_actual = {
        "source_files": len(cohort.receipts),
        "histories": histories,
        "records": len(cohort.records),
        "bytes": sum(int(item["bytes"]) for item in cohort.receipts),
        "native_tool_calls": len(cohort.calls),
        "native_tool_results": len(cohort.results),
        "apparent_projects": project_inventory["apparent_projects"],
        "multi_session_project_groups": (
            project_inventory["multi_session_project_groups"]
        ),
        "histories_with_context_artifact_interactions": len(
            {item.session_key for item in interactions}
        ),
        "context_artifact_tool_interactions": interaction_metrics[
            "qualifying_candidate_calls"
        ],
        "matching_tool_results": interaction_metrics[
            "qualifying_interactions"
        ],
        "explicit_reads": interaction_metrics["explicit_reads"],
        "writes_or_edits": interaction_metrics["writes_or_edits"],
        "bash_search_or_other": interaction_metrics[
            "shell_search_or_other"
        ],
    }
    _validate_expected_inventory(cohort.manifest, inventory_actual)

    parents = _parent_maps(cohort.records)
    serial_pairs = _serial_session_pairs(cohort.records)
    observations, transition_metrics = _state_observations(
        interactions,
        parents,
        serial_pairs,
    )
    transition_metrics["unique_supported_revisions"] = len(
        {
            (item.artifact_key, item.project_key, item.content_sha256)
            for item in observations
        }
    )
    mechanisms, evaluation = _mechanism_metrics(
        interactions,
        observations,
        parents,
        serial_pairs,
        cohort.authority,
    )
    matched_calls = sum(
        _join_result(call, cohort.results) is not None
        for call in cohort.calls
    )
    artifacts = {item.artifact_key for item in observations}
    state_projects = {item.project_key for item in observations}
    negative_controls = _negative_control_metrics(
        interactions,
        observations,
        parents,
        serial_pairs,
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": ANALYSIS_VERSION,
        "dataset": {
            "id": str(cohort.manifest["dataset_id"]),
            "revision": str(cohort.manifest["dataset_revision"]),
            "license": str(cohort.manifest["license"]),
        },
        "input_receipt": {
            "source_files_verified": len(cohort.receipts),
            "source_bytes_verified": sum(
                int(item["bytes"]) for item in cohort.receipts
            ),
            "source_records_verified": len(cohort.records),
            "manifest_cohort_receipt_sha256": manifest_receipt,
            "verified_source_set_sha256": verified_receipt,
            "experiment_config_sha256": experiment_config_sha256,
        },
        "discovery": {
            "histories": histories,
            "histories_with_qualifying_interactions": (
                inventory_actual[
                    "histories_with_context_artifact_interactions"
                ]
            ),
            "records": len(cohort.records),
            "native_calls": len(cohort.calls),
            "native_results": len(cohort.results),
            "joined_native_results": matched_calls,
            "unmatched_native_calls": len(cohort.calls) - matched_calls,
            "branch_points": _branch_points(cohort.records),
            "snapshot_memory_mentions": int(
                cohort.snapshot_audit["memory_path_mentions"]
            ),
            **interaction_metrics,
            "artifacts": len(artifacts),
            "state_projects": len(state_projects),
            "verified_serial_session_pairs": len(serial_pairs),
            **project_inventory,
        },
        "transitions": transition_metrics,
        "evaluation": evaluation,
        "mechanisms": mechanisms,
        "decision_status": _decision_status(
            evaluation,
            mechanisms,
            negative_controls,
            deterministic_contract_enforced=(
                experiment_config_sha256 is not None
            ),
        ),
        "negative_controls": negative_controls,
        "content_policy": {
            "raw_content_emitted": False,
            "artifact_paths_emitted": False,
            "session_identifiers_emitted": False,
            "tool_identifiers_emitted": False,
            "per_artifact_content_hashes_emitted": False,
        },
        "claim_boundary": (
            "This deterministic natural-trace study measures evidence "
            "retention, temporal reconstruction, inactive proposal "
            "representation, and content-minimized composition. It does not "
            "establish failed-job atomicity, memory correctness, usefulness, "
            "human identity, skill, or enterprise transfer."
        ),
    }
    result["result_sha256"] = sha256_value(result)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    discovery = result["discovery"]
    evaluation = result["evaluation"]
    mechanisms = result["mechanisms"]
    controls = result["negative_controls"]
    decision = result["decision_status"]
    placebo = controls["same_basename_different_project_placebo"]
    return "\n".join(
        [
            "# Trace Commons memory composition",
            "",
            "## Aggregate result",
            "",
            f"- Verified histories/records: "
            f"{discovery['histories']} / {discovery['records']}",
            f"- Qualifying interactions: "
            f"{discovery['qualifying_interactions']}",
            f"- Online/post-observation retention queries: "
            f"{evaluation['online_queries']} / "
            f"{evaluation['post_observation_retention_queries']}",
            f"- Exact cross-session write-to-later-read transitions: "
            f"{evaluation['exact_cross_session_write_to_later_read']}",
            f"- Supported observations / unique revisions: "
            f"{result['transitions']['supported_observations']} / "
            f"{result['transitions']['unique_supported_revisions']}",
            f"- Contextual online exact / stale / abstentions: "
            f"{mechanisms['contextual_bitemporal']['online_exact']['numerator']} / "
            f"{mechanisms['contextual_bitemporal']['online_stale_returns']['numerator']} / "
            f"{mechanisms['contextual_bitemporal']['online_abstentions']['numerator']}",
            f"- Latest-only same-basename placebo leaks: "
            f"{placebo['latest_only']['leaks']} / {placebo['cases']}",
            f"- Contextual same-basename placebo leaks: "
            f"{placebo['contextual_bitemporal']['leaks']} / "
            f"{placebo['cases']}",
            f"- Automatically active dream changes: "
            f"{mechanisms['proposal_only_dream']['automatically_active_changes']}",
            f"- Failed-job atomicity control: "
            f"{mechanisms['proposal_only_dream']['failed_job_atomicity_control']['status']}",
            f"- All negative controls passed: "
            f"{str(decision['negative_controls_all_passed']).lower()}",
            f"- Comparative quality claim allowed: "
            f"{str(decision['comparative_quality_claim_allowed']).lower()}",
            f"- Underpowered gates: "
            f"{', '.join(decision['underpowered_reasons'])}",
            "",
            f"Claim boundary: {result['claim_boundary']}",
            "",
            f"Result SHA-256: `{result['result_sha256']}`",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze_manifest(
        args.manifest,
        args.source_root,
        args.experiment_config,
    )
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    summary = render_markdown(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    args.summary.write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
