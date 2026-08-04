#!/usr/bin/env python3
"""Independent aggregate verifier for the Codex command-artifact audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXIT_SUCCESS = re.compile(r"(?:process )?exited with code\s*0", re.IGNORECASE)
EXIT_FAILURE = re.compile(r"(?:process )?exited with code\s*[1-9]\d*", re.IGNORECASE)
ABSOLUTE = re.compile(r"^/(?:[^\s/]+/)+[^\s/]+$")
HEX = re.compile(r"^(?:0x)?[0-9a-f]{8,}$", re.IGNORECASE)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,}$", re.IGNORECASE)
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def command_hash(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        tokens = shlex.split(value)
    except ValueError:
        return None
    normalized = []
    for token in tokens:
        if ABSOLUTE.match(token) or UUID.match(token) or HEX.match(token) or NUMBER.match(token):
            normalized.append("<value>")
        elif len(token) > 120:
            normalized.append("<long>")
        else:
            normalized.append(token)
    return digest(" ".join(normalized)) if normalized else None


def payload_command(payload: dict[str, Any]) -> str | None:
    raw = payload.get("arguments", payload.get("input"))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            pass
    if isinstance(raw, dict):
        for key in ("cmd", "command", "script"):
            if isinstance(raw.get(key), str):
                return raw[key]
    return raw if isinstance(raw, str) else None


def parse_file(path: Path) -> list[tuple[str, str, str]]:
    """Parse one archive with the same record semantics as the audit.

    Verification is independent at the aggregate/correlation layer.  The
    parser intentionally mirrors the audit's LF-delimited streaming behavior:
    ``splitlines()`` is not used because it treats U+2028/U+2029 in tool output
    as JSONL boundaries.
    """
    pending: dict[str, tuple[str, str]] = {}
    scope = digest(path.stem)
    rows: list[tuple[str, str, str]] = []
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
                scope = digest(payload["cwd"])
            kind = payload.get("type")
            call_id = payload.get("call_id")
            if kind in {"function_call", "custom_tool_call"} and isinstance(call_id, str):
                raw = payload.get("arguments", payload.get("input"))
                parsed = raw
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = raw
                command_text = None
                if isinstance(parsed, dict):
                    for key in ("cmd", "command", "script"):
                        if isinstance(parsed.get(key), str):
                            command_text = parsed[key]
                            break
                elif isinstance(parsed, str):
                    command_text = parsed
                if command_text is not None:
                    normalized = command_hash(command_text)
                    if normalized:
                        pending[call_id] = (normalized, scope)
            elif kind in {"function_call_output", "custom_tool_call_output"} and isinstance(call_id, str):
                previous = pending.pop(call_id, None)
                if previous is None:
                    continue
                output = payload.get("output")
                if not isinstance(output, str):
                    continue
                if EXIT_SUCCESS.search(output):
                    rows.append((previous[0], previous[1], "success"))
                elif EXIT_FAILURE.search(output):
                    rows.append((previous[0], previous[1], "failure"))
    return rows


def verify(result_path: Path, input_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    paths = sorted(input_dir.glob("rollout-*.jsonl"))
    rows = [row for path in paths for row in parse_file(path)]
    aggregate = Counter()
    first_scope_success: set[tuple[str, str]] = set()
    first_any_success: set[str] = set()
    for artifact, scope, outcome in rows:
        aggregate["labeled_command_occurrences"] += 1
        aggregate["success_occurrences" if outcome == "success" else "failure_occurrences"] += 1
        key = (scope, artifact)
        if key in first_scope_success:
            aggregate["repeated_occurrences_after_same_scope_success"] += 1
            aggregate["same_scope_prior_success_later_success" if outcome == "success" else "same_scope_prior_success_later_failure"] += 1
        elif artifact in first_any_success:
            aggregate["other_scope_prior_success_later_success" if outcome == "success" else "other_scope_prior_success_later_failure"] += 1
        if outcome == "success":
            first_scope_success.add(key)
            first_any_success.add(artifact)
    aggregate["distinct_command_artifacts"] = len({row[0] for row in rows})
    aggregate["distinct_scopes"] = len({row[1] for row in rows})
    expected = result.get("aggregate", {})
    keys = set(aggregate) | set(expected)
    matches = all(aggregate.get(key, 0) == expected.get(key, 0) for key in keys)
    return {
        "schema_version": "codex-command-artifact-replay-verification-v1",
        "path_count": len(paths),
        "rows_replayed": len(rows),
        "recomputed_aggregate": dict(sorted(aggregate.items())),
        "receipt_aggregate": expected,
        "receipt_matches": matches,
        "independent_evaluator": "separate streaming parser and outcome correlator",
        "claim_boundary": {"verification_passed": matches, "semantic_reuse_confirmed": False, "automatic_replay_authorized": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verified = verify(args.result, args.input_dir)
    args.output.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verified, sort_keys=True))
    return 0 if verified["claim_boundary"]["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
