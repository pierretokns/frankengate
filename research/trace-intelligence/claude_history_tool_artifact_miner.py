#!/usr/bin/env python3
"""Mine strict tool-artifact recurrence and recovery signals from Claude logs.

The source is a local `.claude/projects` export containing paired
``tool_use``/``tool_result`` records.  Tool names, inputs, paths, and result
text never enter the receipt; only hashes and aggregate counts are emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-claude-history-tool-artifact-miner-v1"
PATH_RE = re.compile(r"(?:/|[A-Za-z]:[\\/])[^\s'\"]+")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
NUMBER_RE = re.compile(r"\b\d{2,}\b")


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        value = PATH_RE.sub("<path>", value)
        value = UUID_RE.sub("<uuid>", value)
        value = NUMBER_RE.sub("<n>", value)
        return " ".join(value.lower().split())
    if isinstance(value, dict):
        return {str(key).lower(): normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def manifest(root: Path) -> tuple[int, int, str]:
    rows: list[tuple[str, int]] = []
    total = 0
    for path in sorted(root.rglob("*.jsonl")):
        size = path.stat().st_size
        total += size
        rows.append((str(path.relative_to(root)), size))
    return len(rows), total, digest(rows)


def mine(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = manifest(root)
    artifacts: dict[str, dict[str, Any]] = {}
    sessions = 0
    projects: set[str] = set()
    tool_use_count = 0
    tool_result_count = 0
    paired_count = 0
    unobserved_count = 0
    error_count = 0
    success_count = 0
    recovery_count = 0
    parse_errors = 0
    tool_name_counts: Counter[str] = Counter()

    for path in sorted(root.rglob("*.jsonl")):
        project = path.parent.name
        session_hash = digest(str(path.relative_to(root)))
        sessions += 1
        projects.add(project)
        uses: list[tuple[str, str, str, str | None]] = []
        statuses: dict[str, bool] = {}
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        parse_errors += 1
                        continue
                    message = record.get("message") if isinstance(record, dict) else None
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        item_type = item.get("type")
                        if item_type == "tool_use" and item.get("id"):
                            tool_name = str(item.get("name") or "<missing>").lower()
                            normalized_input = normalize(item.get("input"))
                            fingerprint = digest({"tool": tool_name, "input": normalized_input})
                            keyshape = digest({"tool": tool_name, "input_keys": sorted(normalized_input) if isinstance(normalized_input, dict) else []})
                            uses.append((str(item["id"]), fingerprint, keyshape, tool_name))
                            tool_name_counts[digest(tool_name)] += 1
                            tool_use_count += 1
                        elif item_type == "tool_result" and item.get("tool_use_id"):
                            tool_result_count += 1
                            statuses[str(item["tool_use_id"])] = bool(item.get("is_error", False))
        except OSError:
            continue

        prior_errors: set[str] = set()
        for tool_id, fingerprint, keyshape, tool_name in uses:
            if tool_id not in statuses:
                unobserved_count += 1
                continue
            paired_count += 1
            failed = statuses[tool_id]
            if failed:
                error_count += 1
                prior_errors.add(fingerprint)
            else:
                success_count += 1
                if fingerprint in prior_errors:
                    recovery_count += 1
            entry = artifacts.setdefault(
                fingerprint,
                {"sessions": set(), "projects": set(), "successes": 0, "failures": 0, "keyshapes": set()},
            )
            entry["sessions"].add(session_hash)
            entry["projects"].add(digest(project))
            entry["keyshapes"].add(keyshape)
            entry["successes" if not failed else "failures"] += 1

    recurring_success = [entry for entry in artifacts.values() if entry["successes"] >= 2 and len(entry["sessions"]) >= 2]
    cross_project_success = [entry for entry in recurring_success if len(entry["projects"]) >= 2]
    mixed_outcome = [entry for entry in artifacts.values() if entry["successes"] > 0 and entry["failures"] > 0]
    recurring_failure = [entry for entry in artifacts.values() if entry["failures"] >= 2 and len(entry["sessions"]) >= 2]

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": file_count,
            "byte_count": byte_count,
            "manifest_sha256": manifest_hash,
            "raw_content_committed": False,
        },
        "coverage": {
            "session_count": sessions,
            "project_count": len(projects),
            "parse_error_count": parse_errors,
            "tool_use_count": tool_use_count,
            "tool_result_count": tool_result_count,
            "paired_tool_call_count": paired_count,
            "unobserved_tool_use_count": unobserved_count,
            "success_result_count": success_count,
            "error_result_count": error_count,
            "distinct_strict_artifact_count": len(artifacts),
            "distinct_tool_name_hash_count": len(tool_name_counts),
        },
        "recurrence": {
            "successful_artifacts_recurring_across_sessions": len(recurring_success),
            "successful_artifacts_recurring_across_projects": len(cross_project_success),
            "artifacts_recurring_with_mixed_outcomes": len(mixed_outcome),
            "artifacts_recurring_as_failures": len(recurring_failure),
            "error_to_success_recovery_count": recovery_count,
            "success_recurrence_rate": round(len(recurring_success) / len(artifacts), 6) if artifacts else 0.0,
            "cross_project_success_rate": round(len(cross_project_success) / len(recurring_success), 6) if recurring_success else 0.0,
        },
        "claim_boundary": {
            "artifact_correctness": False,
            "artifact_safety": False,
            "skill_improvement": False,
            "cross_user_transfer": False,
            "reason": "Strict normalized tool recurrence and explicit result status are candidate signals; tool success is not an independent semantic, security, or user-outcome label.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": result["coverage"], "recurrence": result["recurrence"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mine(args.input, args.output)
