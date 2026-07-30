#!/usr/bin/env python3
"""Analyze a sparse share-codex sample without emitting transcript content.

The input is a directory of Hugging Face dataset-server ``rows`` responses.
The analyzer reads message structure, lifecycle identifiers, timestamps, and
already-typed error flags. It deliberately never copies prompts, assistant
text, tool arguments, tool output, paths, session identifiers, or project
identifiers into its result.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_REVISION_HEADER = "x-revision"


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_revision_header(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == EXPECTED_REVISION_HEADER:
            return value.strip()
    return None


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def is_tool_error(message: dict[str, Any]) -> bool:
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return False
    return metadata.get("is_error") is True


def tool_call_name(call: dict[str, Any]) -> str | None:
    function = call.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    return name if isinstance(name, str) and name else None


GENERIC_TOOL_CATEGORIES = {
    "apply_patch": "file_change",
    "Edit": "file_change",
    "MultiEdit": "file_change",
    "Write": "file_change",
    "NotebookEdit": "file_change",
    "Read": "file_read",
    "Glob": "file_search",
    "Grep": "file_search",
    "exec_command": "shell",
    "shell_command": "shell",
    "shell": "shell",
    "Bash": "shell",
    "write_stdin": "shell_session",
    "update_plan": "coordination",
    "web_search_call": "web",
    "view_image": "media",
}


def tool_category(name: str | None) -> str:
    if name is None:
        return "missing_name"
    return GENERIC_TOOL_CATEGORIES.get(name, "other_or_custom")


def analyze_session(row: dict[str, Any]) -> dict[str, Any]:
    messages = row.get("messages")
    if not isinstance(messages, list):
        messages = []
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    roles: collections.Counter[str] = collections.Counter()
    tool_categories: collections.Counter[str] = collections.Counter()
    proposals: dict[str, tuple[str | None, int]] = {}
    result_ids: set[str] = set()
    explicit_errors = 0
    error_result_positions: list[tuple[str, str | None, int]] = []
    successful_result_positions: list[tuple[str, str | None, int]] = []

    for position, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        roles[str(role) if role is not None else "<missing>"] += 1

        calls = message.get("tool_calls")
        if isinstance(calls, list):
            for call in calls:
                if not isinstance(call, dict):
                    continue
                call_id = call.get("id")
                name = tool_call_name(call)
                tool_categories[tool_category(name)] += 1
                if isinstance(call_id, str) and call_id:
                    proposals[call_id] = (name, position)

        if role != "tool":
            continue
        call_id = message.get("tool_call_id")
        if not isinstance(call_id, str) or not call_id:
            continue
        result_ids.add(call_id)
        name = proposals.get(call_id, (None, position))[0]
        if is_tool_error(message):
            explicit_errors += 1
            error_result_positions.append((call_id, name, position))
        else:
            successful_result_positions.append((call_id, name, position))

    later_success_after_error = 0
    later_same_tool_success_after_error = 0
    for _, error_name, error_position in error_result_positions:
        later = [
            item
            for item in successful_result_positions
            if item[2] > error_position
        ]
        if later:
            later_success_after_error += 1
        if error_name is not None and any(
            success_name == error_name for _, success_name, _ in later
        ):
            later_same_tool_success_after_error += 1

    timestamp = parse_timestamp(metadata.get("timestamp"))
    cwd = metadata.get("cwd")
    project_identity = cwd if isinstance(cwd, str) and cwd else None
    return {
        "roles": roles,
        "tool_categories": tool_categories,
        "tool_proposals": len(proposals),
        "tool_results": len(result_ids),
        "matched_tool_results": len(result_ids & proposals.keys()),
        "unresolved_tool_proposals": len(proposals.keys() - result_ids),
        "orphan_tool_results": len(result_ids - proposals.keys()),
        "explicit_errors": explicit_errors,
        "later_success_after_error": later_success_after_error,
        "later_same_tool_success_after_error": (
            later_same_tool_success_after_error
        ),
        "timestamp": timestamp,
        "project_identity": project_identity,
        "source": metadata.get("source"),
        "source_entrypoint": metadata.get("source_entrypoint"),
    }


def analyze_sample(
    sample_dir: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    requests = manifest["sample_design"]["requests"]
    expected_revision = manifest["dataset_revision"]
    all_sessions: list[dict[str, Any]] = []
    integrity: list[dict[str, Any]] = []
    observed_row_indices: list[int] = []

    for request in requests:
        offset = int(request["offset"])
        length = int(request["length"])
        payload_path = sample_dir / f"share-codex.rows-{offset}.json"
        header_path = sample_dir / f"share-codex.rows-{offset}.headers"
        revision = read_revision_header(header_path)
        if revision != expected_revision:
            raise ValueError(
                f"revision mismatch for offset {offset}: {revision!r}"
            )

        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) != length:
            raise ValueError(
                f"expected {length} rows at offset {offset}, got "
                f"{len(rows) if isinstance(rows, list) else 'non-list'}"
            )
        if payload.get("num_rows_total") != manifest["population_rows"]:
            raise ValueError("population row count changed")
        if payload.get("partial") is not False:
            raise ValueError("dataset server returned a partial response")

        indices = []
        for wrapper in rows:
            if not isinstance(wrapper, dict):
                raise ValueError("invalid row wrapper")
            row_index = wrapper.get("row_idx")
            row = wrapper.get("row")
            if not isinstance(row_index, int) or not isinstance(row, dict):
                raise ValueError("invalid row response")
            indices.append(row_index)
            observed_row_indices.append(row_index)
            all_sessions.append(analyze_session(row))
        if indices != list(range(offset, offset + length)):
            raise ValueError(f"unexpected row indices at offset {offset}")

        integrity.append(
            {
                "offset": offset,
                "length": length,
                "response_bytes": payload_path.stat().st_size,
                "response_sha256": file_digest(payload_path),
                "response_revision": revision,
            }
        )

    if len(observed_row_indices) != len(set(observed_row_indices)):
        raise ValueError("sample requests overlap")

    roles: collections.Counter[str] = collections.Counter()
    tool_categories: collections.Counter[str] = collections.Counter()
    sources: collections.Counter[str] = collections.Counter()
    entrypoints: collections.Counter[str] = collections.Counter()
    project_counts: collections.Counter[str] = collections.Counter()
    timestamps: list[dt.datetime] = []
    for session in all_sessions:
        roles.update(session["roles"])
        tool_categories.update(session["tool_categories"])
        source = session["source"]
        if isinstance(source, str) and source:
            sources[source] += 1
        entrypoint = session["source_entrypoint"]
        if isinstance(entrypoint, str) and entrypoint:
            entrypoints[entrypoint] += 1
        project = session["project_identity"]
        if project is not None:
            project_counts[project] += 1
        if session["timestamp"] is not None:
            timestamps.append(session["timestamp"])

    sessions_with_errors = sum(
        session["explicit_errors"] > 0 for session in all_sessions
    )
    sessions_with_later_success = sum(
        session["later_success_after_error"] > 0 for session in all_sessions
    )
    sample_rows = len(all_sessions)
    return {
        "schema_version": "share-codex-sparse-pilot-v1",
        "source": {
            "dataset_id": manifest["dataset_id"],
            "dataset_revision": expected_revision,
            "license": manifest["license"],
            "population_rows": manifest["population_rows"],
            "sample_rows": sample_rows,
            "sampling_fraction": round(
                sample_rows / manifest["population_rows"], 6
            ),
        },
        "privacy": {
            "raw_data_committed": False,
            "content_values_accessed_by_analysis": False,
            "content_emitted": False,
            "identifiers_emitted": False,
            "project_identifiers_retained": False,
            "identity_scope": "one intentionally public dataset owner",
            "embedded_content_use": "structural analysis only",
        },
        "sampling": {
            "design": manifest["sample_design"]["name"],
            "requests": requests,
            "observed_row_index_min": min(observed_row_indices),
            "observed_row_index_max": max(observed_row_indices),
            "response_bytes": sum(
                item["response_bytes"] for item in integrity
            ),
            "integrity": integrity,
        },
        "coverage": {
            "sessions": sample_rows,
            "first_timestamp": (
                min(timestamps).isoformat() if timestamps else None
            ),
            "last_timestamp": (
                max(timestamps).isoformat() if timestamps else None
            ),
            "roles": dict(roles.most_common()),
            "sources": dict(sources.most_common()),
            "source_entrypoints": dict(entrypoints.most_common()),
            "unique_projects": len(project_counts),
            "projects_with_multiple_sessions": sum(
                count > 1 for count in project_counts.values()
            ),
            "maximum_sessions_in_one_project": (
                max(project_counts.values()) if project_counts else 0
            ),
        },
        "lifecycle": {
            "tool_categories": dict(tool_categories.most_common()),
            "tool_proposals": sum(
                item["tool_proposals"] for item in all_sessions
            ),
            "tool_results": sum(
                item["tool_results"] for item in all_sessions
            ),
            "matched_tool_results": sum(
                item["matched_tool_results"] for item in all_sessions
            ),
            "unresolved_tool_proposals": sum(
                item["unresolved_tool_proposals"] for item in all_sessions
            ),
            "orphan_tool_results": sum(
                item["orphan_tool_results"] for item in all_sessions
            ),
            "explicit_error_results": sum(
                item["explicit_errors"] for item in all_sessions
            ),
            "sessions_with_explicit_error": sessions_with_errors,
            "error_results_with_later_success": sum(
                item["later_success_after_error"] for item in all_sessions
            ),
            "error_results_with_later_same_tool_success": sum(
                item["later_same_tool_success_after_error"]
                for item in all_sessions
            ),
            "sessions_with_error_then_later_success": (
                sessions_with_later_success
            ),
        },
        "claim_boundary": {
            "supported": [
                "parser and lifecycle-linkage validation",
                "single-user longitudinal project recurrence",
                "proposal-only friction and recovery candidate extraction",
                "revision-bound sparse sampling",
            ],
            "not_identifiable": [
                "task success or quality",
                "whether a later success caused task recovery",
                "user skill or productivity",
                "cross-user collaboration benefit",
                "causal effect of a model, prompt, memory, skill, or eval",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dir", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = analyze_sample(args.sample_dir.resolve(), manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
