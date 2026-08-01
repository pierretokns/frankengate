#!/usr/bin/env python3
"""Content-free friction screen for Codex rollout JSONL.

The Codex schema carries function calls and function-call outputs rather than
Claude's content-block tool_result shape.  This adapter uses exit_code as the
structured executor signal and deliberately keeps keyword markers separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.IGNORECASE)
ERROR = re.compile(
    r"\b(?:error|exception|traceback|failed|failure|timed? out|timeout|permission denied|unauthorized|forbidden|no such file|syntaxerror|panic)\b",
    re.IGNORECASE,
)
EXPLICIT = {
    "dissatisfaction": re.compile(
        r"\b(?:wrong|incorrect|not what|doesn't work|does not work|still broken|broken|frustrat|ugh|wtf|why did you|you missed|you forgot)\b",
        re.IGNORECASE,
    ),
    "correction": re.compile(
        r"\b(?:actually|instead|no,|not that|change this|fix this|please correct|that is wrong|should be)\b",
        re.IGNORECASE,
    ),
    "retry_or_repair": re.compile(
        r"\b(?:again|retry|rerun|re-run|try again|fix|repair|debug|fails?|failed|failure|error|crash|missing)\b",
        re.IGNORECASE,
    ),
    "clarification": re.compile(
        r"\b(?:clarify|clarification|what do you mean|explain|more detail|be specific|how do i)\b",
        re.IGNORECASE,
    ),
}


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def jaccard(left: str, right: str) -> float:
    a, b = set(TOKEN_RE.findall(normalize(left))), set(TOKEN_RE.findall(normalize(right)))
    return len(a & b) / len(a | b) if a and b else 0.0


def session_id(record: dict[str, Any]) -> str | None:
    value = record.get("session_id")
    if isinstance(value, str):
        return value
    payload = record.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("id"), str):
        return payload["id"]
    return None


def read_records(paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    sid = session_id(record)
                    if sid:
                        grouped[sid].append(record)
    return grouped


def parse_session(sid: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    users: list[str] = []
    assistant_turns = function_calls = function_outputs = 0
    structured_errors = keyword_errors = successes = 0
    repeated_tools = 0
    prior_tools: Counter[str] = Counter()
    explicit = Counter()
    tool_names = Counter()
    timestamps: list[str] = []
    for record in records:
        timestamp = record.get("timestamp")
        if isinstance(timestamp, str):
            timestamps.append(timestamp)
        kind = record.get("type")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        payload_type = payload.get("type")
        if kind == "event_msg" and payload_type == "user_message":
            text = payload.get("message")
            if isinstance(text, str) and text.strip():
                users.append(text)
                for label, pattern in EXPLICIT.items():
                    if pattern.search(text):
                        explicit[label] += 1
        elif kind == "event_msg" and payload_type == "agent_message":
            assistant_turns += 1
        elif kind == "response_item" and payload_type == "function_call":
            function_calls += 1
            name = str(payload.get("name") or "unknown")
            tool_names[name] += 1
            material = json.dumps(
                {"name": name, "arguments": payload.get("arguments")},
                sort_keys=True,
                separators=(",", ":"),
            )
            key = hashlib.sha256(material.encode()).hexdigest()
            if prior_tools[key]:
                repeated_tools += 1
            prior_tools[key] += 1
        elif kind == "response_item" and payload_type == "function_call_output":
            function_outputs += 1
            exit_code = payload.get("exit_code")
            if isinstance(exit_code, int) and exit_code != 0:
                structured_errors += 1
            output = payload.get("output")
            if isinstance(output, str):
                if ERROR.search(output):
                    keyword_errors += 1
                if re.search(r"\b(?:successfully|build succeeded|exit code 0|all tests pass|tests? passed)\b", output, re.I):
                    successes += 1
    repeated_prompts = rephrases = close_pairs = 0
    for left, right in zip(users, users[1:]):
        score = jaccard(left, right)
        if normalize(left) == normalize(right):
            repeated_prompts += 1
        elif score >= 0.35:
            rephrases += 1
        if score >= 0.55:
            close_pairs += 1
    return {
        "session_id": sid,
        "user_prompt_count": len(users),
        "assistant_turn_count": assistant_turns,
        "function_call_count": function_calls,
        "function_call_output_count": function_outputs,
        "structured_executor_error_count": structured_errors,
        "keyword_error_marker_count": keyword_errors,
        "success_marker_count": successes,
        "explicit_signal_counts": dict(explicit),
        "repeated_tool_use_count": repeated_tools,
        "repeated_prompt_count": repeated_prompts,
        "rephrase_pair_count": rephrases,
        "close_prompt_pair_count": close_pairs,
        "distinct_tool_names": len(tool_names),
        "top_tools": tool_names.most_common(10),
        "timestamp_range": [min(timestamps), max(timestamps)] if timestamps else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = []
    for root in args.input:
        paths.extend(sorted(root.rglob("rollout*.jsonl")) if root.is_dir() else [root])
    grouped = read_records(paths)
    rows = [parse_session(sid, records) for sid, records in sorted(grouped.items())]
    explicit = Counter()
    totals = Counter()
    for row in rows:
        explicit.update(row["explicit_signal_counts"])
        for key in (
            "user_prompt_count", "assistant_turn_count", "function_call_count",
            "function_call_output_count", "structured_executor_error_count",
            "keyword_error_marker_count", "success_marker_count",
            "repeated_tool_use_count", "repeated_prompt_count",
            "rephrase_pair_count", "close_prompt_pair_count",
        ):
            totals[key] += row[key]
    result = {
        "schema_version": "codex-history-friction-result-v1",
        "adapter": "codex_rollout_jsonl_v1",
        "source": {"path_count": len(paths), "raw_content_committed": False},
        "aggregate": {
            "session_count": len(rows),
            "totals": dict(totals),
            "explicit_signal_counts": dict(explicit),
            "sessions_with_any_structured_error": sum(r["structured_executor_error_count"] > 0 for r in rows),
            "sessions_with_rephrase": sum(r["rephrase_pair_count"] > 0 for r in rows),
            "sessions_with_repeated_tool": sum(r["repeated_tool_use_count"] > 0 for r in rows),
        },
        "claim_boundary": "Content-free screening only; exit codes are executor outcomes, not user satisfaction or intent labels.",
        "sessions": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
