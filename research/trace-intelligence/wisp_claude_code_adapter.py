#!/usr/bin/env python3
"""Loss-aware Claude Code JSONL adapter for the pinned Wisp corpus.

The adapter produces one canonical trajectory per native JSONL file.  It keeps
the native record in the governed canonical event so schema evolution cannot
silently erase a field, while also projecting useful message, content-block,
tool, session, workspace, and subagent semantics into typed events.

Malformed source bytes are deliberately *not* copied into the output.  Their
line number, byte length, and SHA-256 identity remain, and the omission is
named in the loss receipt.  Callers must not persist or print returned
trajectories outside an appropriately governed store: valid native records and
their canonical content events can contain prompts, reasoning, commands, tool
outputs, paths, and other sensitive material.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ADAPTER_VERSION = "wisp-claude-code-canonical-v1"
CANONICAL_VERSION = "canonical-trajectory-v1"
DEFAULT_DATASET_ID = "crispwisp/wisp-claude-code-sessions"
DEFAULT_DATASET_REVISION = "c2c90b59174318ab0b163ec9c9ac82bb879288ce"

_RECORD_KIND = {
    "user": "conversation.message",
    "assistant": "conversation.message",
    "system": "system.event",
    "attachment": "session.attachment",
    "last-prompt": "session.last_prompt",
    "mode": "session.mode",
    "permission-mode": "session.permission_mode",
    "custom-title": "session.custom_title",
    "agent-name": "session.agent_name",
    "agent-color": "session.agent_color",
    "ai-title": "session.ai_title",
    "queue-operation": "queue.operation",
    "file-history-snapshot": "workspace.file_history_snapshot",
    "started": "subagent.started",
    "result": "subagent.result",
    "pr-link": "workspace.pull_request_link",
}

_BLOCK_KIND = {
    "thinking": "model.thinking",
    "text": "conversation.content.text",
    "tool_use": "tool.proposed",
    "tool_result": "tool.failed",
}


class WispAdapterError(ValueError):
    """Raised for an invalid adapter invocation or failed loss invariant."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def classify_relative_path(relative_path: str | PurePosixPath) -> str:
    """Return the study stratum without inspecting record content."""
    path = PurePosixPath(relative_path)
    text = path.as_posix()
    parts = path.parts
    if "/subagents/workflows/" in f"/{text}":
        return "nested_subagent"
    if len(parts) >= 2 and parts[0] == "-home-me":
        return "main_user"
    if len(parts) >= 2 and parts[0] == "-home-me-ht-hyprland-bench":
        return "benchmark_development"
    if parts and parts[0].startswith("-home-me-ht-hyprland-bench-results-"):
        return "benchmark_task"
    return "other"


def parse_path_context(relative_path: str | PurePosixPath) -> dict[str, Any]:
    """Extract project/session/workflow lineage encoded in Claude Code paths."""
    path = PurePosixPath(relative_path)
    parts = path.parts
    context: dict[str, Any] = {
        "relative_path": path.as_posix(),
        "project_key": parts[0] if parts else None,
        "path_stratum": classify_relative_path(path),
        "source_file_stem": path.stem,
        "is_subagent_workflow": False,
        "parent_session_id": None,
        "workflow_id": None,
        "agent_file_id": None,
        "workflow_file_role": None,
    }
    try:
        marker = parts.index("subagents")
    except ValueError:
        marker = -1
    if marker >= 1 and len(parts) > marker + 3 and parts[marker + 1] == "workflows":
        context.update(
            {
                "is_subagent_workflow": True,
                "parent_session_id": parts[marker - 1],
                "workflow_id": parts[marker + 2],
                "workflow_file_role": (
                    "journal" if path.stem == "journal" else "agent_transcript"
                ),
            }
        )
        if path.stem.startswith("agent-"):
            context["agent_file_id"] = path.stem.removeprefix("agent-")
    return context


def _source_role(record_type: str, record: dict[str, Any]) -> str:
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("role"), str):
        role = message["role"]
        return "agent" if role == "assistant" else role
    if record_type == "assistant":
        return "agent"
    if record_type == "user":
        return "user"
    if record_type == "system":
        return "system"
    if record_type == "result":
        return "tool"
    return "system"


def _record_content(record_type: str, record: dict[str, Any]) -> str | None:
    """Return scalar canonical content; structured/native data stays native."""
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if record_type == "system" and isinstance(record.get("content"), str):
        return record["content"]
    if record_type == "queue-operation" and isinstance(record.get("content"), str):
        return record["content"]
    if record_type == "last-prompt" and isinstance(record.get("lastPrompt"), str):
        return record["lastPrompt"]
    if record_type == "result" and isinstance(record.get("result"), str):
        return record["result"]
    return None


def _session_metadata(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sessionId",
        "promptId",
        "requestId",
        "agentId",
        "slug",
        "cwd",
        "gitBranch",
        "version",
        "entrypoint",
        "userType",
        "promptSource",
        "permissionMode",
        "mode",
        "isSidechain",
        "isMeta",
        "isCompactSummary",
        "isVisibleInTranscriptOnly",
        "operation",
        "subtype",
        "trigger",
        "logicalParentUuid",
        "sourceToolAssistantUUID",
        "sourceToolUseID",
        "interruptedMessageId",
        "messageId",
        "isSnapshotUpdate",
        "retractedMessageUuids",
    )
    return {key: copy.deepcopy(record[key]) for key in keys if key in record}


def _record_event_id(
    relative_path: str, line_number: int, raw_sha256: str
) -> str:
    identity = f"{relative_path}\0{line_number}\0{raw_sha256}".encode("utf-8")
    return f"record-{hashlib.sha256(identity).hexdigest()}"


def _block_event_id(record_event_id: str, block_index: int, block: Any) -> str:
    identity = (
        f"{record_event_id}\0{block_index}\0{_sha256_value(block)}".encode("utf-8")
    )
    return f"block-{hashlib.sha256(identity).hexdigest()}"


def _iter_lines(source_bytes: bytes) -> Iterable[tuple[int, bytes]]:
    # splitlines(keepends=True) preserves the byte identity of every physical
    # line, including final lines without a newline.
    yield from enumerate(source_bytes.splitlines(keepends=True), start=1)


def adapt_wisp_jsonl_bytes(
    source_bytes: bytes,
    *,
    relative_path: str,
    dataset_id: str = DEFAULT_DATASET_ID,
    dataset_revision: str = DEFAULT_DATASET_REVISION,
) -> dict[str, Any]:
    """Convert one Claude Code JSONL file to the canonical research format."""
    if not isinstance(source_bytes, bytes):
        raise WispAdapterError("source_bytes must be bytes")
    normalized_path = PurePosixPath(relative_path).as_posix()
    if normalized_path in {"", "."} or normalized_path.startswith("../"):
        raise WispAdapterError("relative_path must identify a file inside the corpus")

    file_sha256 = _sha256_bytes(source_bytes)
    path_context = parse_path_context(normalized_path)
    records: list[dict[str, Any]] = []
    losses: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []
    source_block_count = 0

    for line_number, raw_line in _iter_lines(source_bytes):
        raw_sha256 = _sha256_bytes(raw_line)
        identity = {
            "relative_path": normalized_path,
            "line_number": line_number,
            "raw_sha256": raw_sha256,
            "raw_byte_length": len(raw_line),
        }
        try:
            decoded = raw_line.decode("utf-8")
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            losses.append(
                {
                    "category": "malformed_source_bytes_not_retained",
                    **identity,
                    "error_type": type(error).__name__,
                    "reason": (
                        "malformed source bytes are represented by identity and "
                        "length, but raw bytes are not copied into canonical output"
                    ),
                }
            )
            records.append(
                {
                    "identity": identity,
                    "record": None,
                    "record_type": "malformed",
                    "malformed": True,
                }
            )
            continue

        if not isinstance(parsed, dict):
            unknowns.append(
                {
                    "category": "non_object_json_record",
                    **identity,
                    "json_type": type(parsed).__name__,
                    "handling": "retained exactly in native_record",
                }
            )
            records.append(
                {
                    "identity": identity,
                    "record": parsed,
                    "record_type": "non-object",
                    "malformed": False,
                }
            )
            continue

        record_type = str(parsed.get("type", "<missing>"))
        if record_type not in _RECORD_KIND:
            unknowns.append(
                {
                    "category": "unknown_record_type",
                    **identity,
                    "record_type": record_type,
                    "handling": "retained exactly in native_record",
                }
            )
        message = parsed.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                source_block_count += len(content)
        records.append(
            {
                "identity": identity,
                "record": parsed,
                "record_type": record_type,
                "malformed": False,
            }
        )

    uuid_to_record_events: dict[str, list[str]] = {}
    for item in records:
        record = item["record"]
        event_id = _record_event_id(
            normalized_path,
            item["identity"]["line_number"],
            item["identity"]["raw_sha256"],
        )
        item["event_id"] = event_id
        if isinstance(record, dict) and isinstance(record.get("uuid"), str):
            uuid_to_record_events.setdefault(record["uuid"], []).append(event_id)

    events: list[dict[str, Any]] = []
    tool_proposals: dict[str, list[dict[str, Any]]] = {}
    pending_tool_results: list[dict[str, Any]] = []
    accounted_blocks = 0

    def append_event(event: dict[str, Any]) -> None:
        event["sequence"] = len(events)
        events.append(event)

    for item in records:
        identity = item["identity"]
        event_id = item["event_id"]
        record = item["record"]
        if item["malformed"]:
            append_event(
                {
                    "event_id": event_id,
                    "kind": "source.malformed_record",
                    "observation_status": "missing",
                    "source_role": "system",
                    "content": None,
                    "source_record_identity": identity,
                    "path_context": copy.deepcopy(path_context),
                    "loss_status": "raw_source_not_retained",
                }
            )
            continue

        if not isinstance(record, dict):
            append_event(
                {
                    "event_id": event_id,
                    "kind": "source.unknown_json_record",
                    "observation_status": "observed",
                    "source_role": "system",
                    "content": None,
                    "source_record_identity": identity,
                    "path_context": copy.deepcopy(path_context),
                    "native_record": copy.deepcopy(record),
                }
            )
            continue

        record_type = item["record_type"]
        parent_uuid = record.get("parentUuid")
        parent_event_id: str | None = None
        if isinstance(parent_uuid, str) and parent_uuid:
            candidates = uuid_to_record_events.get(parent_uuid, [])
            if len(candidates) == 1:
                parent_event_id = candidates[0]
            elif not candidates:
                unknowns.append(
                    {
                        "category": "dangling_parent_uuid",
                        **identity,
                        "uuid": record.get("uuid"),
                        "parent_uuid": parent_uuid,
                        "handling": "parent_event_id left null; native value retained",
                    }
                )
            else:
                unknowns.append(
                    {
                        "category": "ambiguous_parent_uuid",
                        **identity,
                        "uuid": record.get("uuid"),
                        "parent_uuid": parent_uuid,
                        "candidate_count": len(candidates),
                        "handling": "parent_event_id left null; native value retained",
                    }
                )

        base_event: dict[str, Any] = {
            "event_id": event_id,
            "kind": _RECORD_KIND.get(record_type, "source.unknown_record"),
            "observation_status": "observed",
            "source_role": _source_role(record_type, record),
            "content": _record_content(record_type, record),
            "parent_event_id": parent_event_id,
            "source_record_identity": {
                **identity,
                "uuid": record.get("uuid"),
                "parent_uuid": parent_uuid,
                "record_type": record_type,
            },
            "path_context": copy.deepcopy(path_context),
            "session_metadata": _session_metadata(record),
            "native_record": copy.deepcopy(record),
        }
        if record.get("timestamp") is not None:
            base_event["timestamp"] = record["timestamp"]
        if record.get("sessionId") is not None:
            base_event["session_id"] = record["sessionId"]
        if record.get("uuid") is not None:
            base_event["source_uuid"] = record["uuid"]
        if parent_uuid is not None:
            base_event["source_parent_uuid"] = parent_uuid
        if record_type == "system":
            base_event["system_semantics"] = {
                key: copy.deepcopy(record[key])
                for key in (
                    "subtype",
                    "trigger",
                    "durationMs",
                    "messageCount",
                    "compactMetadata",
                    "logicalParentUuid",
                    "retractedMessageUuids",
                    "originalModel",
                    "fallbackModel",
                    "apiRefusalCategory",
                )
                if key in record
            }
        if record_type == "file-history-snapshot":
            base_event["workspace_snapshot"] = {
                "message_id": record.get("messageId"),
                "is_update": record.get("isSnapshotUpdate"),
                "snapshot": copy.deepcopy(record.get("snapshot")),
            }
        if record_type == "queue-operation":
            base_event["queue_operation"] = {
                "operation": record.get("operation"),
                "content": copy.deepcopy(record.get("content")),
            }
        if record_type in {"mode", "permission-mode"}:
            base_event["interaction_policy"] = {
                "mode": record.get("mode"),
                "permission_mode": record.get("permissionMode"),
            }
        if record_type in {"started", "result"}:
            base_event["subagent_workflow"] = {
                "agent_id": record.get("agentId"),
                "key": copy.deepcopy(record.get("key")),
                "result": copy.deepcopy(record.get("result")),
                **copy.deepcopy(path_context),
            }
        if record.get("isCompactSummary") is True:
            base_event["compaction"] = {
                "is_compact_summary": True,
                "source": "user_record",
            }
        append_event(base_event)

        message = record.get("message")
        if not isinstance(message, dict):
            continue
        message_content = message.get("content")
        if isinstance(message_content, str):
            block = {"type": "text", "text": message_content}
            blocks: list[Any] = [block]
            # Scalar content is normalized into a synthetic content block, but
            # is not counted as a native list block in the loss invariant.
            native_list = False
        elif isinstance(message_content, list):
            blocks = message_content
            native_list = True
        else:
            blocks = []
            native_list = False

        for block_index, block in enumerate(blocks):
            if native_list:
                accounted_blocks += 1
            block_event_id = _block_event_id(event_id, block_index, block)
            if not isinstance(block, dict):
                unknowns.append(
                    {
                        "category": "non_object_content_block",
                        **identity,
                        "block_index": block_index,
                        "json_type": type(block).__name__,
                        "handling": "retained exactly in native_block",
                    }
                )
                append_event(
                    {
                        "event_id": block_event_id,
                        "kind": "content.unknown",
                        "observation_status": "observed",
                        "source_role": base_event["source_role"],
                        "content": None,
                        "parent_event_id": event_id,
                        "record_event_id": event_id,
                        "content_block_index": block_index,
                        "native_block": copy.deepcopy(block),
                        "source_record_identity": identity,
                        "path_context": copy.deepcopy(path_context),
                    }
                )
                continue

            block_type = str(block.get("type", "<missing>"))
            kind = _BLOCK_KIND.get(block_type, "content.unknown")
            if block_type == "tool_result" and not (
                block.get("is_error") is True or block.get("isError") is True
            ):
                kind = "tool.completed"
            if block_type not in _BLOCK_KIND:
                unknowns.append(
                    {
                        "category": "unknown_content_block_type",
                        **identity,
                        "block_index": block_index,
                        "block_type": block_type,
                        "handling": "retained exactly in native_block",
                    }
                )

            content: str | None = None
            if block_type == "thinking" and isinstance(block.get("thinking"), str):
                content = block["thinking"]
            elif block_type == "text" and isinstance(block.get("text"), str):
                content = block["text"]
            elif block_type == "tool_result":
                raw_content = block.get("content")
                if isinstance(raw_content, str):
                    content = raw_content
                elif raw_content is not None:
                    content = _stable_json(raw_content)
                    normalizations.append(
                        {
                            "category": "structured_tool_result_content",
                            **identity,
                            "block_index": block_index,
                            "handling": (
                                "stable JSON in canonical content; exact value "
                                "retained in native_block"
                            ),
                        }
                    )

            block_event: dict[str, Any] = {
                "event_id": block_event_id,
                "kind": kind,
                "observation_status": "observed",
                "source_role": (
                    "tool" if block_type == "tool_result" else base_event["source_role"]
                ),
                "content": content,
                "parent_event_id": event_id,
                "record_event_id": event_id,
                "content_block_index": block_index,
                "native_block": copy.deepcopy(block),
                "source_record_identity": identity,
                "path_context": copy.deepcopy(path_context),
            }
            if record.get("timestamp") is not None:
                block_event["timestamp"] = record["timestamp"]

            if block_type == "tool_use":
                call_id = block.get("id")
                block_event.update(
                    {
                        "tool_call_id": call_id,
                        "function_name": block.get("name"),
                        "arguments": copy.deepcopy(block.get("input")),
                        "caller": copy.deepcopy(block.get("caller")),
                        "correlation_status": (
                            "proposal_has_call_id"
                            if isinstance(call_id, str) and call_id
                            else "proposal_missing_call_id"
                        ),
                    }
                )
                if isinstance(call_id, str) and call_id:
                    tool_proposals.setdefault(call_id, []).append(block_event)
                else:
                    unknowns.append(
                        {
                            "category": "tool_proposal_missing_call_id",
                            **identity,
                            "block_index": block_index,
                            "handling": "proposal retained without correlation",
                        }
                    )
            elif block_type == "tool_result":
                call_id = block.get("tool_use_id")
                block_event.update(
                    {
                        "tool_call_id": call_id,
                        "is_error": (
                            block.get("is_error") is True
                            or block.get("isError") is True
                        ),
                        "source_record_parent_event_id": event_id,
                    }
                )
                pending_tool_results.append(block_event)
            append_event(block_event)

    sequence_by_event_id = {event["event_id"]: event["sequence"] for event in events}
    for result in pending_tool_results:
        call_id = result.get("tool_call_id")
        candidates = tool_proposals.get(call_id, []) if isinstance(call_id, str) else []
        prior = [
            event
            for event in candidates
            if sequence_by_event_id[event["event_id"]] < result["sequence"]
        ]
        if len(prior) == 1:
            proposal = prior[0]
            result["parent_event_id"] = proposal["event_id"]
            result["correlated_tool_proposal_event_id"] = proposal["event_id"]
            result["correlation_status"] = "exact_unique_prior"
        elif len(prior) > 1:
            proposal = prior[-1]
            result["parent_event_id"] = proposal["event_id"]
            result["correlated_tool_proposal_event_id"] = proposal["event_id"]
            result["correlation_status"] = "nearest_prior_ambiguous"
            unknowns.append(
                {
                    "category": "ambiguous_tool_result_correlation",
                    **result["source_record_identity"],
                    "tool_call_id": call_id,
                    "candidate_count": len(prior),
                    "selected_event_id": proposal["event_id"],
                    "handling": "nearest prior proposal selected; ambiguity retained",
                }
            )
        else:
            result["correlation_status"] = "unresolved"
            unknowns.append(
                {
                    "category": "unresolved_tool_result_correlation",
                    **result["source_record_identity"],
                    "tool_call_id": call_id,
                    "handling": (
                        "result remains attached to source record; native call "
                        "identifier retained"
                    ),
                }
            )

    source_line_count = len(records)
    receipt = {
        "schema_version": "wisp-claude-code-loss-receipt-v1",
        "source_line_count": source_line_count,
        "source_record_count": source_line_count,
        "accounted_source_record_count": source_line_count,
        "source_content_block_count": source_block_count,
        "accounted_source_content_block_count": accounted_blocks,
        "canonical_event_count": len(events),
        "silently_dropped_record_count": 0,
        "silently_dropped_content_block_count": 0,
        "losses": losses,
        "unknowns": unknowns,
        "normalizations": normalizations,
    }
    receipt["receipt_id"] = _sha256_value(receipt)

    session_ids = sorted(
        {
            str(item["record"]["sessionId"])
            for item in records
            if isinstance(item["record"], dict)
            and item["record"].get("sessionId") is not None
        }
    )
    inferred_session_id = (
        path_context.get("parent_session_id")
        or (session_ids[0] if len(session_ids) == 1 else None)
        or PurePosixPath(normalized_path).stem
    )
    trace_identity = {
        "dataset_id": dataset_id,
        "dataset_revision": dataset_revision,
        "relative_path": normalized_path,
        "source_file_sha256": file_sha256,
    }
    trajectory = {
        "schema_version": CANONICAL_VERSION,
        "trace_id": _sha256_value(trace_identity),
        "source": {
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
            "adapter": ADAPTER_VERSION,
            "native_format": "Claude Code JSONL",
            "relative_path": normalized_path,
            "source_file_sha256": file_sha256,
            "source_file_byte_length": len(source_bytes),
            "path_context": path_context,
            "observed_session_ids": session_ids,
        },
        "task": {
            "task_id": inferred_session_id,
            "session_id": inferred_session_id,
            "project_key": path_context["project_key"],
            "path_stratum": path_context["path_stratum"],
        },
        "events": events,
        "outcome": {
            "value": None,
            "source": "not_present_in_native_transcript",
        },
        "loss_receipt": receipt,
    }
    assert_no_silent_drops(trajectory)
    return trajectory


def adapt_wisp_file(
    source_path: Path,
    *,
    corpus_root: Path,
    dataset_id: str = DEFAULT_DATASET_ID,
    dataset_revision: str = DEFAULT_DATASET_REVISION,
) -> dict[str, Any]:
    """Read and adapt one file while requiring an unambiguous corpus-relative path."""
    source_path = source_path.resolve()
    corpus_root = corpus_root.resolve()
    try:
        relative_path = source_path.relative_to(corpus_root).as_posix()
    except ValueError as error:
        raise WispAdapterError("source_path must be inside corpus_root") from error
    return adapt_wisp_jsonl_bytes(
        source_path.read_bytes(),
        relative_path=relative_path,
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
    )


def canonicalize_wisp_file(
    source_path: Path,
    corpus_root: Path,
    manifest: dict[str, Any] | Path,
) -> dict[str, Any]:
    """Stable loader API returning one trajectory and its embedded receipts.

    ``manifest`` may be an already parsed dataset manifest or its JSON path.
    The pinned dataset identity is carried into the trace ID and source
    provenance, so a loader cannot accidentally merge revisions.
    """
    if isinstance(manifest, Path):
        parsed_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    elif isinstance(manifest, dict):
        parsed_manifest = manifest
    else:
        raise WispAdapterError("manifest must be a dictionary or JSON Path")
    dataset_id = parsed_manifest.get("dataset_id")
    dataset_revision = parsed_manifest.get("dataset_revision")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise WispAdapterError("manifest needs a non-empty dataset_id")
    if not isinstance(dataset_revision, str) or not dataset_revision:
        raise WispAdapterError("manifest needs a non-empty dataset_revision")
    trajectory = adapt_wisp_file(
        source_path,
        corpus_root=corpus_root,
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
    )
    trajectory["source"]["manifest_schema_version"] = parsed_manifest.get(
        "schema_version"
    )
    return trajectory


def assert_no_silent_drops(trajectory: dict[str, Any]) -> None:
    """Prove the adapter's record/block accounting invariants."""
    receipt = trajectory.get("loss_receipt")
    if not isinstance(receipt, dict):
        raise WispAdapterError("trajectory has no loss receipt")
    checks = {
        "source records": (
            receipt.get("source_record_count"),
            receipt.get("accounted_source_record_count"),
        ),
        "source content blocks": (
            receipt.get("source_content_block_count"),
            receipt.get("accounted_source_content_block_count"),
        ),
        "canonical events": (
            receipt.get("canonical_event_count"),
            len(trajectory.get("events", [])),
        ),
    }
    for label, (expected, actual) in checks.items():
        if expected != actual:
            raise WispAdapterError(
                f"{label} accounting mismatch: expected {expected!r}, got {actual!r}"
            )
    if receipt.get("silently_dropped_record_count") != 0:
        raise WispAdapterError("silent source-record drops are forbidden")
    if receipt.get("silently_dropped_content_block_count") != 0:
        raise WispAdapterError("silent content-block drops are forbidden")
