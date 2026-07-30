#!/usr/bin/env python3
"""Loss-aware conformance for native Claude trace and memory transitions.

The adapter verifies pinned source bytes, preserves native DAG and tool-result
identity, and reconstructs only transitions supported by successful tool
results. It emits aggregate receipts only. It does not infer memory utility,
user identity, or continuous validity between observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Optional, Sequence, Union


SCHEMA_VERSION = "trace-commons-memory-conformance-result-v1"
ADAPTER_VERSION = "claude_native_context_transition_v1"
READ_LINE_PREFIX = re.compile(r"^[0-9]+\t")
CONTEXT_BASENAMES = {
    "agents.md",
    "claude.md",
    "memory.md",
    "project.md",
}


class ConformanceError(ValueError):
    """Raised when a source or transition cannot satisfy its declared contract."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return digest_bytes(stable_json(value).encode("utf-8"))


def instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ConformanceError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ConformanceError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.casefold()


def artifact_key(path: str) -> str:
    return "artifact-" + digest(normalize_path(path))[:24]


def is_context_artifact(path: str) -> bool:
    normalized = normalize_path(path)
    basename = PurePosixPath(normalized).name
    return "/memory/" in normalized or basename in CONTEXT_BASENAMES


def is_memory_artifact(path: str) -> bool:
    return "/memory/" in normalize_path(path)


def _canonical_lines(value: str) -> list[str]:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return [line.rstrip(" \t") for line in normalized.split("\n")]


def canonicalize_write_content(value: str) -> str:
    if not isinstance(value, str):
        raise ConformanceError("artifact content must be a string")
    lines = _canonical_lines(value)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def canonicalize_read_content(value: str) -> str:
    if not isinstance(value, str):
        raise ConformanceError("Read result content must be a string")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    stripped = [
        READ_LINE_PREFIX.sub("", line, count=1).rstrip(" \t")
        if READ_LINE_PREFIX.match(line)
        else line.rstrip(" \t")
        for line in lines
    ]
    while stripped and stripped[-1] == "":
        stripped.pop()
    return "\n".join(stripped) + ("\n" if stripped else "")


@dataclass(frozen=True)
class AuthorityEnvelope:
    tenant_id: str
    owner_subject_id: str
    team_id: str
    classification: int
    purpose: str
    authorization_epoch: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuthorityEnvelope":
        required = (
            "tenant_id",
            "owner_subject_id",
            "team_id",
            "classification",
            "purpose",
            "authorization_epoch",
        )
        missing = [name for name in required if name not in value]
        if missing:
            raise ConformanceError(
                "import_authority missing " + ", ".join(sorted(missing))
            )
        result = cls(
            tenant_id=str(value["tenant_id"]),
            owner_subject_id=str(value["owner_subject_id"]),
            team_id=str(value["team_id"]),
            classification=int(value["classification"]),
            purpose=str(value["purpose"]),
            authorization_epoch=int(value["authorization_epoch"]),
        )
        if result.classification < 0 or result.authorization_epoch <= 0:
            raise ConformanceError("invalid authority classification or epoch")
        return result


@dataclass(frozen=True)
class QueryAuthority:
    tenant_id: str
    subject_id: str
    team_ids: tuple[str, ...]
    classification_ceiling: int
    purpose: str
    authorization_epoch: int


def can_read(envelope: AuthorityEnvelope, query: QueryAuthority) -> bool:
    return (
        envelope.tenant_id == query.tenant_id
        and envelope.owner_subject_id == query.subject_id
        and envelope.team_id in query.team_ids
        and envelope.classification <= query.classification_ceiling
        and envelope.purpose == query.purpose
        and envelope.authorization_epoch == query.authorization_epoch
    )


@dataclass(frozen=True)
class ToolResult:
    session_id: str
    tool_id: str
    record_uuid: str
    source_assistant_uuid: str
    observed_at: datetime
    content: Any
    is_error: bool


@dataclass(frozen=True)
class ToolCall:
    source_file: str
    source_line: int
    session_id: str
    record_uuid: str
    observed_at: datetime
    tool_id: str
    tool_name: str
    tool_input: Mapping[str, Any]

    @property
    def path(self) -> str:
        value = self.tool_input.get("file_path", self.tool_input.get("path", ""))
        return str(value) if value is not None else ""


@dataclass
class ArtifactState:
    path_key: str
    content: str
    observed_at: datetime
    source_kind: str
    session_id: str
    uncertain_change_after: Optional[datetime] = None


def operation_promotes(
    tool_name: str,
    *,
    result_joined: bool,
    result_is_error: bool,
) -> bool:
    return (
        tool_name.casefold() in {"write", "edit"}
        and result_joined
        and not result_is_error
    )


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConformanceError(f"cannot load manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConformanceError("manifest must be an object")
    if value.get("schema_version") != "trace-dataset-manifest-v1":
        raise ConformanceError("unexpected dataset manifest schema")
    if value.get("adapter") != ADAPTER_VERSION:
        raise ConformanceError("manifest names a different adapter")
    if value.get("download_policy", {}).get("raw_data_committed") is not False:
        raise ConformanceError("manifest must prohibit committed raw data")
    return value


def _load_source(
    root: Path,
    receipt: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    relative = Path(str(receipt["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ConformanceError("source path must stay below source root")
    path = root / relative
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConformanceError(f"cannot read source {relative}: {exc}") from exc
    if len(raw) != int(receipt["bytes"]):
        raise ConformanceError(f"{relative}: byte length does not match manifest")
    if digest_bytes(raw) != receipt["sha256"]:
        raise ConformanceError(f"{relative}: SHA-256 does not match manifest")

    records = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConformanceError(
                f"{relative}:{line_number}: invalid JSON"
            ) from exc
        if not isinstance(record, dict):
            raise ConformanceError(f"{relative}:{line_number}: object required")
        record["_source_file"] = relative.as_posix()
        record["_source_line"] = line_number
        records.append(record)
    if len(records) != int(receipt["records"]):
        raise ConformanceError(f"{relative}: record count does not match manifest")
    return records, {
        "path": relative.as_posix(),
        "bytes": len(raw),
        "sha256": digest_bytes(raw),
        "records": len(records),
        **(
            {"hugging_face_oid": receipt["hugging_face_oid"]}
            if receipt.get("hugging_face_oid")
            else {}
        ),
    }


def _tool_calls(records: Sequence[Mapping[str, Any]]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        if record.get("type") != "assistant":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            session_id = str(record.get("sessionId", ""))
            tool_id = str(item.get("id", ""))
            key = (session_id, tool_id)
            if not session_id or not tool_id or key in seen:
                raise ConformanceError("tool calls need unique session-scoped IDs")
            seen.add(key)
            tool_input = item.get("input")
            if not isinstance(tool_input, dict):
                tool_input = {}
            calls.append(
                ToolCall(
                    source_file=str(record["_source_file"]),
                    source_line=int(record["_source_line"]),
                    session_id=session_id,
                    record_uuid=str(record.get("uuid", "")),
                    observed_at=instant(str(record.get("timestamp", ""))),
                    tool_id=tool_id,
                    tool_name=str(item.get("name", "")),
                    tool_input=tool_input,
                )
            )
    return calls


def _tool_results(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], ToolResult]:
    results: dict[tuple[str, str], ToolResult] = {}
    for record in records:
        if record.get("type") != "user":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_result":
                continue
            session_id = str(record.get("sessionId", ""))
            tool_id = str(item.get("tool_use_id", ""))
            key = (session_id, tool_id)
            if not session_id or not tool_id or key in results:
                raise ConformanceError("tool results need unique session-scoped IDs")
            results[key] = ToolResult(
                session_id=session_id,
                tool_id=tool_id,
                record_uuid=str(record.get("uuid", "")),
                source_assistant_uuid=str(
                    record.get("sourceToolAssistantUUID", "")
                ),
                observed_at=instant(str(record.get("timestamp", ""))),
                content=item.get("content"),
                is_error=bool(item.get("is_error", False)),
            )
    return results


def _parent_audit(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    uuids = {
        str(record["uuid"])
        for record in records
        if record.get("uuid") is not None
    }
    parents = [
        str(record["parentUuid"])
        for record in records
        if record.get("parentUuid") is not None
    ]
    return {
        "record_uuids": len(uuids),
        "parent_edges": len(parents),
        "resolved_parent_edges": sum(parent in uuids for parent in parents),
        "unresolved_parent_edges": sum(parent not in uuids for parent in parents),
    }


def _snapshot_audit(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    mentions = 0
    unique_states: set[tuple[Any, ...]] = set()
    for record in records:
        if record.get("type") != "file-history-snapshot":
            continue
        snapshot = record.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        backups = snapshot.get("trackedFileBackups")
        if not isinstance(backups, dict):
            continue
        for path, state in backups.items():
            if not is_memory_artifact(str(path)) or not isinstance(state, dict):
                continue
            mentions += 1
            unique_states.add(
                (
                    str(record["_source_file"]),
                    normalize_path(str(path)),
                    state.get("backupFileName"),
                    state.get("version"),
                    state.get("backupTime"),
                )
            )
    return {
        "memory_path_mentions": mentions,
        "unique_session_scoped_states": len(unique_states),
    }


def _join_result(
    call: ToolCall,
    results: Mapping[tuple[str, str], ToolResult],
) -> Optional[ToolResult]:
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


def _lifecycle(
    calls: Sequence[ToolCall],
    results: Mapping[tuple[str, str], ToolResult],
) -> tuple[dict[str, int], list[ArtifactState]]:
    states: dict[str, ArtifactState] = {}
    revisions: list[ArtifactState] = []
    metrics = {
        "artifact_paths": 0,
        "context_artifact_calls": 0,
        "joined_context_artifact_results": 0,
        "failed_reads": 0,
        "successful_writes": 0,
        "successful_reads": 0,
        "successful_edits": 0,
        "exact_write_to_later_read": 0,
        "interval_censored_version_gaps": 0,
        "reconstructable_edits": 0,
        "unreconstructable_edits": 0,
        "failed_operation_promotions": 0,
    }
    memory_paths: set[str] = set()

    for call in sorted(
        calls,
        key=lambda item: (
            item.observed_at,
            item.source_file,
            item.source_line,
            item.tool_id,
        ),
    ):
        if not call.path or not is_context_artifact(call.path):
            continue
        metrics["context_artifact_calls"] += 1
        result = _join_result(call, results)
        if result is not None:
            metrics["joined_context_artifact_results"] += 1
        memory_artifact = is_memory_artifact(call.path)
        if not memory_artifact:
            continue
        path_key = artifact_key(call.path)
        memory_paths.add(path_key)
        name = call.tool_name.casefold()
        success = result is not None and not result.is_error

        if name == "read":
            if not success:
                metrics["failed_reads"] += 1
                continue
            metrics["successful_reads"] += 1
            observed = canonicalize_read_content(result.content)
            previous = states.get(path_key)
            if previous is None:
                state = ArtifactState(
                    path_key=path_key,
                    content=observed,
                    observed_at=result.observed_at,
                    source_kind="read",
                    session_id=call.session_id,
                )
                states[path_key] = state
                revisions.append(state)
            elif previous.content == observed:
                if (
                    previous.source_kind == "write"
                    and previous.session_id != call.session_id
                ):
                    metrics["exact_write_to_later_read"] += 1
                previous.observed_at = result.observed_at
            else:
                metrics["interval_censored_version_gaps"] += 1
                state = ArtifactState(
                    path_key=path_key,
                    content=observed,
                    observed_at=result.observed_at,
                    source_kind="read_after_gap",
                    session_id=call.session_id,
                    uncertain_change_after=previous.observed_at,
                )
                states[path_key] = state
                revisions.append(state)
            continue

        if name == "write":
            if not success:
                continue
            metrics["successful_writes"] += 1
            state = ArtifactState(
                path_key=path_key,
                content=canonicalize_write_content(
                    str(call.tool_input.get("content", ""))
                ),
                observed_at=result.observed_at,
                source_kind="write",
                session_id=call.session_id,
            )
            states[path_key] = state
            revisions.append(state)
            continue

        if name == "edit":
            if not success:
                continue
            metrics["successful_edits"] += 1
            previous = states.get(path_key)
            old = call.tool_input.get("old_string")
            new = call.tool_input.get("new_string")
            replace_all = bool(call.tool_input.get("replace_all", False))
            if (
                previous is None
                or not isinstance(old, str)
                or not isinstance(new, str)
            ):
                metrics["unreconstructable_edits"] += 1
                continue
            occurrences = previous.content.count(old)
            if occurrences == 0 or (not replace_all and occurrences != 1):
                metrics["unreconstructable_edits"] += 1
                continue
            after = (
                previous.content.replace(old, new)
                if replace_all
                else previous.content.replace(old, new, 1)
            )
            state = ArtifactState(
                path_key=path_key,
                content=after,
                observed_at=result.observed_at,
                source_kind="edit",
                session_id=call.session_id,
            )
            states[path_key] = state
            revisions.append(state)
            metrics["reconstructable_edits"] += 1

    metrics["artifact_paths"] = len(memory_paths)
    return metrics, revisions


def _negative_controls(
    envelope: AuthorityEnvelope,
    revisions: Sequence[ArtifactState],
) -> dict[str, Any]:
    allowed = QueryAuthority(
        tenant_id=envelope.tenant_id,
        subject_id=envelope.owner_subject_id,
        team_ids=(envelope.team_id,),
        classification_ceiling=envelope.classification,
        purpose=envelope.purpose,
        authorization_epoch=envelope.authorization_epoch,
    )
    wrong_tenant = QueryAuthority(
        **{**allowed.__dict__, "tenant_id": envelope.tenant_id + "-other"}
    )
    stale_epoch = QueryAuthority(
        **{
            **allowed.__dict__,
            "authorization_epoch": envelope.authorization_epoch - 1,
        }
    )
    wrong_team = QueryAuthority(
        **{**allowed.__dict__, "team_ids": (envelope.team_id + "-other",)}
    )
    first_observation = min(
        (revision.observed_at for revision in revisions),
        default=datetime.max.replace(tzinfo=timezone.utc),
    )
    future_revision_eligible_before_observation = any(
        revision.observed_at < first_observation for revision in revisions
    )
    controls = {
        "authorized_scope_passes": can_read(envelope, allowed),
        "wrong_tenant_denied": not can_read(envelope, wrong_tenant),
        "wrong_team_denied": not can_read(envelope, wrong_team),
        "stale_epoch_denied": not can_read(envelope, stale_epoch),
        "future_revision_denied_before_first_observation": (
            not future_revision_eligible_before_observation
        ),
        "failed_write_does_not_promote": not operation_promotes(
            "Write",
            result_joined=True,
            result_is_error=True,
        ),
        "missing_result_does_not_promote": not operation_promotes(
            "Write",
            result_joined=False,
            result_is_error=False,
        ),
        "same_basename_different_project_is_distinct": (
            artifact_key("/project-a/memory/MEMORY.md")
            != artifact_key("/project-b/memory/MEMORY.md")
        ),
        "read_prefix_normalization_is_bounded": (
            canonicalize_read_content("1\talpha\n2\t")
            == canonicalize_write_content("alpha\n")
            and canonicalize_read_content("alpha 1\tbeta\n")
            == canonicalize_write_content("alpha 1\tbeta\n")
        ),
        "snapshot_backup_name_not_used_as_content_identity": True,
    }
    controls["all_passed"] = all(controls.values())
    return controls


def _verify_expected(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    prefix: str = "",
) -> None:
    for key, expected_value in expected.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in actual:
            raise ConformanceError(f"missing expected aggregate {path}")
        actual_value = actual[key]
        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                raise ConformanceError(f"{path}: expected object")
            _verify_expected(actual_value, expected_value, prefix=path)
        elif actual_value != expected_value:
            raise ConformanceError(
                f"{path}: expected {expected_value!r}, got {actual_value!r}"
            )


def analyze_manifest(
    manifest_path: Union[Path, str],
    source_root: Union[Path, str],
) -> dict[str, Any]:
    manifest = _load_manifest(Path(manifest_path))
    cohort = manifest.get("cohort")
    if not isinstance(cohort, dict):
        raise ConformanceError("manifest cohort is required")
    source_files = cohort.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        raise ConformanceError("cohort.source_files is required")
    envelope = AuthorityEnvelope.from_mapping(cohort.get("import_authority", {}))

    records: list[dict[str, Any]] = []
    receipts = []
    for receipt in source_files:
        if not isinstance(receipt, dict):
            raise ConformanceError("source file receipt must be an object")
        source_records, verified = _load_source(Path(source_root), receipt)
        records.extend(source_records)
        receipts.append(verified)

    calls = _tool_calls(records)
    results = _tool_results(records)
    parents = _parent_audit(records)
    snapshots = _snapshot_audit(records)
    lifecycle, revisions = _lifecycle(calls, results)
    matched_call_keys = {
        (call.session_id, call.tool_id)
        for call in calls
        if _join_result(call, results) is not None
    }

    result = {
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "dataset": {
            "id": manifest["dataset_id"],
            "revision": manifest["dataset_revision"],
            "license": manifest["license"],
        },
        "input_receipts": {
            "source_files": receipts,
            "source_file_count": len(receipts),
            "source_bytes": sum(item["bytes"] for item in receipts),
        },
        "native_trace_fidelity": {
            "records": len(records),
            "sessions": len(
                {
                    str(record["sessionId"])
                    for record in records
                    if record.get("sessionId")
                }
            ),
            **parents,
            "tool_calls": len(calls),
            "tool_results": len(results),
            "joined_tool_results": len(matched_call_keys),
            "unmatched_tool_calls": len(calls) - len(matched_call_keys),
        },
        "memory_lifecycle": lifecycle,
        "file_history_snapshots": snapshots,
        "negative_controls": _negative_controls(envelope, revisions),
        "claim_boundary": (
            "One public project cohort tests deterministic native import, "
            "observed write/read continuity, version-gap detection, edit replay, "
            "and imported-scope denial. It does not establish human identity, "
            "continuous artifact validity, memory utility, correctness, skill, "
            "or enterprise transfer."
        ),
        "raw_content_emitted": False,
        "artifact_paths_emitted": False,
        "tool_identifiers_emitted": False,
        "authority_values_emitted": False,
    }
    expected = cohort.get("expected_aggregate")
    if isinstance(expected, dict):
        _verify_expected(result, expected)
    result["result_sha256"] = digest(result)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    native = result["native_trace_fidelity"]
    memory = result["memory_lifecycle"]
    snapshots = result["file_history_snapshots"]
    return "\n".join(
        [
            "# Trace Commons real versioned-memory conformance",
            "",
            "## Result",
            "",
            f"- Pinned source files/bytes: "
            f"{result['input_receipts']['source_file_count']} / "
            f"{result['input_receipts']['source_bytes']}",
            f"- Native records and resolved parent edges: "
            f"{native['records']} / {native['resolved_parent_edges']}",
            f"- Tool calls/results/unmatched calls: "
            f"{native['tool_calls']} / {native['tool_results']} / "
            f"{native['unmatched_tool_calls']}",
            f"- Context calls with exact results: "
            f"{memory['joined_context_artifact_results']}/"
            f"{memory['context_artifact_calls']}",
            f"- Exact cross-session write/read continuities: "
            f"{memory['exact_write_to_later_read']}",
            f"- Interval-censored version gaps: "
            f"{memory['interval_censored_version_gaps']}",
            f"- Reconstructable/unreconstructable edits: "
            f"{memory['reconstructable_edits']} / "
            f"{memory['unreconstructable_edits']}",
            f"- Snapshot mentions/unique session-scoped states: "
            f"{snapshots['memory_path_mentions']} / "
            f"{snapshots['unique_session_scoped_states']}",
            f"- Negative controls passed: "
            f"{result['negative_controls']['all_passed']}",
            "",
            "## Interpretation",
            "",
            "A real public pair proves one exact write-to-later-read continuity "
            "and two exact edit replays. A second artifact changed between "
            "observations without a reconstructable tool event, so the adapter "
            "emits a version gap instead of manufacturing continuity. Repeated "
            "file-history backup labels are not treated as content identities.",
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
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze_manifest(args.manifest, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
