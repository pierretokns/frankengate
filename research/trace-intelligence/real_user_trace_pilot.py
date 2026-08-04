#!/usr/bin/env python3
"""Aggregate a public longitudinal Claude Code export without emitting content.

The pilot intentionally reports structural and lifecycle evidence only. It does
not print prompts, tool arguments, tool output, paths found inside events, or
model reasoning. That makes the result suitable for version control while the
raw public corpus remains in temporary storage.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def classify_file(relative_path: Path) -> str:
    parts = relative_path.parts
    text = relative_path.as_posix()
    if "/subagents/workflows/" in f"/{text}":
        return "nested_subagent"
    if len(parts) == 2 and parts[0] == "-home-me":
        return "main_user"
    if len(parts) == 2 and parts[0] == "-home-me-ht-hyprland-bench":
        return "benchmark_development"
    if parts and parts[0].startswith(
        "-home-me-ht-hyprland-bench-results-"
    ):
        return "benchmark_task"
    return "other"


def iter_content_blocks(record: dict[str, Any]) -> Iterable[dict[str, Any]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict):
            yield block


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def tool_result_is_error(block: dict[str, Any]) -> bool:
    # Claude Code versions have used both spellings.
    return block.get("is_error") is True or block.get("isError") is True


def analyze_file(path: Path, root: Path) -> dict[str, Any]:
    records = 0
    invalid_records = 0
    record_types: collections.Counter[str] = collections.Counter()
    content_types: collections.Counter[str] = collections.Counter()
    tool_names: collections.Counter[str] = collections.Counter()
    explicit_errors = 0
    recovered_errors = 0
    pending_error = False
    timestamps: list[dt.datetime] = []
    uuids: set[str] = set()
    parent_counts: collections.Counter[str] = collections.Counter()
    parent_refs: set[str] = set()

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for raw_line in stream:
            digest.update(raw_line)
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                invalid_records += 1
                continue
            if not isinstance(record, dict):
                invalid_records += 1
                continue

            records += 1
            record_types[str(record.get("type", "<missing>"))] += 1
            timestamp = parse_timestamp(record.get("timestamp"))
            if timestamp is not None:
                timestamps.append(timestamp)

            uuid = record.get("uuid")
            if isinstance(uuid, str) and uuid:
                uuids.add(uuid)
            parent_uuid = record.get("parentUuid")
            if isinstance(parent_uuid, str) and parent_uuid:
                parent_refs.add(parent_uuid)
                parent_counts[parent_uuid] += 1

            for block in iter_content_blocks(record):
                block_type = str(block.get("type", "<missing>"))
                content_types[block_type] += 1
                if block_type == "tool_use":
                    name = block.get("name")
                    if isinstance(name, str) and name:
                        tool_names[name] += 1
                elif block_type == "tool_result":
                    if tool_result_is_error(block):
                        explicit_errors += 1
                        pending_error = True
                    elif pending_error:
                        recovered_errors += 1
                        pending_error = False

    dangling_parents = len(parent_refs - uuids)
    branch_points = sum(1 for count in parent_counts.values() if count > 1)
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "stratum": classify_file(path.relative_to(root)),
        "sha256": digest.hexdigest(),
        "records": records,
        "invalid_records": invalid_records,
        "record_types": dict(record_types),
        "content_types": dict(content_types),
        "tool_names": dict(tool_names),
        "explicit_error_results": explicit_errors,
        "recovered_error_episodes": recovered_errors,
        "branch_points": branch_points,
        "dangling_parent_references": dangling_parents,
        "first_timestamp": min(timestamps).isoformat() if timestamps else None,
        "last_timestamp": max(timestamps).isoformat() if timestamps else None,
    }


def merge_counters(
    analyses: list[dict[str, Any]], key: str
) -> collections.Counter[str]:
    merged: collections.Counter[str] = collections.Counter()
    for analysis in analyses:
        merged.update(analysis[key])
    return merged


def analyze_corpus(root: Path, source: dict[str, Any]) -> dict[str, Any]:
    files = sorted(root.rglob("*.jsonl"))
    analyses = [analyze_file(path, root) for path in files]
    strata = collections.Counter(item["stratum"] for item in analyses)
    record_types = merge_counters(analyses, "record_types")
    content_types = merge_counters(analyses, "content_types")
    tool_names = merge_counters(analyses, "tool_names")
    first_timestamps = [
        item["first_timestamp"] for item in analyses if item["first_timestamp"]
    ]
    last_timestamps = [
        item["last_timestamp"] for item in analyses if item["last_timestamp"]
    ]

    return {
        "schema_version": "real-user-trace-pilot-v1",
        "source": source,
        "privacy": {
            "raw_data_committed": False,
            "content_emitted": False,
            "identity_scope": "one intentionally public contributor",
            "permitted_claim": (
                "single-user longitudinal mechanism and parser validation"
            ),
            "prohibited_claims": [
                "representative employee behavior",
                "individual competence or productivity",
                "cross-user collaboration benefit",
                "causal effect of a prompt, skill, memory, or model",
            ],
        },
        "coverage": {
            "jsonl_files": len(analyses),
            "files_by_stratum": dict(sorted(strata.items())),
            "valid_records": sum(item["records"] for item in analyses),
            "invalid_records": sum(item["invalid_records"] for item in analyses),
            "first_timestamp": min(first_timestamps) if first_timestamps else None,
            "last_timestamp": max(last_timestamps) if last_timestamps else None,
            "record_types": dict(record_types.most_common()),
            "content_types": dict(content_types.most_common()),
            "top_tool_names": dict(tool_names.most_common(25)),
        },
        "lifecycle": {
            "tool_uses": content_types["tool_use"],
            "tool_results": content_types["tool_result"],
            "explicit_error_results": sum(
                item["explicit_error_results"] for item in analyses
            ),
            "files_with_explicit_error": sum(
                item["explicit_error_results"] > 0 for item in analyses
            ),
            "recovered_error_episodes": sum(
                item["recovered_error_episodes"] for item in analyses
            ),
            "branch_points": sum(item["branch_points"] for item in analyses),
            "dangling_parent_references": sum(
                item["dangling_parent_references"] for item in analyses
            ),
        },
        "file_integrity": [
            {
                "relative_path": item["relative_path"],
                "stratum": item["stratum"],
                "sha256": item["sha256"],
                "records": item["records"],
                "invalid_records": item["invalid_records"],
            }
            for item in analyses
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = analyze_corpus(args.corpus_root.resolve(), manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
