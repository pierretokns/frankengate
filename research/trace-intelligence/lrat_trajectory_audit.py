#!/usr/bin/env python3
"""Audit the public LRAT sample trajectories without committing their text."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-lrat-trajectory-audit-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_json(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def audit(root: Path) -> dict[str, Any]:
    paths = sorted(root.rglob("*.json"))
    status = Counter()
    step_types = Counter()
    tool_names = Counter()
    metadata_keys = Counter()
    step_key_presence = Counter()
    tool_calls = 0
    nonempty_tool_outputs = 0
    search_calls = 0
    browse_calls = 0
    answer_chars: list[int] = []
    retrieved_doc_counts: list[int] = []
    explicit_outcome_fields = Counter()
    malformed = 0
    receipts: list[dict[str, Any]] = []
    for path in paths:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                malformed += 1
                continue
        except (OSError, json.JSONDecodeError):
            malformed += 1
            continue
        status[str(row.get("status", "<missing>"))] += 1
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        metadata_keys.update(metadata.keys())
        answer_chars.append(len(str(row.get("answer", ""))))
        retrieved_doc_counts.append(len(row.get("retrieved_docids", [])) if isinstance(row.get("retrieved_docids"), list) else 0)
        for key in ("reward", "score", "correct", "success", "failure", "gold_answer", "evaluation", "outcome"):
            if key in row:
                explicit_outcome_fields[key] += 1
        steps = row.get("result") if isinstance(row.get("result"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                malformed += 1
                continue
            step_types[str(step.get("type", "<missing>"))] += 1
            for key in ("type", "tool_name", "arguments", "output"):
                if key in step:
                    step_key_presence[key] += 1
            if step.get("type") != "tool_call":
                continue
            tool_calls += 1
            tool = str(step.get("tool_name", "<missing>"))
            tool_names[tool] += 1
            output = step.get("output")
            if output not in (None, "", [], {}):
                nonempty_tool_outputs += 1
            if tool == "search":
                search_calls += 1
            if tool in {"visit", "get_document"}:
                browse_calls += 1
        receipts.append({"relative_path": path.relative_to(root).as_posix(), "sha256": sha256(path)})
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "root_name": root.name,
            "trajectory_files": len(paths),
            "malformed_records_or_steps": malformed,
            "raw_content_committed": False,
        },
        "records": {
            "status_counts": dict(status),
            "step_type_counts": dict(step_types),
            "tool_name_counts": dict(tool_names),
            "tool_calls": tool_calls,
            "nonempty_tool_outputs": nonempty_tool_outputs,
            "search_calls": search_calls,
            "browse_calls": browse_calls,
            "answer_characters": {"min": min(answer_chars, default=0), "max": max(answer_chars, default=0), "mean": round(sum(answer_chars) / len(answer_chars), 3) if answer_chars else 0.0},
            "retrieved_docids": {"min": min(retrieved_doc_counts, default=0), "max": max(retrieved_doc_counts, default=0), "mean": round(sum(retrieved_doc_counts) / len(retrieved_doc_counts), 3) if retrieved_doc_counts else 0.0},
        },
        "field_presence": {
            "metadata_keys": dict(metadata_keys),
            "step_keys": dict(step_key_presence),
            "explicit_outcome_fields": dict(explicit_outcome_fields),
        },
        "raw_receipts": receipts,
        "claim_boundary": {
            "trajectory_mechanics_audited": True,
            "trajectory_supervised_retrieval_training_measured": False,
            "natural_friction_measured": False,
            "enterprise_alias_or_artifact_learning_measured": False,
            "correctness_outcome_field_present_in_samples": bool(explicit_outcome_fields),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"trajectory_files": result["dataset"]["trajectory_files"], "tool_calls": result["records"]["tool_calls"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
