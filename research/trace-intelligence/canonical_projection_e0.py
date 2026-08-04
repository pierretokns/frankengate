#!/usr/bin/env python3
"""E0 canonical projection conformance for ATIF and OpenInference/OTel.

The canonical event DAG remains the evidence authority.  ATIF v1.7 and
OpenInference/OpenTelemetry are deterministic projections with explicit,
machine-checkable loss receipts; neither is used as a peer canonical store.

The OpenInference/OTel output is a dependency-free research envelope.  Its
``otlp`` member follows OTLP JSON field names and can be separated from the
Frankengate projection metadata.  Content and authority values are omitted by
default.  A deterministic reimport restores the typed event topology that is
actually represented, not the omitted evidence.
"""

from __future__ import annotations

import argparse
import collections
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from atif_adapter import (
    ATIF_VERSION,
    CANONICAL_VERSION,
    assert_no_silent_loss,
    atif_to_canonical,
    canonical_to_atif,
)


E0_RECEIPT_VERSION = "canonical-projection-loss-receipt-v1"
E0_RESULT_VERSION = "canonical-projection-e0-conformance-result-v1"
OTEL_ENVELOPE_VERSION = "frankengate-openinference-otlp-envelope-v1"
OTEL_TARGET = "OpenInference-v0.1.30+OTel-SemConv-v1.43.0"
OTEL_SCOPE_NAME = "frankengate.trace-projection"
OTEL_SCOPE_VERSION = "e0-v1"
OPENINFERENCE_REVISION = "789d41974c08a9a13147977f28ef4142a07e2106"
OTEL_CORE_REVISION = "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d"
OTEL_GENAI_REVISION = "434c91dcc34ed038e3048c07720ddfed2c6bddfc"


class ProjectionValidationError(ValueError):
    """Raised when source, projection, or receipt invariants fail."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _validate_canonical(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(canonical, dict):
        raise ProjectionValidationError("canonical trajectory must be an object")
    if canonical.get("schema_version") != CANONICAL_VERSION:
        raise ProjectionValidationError(
            f"expected canonical schema {CANONICAL_VERSION!r}"
        )
    if not isinstance(canonical.get("trace_id"), str):
        raise ProjectionValidationError("canonical trace_id must be a string")
    events = canonical.get("events")
    if not isinstance(events, list):
        raise ProjectionValidationError("canonical events must be an array")
    ordered = sorted(
        events,
        key=lambda event: (
            event.get("sequence", 0) if isinstance(event, dict) else 0,
            str(event.get("event_id", "")) if isinstance(event, dict) else "",
        ),
    )
    event_ids: set[str] = set()
    sequences: set[int] = set()
    for event in ordered:
        if not isinstance(event, dict):
            raise ProjectionValidationError("canonical event must be an object")
        event_id = event.get("event_id")
        sequence = event.get("sequence")
        if not isinstance(event_id, str) or not event_id:
            raise ProjectionValidationError("canonical event_id must be nonempty")
        if event_id in event_ids:
            raise ProjectionValidationError(
                f"duplicate canonical event_id {event_id!r}"
            )
        if not isinstance(sequence, int) or sequence < 0:
            raise ProjectionValidationError(
                f"canonical event {event_id!r} has invalid sequence"
            )
        if sequence in sequences:
            raise ProjectionValidationError(
                f"duplicate canonical sequence {sequence!r}"
            )
        if not isinstance(event.get("kind"), str):
            raise ProjectionValidationError(
                f"canonical event {event_id!r} needs kind"
            )
        event_ids.add(event_id)
        sequences.add(sequence)
    return ordered


def _capability_paths(
    canonical: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    """Identify capability-bearing fields without copying their values."""
    capabilities: dict[str, list[dict[str, str]]] = {
        "dag": [],
        "parallelism": [],
        "authorization": [],
        "environment": [],
        "evaluation": [],
        "replay": [],
    }
    dag_fields = {
        "parent_event_id",
        "caused_by_event_id",
        "linked_event_ids",
        "predecessor_event_ids",
        "evidence_event_ids",
        "supersedes_event_id",
        "cached_decision_event_id",
        "authorization_decision_event_id",
        "proposal_event_id",
        "result_event_id",
    }
    parallel_fields = {
        "branch_id",
        "branch_ids",
        "parallel_group_id",
        "concurrent_group_id",
        "predecessor_event_ids",
        "join_event_ids",
    }
    environment_fields = {
        "state_before_ref",
        "state_after_ref",
        "before_digest",
        "after_digest",
        "resource_id",
        "environment_id",
        "state_delta",
        "side_effects",
    }
    replay_fields = {
        "replay",
        "replay_level",
        "replayable",
        "checkpoint_ref",
        "snapshot_ref",
        "environment_snapshot_ref",
        "state_before_ref",
        "state_after_ref",
        "before_digest",
        "after_digest",
        "side_effects",
    }

    def add(capability: str, path: str, event_id: str | None = None) -> None:
        item = {"path": path}
        if event_id is not None:
            item["event_id"] = event_id
        if item not in capabilities[capability]:
            capabilities[capability].append(item)

    for root_field in (
        "authority",
        "authorization",
        "authorization_epoch",
        "classification",
        "allowed_purposes",
        "purpose",
        "tenant_id",
        "owner_subject_id",
        "team_id",
    ):
        if root_field in canonical:
            add("authorization", root_field)
    for root_field in (
        "environment",
        "environment_snapshot_ref",
        "checkpoint_ref",
        "replay",
        "replay_level",
    ):
        if root_field in canonical:
            add(
                "replay" if "replay" in root_field or "checkpoint" in root_field
                else "environment",
                root_field,
            )
    if canonical.get("outcome") is not None:
        add("evaluation", "outcome")
    if canonical.get("evaluation") is not None:
        add("evaluation", "evaluation")

    for index, event in enumerate(canonical.get("events", [])):
        event_id = str(event.get("event_id", f"index-{index}"))
        kind = str(event.get("kind", ""))
        prefix = f"events[{event_id}]"
        if kind.startswith(("authorization", "governance", "cache_authority")):
            add("authorization", f"{prefix}.kind", event_id)
        if kind.startswith("environment") or kind in {
            "state_delta",
            "workspace.file_history_snapshot",
        }:
            add("environment", f"{prefix}.kind", event_id)
        if kind.startswith(("evaluation", "outcome", "reward")):
            add("evaluation", f"{prefix}.kind", event_id)
        if kind.startswith(("branch", "parallel")):
            add("parallelism", f"{prefix}.kind", event_id)
        if kind.startswith(("checkpoint", "replay")) or kind in {
            "state_delta",
            "environment.checkpointed",
        }:
            add("replay", f"{prefix}.kind", event_id)

        for field in event:
            path = f"{prefix}.{field}"
            lowered = field.lower()
            if field in dag_fields:
                add("dag", path, event_id)
            if field in parallel_fields:
                add("parallelism", path, event_id)
            if (
                "authoriz" in lowered
                or "principal" in lowered
                or "subject" in lowered
                or "classification" in lowered
                or lowered in {"scope", "scopes", "purpose", "allowed_purposes"}
            ):
                add("authorization", path, event_id)
            if field in environment_fields:
                add("environment", path, event_id)
            if (
                lowered.startswith(("reward", "score", "evaluation"))
                or lowered in {"evaluator", "outcome"}
            ):
                add("evaluation", path, event_id)
            if field in replay_fields:
                add("replay", path, event_id)
    return capabilities


def _item(
    capability: str,
    category: str,
    path: str,
    reason: str,
    *,
    event_id: str | None = None,
    target_path: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "capability": capability,
        "category": category,
        "path": path,
        "reason": reason,
    }
    if event_id is not None:
        item["event_id"] = event_id
    if target_path is not None:
        item["target_path"] = target_path
    return item


def _finish_receipt(
    *,
    direction: str,
    target_format: str,
    source: dict[str, Any],
    projection: dict[str, Any],
    accounted_events: int,
    items: list[dict[str, Any]],
    capabilities: dict[str, list[dict[str, str]]],
    native_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    categories = collections.Counter(item["category"] for item in items)
    capability_summary = {}
    for capability, paths in capabilities.items():
        capability_items = [
            item for item in items if item["capability"] == capability
        ]
        capability_summary[capability] = {
            "present": bool(paths),
            "source_field_count": len(paths),
            "receipted_field_count": len(
                {item["path"] for item in capability_items}
            ),
            "categories": dict(
                sorted(
                    collections.Counter(
                        item["category"] for item in capability_items
                    ).items()
                )
            ),
        }
    receipt: dict[str, Any] = {
        "schema_version": E0_RECEIPT_VERSION,
        "direction": direction,
        "source_format": CANONICAL_VERSION,
        "target_format": target_format,
        "source_event_count": len(source.get("events", [])),
        "accounted_source_event_count": accounted_events,
        "silently_dropped_event_count": 0,
        "source_sha256": digest(source),
        "projection_sha256": digest(projection),
        "item_category_counts": dict(sorted(categories.items())),
        "capability_summary": capability_summary,
        "items": items,
    }
    if native_receipt is not None:
        receipt["native_receipt_id"] = native_receipt["receipt_id"]
        receipt["native_receipt"] = copy.deepcopy(native_receipt)
    receipt["receipt_id"] = digest(receipt)
    return receipt


def verify_projection_receipt(
    source: dict[str, Any],
    projection: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    if receipt.get("silently_dropped_event_count") != 0:
        raise ProjectionValidationError("receipt reports a silent drop")
    receipt_without_identity = {
        key: value for key, value in receipt.items() if key != "receipt_id"
    }
    if receipt.get("receipt_id") != digest(receipt_without_identity):
        raise ProjectionValidationError("receipt identity mismatch")
    if receipt.get("source_event_count") != len(source.get("events", [])):
        raise ProjectionValidationError("receipt source event count mismatch")
    if receipt.get("accounted_source_event_count") != len(
        source.get("events", [])
    ):
        raise ProjectionValidationError("receipt does not account for every event")
    if receipt.get("source_sha256") != digest(source):
        raise ProjectionValidationError("source mutation or receipt mismatch")
    if receipt.get("projection_sha256") != digest(projection):
        raise ProjectionValidationError("projection mutation or receipt mismatch")
    present = [
        name
        for name, summary in receipt.get("capability_summary", {}).items()
        if summary.get("present")
    ]
    for capability in present:
        summary = receipt["capability_summary"][capability]
        if summary["source_field_count"] != summary["receipted_field_count"]:
            raise ProjectionValidationError(
                f"capability {capability!r} has unreceipted fields"
            )


def canonical_to_atif_e0(
    canonical: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project through the ATIF v1.7 adapter plus an E0 capability receipt."""
    ordered = _validate_canonical(canonical)
    before = copy.deepcopy(canonical)
    projectable = copy.deepcopy(canonical)
    root_classification = projectable.get("classification")
    root_is_sensitive = root_classification not in {
        None,
        0,
        "public",
        "unclassified",
    }
    redacted_paths: list[dict[str, str]] = []
    for event in projectable["events"]:
        event_classification = event.get("classification")
        event_is_sensitive = event_classification not in {
            None,
            0,
            "public",
            "unclassified",
        }
        authority_event = str(event.get("kind", "")).startswith(
            ("authorization", "governance", "cache_authority")
        )
        if (
            event.get("content") is not None
            and (root_is_sensitive or event_is_sensitive or authority_event)
        ):
            event["redacted"] = True
            event.setdefault(
                "redaction_revision", "e0-classification-policy-v1"
            )
            redacted_paths.append(
                {
                    "path": f"events[{event['event_id']}].content",
                    "event_id": str(event["event_id"]),
                }
            )
    atif, native_receipt = canonical_to_atif(projectable)
    assert_no_silent_loss(native_receipt)
    if canonical != before:
        raise ProjectionValidationError("ATIF adapter mutated canonical input")

    capabilities = _capability_paths(canonical)
    items: list[dict[str, Any]] = []
    reasons = {
        "dag": (
            "ATIF's ordered steps and containment cannot carry a general "
            "multi-edge event DAG; Frankengate extra or a hash manifest is "
            "non-portable"
        ),
        "parallelism": (
            "ATIF can group parallel tool proposals in one step but cannot "
            "preserve general branch partial order and many-to-one joins"
        ),
        "authorization": (
            "ATIF extra is not an authorization boundary; authority fields are "
            "non-portable and sensitive policy inputs remain suppressed"
        ),
        "environment": (
            "environment transitions have no first-class ATIF v1.7 event type "
            "and survive only in non-portable extra or manifests"
        ),
        "evaluation": (
            "outcomes and evaluator facts are non-portable ATIF extra and "
            "cannot be promoted to trusted reward"
        ),
        "replay": (
            "ATIF has no environment snapshot, side-effect, or replay "
            "fidelity contract"
        ),
    }
    for capability, paths in capabilities.items():
        for path in paths:
            items.append(
                _item(
                    capability,
                    "unsupported",
                    path["path"],
                    reasons[capability],
                    event_id=path.get("event_id"),
                )
            )
    for path in redacted_paths:
        items.append(
            _item(
                "content",
                "redacted",
                path["path"],
                "classified or authority-bearing content was redacted before "
                "portable ATIF projection",
                event_id=path["event_id"],
            )
        )

    receipt = _finish_receipt(
        direction="canonical-to-atif-v1.7",
        target_format=ATIF_VERSION,
        source=canonical,
        projection=atif,
        accounted_events=native_receipt["accounted_source_event_count"],
        items=items,
        capabilities=capabilities,
        native_receipt=native_receipt,
    )
    verify_projection_receipt(canonical, atif, receipt)
    return atif, receipt


def _span_id(trace_id: str, event_id: str) -> str:
    return hashlib.sha256(
        f"{trace_id}\0{event_id}".encode("utf-8")
    ).hexdigest()[:16]


def _trace_id(trace_id: str) -> str:
    return hashlib.sha256(trace_id.encode("utf-8")).hexdigest()[:32]


def _any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def _attribute(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "value": _any_value(value)}


def _attributes_to_dict(attributes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in attributes:
        value = attribute.get("value", {})
        if "stringValue" in value:
            decoded: Any = value["stringValue"]
        elif "intValue" in value:
            decoded = int(value["intValue"])
        elif "doubleValue" in value:
            decoded = float(value["doubleValue"])
        elif "boolValue" in value:
            decoded = bool(value["boolValue"])
        else:
            continue
        result[str(attribute.get("key"))] = decoded
    return result


def _parse_time_nanos(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1_000_000_000)


def _span_kind(kind: str) -> str:
    if kind.startswith(("tool.", "tool_", "tool_result", "tool_execution")):
        return "TOOL"
    if kind.startswith(("model.", "conversation.", "provider_attempt")):
        return "LLM"
    if kind.startswith(("retrieval", "evidence_chunk")):
        return "RETRIEVER"
    if kind.startswith(("evaluation", "outcome", "reward")):
        return "EVALUATOR"
    if kind.startswith(
        ("agent", "delegation", "subagent", "branch", "parallel")
    ):
        return "AGENT"
    if kind.startswith("prompt"):
        return "PROMPT"
    return "CHAIN"


def _operation_name(kind: str) -> str | None:
    span_kind = _span_kind(kind)
    if span_kind == "TOOL":
        return "execute_tool"
    if span_kind == "LLM":
        return "chat"
    if span_kind == "AGENT":
        return "invoke_agent"
    return None


def _relationship_values(
    event: dict[str, Any], known_event_ids: set[str]
) -> list[tuple[str, str]]:
    relationships: list[tuple[str, str]] = []
    for field, value in event.items():
        if field == "parent_event_id":
            continue
        candidates: list[Any]
        if field.endswith("_event_id"):
            candidates = [value]
        elif field.endswith("_event_ids") and isinstance(value, list):
            candidates = value
        else:
            continue
        for candidate in candidates:
            if isinstance(candidate, str) and candidate in known_event_ids:
                relationship = (field, candidate)
                if relationship not in relationships:
                    relationships.append(relationship)
    return relationships


def canonical_to_openinference_otel(
    canonical: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build an OTLP JSON envelope with OpenInference span attributes."""
    ordered = _validate_canonical(canonical)
    before = copy.deepcopy(canonical)
    trace_id = _trace_id(canonical["trace_id"])
    event_ids = {str(event["event_id"]) for event in ordered}
    span_ids = {
        event_id: _span_id(canonical["trace_id"], event_id)
        for event_id in event_ids
    }
    if len(set(span_ids.values())) != len(span_ids):
        raise ProjectionValidationError("deterministic span ID collision")

    capabilities = _capability_paths(canonical)
    items: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    for event in ordered:
        event_id = str(event["event_id"])
        sequence = int(event["sequence"])
        kind = str(event["kind"])
        attributes = [
            _attribute("openinference.span.kind", _span_kind(kind)),
            _attribute("frankengate.canonical.event_id", event_id),
            _attribute("frankengate.canonical.sequence", sequence),
            _attribute("frankengate.canonical.kind", kind),
            _attribute(
                "frankengate.canonical.observation_status",
                event.get("observation_status", "observed"),
            ),
            _attribute(
                "frankengate.canonical.source_role",
                event.get("source_role", "unknown"),
            ),
        ]
        operation = _operation_name(kind)
        if operation is not None:
            attributes.append(_attribute("gen_ai.operation.name", operation))
        if event.get("tool_call_id") is not None:
            attributes.append(
                _attribute("gen_ai.tool.call.id", event["tool_call_id"])
            )
        if event.get("function_name") or event.get("tool_name"):
            attributes.append(
                _attribute(
                    "gen_ai.tool.name",
                    event.get("function_name") or event.get("tool_name"),
                )
            )
        if event.get("attempt") is not None:
            attributes.append(
                _attribute("frankengate.attempt", event["attempt"])
            )

        start = (
            _parse_time_nanos(event.get("started_at"))
            or _parse_time_nanos(event.get("timestamp"))
        )
        if start is None:
            start = (sequence + 1) * 1_000_000
            items.append(
                _item(
                    "operational_timing",
                    "reconstructed",
                    f"events[{event_id}].timestamp",
                    "missing span start time reconstructed deterministically "
                    "from canonical sequence",
                    event_id=event_id,
                )
            )
        end = _parse_time_nanos(event.get("ended_at"))
        if end is None or end < start:
            end = start + 1
            items.append(
                _item(
                    "operational_timing",
                    "reconstructed",
                    f"events[{event_id}].ended_at",
                    "missing or invalid span end reconstructed as start plus "
                    "one nanosecond",
                    event_id=event_id,
                )
            )

        span: dict[str, Any] = {
            "traceId": trace_id,
            "spanId": span_ids[event_id],
            "name": f"frankengate.{kind}",
            "kind": 1,
            "startTimeUnixNano": str(start),
            "endTimeUnixNano": str(end),
            "attributes": attributes,
            "status": {
                "code": (
                    "STATUS_CODE_ERROR"
                    if kind.endswith("failed")
                    or event.get("status") in {"error", "failed"}
                    else "STATUS_CODE_UNSET"
                )
            },
        }
        parent = event.get("parent_event_id")
        if isinstance(parent, str) and parent in span_ids:
            span["parentSpanId"] = span_ids[parent]
        elif parent is not None:
            items.append(
                _item(
                    "dag",
                    "unsupported",
                    f"events[{event_id}].parent_event_id",
                    "dangling canonical parent has no target span",
                    event_id=event_id,
                )
            )

        links = []
        for relationship, target_event_id in _relationship_values(
            event, event_ids
        ):
            links.append(
                {
                    "traceId": trace_id,
                    "spanId": span_ids[target_event_id],
                    "attributes": [
                        _attribute(
                            "frankengate.relationship", relationship
                        )
                    ],
                }
            )
        if links:
            span["links"] = links
        spans.append(span)

        if event.get("content") is not None:
            items.append(
                _item(
                    "content",
                    "redacted",
                    f"events[{event_id}].content",
                    "event content omitted from telemetry projection; governed "
                    "canonical evidence remains authoritative",
                    event_id=event_id,
                )
            )
        for field in ("arguments", "command", "reasoning_content"):
            if event.get(field) is not None:
                items.append(
                    _item(
                        "content",
                        "redacted",
                        f"events[{event_id}].{field}",
                        "high-cardinality or sensitive payload omitted from "
                        "telemetry attributes",
                        event_id=event_id,
                    )
                )

    projection = {
        "schemaVersion": OTEL_ENVELOPE_VERSION,
        "projectionMetadata": {
            "sourceSchemaVersion": CANONICAL_VERSION,
            "sourceTraceId": canonical["trace_id"],
            "sourceEventCount": len(ordered),
            "openInferenceRevision": OPENINFERENCE_REVISION,
            "otelCoreRevision": OTEL_CORE_REVISION,
            "otelGenAIRevision": OTEL_GENAI_REVISION,
            "contentIncluded": False,
            "authorityValuesIncluded": False,
        },
        "otlp": {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            _attribute(
                                "service.name",
                                "frankengate-trace-projection",
                            ),
                            _attribute(
                                "frankengate.canonical.schema_version",
                                CANONICAL_VERSION,
                            ),
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": OTEL_SCOPE_NAME,
                                "version": OTEL_SCOPE_VERSION,
                            },
                            "spans": spans,
                        }
                    ],
                }
            ]
        },
    }

    reasons = {
        "dag": (
            "primary parent is represented as parentSpanId and additional "
            "known event relations as OTel links; relationship semantics are "
            "Frankengate attributes rather than portable graph constraints"
        ),
        "parallelism": (
            "OTel spans and links preserve observable timing/causality but "
            "cannot prove branch scheduling or a complete partial order when "
            "source timestamps are missing"
        ),
        "authorization": (
            "authority values are intentionally omitted because an OTel "
            "collector is not assumed to enforce equal-or-stronger policy"
        ),
        "environment": (
            "environment events become spans, but state payload and transition "
            "semantics remain governed canonical evidence"
        ),
        "evaluation": (
            "evaluation events become EVALUATOR spans; root outcome, reward, "
            "and score values are omitted from telemetry attributes"
        ),
        "replay": (
            "replay snapshots, state digests, and side-effect contracts are "
            "not operational telemetry semantics"
        ),
    }
    for capability, paths in capabilities.items():
        for path in paths:
            category = "normalized" if capability in {
                "dag",
                "parallelism",
                "environment",
                "evaluation",
            } else "unsupported"
            if capability == "authorization":
                category = "redacted"
            items.append(
                _item(
                    capability,
                    category,
                    path["path"],
                    reasons[capability],
                    event_id=path.get("event_id"),
                )
            )

    receipt = _finish_receipt(
        direction="canonical-to-openinference-otel",
        target_format=OTEL_TARGET,
        source=canonical,
        projection=projection,
        accounted_events=len(spans),
        items=items,
        capabilities=capabilities,
    )
    if canonical != before:
        raise ProjectionValidationError(
            "OpenInference/OTel projection mutated canonical input"
        )
    verify_projection_receipt(canonical, projection, receipt)
    return projection, receipt


def _spans(projection: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        resource_spans = projection["otlp"]["resourceSpans"]
        spans = resource_spans[0]["scopeSpans"][0]["spans"]
    except (KeyError, IndexError, TypeError) as error:
        raise ProjectionValidationError(
            "invalid Frankengate OpenInference/OTLP envelope"
        ) from error
    if not isinstance(spans, list):
        raise ProjectionValidationError("OTLP spans must be an array")
    return spans


def openinference_otel_to_canonical(
    projection: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deterministically reimport the typed topology represented by the envelope."""
    if projection.get("schemaVersion") != OTEL_ENVELOPE_VERSION:
        raise ProjectionValidationError(
            f"expected envelope {OTEL_ENVELOPE_VERSION!r}"
        )
    spans = _spans(projection)
    metadata = projection.get("projectionMetadata", {})
    source_trace_id = metadata.get("sourceTraceId")
    trace_id = (
        source_trace_id
        if isinstance(source_trace_id, str) and len(source_trace_id) == 64
        else digest(projection)
    )
    span_to_event: dict[str, str] = {}
    decoded: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for span in spans:
        attributes = _attributes_to_dict(span.get("attributes", []))
        event_id = attributes.get("frankengate.canonical.event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ProjectionValidationError(
                "span is missing canonical event identity"
            )
        span_id = span.get("spanId")
        if not isinstance(span_id, str) or span_id in span_to_event:
            raise ProjectionValidationError(
                "span ID is missing or duplicated"
            )
        span_to_event[span_id] = event_id
        decoded.append((span, attributes))

    events: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for span, attributes in decoded:
        event_id = str(attributes["frankengate.canonical.event_id"])
        event: dict[str, Any] = {
            "event_id": event_id,
            "sequence": int(
                attributes.get("frankengate.canonical.sequence", 0)
            ),
            "kind": str(
                attributes.get(
                    "frankengate.canonical.kind", "telemetry.span"
                )
            ),
            "observation_status": str(
                attributes.get(
                    "frankengate.canonical.observation_status",
                    "reconstructed",
                )
            ),
            "source_role": str(
                attributes.get(
                    "frankengate.canonical.source_role", "telemetry"
                )
            ),
            "content": None,
            "telemetry_start_unix_nano": int(span["startTimeUnixNano"]),
            "telemetry_end_unix_nano": int(span["endTimeUnixNano"]),
        }
        parent_span = span.get("parentSpanId")
        if isinstance(parent_span, str) and parent_span in span_to_event:
            event["parent_event_id"] = span_to_event[parent_span]
        if attributes.get("gen_ai.tool.call.id") is not None:
            event["tool_call_id"] = attributes["gen_ai.tool.call.id"]
        if attributes.get("gen_ai.tool.name") is not None:
            event["function_name"] = attributes["gen_ai.tool.name"]
        if attributes.get("frankengate.attempt") is not None:
            event["attempt"] = attributes["frankengate.attempt"]

        relationship_values: dict[str, list[str]] = collections.defaultdict(
            list
        )
        for link in span.get("links", []):
            target = span_to_event.get(str(link.get("spanId")))
            link_attributes = _attributes_to_dict(
                link.get("attributes", [])
            )
            relationship = link_attributes.get(
                "frankengate.relationship"
            )
            if target is not None and isinstance(relationship, str):
                relationship_values[relationship].append(target)
        for relationship, targets in relationship_values.items():
            event[relationship] = (
                targets if relationship.endswith("_event_ids") else targets[0]
            )
        events.append(event)
        items.append(
            _item(
                "event",
                "normalized",
                f"spans[{event_id}]",
                "span identity, type, role, topology, and low-cardinality tool "
                "fields reimported; omitted content remains missing",
                event_id=event_id,
            )
        )
    events.sort(key=lambda event: (event["sequence"], event["event_id"]))
    canonical = {
        "schema_version": CANONICAL_VERSION,
        "trace_id": trace_id,
        "source": {
            "dataset_id": "openinference-otel-projection",
            "dataset_revision": OTEL_TARGET,
            "adapter": "frankengate-openinference-otel-import-v1",
        },
        "task": {"task_id": "projection-reimport"},
        "events": events,
        "outcome": {"value": None, "source": "missing"},
        "loss_receipt": {
            "source_event_count": len(spans),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": [
                "events[].content",
                "events[].telemetry_start_unix_nano",
                "events[].telemetry_end_unix_nano",
            ],
            "known_missing_fields": [
                "authority",
                "environment_state",
                "evaluation_values",
                "replay_contract",
            ],
        },
    }
    receipt = {
        "schema_version": E0_RECEIPT_VERSION,
        "direction": "openinference-otel-to-canonical",
        "source_format": OTEL_TARGET,
        "target_format": CANONICAL_VERSION,
        "source_event_count": len(spans),
        "accounted_source_event_count": len(events),
        "silently_dropped_event_count": 0,
        "source_sha256": digest(projection),
        "projection_sha256": digest(canonical),
        "item_category_counts": {"normalized": len(events)},
        "capability_summary": {},
        "items": items,
    }
    receipt["receipt_id"] = digest(receipt)
    return canonical, receipt


def _edge_set(canonical: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(event["event_id"]), str(event["parent_event_id"]))
        for event in canonical.get("events", [])
        if event.get("parent_event_id") is not None
    }


def _category_totals(receipts: list[dict[str, Any]]) -> dict[str, int]:
    totals: collections.Counter[str] = collections.Counter()
    for receipt in receipts:
        totals.update(receipt.get("item_category_counts", {}))
    return dict(sorted(totals.items()))


def _native_category_totals(
    receipts: list[dict[str, Any]],
) -> dict[str, int]:
    totals: collections.Counter[str] = collections.Counter()
    for receipt in receipts:
        native = receipt.get("native_receipt", {})
        totals.update(
            item.get("category", "missing")
            for item in native.get("items", [])
        )
    return dict(sorted(totals.items()))


def run_conformance(fixtures_root: Path) -> dict[str, Any]:
    fixture_paths = sorted(fixtures_root.glob("*.json"))
    if not fixture_paths:
        raise ProjectionValidationError("no canonical fixtures found")

    source_event_total = 0
    source_edge_total = 0
    atif_reimport_events = 0
    atif_identity_events = 0
    atif_parent_edges = 0
    atif_receipts: list[dict[str, Any]] = []
    otel_reimport_events = 0
    otel_identity_events = 0
    otel_parent_edges = 0
    otel_receipts: list[dict[str, Any]] = []
    capability_fixture_counts: collections.Counter[str] = (
        collections.Counter()
    )
    capability_receipt_checks = {
        "ATIF_v1.7": collections.Counter(),
        "OpenInference_OTel": collections.Counter(),
    }
    deterministic_checks = collections.Counter()

    for fixture_path in fixture_paths:
        source = json.loads(fixture_path.read_text(encoding="utf-8"))
        ordered = _validate_canonical(source)
        source_before = copy.deepcopy(source)
        source_ids = {str(event["event_id"]) for event in ordered}
        source_edges = _edge_set(source)
        source_event_total += len(ordered)
        source_edge_total += len(source_edges)
        capabilities = _capability_paths(source)
        for capability, paths in capabilities.items():
            if paths:
                capability_fixture_counts[capability] += 1

        atif_one, atif_receipt = canonical_to_atif_e0(source)
        atif_two, atif_receipt_two = canonical_to_atif_e0(source)
        if atif_one != atif_two or atif_receipt != atif_receipt_two:
            raise ProjectionValidationError(
                "ATIF projection is not deterministic"
            )
        verify_projection_receipt(source, atif_one, atif_receipt)
        atif_import_one, atif_import_receipt = atif_to_canonical(atif_one)
        atif_import_two, _ = atif_to_canonical(atif_one)
        assert_no_silent_loss(atif_import_receipt)
        if atif_import_one != atif_import_two:
            raise ProjectionValidationError(
                "ATIF reimport is not deterministic"
            )
        imported_ids = {
            str(event["event_id"])
            for event in atif_import_one.get("events", [])
        }
        atif_reimport_events += len(atif_import_one.get("events", []))
        atif_identity_events += len(source_ids & imported_ids)
        atif_parent_edges += len(source_edges & _edge_set(atif_import_one))
        atif_receipts.append(atif_receipt)
        deterministic_checks["atif_projection"] += 1
        deterministic_checks["atif_reimport"] += 1

        otel_one, otel_receipt = canonical_to_openinference_otel(source)
        otel_two, otel_receipt_two = canonical_to_openinference_otel(source)
        if otel_one != otel_two or otel_receipt != otel_receipt_two:
            raise ProjectionValidationError(
                "OpenInference/OTel projection is not deterministic"
            )
        verify_projection_receipt(source, otel_one, otel_receipt)
        otel_import_one, otel_import_receipt = (
            openinference_otel_to_canonical(otel_one)
        )
        otel_import_two, _ = openinference_otel_to_canonical(otel_one)
        if otel_import_one != otel_import_two:
            raise ProjectionValidationError(
                "OpenInference/OTel reimport is not deterministic"
            )
        if otel_import_receipt["silently_dropped_event_count"] != 0:
            raise ProjectionValidationError(
                "OpenInference/OTel reimport silently dropped events"
            )
        imported_ids = {
            str(event["event_id"])
            for event in otel_import_one.get("events", [])
        }
        otel_reimport_events += len(otel_import_one.get("events", []))
        otel_identity_events += len(source_ids & imported_ids)
        otel_parent_edges += len(source_edges & _edge_set(otel_import_one))
        otel_receipts.append(otel_receipt)
        deterministic_checks["otel_projection"] += 1
        deterministic_checks["otel_reimport"] += 1

        for label, receipt in (
            ("ATIF_v1.7", atif_receipt),
            ("OpenInference_OTel", otel_receipt),
        ):
            for capability, paths in capabilities.items():
                if not paths:
                    continue
                summary = receipt["capability_summary"][capability]
                if (
                    summary["receipted_field_count"]
                    != summary["source_field_count"]
                ):
                    raise ProjectionValidationError(
                        f"{label} missed {capability} receipt fields"
                    )
                capability_receipt_checks[label][capability] += 1
        if source != source_before:
            raise ProjectionValidationError(
                "conformance run mutated canonical fixture"
            )
        deterministic_checks["source_immutability"] += 1

    def ratio(numerator: int, denominator: int) -> float | None:
        return (
            round(numerator / denominator, 6)
            if denominator
            else None
        )

    result = {
        "schema_version": E0_RESULT_VERSION,
        "fixture_corpus": {
            "fixtures": len(fixture_paths),
            "canonical_events": source_event_total,
            "canonical_parent_edges": source_edge_total,
            "capability_fixture_counts": dict(
                sorted(capability_fixture_counts.items())
            ),
            "raw_fixtures_or_identifiers_emitted": False,
        },
        "ATIF_v1_7": {
            "target_revision": ATIF_VERSION,
            "reimported_events": atif_reimport_events,
            "canonical_event_identity_retained": atif_identity_events,
            "canonical_event_identity_retention": ratio(
                atif_identity_events, source_event_total
            ),
            "canonical_parent_edges_retained": atif_parent_edges,
            "canonical_parent_edge_retention": ratio(
                atif_parent_edges, source_edge_total
            ),
            "loss_item_categories": _category_totals(atif_receipts),
            "native_adapter_loss_item_categories": (
                _native_category_totals(atif_receipts)
            ),
            "capability_receipt_fixture_counts": dict(
                sorted(capability_receipt_checks["ATIF_v1.7"].items())
            ),
            "silent_drop_count": sum(
                receipt["silently_dropped_event_count"]
                for receipt in atif_receipts
            ),
        },
        "OpenInference_OTel": {
            "target_revision": OTEL_TARGET,
            "openinference_revision": OPENINFERENCE_REVISION,
            "otel_core_revision": OTEL_CORE_REVISION,
            "otel_genai_revision": OTEL_GENAI_REVISION,
            "projected_spans": source_event_total,
            "reimported_events": otel_reimport_events,
            "canonical_event_identity_retained": otel_identity_events,
            "canonical_event_identity_retention": ratio(
                otel_identity_events, source_event_total
            ),
            "canonical_parent_edges_retained": otel_parent_edges,
            "canonical_parent_edge_retention": ratio(
                otel_parent_edges, source_edge_total
            ),
            "loss_item_categories": _category_totals(otel_receipts),
            "capability_receipt_fixture_counts": dict(
                sorted(
                    capability_receipt_checks[
                        "OpenInference_OTel"
                    ].items()
                )
            ),
            "silent_drop_count": sum(
                receipt["silently_dropped_event_count"]
                for receipt in otel_receipts
            ),
        },
        "determinism_and_mutation": {
            "checks": dict(sorted(deterministic_checks.items())),
            "all_passed": all(
                count == len(fixture_paths)
                for count in deterministic_checks.values()
            ),
            "receipt_hashes_cover_source_and_projection": True,
        },
        "claim_limits": [
            (
                "ATIF and OpenInference/OTel are projections, not canonical "
                "authorization or evidence stores"
            ),
            (
                "event identity/topology retention does not imply content, "
                "environment, evaluation, or replay fidelity"
            ),
            (
                "the OTLP envelope is dependency-free research JSON and has "
                "not been round-tripped through a production collector"
            ),
            (
                "synthetic governed fixtures test conformance edge cases, not "
                "population prevalence or enterprise outcomes"
            ),
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run_conformance(args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "fixtures": result["fixture_corpus"]["fixtures"],
                "events": result["fixture_corpus"]["canonical_events"],
                "atif_identity_retention": result["ATIF_v1_7"][
                    "canonical_event_identity_retention"
                ],
                "otel_identity_retention": result["OpenInference_OTel"][
                    "canonical_event_identity_retention"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
