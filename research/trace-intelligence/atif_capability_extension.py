#!/usr/bin/env python3
"""Frankengate's explicit, namespaced ATIF capability extension.

ATIF v1.7 remains the portable interchange envelope.  This profile is an
opt-in companion for readers that need the control facts which ATIF does not
define: authorization epochs, environment reset/termination facts, replay
references, reward attribution, and memory lineage.  It deliberately does
not copy prompt/tool payloads or opaque state snapshots.  Those are accounted
for by content hashes in a loss receipt, so a portable reader cannot mistake
an ATIF document for an evidence-complete replay.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from atif_adapter import (
    ATIF_VERSION,
    CANONICAL_VERSION,
    ATIFValidationError,
    atif_to_canonical,
    canonical_to_atif,
    _safe_copy,
)


PROFILE_URI = "https://frankengate.dev/profiles/atif-v1/capability-v2"
EXTENSION_SCHEMA_VERSION = "frankengate-atif-capability-extension-v2"
RECEIPT_SCHEMA_VERSION = "frankengate-atif-capability-loss-receipt-v2"
HASH_ALGORITHM = "sha256"
CANONICALIZATION = "json-sort-keys-separators-utf8"
REFERENCE_POLICY = "governed-reference-required;hash-only-is-not-replayable"

# These are structural facts, not prompt/tool/state payloads.  Keep this list
# deliberately explicit: adding a field is a schema decision that should be
# reviewed for classification and privacy impact.
_IDENTITY_FIELDS = {
    "event_id",
    "sequence",
    "kind",
    "observation_status",
    "source_role",
    "parent_event_id",
    "caused_by_event_id",
    "linked_event_ids",
    "evidence_event_ids",
    "supersedes_event_id",
    "proposal_event_id",
    "result_event_id",
    "cached_decision_event_id",
    "authorization_decision_event_id",
    "branch_id",
    "branch_ids",
    "parallel_group_id",
    "concurrent_group_id",
    "predecessor_event_ids",
    "join_event_ids",
    "delegation_id",
    "workflow_id",
    "parent_session_id",
    "is_subagent_workflow",
    "tool_call_id",
    "call_id",
    "function_name",
    "tool_name",
    "attempt",
    "attempt_index",
    "retry",
    "retry_count",
    "fallback_index",
    "status",
    "error_type",
    "error_code",
    "timestamp",
    "started_at",
    "ended_at",
    "observed_at",
    "created_at",
    "updated_at",
}

_AUTHORIZATION_FIELDS = {
    "authorization",
    "authorization_decision",
    "authorization_epoch",
    "classification",
    "allowed_purposes",
    "purpose",
    "tenant_id",
    "owner_subject_id",
    "team_id",
    "governance_scope",
    "principal_id",
    "subject_id",
}

_ENVIRONMENT_FIELDS = {
    "environment",
    "environment_id",
    "environment_seed",
    "environment_snapshot_ref",
    "checkpoint_ref",
    "snapshot_ref",
    "state_before_ref",
    "state_after_ref",
    "before_digest",
    "after_digest",
    "state_delta_ref",
    "side_effects_ref",
    "reset_state_ref",
    "reset_semantics",
    "termination_semantics",
    "replay_reference",
    "artifact_ref",
    "artifact_sha256",
    "access_scope_ref",
    "retention_class",
    "availability_status",
    "reset_id",
    "termination",
    "terminated",
    "truncated",
    "done",
    "success",
    "final_score",
    "termination_reason",
    "max_steps",
}

_REWARD_FIELDS = {
    "reward",
    "reward_total",
    "reward_components",
    "score",
    "evaluation_id",
    "evaluator",
    "outcome_id",
}

_MEMORY_FIELDS = {
    "memory_before_ref",
    "memory_after_ref",
    "memory_snapshot_before_ref",
    "memory_snapshot_after_ref",
    "memory_source_lineage_ref",
    "memory_candidate_id",
    "memory_revision",
    "memory_scope",
    "memory_epoch",
    "memory_digest",
    "memory_status",
}

_PROVENANCE_FIELDS = {
    "dataset_id",
    "dataset_revision",
    "adapter",
    "native_format",
    "source_file",
    "source_file_sha256",
    "source_file_byte_length",
    "relative_path",
    "source_record_identity",
    "record_event_id",
    "content_block_index",
    "source_step",
    "path_context_ref",
    "schema_version",
    "format_revision",
}

_OPAQUE_FIELDS = {
    "content",
    "arguments",
    "native_block",
    "native_record",
    "observation",
    "state_delta",
    "side_effects",
    "memory_snapshot_before",
    "memory_snapshot_after",
    "memory_source_lineage",
    "raw_content",
}


class CapabilityExtensionError(ATIFValidationError):
    """Raised when the opt-in capability profile is malformed or ambiguous."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _is_allowed_field(key: str) -> bool:
    return key in (
        _IDENTITY_FIELDS
        | _AUTHORIZATION_FIELDS
        | _ENVIRONMENT_FIELDS
        | _REWARD_FIELDS
        | _MEMORY_FIELDS
        | _PROVENANCE_FIELDS
    )


def _safe_structural_value(key: str, value: Any) -> Any:
    """Copy a structural value while never copying an opaque payload."""
    if key in _OPAQUE_FIELDS:
        raise KeyError(key)
    # `_safe_copy` removes credential/token-shaped keys recursively.  The
    # extension is still subject to the caller's classification policy.
    return _safe_copy(value)


def _selected_fields(value: Mapping[str, Any], *, event: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    retained: dict[str, Any] = {}
    omitted: list[dict[str, Any]] = []
    for key in sorted(value):
        if not isinstance(key, str):
            continue
        if _is_allowed_field(key):
            try:
                retained[key] = _safe_structural_value(key, value[key])
            except KeyError:
                pass
            else:
                continue
        # The receipt records a digest only; it never exports the omitted
        # payload.  This includes content and tool arguments.
        omitted.append(
            {
                "path": f"events[{value.get('event_id', '<unknown>')}].{key}" if event else key,
                "sha256": _digest(value[key]),
                "reason": "opaque_or_not_in_capability_profile",
            }
        )
    return retained, omitted


def _root_fields(canonical: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # Root trace/task/source/loss metadata already has a first-class or
    # Frankengate base extension representation.  Only root capability facts
    # are duplicated here, making this profile composable with base ATIF.
    return _selected_fields(canonical, event=False)


def _extension_from_canonical(canonical: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root, omitted = _root_fields(canonical)
    event_records: list[dict[str, Any]] = []
    event_ids: list[str] = []
    for event in sorted(
        canonical.get("events", []),
        key=lambda item: (int(item.get("sequence", 0)), str(item.get("event_id", ""))),
    ):
        event_id = str(event["event_id"])
        fields, event_omitted = _selected_fields(event, event=True)
        # Identity is required even for an event whose only useful fact was a
        # payload that this profile intentionally refuses to copy.
        if "event_id" not in fields:
            fields["event_id"] = event_id
        event_records.append({"event_id": event_id, "fields": fields})
        event_ids.append(event_id)
        omitted.extend(event_omitted)
    extension: dict[str, Any] = {
        "schema_version": EXTENSION_SCHEMA_VERSION,
        "profile": PROFILE_URI,
        "canonical_schema_version": CANONICAL_VERSION,
        "source_trace_id": canonical.get("trace_id"),
        "source_event_count": len(event_records),
        "source_event_ids": event_ids,
        "contract": {
            "hash_algorithm": HASH_ALGORITHM,
            "canonicalization": CANONICALIZATION,
            "min_reader_version": EXTENSION_SCHEMA_VERSION,
            "reference_policy": REFERENCE_POLICY,
            "opaque_payload_policy": "hash-only;not-replayable-without-governed-reference",
        },
        "root_fields": root,
        "event_records": event_records,
        "omitted_field_manifests": omitted,
    }
    receipt_without_id = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "profile": PROFILE_URI,
        "source_event_count": len(event_records),
        "hash_algorithm": HASH_ALGORITHM,
        "canonicalization": CANONICALIZATION,
        "reference_policy": REFERENCE_POLICY,
        "retained_root_field_count": len(root),
        "retained_event_field_count": sum(len(item["fields"]) for item in event_records),
        "omitted_field_count": len(omitted),
        "omitted_field_paths": [item["path"] for item in omitted],
        "source_sha256": _digest(canonical),
        "silently_dropped_event_count": 0,
    }
    receipt = {**receipt_without_id, "receipt_id": _digest(receipt_without_id)}
    extension["receipt_id"] = receipt["receipt_id"]
    return extension, receipt


def canonical_to_atif_capability(
    canonical: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Export canonical data with the explicit capability profile attached."""
    if canonical.get("schema_version") != CANONICAL_VERSION:
        raise CapabilityExtensionError(f"expected {CANONICAL_VERSION!r}")
    if not isinstance(canonical.get("events"), list):
        raise CapabilityExtensionError("canonical events must be an array")
    before = copy.deepcopy(canonical)
    atif, base_receipt = canonical_to_atif(canonical)
    extension, receipt = _extension_from_canonical(canonical)
    atif.setdefault("extra", {}).setdefault("frankengate", {})[
        "capability_extension"
    ] = extension
    atif["extra"]["frankengate"]["capability_extension_receipt_id"] = receipt["receipt_id"]
    if canonical != before:
        raise CapabilityExtensionError("export mutated canonical input")
    result = copy.deepcopy(receipt)
    result["base_atif_receipt_id"] = base_receipt["receipt_id"]
    result["base_atif_schema_version"] = ATIF_VERSION
    result["receipt_id"] = _digest({key: value for key, value in result.items() if key != "receipt_id"})
    return atif, result


def _merge(existing: dict[str, Any], incoming: Mapping[str, Any], path: str) -> None:
    for key, value in incoming.items():
        # The generic ATIF adapter is allowed to reconstruct sequence numbers,
        # roles, and event kinds when the native envelope has no such field.
        # The explicit capability profile is the authoritative source for
        # those structural facts on a profile-aware round trip.
        if key in {
            "sequence",
            "kind",
            "source_role",
            "observation_status",
            "parent_event_id",
            "caused_by_event_id",
            "linked_event_ids",
            "evidence_event_ids",
            "supersedes_event_id",
            "proposal_event_id",
            "result_event_id",
            "cached_decision_event_id",
            "authorization_decision_event_id",
        }:
            existing[key] = copy.deepcopy(value)
            continue
        if key in existing and existing[key] not in (None, "") and existing[key] != value:
            raise CapabilityExtensionError(f"conflicting values at {path}.{key}")
        existing[key] = copy.deepcopy(value)


def _validate_extension(extension: Mapping[str, Any]) -> None:
    if extension.get("schema_version") != EXTENSION_SCHEMA_VERSION:
        raise CapabilityExtensionError("unsupported capability extension schema")
    if extension.get("profile") != PROFILE_URI:
        raise CapabilityExtensionError("unsupported capability extension profile")
    contract = extension.get("contract")
    if not isinstance(contract, dict):
        raise CapabilityExtensionError("capability extension contract is required")
    if contract.get("hash_algorithm") != HASH_ALGORITHM:
        raise CapabilityExtensionError("unsupported capability extension hash algorithm")
    if contract.get("canonicalization") != CANONICALIZATION:
        raise CapabilityExtensionError("unsupported capability extension canonicalization")
    if contract.get("min_reader_version") != EXTENSION_SCHEMA_VERSION:
        raise CapabilityExtensionError("capability extension reader version mismatch")
    if contract.get("reference_policy") != REFERENCE_POLICY:
        raise CapabilityExtensionError("unsupported capability extension reference policy")
    if not isinstance(extension.get("root_fields"), dict):
        raise CapabilityExtensionError("capability extension root_fields must be an object")
    records = extension.get("event_records")
    ids = extension.get("source_event_ids")
    if not isinstance(records, list) or not isinstance(ids, list):
        raise CapabilityExtensionError("capability extension event records are required")
    observed_ids: list[str] = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("event_id"), str):
            raise CapabilityExtensionError("capability extension event record is invalid")
        if not isinstance(record.get("fields"), dict):
            raise CapabilityExtensionError("capability extension event fields are invalid")
        observed_ids.append(record["event_id"])
    if observed_ids != [str(item) for item in ids]:
        raise CapabilityExtensionError("capability extension event identity order mismatch")
    if extension.get("source_event_count") != len(records):
        raise CapabilityExtensionError("capability extension event count mismatch")


def atif_capability_to_canonical(
    atif: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import ATIF plus the profile, restoring structural capability facts."""
    base, base_receipt = atif_to_canonical(atif)
    extension = (
        atif.get("extra", {})
        .get("frankengate", {})
        .get("capability_extension")
    )
    if extension is None:
        raise CapabilityExtensionError("capability extension is required")
    _validate_extension(extension)
    restored = copy.deepcopy(base)
    _merge(restored, extension["root_fields"], "root_fields")
    # The base adapter creates this only to satisfy ATIF's non-empty-step
    # requirement.  Once the profile supplies the source event inventory it
    # is no longer evidence and must not survive as a phantom event.
    if extension["event_records"]:
        restored["events"] = [
            event
            for event in restored.get("events", [])
            if event.get("event_id") != "synthetic-empty-projection"
        ]
    events_by_id = {
        str(event.get("event_id")): event
        for event in restored.get("events", [])
        if isinstance(event, dict) and event.get("event_id") is not None
    }
    used_sequences = {
        int(event["sequence"])
        for event in restored.get("events", [])
        if isinstance(event, dict) and isinstance(event.get("sequence"), int)
    }
    next_sequence = max(used_sequences, default=-1) + 1
    for record in extension["event_records"]:
        event_id = str(record["event_id"])
        fields = copy.deepcopy(record["fields"])
        if event_id in events_by_id:
            _merge(events_by_id[event_id], fields, f"events[{event_id}]")
            continue
        fields.setdefault("event_id", event_id)
        fields.setdefault("kind", "unprojected.event")
        fields.setdefault("observation_status", "reconstructed")
        fields.setdefault("source_role", "system")
        original_sequence = fields.get("sequence")
        if not isinstance(original_sequence, int) or original_sequence in used_sequences:
            if isinstance(original_sequence, int):
                fields["original_sequence"] = original_sequence
            fields["sequence"] = next_sequence
        used_sequences.add(int(fields["sequence"]))
        next_sequence = max(next_sequence, int(fields["sequence"]) + 1)
        fields.setdefault("content", None)
        restored.setdefault("events", []).append(fields)
        events_by_id[event_id] = fields
    restored["events"].sort(key=lambda event: (int(event.get("sequence", 0)), str(event.get("event_id", ""))))
    restored.setdefault("loss_receipt", {})["capability_extension_receipt_id"] = extension.get("receipt_id")
    restored["loss_receipt"]["capability_extension_omitted_field_count"] = len(
        extension.get("omitted_field_manifests", [])
    )
    result = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "profile": PROFILE_URI,
        "direction": "atif-capability-to-canonical",
        "base_atif_receipt_id": base_receipt["receipt_id"],
        "source_event_count": extension["source_event_count"],
        "restored_event_count": len(restored.get("events", [])),
        "omitted_field_count": len(extension.get("omitted_field_manifests", [])),
        "silently_dropped_event_count": 0,
    }
    result["receipt_id"] = _digest(result)
    return restored, result


def capability_projection(canonical: Mapping[str, Any]) -> dict[str, Any]:
    """Return only profile-retained facts for exact, content-free comparison."""
    root, _ = _root_fields(canonical)
    events = []
    for event in sorted(canonical.get("events", []), key=lambda item: (int(item.get("sequence", 0)), str(item.get("event_id", "")))):
        fields, _ = _selected_fields(event, event=True)
        events.append(fields)
    return {"root_fields": root, "event_records": events}


def assert_capability_round_trip(canonical: dict[str, Any]) -> dict[str, Any]:
    """Fail closed if any profile-retained structural fact changes."""
    atif, export_receipt = canonical_to_atif_capability(canonical)
    restored, import_receipt = atif_capability_to_canonical(atif)
    expected = capability_projection(canonical)
    actual = capability_projection(restored)
    if expected != actual:
        raise AssertionError("capability extension changed a retained structural fact")
    if export_receipt["silently_dropped_event_count"] != 0 or import_receipt["silently_dropped_event_count"] != 0:
        raise AssertionError("capability extension reported a silent event drop")
    return {
        "export_receipt_id": export_receipt["receipt_id"],
        "import_receipt_id": import_receipt["receipt_id"],
        "source_event_count": len(canonical.get("events", [])),
        "retained_root_field_count": len(expected["root_fields"]),
        "retained_event_field_count": sum(len(item) for item in expected["event_records"]),
        "omitted_field_count": export_receipt["omitted_field_count"],
    }
