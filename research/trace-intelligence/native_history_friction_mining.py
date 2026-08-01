#!/usr/bin/env python3
"""Content-free friction mining for native Claude Code JSONL histories.

The adapter deliberately emits aggregate counts and hashes, never message text.
Signals are screening features, not satisfaction labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "native-history-friction-result-v1"

TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.IGNORECASE)
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
ERROR = re.compile(
    r"\b(?:error|exception|traceback|failed|failure|timed? out|timeout|permission denied|unauthorized|forbidden|no such file|syntaxerror|panic)\b",
    re.IGNORECASE,
)
SUCCESS = re.compile(
    r"\b(?:all tests pass|tests? passed|successfully|build succeeded|completed successfully|exit code 0|approved|merged)\b",
    re.IGNORECASE,
)


def text_blocks(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item
            elif isinstance(item, dict):
                if item.get("type") in {"text", "input_text"} and isinstance(item.get("text"), str):
                    yield item["text"]
                elif item.get("type") == "tool_result":
                    content = item.get("content")
                    yield from text_blocks(content)
    elif isinstance(value, dict):
        for key in ("text", "content", "stdout", "stderr", "output"):
            if key in value:
                yield from text_blocks(value[key])


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def jaccard(left: str, right: str) -> float:
    a, b = set(TOKEN_RE.findall(normalize(left))), set(TOKEN_RE.findall(normalize(right)))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_session(path: Path) -> dict[str, Any]:
    users: list[str] = []
    assistant_turns = 0
    tool_uses = 0
    tool_results = 0
    keyword_error_markers = 0
    structured_errors = 0
    stderr_count = 0
    interrupted_count = 0
    successes = 0
    explicit = Counter()
    tool_names = Counter()
    repeated_tool_use = 0
    prior_tool_keys: Counter[str] = Counter()
    repeated_prompts = 0
    rephrase_pairs = 0
    close_pairs = 0
    user_turns_with_tool_result = 0
    cwd_values: set[str] = set()
    timestamps: list[str] = []

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if isinstance(record.get("cwd"), str):
                cwd_values.add(record["cwd"])
            if isinstance(record.get("timestamp"), str):
                timestamps.append(record["timestamp"])
            kind = record.get("type")
            message = record.get("message") if isinstance(record.get("message"), dict) else {}
            role = message.get("role")
            content = message.get("content")
            blocks = list(content) if isinstance(content, list) else []
            block_types = {b.get("type") for b in blocks if isinstance(b, dict)}

            if kind == "assistant" and role == "assistant":
                assistant_turns += 1
            if kind == "user" and role == "user":
                has_tool_result = "tool_result" in block_types
                if has_tool_result:
                    user_turns_with_tool_result += 1
                else:
                    prompt = "\n".join(text_blocks(content)).strip()
                    if prompt:
                        users.append(prompt)
                        for label, pattern in EXPLICIT.items():
                            if pattern.search(prompt):
                                explicit[label] += 1

            # Count tool calls/results from native content blocks.
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "tool_use":
                    tool_uses += 1
                    name = str(block.get("name") or "unknown")
                    tool_names[name] += 1
                    key_material = json.dumps(
                        {"name": name, "input": block.get("input")},
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    key = hashlib.sha256(key_material.encode()).hexdigest()
                    if prior_tool_keys[key]:
                        repeated_tool_use += 1
                    prior_tool_keys[key] += 1
                elif block_type == "tool_result":
                    tool_results += 1
                    result = "\n".join(text_blocks(block.get("content")))
                    if ERROR.search(result):
                        keyword_error_markers += 1
                    # Native Claude records carry an explicit boolean on many
                    # tool_result blocks.  This is the only signal counted as a
                    # structured executor error here; prose containing the word
                    # "error" is deliberately not treated as a failure.
                    if block.get("is_error") is True:
                        structured_errors += 1
                    if SUCCESS.search(result):
                        successes += 1

            # Native Claude also records executor metadata outside message
            # content.  Count these once per record, while keeping keyword
            # screening separate from structured failure truth.
            tool_use_result = record.get("toolUseResult")
            if isinstance(tool_use_result, dict):
                if tool_use_result.get("is_error") is True and not any(
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and block.get("is_error") is True
                    for block in blocks
                ):
                    structured_errors += 1
                if tool_use_result.get("interrupted") is True:
                    interrupted_count += 1
                if isinstance(tool_use_result.get("stderr"), str) and tool_use_result["stderr"].strip():
                    stderr_count += 1
                result = "\n".join(text_blocks(tool_use_result))
                if result and ERROR.search(result):
                    keyword_error_markers += 1
                if result and SUCCESS.search(result):
                    successes += 1

    for left, right in zip(users, users[1:]):
        score = jaccard(left, right)
        if normalize(left) == normalize(right):
            repeated_prompts += 1
        elif score >= 0.35:
            rephrase_pairs += 1
        if score >= 0.55:
            close_pairs += 1

    return {
        "session_id": path.stem,
        "source_sha256": content_hash(path),
        "bytes": path.stat().st_size,
        "user_prompt_count": len(users),
        "assistant_turn_count": assistant_turns,
        "tool_use_count": tool_uses,
        "tool_result_count": tool_results,
        "tool_result_keyword_error_marker_count": keyword_error_markers,
        "tool_result_structured_error_count": structured_errors,
        "tool_result_stderr_count": stderr_count,
        "tool_result_interrupted_count": interrupted_count,
        "tool_result_success_marker_count": successes,
        "explicit_signal_counts": dict(explicit),
        "repeated_tool_use_count": repeated_tool_use,
        "repeated_prompt_count": repeated_prompts,
        "rephrase_pair_count": rephrase_pairs,
        "close_prompt_pair_count": close_pairs,
        "user_turns_with_tool_result": user_turns_with_tool_result,
        "distinct_tool_names": len(tool_names),
        "top_tools": tool_names.most_common(10),
        "cwd_count": len(cwd_values),
        "timestamp_range": [min(timestamps), max(timestamps)] if timestamps else [],
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    explicit = Counter()
    for row in rows:
        explicit.update(row["explicit_signal_counts"])
    totals = Counter()
    for row in rows:
        for key in (
            "user_prompt_count", "assistant_turn_count", "tool_use_count",
            "tool_result_count", "tool_result_keyword_error_marker_count",
            "tool_result_structured_error_count", "tool_result_stderr_count",
            "tool_result_interrupted_count",
            "tool_result_success_marker_count", "repeated_tool_use_count",
            "repeated_prompt_count", "rephrase_pair_count",
            "close_prompt_pair_count", "user_turns_with_tool_result",
        ):
            totals[key] += row[key]
    return {
        "session_count": len(rows),
        "totals": dict(totals),
        "explicit_signal_counts": dict(explicit),
        "sessions_with_any_structured_error": sum(
            row["tool_result_structured_error_count"] > 0 for row in rows
        ),
        "sessions_with_any_stderr": sum(row["tool_result_stderr_count"] > 0 for row in rows),
        "sessions_with_any_interruption": sum(
            row["tool_result_interrupted_count"] > 0 for row in rows
        ),
        "sessions_with_explicit_dissatisfaction": sum(
            row["explicit_signal_counts"].get("dissatisfaction", 0) > 0 for row in rows
        ),
        "sessions_with_rephrase": sum(row["rephrase_pair_count"] > 0 for row in rows),
        "sessions_with_repeated_tool": sum(row["repeated_tool_use_count"] > 0 for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.input.rglob("*.jsonl"))
    rows = [parse_session(path) for path in paths]
    result = {
        "schema_version": SCHEMA_VERSION,
        "adapter": "claude_code_native_jsonl_v1",
        "source": {"path_count": len(paths), "raw_content_committed": False},
        "aggregate": aggregate(rows),
        "sessions": rows,
        "claim_boundary": (
            "Screening signals only; no satisfaction, correctness, or user-intent gold labels. "
            "Keyword error markers are intentionally separate from structured executor errors; "
            "prompt repetition, stderr, and interruption still require adjudication."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
