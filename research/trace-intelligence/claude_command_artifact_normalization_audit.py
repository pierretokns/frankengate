#!/usr/bin/env python3
"""Audit command-artifact normalization on native Claude JSONL sessions.

This probe compares exact command identity with a conservative parameterized
identity. It reports only hashes and aggregate counts. No logged command is
executed and no command text, output, path, or identifier enters the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-claude-command-artifact-normalization-v1"
ABSOLUTE = re.compile(r"^/(?:[^\s/]+/)+[^\s/]+$")
HEX = re.compile(r"^(?:0x)?[0-9a-f]{8,}$", re.IGNORECASE)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,}$", re.IGNORECASE)
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_tokens(command: str) -> list[str] | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    return tokens or None


def normalized_command(command: str) -> str | None:
    tokens = command_tokens(command)
    if not tokens:
        return None
    normalized: list[str] = []
    for token in tokens:
        if ABSOLUTE.match(token) or UUID.match(token) or HEX.match(token) or NUMBER.match(token):
            normalized.append("<value>")
        elif len(token) > 120:
            normalized.append("<long>")
        else:
            normalized.append(token)
    return " ".join(normalized)


def content_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def parse_paths(paths: list[Path]) -> list[dict[str, str]]:
    pending: dict[str, dict[str, str]] = {}
    rows: list[dict[str, str]] = []
    for path in sorted(paths):
        session_hash = sha256_text(path.stem)
        scope_hash = sha256_text(path.stem)
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                cwd = record.get("cwd")
                if not isinstance(cwd, str):
                    cwd = record.get("message", {}).get("cwd") if isinstance(record.get("message"), dict) else None
                if isinstance(cwd, str) and cwd:
                    scope_hash = sha256_text(cwd)
                timestamp = str(record.get("timestamp") or "")
                if record.get("type") == "assistant":
                    for block in content_blocks(record):
                        if block.get("type") != "tool_use" or block.get("name") not in {"Bash", "bash"}:
                            continue
                        tool_id = block.get("id")
                        command = block.get("input", {}).get("command") if isinstance(block.get("input"), dict) else None
                        if isinstance(tool_id, str) and isinstance(command, str) and command.strip():
                            normalized = normalized_command(command)
                            if normalized is not None:
                                pending[tool_id] = {
                                    "exact_hash": sha256_text(command.strip()),
                                    "normalized_hash": sha256_text(normalized),
                                    "scope_hash": scope_hash,
                                    "session_hash": session_hash,
                                    "timestamp": timestamp,
                                }
                elif record.get("type") == "user":
                    for block in content_blocks(record):
                        if block.get("type") != "tool_result":
                            continue
                        tool_id = block.get("tool_use_id")
                        prior = pending.pop(tool_id, None) if isinstance(tool_id, str) else None
                        if prior is None:
                            continue
                        failed = bool(block.get("is_error"))
                        tool_result = record.get("toolUseResult")
                        if isinstance(tool_result, dict) and (tool_result.get("interrupted") or tool_result.get("is_error")):
                            failed = True
                        prior["outcome"] = "failure" if failed else "success"
                        prior["timestamp"] = timestamp or prior["timestamp"]
                        rows.append(prior)
    return rows


def representation_metrics(rows: list[dict[str, str]], representation: str) -> dict[str, Any]:
    outcome_by_artifact: dict[str, Counter[str]] = defaultdict(Counter)
    scopes_by_artifact: dict[str, set[str]] = defaultdict(set)
    raw_by_parameterized: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        artifact = row[f"{representation}_hash"]
        outcome_by_artifact[artifact][row["outcome"]] += 1
        scopes_by_artifact[artifact].add(row["scope_hash"])
        if representation == "normalized":
            raw_by_parameterized[artifact].add(row["exact_hash"])

    prior_same_success = prior_same_failure = prior_other_success = prior_other_failure = repeated = 0
    seen_scope_success: set[tuple[str, str]] = set()
    seen_artifact_success: set[str] = set()
    for row in rows:
        artifact = row[f"{representation}_hash"]
        scope = row["scope_hash"]
        if (scope, artifact) in seen_scope_success:
            repeated += 1
            if row["outcome"] == "success":
                prior_same_success += 1
            else:
                prior_same_failure += 1
        elif artifact in seen_artifact_success:
            if row["outcome"] == "success":
                prior_other_success += 1
            else:
                prior_other_failure += 1
        if row["outcome"] == "success":
            seen_scope_success.add((scope, artifact))
            seen_artifact_success.add(artifact)
    mixed = sum(bool(counts.get("success")) and bool(counts.get("failure")) for counts in outcome_by_artifact.values())
    collision_buckets = sum(len(values) > 1 for values in raw_by_parameterized.values())
    collision_pairs = sum(len(values) - 1 for values in raw_by_parameterized.values() if len(values) > 1)
    total = len(rows)
    successes = sum(row["outcome"] == "success" for row in rows)
    return {
        "labeled_occurrences": total,
        "distinct_artifacts": len(outcome_by_artifact),
        "success_occurrences": successes,
        "failure_occurrences": total - successes,
        "overall_success_rate": round(successes / total, 6) if total else 0.0,
        "repeated_after_same_scope_success": repeated,
        "same_scope_later_success": prior_same_success,
        "same_scope_later_failure": prior_same_failure,
        "same_scope_success_rate": round(prior_same_success / repeated, 6) if repeated else 0.0,
        "other_scope_later_success": prior_other_success,
        "other_scope_later_failure": prior_other_failure,
        "other_scope_success_rate": round(prior_other_success / (prior_other_success + prior_other_failure), 6) if prior_other_success + prior_other_failure else 0.0,
        "mixed_outcome_artifact_buckets": mixed,
        "parameterized_buckets_with_multiple_exact_commands": collision_buckets,
        "parameterized_extra_exact_command_collisions": collision_pairs,
    }


def run(root: Path, output: Path) -> dict[str, Any]:
    paths = sorted(root.rglob("*.jsonl"))
    rows = parse_paths(paths)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "path_count": len(paths),
            "path_sha256": sha256_text("\n".join(sha256_file(path) for path in paths)),
            "raw_content_committed": False,
        },
        "representations": {
            "exact": representation_metrics(rows, "exact"),
            "normalized": representation_metrics(rows, "normalized"),
        },
        "claim_boundary": {
            "commands_executed": False,
            "intent_labels": False,
            "semantic_equivalence": False,
            "user_utility": False,
            "reason": "This is a retrospective command/result association and normalization-collision audit, not a replay or semantic-intent benchmark.",
        },
    }
    result["result_sha256"] = sha256_text(json.dumps(result, sort_keys=True, separators=(",", ":")))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["representations"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
