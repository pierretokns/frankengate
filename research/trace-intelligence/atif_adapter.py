#!/usr/bin/env python3
"""Dependency-free ATIF v1.7 projection for research canonical trajectories.

ATIF is an interchange projection, not the source of truth.  This module
therefore returns a machine-readable loss receipt for every conversion.  A
canonical event is either represented by an ATIF construct or named in that
receipt; the adapter never silently drops an event.

The ``extra.frankengate`` profile retains safe identifiers and source
provenance for Frankengate-aware round trips.  Those values are still recorded
as non-portable because a conforming generic ATIF reader can discard ``extra``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

ATIF_VERSION = "ATIF-v1.7"
CANONICAL_VERSION = "canonical-trajectory-v1"
RECEIPT_VERSION = "atif-projection-loss-receipt-v1"
EXTENSION_PROFILE = "https://frankengate.dev/profiles/atif-v1"

_STEP_SOURCES = {"system", "user", "agent"}
_TOOL_TERMINAL_KINDS = {"tool.completed", "tool.failed"}
_SENSITIVE_KEYS = {
    "credential",
    "credential_id",
    "raw_credential",
    "token",
    "api_key",
    "authorization_policy_inputs",
}


class ATIFValidationError(ValueError):
    """Raised when a document cannot safely be interpreted as ATIF."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _safe_copy(value: Any) -> Any:
    """Deep-copy metadata while removing values that must never enter ATIF extra."""
    if isinstance(value, dict):
        return {
            key: _safe_copy(item)
            for key, item in value.items()
            if key.lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_safe_copy(item) for item in value]
    return copy.deepcopy(value)


def _item(
    category: str,
    path: str,
    reason: str,
    *,
    event_id: str | None = None,
    target_path: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"category": category, "path": path, "reason": reason}
    if event_id is not None:
        result["event_id"] = event_id
    if target_path is not None:
        result["target_path"] = target_path
    return result


def _finish_receipt(
    direction: str,
    source_format: str,
    target_format: str,
    source_trace_id: str | None,
    source_event_count: int,
    accounted_event_ids: set[str],
    items: list[dict[str, Any]],
    manifests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": RECEIPT_VERSION,
        "direction": direction,
        "source_format": source_format,
        "target_format": target_format,
        "source_trace_id": source_trace_id,
        "source_event_count": source_event_count,
        "accounted_source_event_count": len(accounted_event_ids),
        "silently_dropped_event_count": 0,
        "items": items,
    }
    if manifests:
        payload["unprojected_event_manifests"] = manifests
    payload["receipt_id"] = _digest(payload)
    return payload


def _content_to_atif(event: dict[str, Any], items: list[dict[str, Any]]) -> Any:
    event_id = str(event["event_id"])
    if event.get("redacted") or event.get("redaction_revision"):
        items.append(
            _item(
                "redacted",
                f"events[{event_id}].content",
                "content was redacted before ATIF projection",
                event_id=event_id,
            )
        )
        return "[REDACTED]"
    content = event.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        valid = True
        for part in content:
            if not isinstance(part, dict) or part.get("type") not in {"text", "image"}:
                valid = False
                break
            if part["type"] == "text" and not isinstance(part.get("text"), str):
                valid = False
                break
            if part["type"] == "image":
                source = part.get("source")
                if (
                    not isinstance(source, dict)
                    or source.get("media_type")
                    not in {"image/jpeg", "image/png", "image/gif", "image/webp"}
                    or not isinstance(source.get("path"), str)
                ):
                    valid = False
                    break
        if valid:
            return copy.deepcopy(content)
        items.append(
            _item(
                "normalized",
                f"events[{event_id}].content",
                "content parts outside ATIF v1.7 text/image schema were serialized as stable JSON",
                event_id=event_id,
            )
        )
        return _stable_json(content)
    if content is None:
        return ""
    items.append(
        _item(
            "normalized",
            f"events[{event_id}].content",
            "non-string content was serialized as stable JSON",
            event_id=event_id,
        )
    )
    return _stable_json(content)


def _extension_for_event(event: dict[str, Any]) -> dict[str, Any]:
    core = {
        "event_id",
        "sequence",
        "kind",
        "observation_status",
        "source_role",
        "content",
        "command",
        "parent_event_id",
        "tool_call_id",
        "function_name",
        "arguments",
        "timestamp",
        "started_at",
        "ended_at",
        "status",
        "error_type",
        "error_code",
        "redacted",
        "redaction_revision",
    }
    metadata = _safe_copy({key: value for key, value in event.items() if key not in core})
    result: dict[str, Any] = {
        "profile": EXTENSION_PROFILE,
        "canonical_event_id": str(event["event_id"]),
        "canonical_kind": str(event["kind"]),
        "observation_status": event.get("observation_status", "observed"),
    }
    if metadata:
        result["canonical_metadata"] = metadata
    return result


def _event_tool_call_id(event: dict[str, Any]) -> str | None:
    value = event.get("tool_call_id") or event.get("call_id")
    return str(value) if value is not None else None


def canonical_to_atif(canonical: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project a canonical trajectory into ATIF v1.7 plus a loss receipt."""
    if canonical.get("schema_version") != CANONICAL_VERSION:
        raise ATIFValidationError(f"expected {CANONICAL_VERSION!r}")
    events = canonical.get("events")
    if not isinstance(events, list):
        raise ATIFValidationError("canonical events must be an array")

    ordered = sorted(events, key=lambda event: (event.get("sequence", 0), str(event.get("event_id", ""))))
    seen_event_ids: set[str] = set()
    for event in ordered:
        if not isinstance(event, dict) or not event.get("event_id") or not event.get("kind"):
            raise ATIFValidationError("every canonical event needs event_id and kind")
        event_id = str(event["event_id"])
        if event_id in seen_event_ids:
            raise ATIFValidationError(f"duplicate canonical event_id {event_id!r}")
        seen_event_ids.add(event_id)

    items: list[dict[str, Any]] = []
    accounted: set[str] = set()
    manifests: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    event_step: dict[str, dict[str, Any]] = {}
    call_step: dict[str, dict[str, Any]] = {}
    call_counts: dict[str, int] = {}

    def new_step(event: dict[str, Any], *, source: str | None = None) -> dict[str, Any]:
        role = source or str(event.get("source_role", "agent"))
        if role not in _STEP_SOURCES:
            items.append(
                _item(
                    "normalized",
                    f"events[{event['event_id']}].source_role",
                    f"ATIF cannot represent actor role {role!r}; normalized to 'agent'",
                    event_id=str(event["event_id"]),
                )
            )
            role = "agent"
        extension = _extension_for_event(event)
        step: dict[str, Any] = {
            "step_id": len(steps) + 1,
            "source": role,
            "message": _content_to_atif(event, items),
            "extra": {"frankengate": extension},
        }
        timestamp = event.get("timestamp") or event.get("started_at") or event.get("observed_at")
        if timestamp is not None:
            step["timestamp"] = timestamp
        if role == "agent":
            if event.get("model_name") or event.get("requested_model"):
                step["model_name"] = event.get("model_name") or event.get("requested_model")
            if event.get("reasoning_content") is not None:
                step["reasoning_content"] = event["reasoning_content"]
            step["llm_call_count"] = int(event.get("llm_call_count", 1))
        steps.append(step)
        event_step[str(event["event_id"])] = step
        return step

    # Conversation/model turns establish ATIF step boundaries first.
    for event in ordered:
        kind = str(event["kind"])
        if kind == "conversation.message" or kind in {"model.completed", "model.failed"}:
            step = new_step(event)
            accounted.add(str(event["event_id"]))
            items.append(
                _item(
                    "exact" if kind == "conversation.message" else "normalized",
                    f"events[{event['event_id']}]",
                    "represented as an ATIF step"
                    if kind == "conversation.message"
                    else "model lifecycle represented as an ATIF agent step",
                    event_id=str(event["event_id"]),
                    target_path=f"steps[{step['step_id'] - 1}]",
                )
            )

    # Tool proposals attach to their causal/model step.  Orphan proposals receive
    # an explicit synthetic step so they remain visible.
    for event in ordered:
        if event["kind"] != "tool.proposed":
            continue
        event_id = str(event["event_id"])
        parent_id = event.get("parent_event_id") or event.get("caused_by_event_id")
        step = event_step.get(str(parent_id)) if parent_id is not None else None
        if step is None:
            step = new_step(
                {
                    **event,
                    "event_id": f"synthetic-dispatch-for-{event_id}",
                    "content": event.get("content") or "Tool proposal",
                    "source_role": "agent",
                    "kind": "conversation.message",
                    "observation_status": "reconstructed",
                }
            )
            items.append(
                _item(
                    "reconstructed",
                    f"events[{event_id}]",
                    "orphan tool proposal required a synthetic ATIF agent step",
                    event_id=event_id,
                    target_path=f"steps[{step['step_id'] - 1}]",
                )
            )
        call_id = _event_tool_call_id(event) or f"reconstructed-{event_id}"
        count = call_counts.get(call_id, 0)
        call_counts[call_id] = count + 1
        projected_call_id = call_id if count == 0 else f"{call_id}__attempt_{count + 1}"
        if count:
            items.append(
                _item(
                    "normalized",
                    f"events[{event_id}].tool_call_id",
                    "repeated tool_call_id was made unique for ATIF; original remains in extra",
                    event_id=event_id,
                )
            )
        tool_call = {
            "tool_call_id": projected_call_id,
            "function_name": str(event.get("function_name") or event.get("tool_name") or event.get("command") or "unknown"),
            "arguments": (
                copy.deepcopy(event.get("arguments"))
                if isinstance(event.get("arguments"), dict)
                else {}
            ),
            "extra": {
                "frankengate": {
                    **_extension_for_event(event),
                    "original_tool_call_id": call_id,
                    "attempt": event.get("attempt"),
                }
            },
        }
        step.setdefault("tool_calls", []).append(tool_call)
        if event.get("arguments") is not None and not isinstance(event.get("arguments"), dict):
            items.append(
                _item(
                    "normalized",
                    f"events[{event_id}].arguments",
                    "ATIF ToolCall arguments must be an object; non-object arguments were omitted",
                    event_id=event_id,
                )
            )
        call_step[projected_call_id] = step
        # Results normally carry the original ID.  Retry attempts may specify
        # attempt to select the rewritten ATIF ID.
        call_step[f"{call_id}#{event.get('attempt', 1)}"] = step
        call_step.setdefault(call_id, step)
        event_step[event_id] = step
        accounted.add(event_id)
        items.append(
            _item(
                "exact",
                f"events[{event_id}]",
                "tool proposal represented by ATIF ToolCall",
                event_id=event_id,
                target_path=f"steps[{step['step_id'] - 1}].tool_calls[{len(step['tool_calls']) - 1}]",
            )
        )

    # Results attach only when correlated.  A result without a visible proposal
    # receives a synthetic proposal and an explicit reconstruction receipt.
    for event in ordered:
        if event["kind"] not in _TOOL_TERMINAL_KINDS:
            continue
        event_id = str(event["event_id"])
        call_id = _event_tool_call_id(event)
        attempt = event.get("attempt", 1)
        step = call_step.get(f"{call_id}#{attempt}") if call_id else None
        step = step or (call_step.get(call_id) if call_id else None)
        if step is None:
            step = new_step(
                {
                    **event,
                    "event_id": f"synthetic-proposal-for-{event_id}",
                    "kind": "conversation.message",
                    "observation_status": "reconstructed",
                    "content": "Reconstructed tool lifecycle",
                    "source_role": "agent",
                }
            )
            projected_call_id = call_id or f"reconstructed-{event_id}"
            step["tool_calls"] = [
                {
                    "tool_call_id": projected_call_id,
                    "function_name": str(event.get("function_name") or event.get("tool_name") or "unknown"),
                    "arguments": {},
                    "extra": {
                        "frankengate": {
                            "profile": EXTENSION_PROFILE,
                            "reconstructed_from_result_event_id": event_id,
                        }
                    },
                }
            ]
            items.append(
                _item(
                    "reconstructed",
                    f"events[{event_id}]",
                    "tool result without a proposal required a synthetic ToolCall",
                    event_id=event_id,
                )
            )
        projected_call_id = str(step["tool_calls"][-1]["tool_call_id"])
        for candidate in step.get("tool_calls", []):
            fg = candidate.get("extra", {}).get("frankengate", {})
            if fg.get("original_tool_call_id") == call_id and (
                event.get("attempt") is None or fg.get("attempt") == event.get("attempt")
            ):
                projected_call_id = str(candidate["tool_call_id"])
                break
        result_extra = {
            "frankengate": {
                **_extension_for_event(event),
                "status": event.get("status") or ("error" if event["kind"] == "tool.failed" else "success"),
                "started_at": event.get("started_at"),
                "ended_at": event.get("ended_at"),
                "error_type": event.get("error_type"),
                "error_code": event.get("error_code"),
                "original_tool_call_id": call_id,
            }
        }
        result = {
            "source_call_id": projected_call_id,
            "content": _content_to_atif(event, items),
            "extra": result_extra,
        }
        step.setdefault("observation", {"results": []})["results"].append(result)
        event_step[event_id] = step
        accounted.add(event_id)
        items.append(
            _item(
                "normalized",
                f"events[{event_id}]",
                "tool result content is first-class; execution status/timing are non-portable extra",
                event_id=event_id,
                target_path=f"steps[{step['step_id'] - 1}].observation.results",
            )
        )

    # Environment and reward facts fit only in the registered extension profile.
    environment_events = {
        "environment.observed",
        "environment.transitioned",
        "environment.checkpointed",
        "evaluation.recorded",
        "outcome.recorded",
    }
    for event in ordered:
        event_id = str(event["event_id"])
        if event_id in accounted or event["kind"] not in environment_events:
            continue
        parent_id = event.get("parent_event_id") or event.get("caused_by_event_id")
        step = event_step.get(str(parent_id)) if parent_id is not None else None
        if step is None:
            step = new_step({**event, "source_role": "system"})
        else:
            step.setdefault("extra", {}).setdefault("frankengate", {}).setdefault(
                "environment_and_reward_events", []
            ).append(_safe_copy(event))
        accounted.add(event_id)
        items.append(
            _item(
                "unsupported",
                f"events[{event_id}]",
                "environment/reward semantics exist only in Frankengate extra, not ATIF v1.7 fields",
                event_id=event_id,
                target_path=f"steps[{step['step_id'] - 1}].extra.frankengate.environment_and_reward_events",
            )
        )

    # All remaining events are explicitly manifested and receipted.  Their
    # content hash proves which source evidence the projection could not carry.
    for event in ordered:
        event_id = str(event["event_id"])
        if event_id in accounted:
            continue
        manifests.append(
            {
                "event_id": event_id,
                "kind": str(event["kind"]),
                "content_sha256": _digest(event),
            }
        )
        accounted.add(event_id)
        items.append(
            _item(
                "dropped",
                f"events[{event_id}]",
                f"ATIF v1.7 dropped the event payload because it has no first-class representation for {event['kind']!r}; manifest and hash remain",
                event_id=event_id,
                target_path="extra.frankengate.unprojected_event_manifests",
            )
        )

    # General graph edges are outside ATIF's sequential/containment model even
    # when their event itself has a first-class projection.
    for event in ordered:
        event_id = str(event["event_id"])
        for field in ("parent_event_id", "caused_by_event_id", "linked_event_ids", "branch_id", "delegation_id"):
            if event.get(field) not in (None, [], ""):
                items.append(
                    _item(
                        "unsupported",
                        f"events[{event_id}].{field}",
                        "causal/branch/delegation graph relation is non-portable in sequential ATIF",
                        event_id=event_id,
                    )
                )

    if not steps:
        synthetic = {
            "event_id": "synthetic-empty-projection",
            "sequence": 0,
            "kind": "conversation.message",
            "observation_status": "reconstructed",
            "source_role": "system",
            "content": "No canonical event has an ATIF first-class representation.",
        }
        new_step(synthetic)
        items.append(
            _item(
                "reconstructed",
                "steps[0]",
                "ATIF requires at least one step; adapter created a non-source placeholder",
                target_path="steps[0]",
            )
        )

    source = canonical.get("source", {})
    agent_info = source.get("agent", {}) if isinstance(source.get("agent"), dict) else {}
    atif: dict[str, Any] = {
        "schema_version": ATIF_VERSION,
        "session_id": canonical.get("run_id") or canonical.get("task", {}).get("session_id") or canonical["trace_id"],
        "trajectory_id": canonical["trace_id"],
        "agent": {
            "name": str(agent_info.get("name") or source.get("harness_name") or source.get("adapter") or "frankengate"),
            "version": str(agent_info.get("version") or source.get("harness_version") or source.get("dataset_revision") or "unknown"),
        },
        "steps": steps,
        "extra": {
            "frankengate": {
                "profile": EXTENSION_PROFILE,
                "canonical_schema_version": CANONICAL_VERSION,
                "source_trace_id": canonical["trace_id"],
                "source": _safe_copy(source),
                "task": _safe_copy(canonical.get("task", {})),
                "outcome": _safe_copy(canonical.get("outcome", {})),
                "unprojected_event_manifests": manifests,
            }
        },
    }
    if agent_info.get("model_name") or source.get("model_name"):
        atif["agent"]["model_name"] = agent_info.get("model_name") or source.get("model_name")
    if source.get("tool_definitions"):
        atif["agent"]["tool_definitions"] = _safe_copy(source["tool_definitions"])

    receipt = _finish_receipt(
        "canonical-to-atif",
        CANONICAL_VERSION,
        ATIF_VERSION,
        str(canonical["trace_id"]),
        len(ordered),
        accounted,
        items,
        manifests,
    )
    atif["extra"]["frankengate"]["loss_receipt_id"] = receipt["receipt_id"]
    return atif, receipt


def _validate_atif(atif: dict[str, Any]) -> None:
    if not isinstance(atif, dict):
        raise ATIFValidationError("ATIF trajectory must be an object")
    if atif.get("schema_version") != ATIF_VERSION:
        raise ATIFValidationError(f"only {ATIF_VERSION!r} is supported")
    if not isinstance(atif.get("agent"), dict):
        raise ATIFValidationError("ATIF agent must be an object")
    for key in ("name", "version"):
        if not isinstance(atif["agent"].get(key), str):
            raise ATIFValidationError(f"ATIF agent.{key} must be a string")
    if not isinstance(atif.get("steps"), list) or not atif["steps"]:
        raise ATIFValidationError("ATIF steps must be a non-empty array")
    for index, step in enumerate(atif["steps"], 1):
        if not isinstance(step, dict):
            raise ATIFValidationError(f"ATIF step {index} must be an object")
        if step.get("step_id") != index:
            raise ATIFValidationError(f"ATIF step_id must be sequential from 1; got {step.get('step_id')!r}")
        if step.get("source") not in _STEP_SOURCES:
            # Tolerant import retains an unknown source as canonical evidence.
            if not isinstance(step.get("source"), str):
                raise ATIFValidationError(f"ATIF step {index} source must be a string")
        if "message" not in step:
            raise ATIFValidationError(f"ATIF step {index} needs message")
        calls = step.get("tool_calls") or []
        if not isinstance(calls, list):
            raise ATIFValidationError(f"ATIF step {index} tool_calls must be an array")
        call_ids: set[str] = set()
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("tool_call_id"), str):
                raise ATIFValidationError(f"ATIF step {index} has invalid ToolCall")
            if call["tool_call_id"] in call_ids:
                raise ATIFValidationError(f"ATIF step {index} has duplicate tool_call_id")
            call_ids.add(call["tool_call_id"])
        observation = step.get("observation")
        if observation is not None:
            if not isinstance(observation, dict) or not isinstance(observation.get("results"), list):
                raise ATIFValidationError(f"ATIF step {index} has invalid observation")
            for result in observation["results"]:
                if not isinstance(result, dict):
                    raise ATIFValidationError(f"ATIF step {index} has invalid observation result")
                source_call_id = result.get("source_call_id")
                if source_call_id is not None and source_call_id not in call_ids:
                    raise ATIFValidationError(
                        f"ATIF step {index} observation references unknown tool_call_id {source_call_id!r}"
                    )


def _message_content(
    value: Any,
    step_index: int,
    items: list[dict[str, Any]],
) -> tuple[Any, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if value is None:
        return None, metadata
    if isinstance(value, str):
        return value, metadata
    if isinstance(value, list):
        normalized: list[dict[str, Any]] = []
        unknown = False
        for part_index, part in enumerate(value):
            if not isinstance(part, dict) or part.get("type") not in {"text", "image"}:
                unknown = True
                items.append(
                    _item(
                        "unsupported",
                        f"steps[{step_index}].message[{part_index}]",
                        "unknown ATIF content part retained in canonical raw_content_parts",
                    )
                )
            normalized.append(copy.deepcopy(part) if isinstance(part, dict) else {"raw": copy.deepcopy(part)})
        metadata["content_parts"] = normalized
        metadata["has_unknown_content_part"] = unknown
        return _stable_json(normalized), metadata
    items.append(
        _item(
            "unsupported",
            f"steps[{step_index}].message",
            "nonconforming ATIF message retained as stable JSON",
        )
    )
    metadata["raw_message"] = copy.deepcopy(value)
    return _stable_json(value), metadata


def atif_to_canonical(atif: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import ATIF v1.7 into canonical events plus an import loss receipt."""
    _validate_atif(atif)
    root_fg = atif.get("extra", {}).get("frankengate", {})
    source_trace_id = root_fg.get("source_trace_id") or atif.get("trajectory_id")
    trace_id = str(source_trace_id) if isinstance(source_trace_id, str) and len(source_trace_id) == 64 else _digest(atif)
    events: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    accounted: set[str] = set()
    semantic_count = 0
    sequence = 0

    for step_index, step in enumerate(atif["steps"]):
        semantic_count += 1
        fg = step.get("extra", {}).get("frankengate", {})
        message_event_id = str(fg.get("canonical_event_id") or f"step-{step_index + 1}:message")
        content, content_metadata = _message_content(step["message"], step_index, items)
        source_role = str(step["source"])
        kind = str(fg.get("canonical_kind") or "conversation.message")
        event: dict[str, Any] = {
            "event_id": message_event_id,
            "sequence": sequence,
            "kind": kind,
            "observation_status": str(fg.get("observation_status") or "observed"),
            "source_role": source_role,
            "content": content,
        }
        sequence += 1
        if step.get("timestamp") is not None:
            event["timestamp"] = step["timestamp"]
        if step.get("model_name") is not None:
            event["model_name"] = step["model_name"]
        if step.get("reasoning_content") is not None:
            event["reasoning_content"] = step["reasoning_content"]
        event.update(_safe_copy(fg.get("canonical_metadata", {})))
        event.update(content_metadata)
        events.append(event)
        accounted.add(f"step:{step_index + 1}")
        items.append(
            _item(
                "exact" if kind == "conversation.message" else "normalized",
                f"steps[{step_index}]",
                "ATIF step imported as canonical event",
                event_id=message_event_id,
                target_path=f"events[{len(events) - 1}]",
            )
        )
        if source_role not in _STEP_SOURCES:
            items.append(
                _item(
                    "unsupported",
                    f"steps[{step_index}].source",
                    "unknown source role retained but is outside ATIF v1.7",
                    event_id=message_event_id,
                )
            )

        call_event_ids: dict[str, str] = {}
        for call_index, call in enumerate(step.get("tool_calls") or []):
            semantic_count += 1
            call_fg = call.get("extra", {}).get("frankengate", {})
            event_id = str(call_fg.get("canonical_event_id") or f"step-{step_index + 1}:call-{call_index + 1}")
            original_call_id = str(call_fg.get("original_tool_call_id") or call["tool_call_id"])
            tool_event = {
                "event_id": event_id,
                "sequence": sequence,
                "kind": str(call_fg.get("canonical_kind") or "tool.proposed"),
                "observation_status": str(call_fg.get("observation_status") or "observed"),
                "source_role": "agent",
                "content": None,
                "command": call.get("function_name"),
                "function_name": call.get("function_name"),
                "arguments": copy.deepcopy(call.get("arguments") or {}),
                "tool_call_id": original_call_id,
                "parent_event_id": message_event_id,
            }
            sequence += 1
            if call_fg.get("attempt") is not None:
                tool_event["attempt"] = call_fg["attempt"]
            tool_event.update(_safe_copy(call_fg.get("canonical_metadata", {})))
            events.append(tool_event)
            call_event_ids[call["tool_call_id"]] = event_id
            accounted.add(f"step:{step_index + 1}:call:{call_index + 1}")
            items.append(
                _item(
                    "exact",
                    f"steps[{step_index}].tool_calls[{call_index}]",
                    "ATIF ToolCall imported as tool.proposed",
                    event_id=event_id,
                    target_path=f"events[{len(events) - 1}]",
                )
            )

        observation = step.get("observation") or {"results": []}
        for result_index, result in enumerate(observation["results"]):
            semantic_count += 1
            result_fg = result.get("extra", {}).get("frankengate", {})
            event_id = str(result_fg.get("canonical_event_id") or f"step-{step_index + 1}:result-{result_index + 1}")
            status = result_fg.get("status")
            kind = str(result_fg.get("canonical_kind") or ("tool.failed" if status == "error" else "tool.completed"))
            source_call_id = result.get("source_call_id")
            original_call_id = result_fg.get("original_tool_call_id") or source_call_id
            result_content, result_metadata = _message_content(
                result.get("content"), step_index, items
            )
            result_event: dict[str, Any] = {
                "event_id": event_id,
                "sequence": sequence,
                "kind": kind if source_call_id is not None else "environment.observed",
                "observation_status": str(result_fg.get("observation_status") or "observed"),
                "source_role": "tool" if source_call_id is not None else "environment",
                "content": result_content,
                "parent_event_id": call_event_ids.get(source_call_id, message_event_id),
            }
            sequence += 1
            if original_call_id is not None:
                result_event["tool_call_id"] = original_call_id
            for field in ("status", "started_at", "ended_at", "error_type", "error_code"):
                if result_fg.get(field) is not None:
                    result_event[field] = result_fg[field]
            result_event.update(_safe_copy(result_fg.get("canonical_metadata", {})))
            result_event.update(result_metadata)
            events.append(result_event)
            accounted.add(f"step:{step_index + 1}:result:{result_index + 1}")
            items.append(
                _item(
                    "normalized",
                    f"steps[{step_index}].observation.results[{result_index}]",
                    "ATIF observation imported as correlated result/environment event",
                    event_id=event_id,
                    target_path=f"events[{len(events) - 1}]",
                )
            )

        environment_events = fg.get("environment_and_reward_events") or []
        for env_index, env_event in enumerate(environment_events):
            semantic_count += 1
            restored = _safe_copy(env_event)
            restored["sequence"] = sequence
            sequence += 1
            restored.setdefault("event_id", f"step-{step_index + 1}:environment-{env_index + 1}")
            restored.setdefault("kind", "environment.observed")
            restored.setdefault("observation_status", "reconstructed")
            restored.setdefault("source_role", "environment")
            restored.setdefault("content", None)
            events.append(restored)
            accounted.add(f"step:{step_index + 1}:environment:{env_index + 1}")
            items.append(
                _item(
                    "unsupported",
                    f"steps[{step_index}].extra.frankengate.environment_and_reward_events[{env_index}]",
                    "environment/reward event restored from non-portable Frankengate extra",
                    event_id=str(restored["event_id"]),
                    target_path=f"events[{len(events) - 1}]",
                )
            )

        # The executable ATIF model has no reward field.  Preserve but do not
        # promote an arbitrary extra.reward to trusted outcome truth.
        reward_locations: list[tuple[str, Any]] = []
        if isinstance(step.get("metrics"), dict) and isinstance(step["metrics"].get("extra"), dict):
            if "reward" in step["metrics"]["extra"]:
                reward_locations.append(("metrics.extra.reward", step["metrics"]["extra"]["reward"]))
        if isinstance(step.get("extra"), dict) and "reward" in step["extra"]:
            reward_locations.append(("extra.reward", step["extra"]["reward"]))
        for reward_index, (location, reward) in enumerate(reward_locations):
            semantic_count += 1
            reward_event_id = f"step-{step_index + 1}:untrusted-reward-{reward_index + 1}"
            events.append(
                {
                    "event_id": reward_event_id,
                    "sequence": sequence,
                    "kind": "evaluation.recorded",
                    "observation_status": "reconstructed",
                    "source_role": "evaluator",
                    "content": None,
                    "reward_total": copy.deepcopy(reward),
                    "reward_trust": "untrusted_atif_extra",
                    "parent_event_id": message_event_id,
                }
            )
            sequence += 1
            accounted.add(f"step:{step_index + 1}:reward:{reward_index + 1}")
            items.append(
                _item(
                    "unsupported",
                    f"steps[{step_index}].{location}",
                    "atif.reward_in_extra: retained as untrusted evidence, not ground truth",
                    event_id=reward_event_id,
                    target_path=f"events[{len(events) - 1}]",
                )
            )

    source = _safe_copy(root_fg.get("source", {}))
    source.setdefault("dataset_id", "atif-import")
    source.setdefault("dataset_revision", atif["schema_version"])
    source.setdefault("adapter", "atif_adapter.py")
    source["format_revision"] = atif["schema_version"]
    source["agent"] = _safe_copy(atif["agent"])
    task = _safe_copy(root_fg.get("task", {}))
    task.setdefault("task_id", atif.get("session_id") or atif.get("trajectory_id") or trace_id)
    outcome = _safe_copy(root_fg.get("outcome", {}))
    outcome.setdefault("value", None)
    outcome.setdefault("source", "missing")

    receipt = _finish_receipt(
        "atif-to-canonical",
        ATIF_VERSION,
        CANONICAL_VERSION,
        trace_id,
        semantic_count,
        accounted,
        items,
    )
    canonical = {
        "schema_version": CANONICAL_VERSION,
        "trace_id": trace_id,
        "source": source,
        "task": task,
        "events": events,
        "outcome": outcome,
        "loss_receipt": {
            "source_event_count": semantic_count,
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": [
                item["path"] for item in items if item["category"] == "reconstructed"
            ],
            "known_missing_fields": [
                item["path"] for item in items if item["category"] == "unsupported"
            ],
            "atif_projection_receipt_id": receipt["receipt_id"],
        },
    }
    return canonical, receipt


def stable_round_trip(atif: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """ATIF → canonical → ATIF with both receipts, useful for conformance tests."""
    canonical, import_receipt = atif_to_canonical(atif)
    projected, export_receipt = canonical_to_atif(canonical)
    return projected, [import_receipt, export_receipt]


def assert_no_silent_loss(receipt: dict[str, Any]) -> None:
    """Fail closed when a receipt violates the adapter accounting contract."""
    if receipt.get("silently_dropped_event_count") != 0:
        raise AssertionError("projection reports silently dropped events")
    if receipt.get("source_event_count") != receipt.get("accounted_source_event_count"):
        raise AssertionError(
            "not every source semantic event is represented or explicitly receipted"
        )
