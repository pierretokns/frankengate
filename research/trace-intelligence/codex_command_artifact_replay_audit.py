#!/usr/bin/env python3
"""Audit reusable command artifacts from current Codex rollout archives.

This is a retrospective mechanics study, not an intent or productivity claim.
It correlates a function call with its structured process-exit output, hashes a
normalized command and project scope, then asks whether a prior successful
occurrence predicts later success. Raw commands, arguments, outputs, and paths
never enter the receipt and no logged command is executed.
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


SCHEMA_VERSION = "codex-command-artifact-replay-audit-v1"
EXIT_SUCCESS = re.compile(r"(?:process )?exited with code\s*0", re.IGNORECASE)
EXIT_FAILURE = re.compile(r"(?:process )?exited with code\s*[1-9]\d*", re.IGNORECASE)
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


def normalized_command(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        tokens = shlex.split(value)
    except ValueError:
        return None
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


def command_from_payload(payload: dict[str, Any]) -> str | None:
    raw = payload.get("arguments", payload.get("input"))
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
    else:
        parsed = raw
    if isinstance(parsed, dict):
        for key in ("cmd", "command", "script"):
            if isinstance(parsed.get(key), str):
                return normalized_command(parsed[key])
    if isinstance(parsed, str):
        return normalized_command(parsed)
    return None


def outcome_from_output(payload: dict[str, Any]) -> str | None:
    output = payload.get("output")
    if not isinstance(output, str):
        return None
    if EXIT_SUCCESS.search(output):
        return "success"
    if EXIT_FAILURE.search(output):
        return "failure"
    return None


def parse_session(path: Path) -> list[dict[str, Any]]:
    pending: dict[str, tuple[str, str, str]] = {}
    rows: list[dict[str, Any]] = []
    session_hash = sha256_text(path.stem)
    scope_hash = sha256_text(path.stem)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload") if isinstance(record, dict) else None
            if not isinstance(payload, dict):
                continue
            if isinstance(payload.get("cwd"), str):
                scope_hash = sha256_text(payload["cwd"])
            kind = payload.get("type")
            call_id = payload.get("call_id")
            if kind in {"function_call", "custom_tool_call"} and isinstance(call_id, str):
                command = command_from_payload(payload)
                if command is not None:
                    pending[call_id] = (sha256_text(command), scope_hash, session_hash)
            elif kind in {"function_call_output", "custom_tool_call_output"} and isinstance(call_id, str):
                pending_value = pending.pop(call_id, None)
                if pending_value is None:
                    continue
                outcome = outcome_from_output(payload)
                if outcome is None:
                    continue
                artifact_hash, call_scope_hash, call_session_hash = pending_value
                rows.append({
                    "artifact_hash": artifact_hash,
                    "scope_hash": call_scope_hash,
                    "session_hash": call_session_hash,
                    "outcome": outcome,
                })
    return rows


def audit(paths: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    # Rollout filenames carry their start timestamp; ``paths`` is sorted by
    # filename, so preserving this order gives a deterministic temporal split.
    for path in paths:
        rows.extend(parse_session(path))
    artifact_outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    scope_artifacts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        artifact_outcomes[row["artifact_hash"]][row["outcome"]] += 1
        scope_artifacts[(row["scope_hash"], row["artifact_hash"])][row["outcome"]] += 1

    repeated_rows = 0
    prior_success_same_scope = 0
    prior_success_same_scope_later_success = 0
    prior_success_same_scope_later_failure = 0
    prior_success_other_scope = 0
    prior_success_other_scope_later_success = 0
    prior_success_other_scope_later_failure = 0
    first_success_by_artifact: dict[str, tuple[int, str]] = {}
    first_success_by_scope_artifact: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        artifact = row["artifact_hash"]
        scope = row["scope_hash"]
        key = (scope, artifact)
        if key in first_success_by_scope_artifact:
            repeated_rows += 1
            prior_success_same_scope += 1
            if row["outcome"] == "success":
                prior_success_same_scope_later_success += 1
            else:
                prior_success_same_scope_later_failure += 1
        if artifact in first_success_by_artifact and key not in first_success_by_scope_artifact:
            prior_success_other_scope += 1
            if row["outcome"] == "success":
                prior_success_other_scope_later_success += 1
            else:
                prior_success_other_scope_later_failure += 1
        if row["outcome"] == "success":
            first_success_by_scope_artifact.setdefault(key, index)
            first_success_by_artifact.setdefault(artifact, (index, scope))

    distinct_artifacts = len(artifact_outcomes)
    distinct_scopes = len({row["scope_hash"] for row in rows})
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"path_count": len(paths), "path_sha256": sha256_text("\n".join(sorted(sha256_file(path) for path in paths))), "raw_content_committed": False},
        "aggregate": {
            "labeled_command_occurrences": len(rows),
            "distinct_command_artifacts": distinct_artifacts,
            "distinct_scopes": distinct_scopes,
            "success_occurrences": sum(row["outcome"] == "success" for row in rows),
            "failure_occurrences": sum(row["outcome"] == "failure" for row in rows),
            "repeated_occurrences_after_same_scope_success": repeated_rows,
            "same_scope_prior_success_later_success": prior_success_same_scope_later_success,
            "same_scope_prior_success_later_failure": prior_success_same_scope_later_failure,
            "other_scope_prior_success_later_success": prior_success_other_scope_later_success,
            "other_scope_prior_success_later_failure": prior_success_other_scope_later_failure,
        },
        "claim_boundary": "Retrospective command-template/outcome association only; no intent, semantic equivalence, user satisfaction, or safe automatic reuse claim. No logged command is executed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths: list[Path] = []
    for root in args.input:
        paths.extend(sorted(root.glob("rollout-*.jsonl")) if root.is_dir() else [root])
    result = audit(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
