#!/usr/bin/env python3
"""Build blinded human-adjudication packets for Wisp recovery candidates.

Raw packet content is credential-clean but otherwise full fidelity: authorized
internal PII, source code, paths, and classified material are not redacted.
Only a content-free run manifest is suitable for Git.
"""

from __future__ import annotations

import argparse
import collections
import copy
import enum
import hashlib
import hmac
import json
import os
import pathlib
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple

from canonical_recovery_episodes import (
    DEFAULT_MAX_LIFECYCLE_DISTANCE,
    EVENT_ERROR,
    EVENT_PROPOSED,
    EVENT_SUCCESS,
    LifecycleEvent,
    construct_recovery_episodes,
    tool_family,
)
from credential_only_gate import (
    RULE_SET_SHA256,
    transform_credentials,
    verify_credential_free,
)


SCHEMA_VERSION = "frankengate.wisp-recovery-adjudication-packet.v1"
MANIFEST_SCHEMA_VERSION = (
    "frankengate.wisp-recovery-adjudication-manifest.v1"
)
DEFAULT_SEED = "wisp-recovery-adjudication-20260730"
DEFAULT_CONTEXT_EVENTS_EACH_SIDE = 4
DEFAULT_MAX_CONTEXT_EVENTS = 64
DEFAULT_MAX_CONTEXT_BYTES = 196_608


class PacketError(ValueError):
    """The packet would violate its blinding or evidence contract."""


class RelationLabel(str, enum.Enum):
    SAME_TASK_RETRY = "same_task_retry"
    SAME_GOAL_CHANGED_METHOD = "same_goal_changed_method"
    RELATED_SUBTASK = "related_subtask"
    UNRELATED = "unrelated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class OutcomeLabel(str, enum.Enum):
    RECOVERED_VERIFIED = "recovered_verified"
    LATER_TOOL_SUCCEEDED_TASK_UNVERIFIED = (
        "later_tool_succeeded_task_unverified"
    )
    NOT_RECOVERED = "not_recovered"
    REGRESSED = "regressed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CauseLabel(str, enum.Enum):
    TOOL_OR_ENVIRONMENT = "tool_or_environment"
    PERMISSION_OR_POLICY = "permission_or_policy"
    INVALID_ARGUMENT_OR_COMMAND = "invalid_argument_or_command"
    DEPENDENCY_OR_CONFIGURATION = "dependency_or_configuration"
    MODEL_OR_HARNESS = "model_or_harness"
    AMBIGUOUS_REQUIREMENT = "ambiguous_requirement"
    UNKNOWN = "unknown"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceStrengthLabel(str, enum.Enum):
    DIRECT_EXECUTABLE = "direct_executable"
    DIRECT_TRACE = "direct_trace"
    CORROBORATED = "corroborated"
    CIRCUMSTANTIAL = "circumstantial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ProductiveExplorationLabel(str, enum.Enum):
    PRODUCTIVE = "productive"
    MIXED = "mixed"
    UNPRODUCTIVE = "unproductive"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class UsefulnessLabel(str, enum.Enum):
    EVAL_CANDIDATE = "eval_candidate"
    SUPPORT_CANDIDATE = "support_candidate"
    WORKFLOW_PATTERN_CANDIDATE = "workflow_pattern_candidate"
    MEMORY_CANDIDATE = "memory_candidate"
    NOT_USEFUL = "not_useful"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


LABEL_ENUMS = {
    "relation": RelationLabel,
    "outcome": OutcomeLabel,
    "cause": CauseLabel,
    "evidence_strength": EvidenceStrengthLabel,
    "productive_exploration": ProductiveExplorationLabel,
    "usefulness": UsefulnessLabel,
}


def label_contract() -> Dict[str, Tuple[str, ...]]:
    """Return the exact controlled vocabulary accepted from reviewers."""

    return {
        name: tuple(item.value for item in label_enum)
        for name, label_enum in LABEL_ENUMS.items()
    }


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_file_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _hmac_ref(key: bytes, domain: str, value: str, prefix: str) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise PacketError("blinding key must be at least 32 bytes")
    digest = hmac.new(
        key,
        (domain + "\0" + value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return prefix + digest[:24]


def _extract_session(
    records: Sequence[Mapping[str, Any]],
) -> Tuple[list, Tuple[LifecycleEvent, ...], Dict[int, int]]:
    """Return packet events and their exact lifecycle projection."""

    source_events = []
    lifecycle = []
    lifecycle_to_source = {}
    for record_index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            continue
        record = dict(raw_record)
        source_loss = record.get("_packet_source_loss")
        if isinstance(source_loss, Mapping):
            payload = {"source_loss": copy.deepcopy(dict(source_loss))}
            if "_packet_source_value" in record:
                payload["source_value"] = copy.deepcopy(
                    record["_packet_source_value"]
                )
            source_events.append(
                {
                    "record_index": record_index,
                    "block_index": None,
                    "kind": "source.loss_receipt",
                    "role": "system",
                    "call_key": None,
                    "lifecycle_order": None,
                    "payload": payload,
                }
            )
            continue
        message = record.get("message")
        if not isinstance(message, Mapping):
            content = record.get("content")
            if isinstance(content, str):
                source_events.append(
                    {
                        "record_index": record_index,
                        "block_index": None,
                        "kind": "system_text",
                        "role": str(record.get("type") or "system"),
                        "call_key": None,
                        "lifecycle_order": None,
                        "payload": {"content": content},
                    }
                )
            continue
        role = str(message.get("role") or record.get("type") or "unknown")
        content = message.get("content")
        if isinstance(content, str):
            source_events.append(
                {
                    "record_index": record_index,
                    "block_index": None,
                    "kind": "message_text",
                    "role": role,
                    "call_key": None,
                    "lifecycle_order": None,
                    "payload": {"content": content},
                }
            )
            continue
        if not isinstance(content, list):
            continue
        for block_index, raw_block in enumerate(content):
            if not isinstance(raw_block, Mapping):
                source_events.append(
                    {
                        "record_index": record_index,
                        "block_index": block_index,
                        "kind": "unknown_block",
                        "role": role,
                        "call_key": None,
                        "lifecycle_order": None,
                        "payload": {"block": copy.deepcopy(raw_block)},
                    }
                )
                continue
            block = copy.deepcopy(dict(raw_block))
            block_type = block.get("type")
            call_key = None
            lifecycle_order = None
            kind = str(block_type or "unknown_block")
            if block_type == "tool_use":
                call_key = block.get("id")
                call_key = call_key if isinstance(call_key, str) else None
                lifecycle_order = len(lifecycle)
                lifecycle.append(
                    LifecycleEvent(
                        order=lifecycle_order,
                        kind=EVENT_PROPOSED,
                        call_key=call_key,
                        tool_family=tool_family(block.get("name")),
                    )
                )
                kind = "tool.proposed"
            elif block_type == "tool_result":
                call_key = block.get("tool_use_id")
                call_key = call_key if isinstance(call_key, str) else None
                is_error = (
                    block.get("is_error") is True
                    or block.get("isError") is True
                )
                lifecycle_order = len(lifecycle)
                lifecycle.append(
                    LifecycleEvent(
                        order=lifecycle_order,
                        kind=EVENT_ERROR if is_error else EVENT_SUCCESS,
                        call_key=call_key,
                        tool_family=None,
                    )
                )
                kind = "tool.result.error" if is_error else "tool.result.success"
            source_index = len(source_events)
            source_events.append(
                {
                    "record_index": record_index,
                    "block_index": block_index,
                    "kind": kind,
                    "role": role,
                    "call_key": call_key,
                    "lifecycle_order": lifecycle_order,
                    "payload": {"block": block},
                }
            )
            if lifecycle_order is not None:
                lifecycle_to_source[lifecycle_order] = source_index
    return source_events, tuple(lifecycle), lifecycle_to_source


def _candidate_context(
    *,
    source_locator: str,
    source_events: Sequence[Mapping[str, Any]],
    lifecycle: Sequence[LifecycleEvent],
    lifecycle_to_source: Mapping[int, int],
    episode: Any,
    episode_index: int,
    blind_key: bytes,
    context_events_each_side: int,
    max_context_events: int,
    max_context_bytes: int,
) -> Tuple[Optional[dict], Optional[str]]:
    error_event = lifecycle[episode.error_order]
    if error_event.call_key is None:
        return None, "incomplete_tool_context"
    failed_proposals = [
        event.order
        for event in lifecycle
        if event.kind == EVENT_PROPOSED
        and event.call_key == error_event.call_key
        and event.order < episode.error_order
    ]
    if len(failed_proposals) != 1:
        return None, "incomplete_tool_context"
    failed_proposal_order = failed_proposals[0]
    anchor_roles = {
        failed_proposal_order: "failed_proposal",
        episode.error_order: "failed_result",
        episode.recovery_proposal_order: "recovery_proposal",
        episode.recovery_result_order: "recovery_result",
    }
    anchor_source_indices = [
        lifecycle_to_source[order] for order in anchor_roles
    ]
    start = max(0, min(anchor_source_indices) - context_events_each_side)
    end = min(
        len(source_events) - 1,
        max(anchor_source_indices) + context_events_each_side,
    )

    call_positions: Dict[str, list] = collections.defaultdict(list)
    call_kinds: Dict[str, list] = collections.defaultdict(list)
    for index, event in enumerate(source_events):
        call_key = event.get("call_key")
        if isinstance(call_key, str) and call_key:
            call_positions[call_key].append(index)
            call_kinds[call_key].append(str(event["kind"]))

    while True:
        selected_calls = {
            str(source_events[index]["call_key"])
            for index in range(start, end + 1)
            if source_events[index].get("call_key")
        }
        for call_key in selected_calls:
            kinds = call_kinds[call_key]
            proposals = sum(kind == "tool.proposed" for kind in kinds)
            outcomes = sum(
                kind in {"tool.result.error", "tool.result.success"}
                for kind in kinds
            )
            if proposals != 1 or outcomes != 1:
                return None, "incomplete_tool_context"
        closed_positions = [
            position
            for call_key in selected_calls
            for position in call_positions[call_key]
        ]
        new_start = min([start] + closed_positions)
        new_end = max([end] + closed_positions)
        if new_start == start and new_end == end:
            break
        start, end = new_start, new_end

    if end - start + 1 > max_context_events:
        return None, "context_event_bound"
    natural_identity = (
        source_locator
        + "\0"
        + str(episode.error_order)
        + "\0"
        + str(episode.recovery_result_order)
        + "\0"
        + str(episode_index)
    )
    blind_id = _hmac_ref(
        blind_key,
        "wisp-recovery-candidate",
        natural_identity,
        "C-",
    )
    context = []
    for source_index in range(start, end + 1):
        source_event = source_events[source_index]
        call_key = source_event.get("call_key")
        call_ref = (
            _hmac_ref(
                blind_key,
                "wisp-recovery-call",
                natural_identity + "\0" + str(call_key),
                "T-",
            )
            if call_key
            else None
        )
        payload = copy.deepcopy(source_event["payload"])
        block = payload.get("block")
        if isinstance(block, dict):
            block.pop("id", None)
            block.pop("tool_use_id", None)
            if call_ref is not None:
                block["tool_call_ref"] = call_ref
        lifecycle_order = source_event.get("lifecycle_order")
        context.append(
            {
                "evidence_ref": _hmac_ref(
                    blind_key,
                    "wisp-recovery-evidence",
                    natural_identity + "\0" + str(source_index),
                    "E-",
                ),
                "kind": source_event["kind"],
                "role": source_event["role"],
                "candidate_role": anchor_roles.get(lifecycle_order),
                "payload": payload,
            }
        )
    context_bytes = len(_stable_json(context).encode("utf-8"))
    if context_bytes > max_context_bytes:
        return None, "context_byte_bound"
    candidate = {
        "blind_id": blind_id,
        "controlled_tool_family": episode.tool_family,
        "context": context,
        "context_event_count": len(context),
        "context_byte_length_before_credential_transform": context_bytes,
        "adjudication_template": {
            dimension: {"label": None, "evidence_refs": []}
            for dimension in LABEL_ENUMS
        },
    }
    assert_tool_complete_candidate(candidate)
    return candidate, None


def assert_tool_complete_candidate(candidate: Mapping[str, Any]) -> None:
    """Require one proposal and one terminal result for every shown call."""

    calls: Dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for event in candidate.get("context", []):
        if not isinstance(event, Mapping):
            raise PacketError("candidate context event is invalid")
        payload = event.get("payload")
        block = payload.get("block") if isinstance(payload, Mapping) else None
        call_ref = (
            block.get("tool_call_ref")
            if isinstance(block, Mapping)
            else None
        )
        if call_ref is None:
            continue
        calls[str(call_ref)][str(event.get("kind"))] += 1
    if not calls:
        raise PacketError("candidate contains no tool evidence")
    for call_ref, kinds in calls.items():
        proposal_count = kinds["tool.proposed"]
        outcome_count = (
            kinds["tool.result.error"] + kinds["tool.result.success"]
        )
        if proposal_count != 1 or outcome_count != 1:
            raise PacketError(
                f"{call_ref}: context is not tool-complete"
            )


def _rubric() -> dict:
    return {
        "unit_of_judgment": "bounded_trace_episode",
        "claims": (
            "Judge only the relationship, observed outcome, trace-supported "
            "cause, evidence strength, exploration behavior, and candidate "
            "usefulness."
        ),
        "prohibited_inferences": [
            "person_level_skill_gap",
            "employee_capability",
            "intelligence_or_aptitude",
            "productivity_from_tool_success_alone",
        ],
        "structural_success_warning": (
            "A later successful tool result does not establish task recovery."
        ),
        "evidence_rule": (
            "Every label requires one or more evidence_ref values from the "
            "same candidate."
        ),
    }


def build_packet_from_sessions(
    sessions: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    dataset_id: str,
    dataset_revision: str,
    blind_key: bytes,
    receipt_hmac_key: bytes,
    seed: str = DEFAULT_SEED,
    scope_ref: str,
    purpose: str,
    context_events_each_side: int = DEFAULT_CONTEXT_EVENTS_EACH_SIDE,
    max_context_events: int = DEFAULT_MAX_CONTEXT_EVENTS,
    max_context_bytes: int = DEFAULT_MAX_CONTEXT_BYTES,
    max_lifecycle_distance: int = DEFAULT_MAX_LIFECYCLE_DISTANCE,
) -> Tuple[dict, dict]:
    """Build one credential-clean packet and its content-free manifest."""

    if not sessions:
        raise PacketError("Wisp session collection is empty")
    if not seed or context_events_each_side < 0:
        raise PacketError("packet order and context bounds are invalid")
    if max_context_events < 4 or max_context_bytes < 1:
        raise PacketError("context bounds cannot hold anchor evidence")
    candidates = []
    exclusions: collections.Counter = collections.Counter()
    family_counts: collections.Counter = collections.Counter()
    source_loss_counts: collections.Counter = collections.Counter()
    structural_candidates = 0
    for source_locator in sorted(sessions):
        records = sessions[source_locator]
        for record in records:
            source_loss = (
                record.get("_packet_source_loss")
                if isinstance(record, Mapping)
                else None
            )
            if isinstance(source_loss, Mapping):
                source_loss_counts[str(source_loss.get("category"))] += 1
        source_events, lifecycle, lifecycle_to_source = _extract_session(
            records
        )
        construction = construct_recovery_episodes(
            lifecycle,
            max_lifecycle_distance=max_lifecycle_distance,
        )
        structural_candidates += len(construction.matched_episodes)
        for episode_index, episode in enumerate(
            construction.matched_episodes
        ):
            candidate, exclusion = _candidate_context(
                source_locator=source_locator,
                source_events=source_events,
                lifecycle=lifecycle,
                lifecycle_to_source=lifecycle_to_source,
                episode=episode,
                episode_index=episode_index,
                blind_key=blind_key,
                context_events_each_side=context_events_each_side,
                max_context_events=max_context_events,
                max_context_bytes=max_context_bytes,
            )
            if exclusion is not None:
                exclusions[exclusion] += 1
                continue
            assert candidate is not None
            family_counts[episode.tool_family] += 1
            candidates.append(candidate)
    candidates.sort(
        key=lambda candidate: hashlib.sha256(
            (
                seed + "\0" + str(candidate["blind_id"])
            ).encode("utf-8")
        ).hexdigest()
    )
    packet_before_gate = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
        },
        "blind_review": {
            "candidate_ids": "keyed_hmac_24_hex",
            "candidate_order": "sha256_frozen_seed_plus_blind_id",
            "source_locators_included": False,
            "native_call_ids_included": False,
        },
        "rubric": _rubric(),
        "label_contract": label_contract(),
        "candidates": candidates,
    }
    clean_packet, credential_receipt = transform_credentials(
        packet_before_gate,
        boundary="evaluator",
        receipt_hmac_key=receipt_hmac_key,
        scope_ref=scope_ref,
        purpose=purpose,
    )
    verify_credential_free(
        clean_packet,
        boundary="evaluator",
        receipt_hmac_key=receipt_hmac_key,
        scope_ref=scope_ref,
        purpose=purpose,
    )
    packet_sha256 = hashlib.sha256(
        _json_file_bytes(clean_packet)
    ).hexdigest()
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "packet_schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_revision": dataset_revision,
        "source_session_count": len(sessions),
        "structural_candidate_count": structural_candidates,
        "candidate_count": len(candidates),
        "excluded_candidate_counts": dict(sorted(exclusions.items())),
        "controlled_tool_family_counts": dict(sorted(family_counts.items())),
        "source_loss_counts": dict(sorted(source_loss_counts.items())),
        "raw_packet_sha256": packet_sha256,
        "raw_packet_committed": False,
        "raw_packet_path_policy": "/private/tmp only",
        "labels": {
            name: list(values)
            for name, values in label_contract().items()
        },
        "rubric_contract": {
            "unit_of_judgment": "bounded_trace_episode",
            "person_level_skill_gap_inference_allowed": False,
            "evidence_refs_required_for_every_label": True,
            "later_tool_success_proves_task_recovery": False,
        },
        "blinding_contract": {
            "deterministic_blind_ids": True,
            "deterministic_seeded_order": True,
            "source_locators_emitted": False,
            "native_call_ids_emitted": False,
        },
        "context_contract": {
            "context_events_each_side": context_events_each_side,
            "max_context_events": max_context_events,
            "max_context_bytes": max_context_bytes,
            "whole_event_only": True,
            "tool_complete": True,
        },
        "credential_transform": {
            "rule_set_sha256": RULE_SET_SHA256,
            "disposition": credential_receipt["disposition"],
            "transformed_values": credential_receipt[
                "transformed_values"
            ],
            "counts_by_class": credential_receipt["counts_by_class"],
            "authorized_internal_pii_retained": True,
            "authorized_classified_content_retained": True,
        },
    }
    assert_content_free_manifest(manifest)
    return clean_packet, manifest


def assert_content_free_manifest(manifest: Mapping[str, Any]) -> None:
    """Reject fields that could serialize a candidate or source locator."""

    forbidden_keys = {
        "blind_id",
        "candidates",
        "context",
        "evidence_ref",
        "payload",
        "source_path",
        "relative_path",
        "source_locator",
    }

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key) in forbidden_keys:
                    raise PacketError(
                        f"manifest contains raw field {key}"
                    )
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(manifest)


def validate_adjudication(
    candidate: Mapping[str, Any],
    submission: Mapping[str, Any],
) -> dict:
    """Validate a closed-vocabulary, evidence-backed episode judgment."""

    if not isinstance(submission, Mapping) or set(submission) != {
        "blind_id",
        "labels",
    }:
        raise PacketError("adjudication must contain exact fields")
    if submission.get("blind_id") != candidate.get("blind_id"):
        raise PacketError("adjudication blind_id does not match candidate")
    labels = submission.get("labels")
    if not isinstance(labels, Mapping) or set(labels) != set(LABEL_ENUMS):
        raise PacketError("adjudication label dimensions are incomplete")
    evidence_refs = {
        event.get("evidence_ref")
        for event in candidate.get("context", [])
        if isinstance(event, Mapping)
    }
    for dimension, label_enum in LABEL_ENUMS.items():
        decision = labels[dimension]
        if not isinstance(decision, Mapping) or set(decision) != {
            "label",
            "evidence_refs",
        }:
            raise PacketError(
                f"{dimension} decision must contain exact fields"
            )
        allowed = {item.value for item in label_enum}
        if decision.get("label") not in allowed:
            raise PacketError(f"{dimension} label is invalid")
        refs = decision.get("evidence_refs")
        if (
            not isinstance(refs, list)
            or not refs
            or len(refs) != len(set(refs))
            or any(ref not in evidence_refs for ref in refs)
        ):
            raise PacketError(
                f"{dimension} evidence_ref is invalid"
            )
    return json.loads(_stable_json(submission))


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_private_tmp_output(path: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path)
    if not path.name or not path.parent.is_dir():
        raise PacketError("raw packet parent must already exist")
    resolved_parent = path.parent.resolve(strict=True)
    private_tmp = pathlib.Path("/private/tmp").resolve(strict=True)
    try:
        common = pathlib.Path(
            os.path.commonpath(
                [str(resolved_parent), str(private_tmp)]
            )
        )
    except ValueError as error:
        raise PacketError("raw packet must stay under /private/tmp") from error
    if common != private_tmp:
        raise PacketError("raw packet must stay under /private/tmp")
    if any(
        (ancestor / ".git").exists()
        for ancestor in (resolved_parent, *resolved_parent.parents)
    ):
        raise PacketError(
            "raw packet must stay under /private/tmp outside a Git worktree"
        )
    return resolved_parent / path.name


def write_raw_packet(packet: Mapping[str, Any], path: pathlib.Path) -> dict:
    """Create a mode-0600 raw packet only beneath ``/private/tmp``."""

    destination = _require_private_tmp_output(path)
    encoded = _json_file_bytes(packet)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as error:
        raise PacketError("raw packet output is immutable") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "mode": "0600",
    }


def load_wisp_sessions(
    root: pathlib.Path,
) -> Dict[str, Tuple[dict, ...]]:
    """Load the closed Wisp JSONL tree without silently dropping records."""

    root = pathlib.Path(root)
    if not root.is_dir():
        raise PacketError("Wisp root is not a directory")
    resolved_root = root.resolve(strict=True)
    paths = sorted(root.rglob("*.jsonl"))
    if not paths:
        raise PacketError("Wisp root contains no JSONL files")
    sessions: Dict[str, Tuple[dict, ...]] = {}
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise PacketError("Wisp corpus contains a non-ordinary JSONL file")
        resolved = path.resolve(strict=True)
        try:
            relative = resolved.relative_to(resolved_root).as_posix()
        except ValueError as error:
            raise PacketError("Wisp JSONL escapes the corpus root") from error
        records = []
        with path.open("rb") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                try:
                    value = json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    records.append(
                        {
                            "_packet_source_loss": {
                                "category": "malformed_json_record",
                                "line_number": line_number,
                                "byte_length": len(raw_line),
                                "raw_sha256": hashlib.sha256(
                                    raw_line
                                ).hexdigest(),
                            }
                        }
                    )
                    continue
                if not isinstance(value, dict):
                    records.append(
                        {
                            "_packet_source_loss": {
                                "category": "non_object_json_record",
                                "line_number": line_number,
                                "byte_length": len(raw_line),
                                "raw_sha256": hashlib.sha256(
                                    raw_line
                                ).hexdigest(),
                                "json_type": type(value).__name__,
                            },
                            "_packet_source_value": value,
                        }
                    )
                    continue
                records.append(value)
        sessions[relative] = tuple(records)
    return sessions


def write_content_free_manifest(
    manifest: Mapping[str, Any],
    path: pathlib.Path,
) -> dict:
    """Create an immutable, reviewable manifest containing no raw cases."""

    assert_content_free_manifest(manifest)
    destination = pathlib.Path(path)
    if not destination.parent.is_dir():
        raise PacketError("manifest parent must already exist")
    encoded = _json_file_bytes(manifest)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o644)
    except FileExistsError as error:
        raise PacketError("committed manifest is immutable") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }


def _read_key(path: pathlib.Path, label: str) -> bytes:
    try:
        value = pathlib.Path(path).read_bytes().strip()
    except OSError as error:
        raise PacketError(f"{label} cannot be read") from error
    if len(value) == 64:
        try:
            value = bytes.fromhex(value.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            pass
    if len(value) < 32:
        raise PacketError(f"{label} must contain at least 32 bytes")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wisp-root", type=pathlib.Path, required=True)
    parser.add_argument("--dataset-manifest", type=pathlib.Path, required=True)
    parser.add_argument("--raw-packet-output", type=pathlib.Path, required=True)
    parser.add_argument("--manifest-output", type=pathlib.Path, required=True)
    parser.add_argument("--blind-key-file", type=pathlib.Path, required=True)
    parser.add_argument(
        "--receipt-key-file",
        type=pathlib.Path,
        required=True,
    )
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--scope-ref", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument(
        "--context-events-each-side",
        type=int,
        default=DEFAULT_CONTEXT_EVENTS_EACH_SIDE,
    )
    parser.add_argument(
        "--max-context-events",
        type=int,
        default=DEFAULT_MAX_CONTEXT_EVENTS,
    )
    parser.add_argument(
        "--max-context-bytes",
        type=int,
        default=DEFAULT_MAX_CONTEXT_BYTES,
    )
    parser.add_argument(
        "--max-lifecycle-distance",
        type=int,
        default=DEFAULT_MAX_LIFECYCLE_DISTANCE,
    )
    args = parser.parse_args()

    dataset_manifest = json.loads(
        args.dataset_manifest.read_text(encoding="utf-8")
    )
    sessions = load_wisp_sessions(args.wisp_root)
    raw_packet, manifest = build_packet_from_sessions(
        sessions,
        dataset_id=str(dataset_manifest["dataset_id"]),
        dataset_revision=str(dataset_manifest["dataset_revision"]),
        blind_key=_read_key(args.blind_key_file, "blind key"),
        receipt_hmac_key=_read_key(
            args.receipt_key_file,
            "receipt key",
        ),
        seed=args.seed,
        scope_ref=args.scope_ref,
        purpose=args.purpose,
        context_events_each_side=args.context_events_each_side,
        max_context_events=args.max_context_events,
        max_context_bytes=args.max_context_bytes,
        max_lifecycle_distance=args.max_lifecycle_distance,
    )
    raw_receipt = write_raw_packet(raw_packet, args.raw_packet_output)
    if raw_receipt["sha256"] != manifest["raw_packet_sha256"]:
        raise PacketError("raw packet writer changed the packet commitment")
    manifest["raw_packet_bytes"] = raw_receipt["bytes"]
    manifest_receipt = write_content_free_manifest(
        manifest,
        args.manifest_output,
    )
    print(
        json.dumps(
            {
                "candidate_count": manifest["candidate_count"],
                "structural_candidate_count": manifest[
                    "structural_candidate_count"
                ],
                "excluded_candidate_counts": manifest[
                    "excluded_candidate_counts"
                ],
                "raw_packet_sha256": raw_receipt["sha256"],
                "raw_packet_bytes": raw_receipt["bytes"],
                "manifest_sha256": manifest_receipt["sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
