#!/usr/bin/env python3
"""Content-free mining of current Codex archived rollout JSONL.

Current Codex archives store one rollout per file and put events under a
``payload`` object.  The older ``codex_history_friction_mining.py`` adapter
expects a different rollout schema and therefore must not be used on these
files.  This adapter emits only aggregate/session counters and source hashes;
prompts, tool arguments, outputs, and identifiers never enter the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "codex-archive-history-mining-v1"
TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.IGNORECASE)
ERROR = re.compile(
    r"\b(?:error|exception|traceback|failed|failure|timed? out|timeout|permission denied|unauthorized|forbidden|no such file|syntaxerror|panic)\b",
    re.IGNORECASE,
)
NONZERO_EXIT = re.compile(r"(?:process )?exited with code\s*[1-9]\d*", re.IGNORECASE)
SUCCESS = re.compile(
    r"\b(?:all tests pass|tests? passed|successfully|build succeeded|exit code 0|approved|merged)\b",
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def jaccard(left: str, right: str) -> float:
    a, b = set(TOKEN_RE.findall(normalize(left))), set(TOKEN_RE.findall(normalize(right)))
    return len(a & b) / len(a | b) if a and b else 0.0


def payload_text(payload: dict[str, Any]) -> str:
    value = payload.get("message", payload.get("output", ""))
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""


def parse_session(path: Path) -> dict[str, Any]:
    user_prompts: list[str] = []
    episodes: list[dict[str, Any]] = []
    current_episode: dict[str, Any] | None = None
    assistant_turns = 0
    function_calls = function_outputs = custom_calls = custom_outputs = 0
    structured_errors = keyword_errors = successes = 0
    repeated_tools = 0
    prior_tools: Counter[str] = Counter()
    explicit = Counter()
    tool_names = Counter()
    timestamps: list[str] = []
    cwd_values: set[str] = set()
    model_values: set[str] = set()

    def begin_episode(prompt: str) -> None:
        nonlocal current_episode
        if current_episode is not None:
            episodes.append(current_episode)
        current_episode = {
            "prompt": prompt,
            "explicit_signal_counts": Counter(),
            "structured_error_count": 0,
            "keyword_error_count": 0,
            "success_marker_count": 0,
            "tool_result_count": 0,
        }

    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if isinstance(record.get("timestamp"), str):
                timestamps.append(record["timestamp"])
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = payload.get("type")
            if isinstance(payload.get("cwd"), str):
                cwd_values.add(payload["cwd"])
            if isinstance(payload.get("model"), str):
                model_values.add(payload["model"])

            if kind == "user_message":
                prompt = payload_text(payload).strip()
                if prompt:
                    user_prompts.append(prompt)
                    begin_episode(prompt)
                    for label, pattern in EXPLICIT.items():
                        if pattern.search(prompt):
                            explicit[label] += 1
                            current_episode["explicit_signal_counts"][label] += 1
            elif kind in {"agent_message", "message"}:
                if payload.get("role") == "assistant" or kind == "agent_message":
                    assistant_turns += 1
                if kind == "message" and payload.get("role") == "user":
                    prompt = payload_text(payload).strip()
                    if prompt:
                        user_prompts.append(prompt)
                        begin_episode(prompt)
                        for label, pattern in EXPLICIT.items():
                            if pattern.search(prompt):
                                explicit[label] += 1
                                current_episode["explicit_signal_counts"][label] += 1
            elif kind == "function_call":
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
            elif kind == "function_call_output":
                function_outputs += 1
                output = payload_text(payload)
                if current_episode is not None:
                    current_episode["tool_result_count"] += 1
                if NONZERO_EXIT.search(output):
                    structured_errors += 1
                    if current_episode is not None:
                        current_episode["structured_error_count"] += 1
                if ERROR.search(output):
                    keyword_errors += 1
                    if current_episode is not None:
                        current_episode["keyword_error_count"] += 1
                if SUCCESS.search(output):
                    successes += 1
                    if current_episode is not None:
                        current_episode["success_marker_count"] += 1
            elif kind == "custom_tool_call":
                custom_calls += 1
                name = str(payload.get("name") or "unknown")
                tool_names[name] += 1
                material = json.dumps(
                    {"name": name, "input": payload.get("input")},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                key = hashlib.sha256(material.encode()).hexdigest()
                if prior_tools[key]:
                    repeated_tools += 1
                prior_tools[key] += 1
            elif kind == "custom_tool_call_output":
                custom_outputs += 1
                output = payload_text(payload)
                if current_episode is not None:
                    current_episode["tool_result_count"] += 1
                if ERROR.search(output):
                    keyword_errors += 1
                    if current_episode is not None:
                        current_episode["keyword_error_count"] += 1
                if SUCCESS.search(output):
                    successes += 1
                    if current_episode is not None:
                        current_episode["success_marker_count"] += 1

    if current_episode is not None:
        episodes.append(current_episode)

    repeated_prompts = rephrase_pairs = close_pairs = 0
    for left, right in zip(user_prompts, user_prompts[1:]):
        score = jaccard(left, right)
        if normalize(left) == normalize(right):
            repeated_prompts += 1
        elif score >= 0.35:
            rephrase_pairs += 1
        if score >= 0.55:
            close_pairs += 1

    recovery_episodes = sum(
        left["structured_error_count"] > 0
        and bool(
            right["explicit_signal_counts"].get("retry_or_repair")
            or right["explicit_signal_counts"].get("correction")
        )
        for left, right in zip(episodes, episodes[1:])
    )
    episode_error_count = sum(episode["structured_error_count"] > 0 for episode in episodes)
    episode_success_count = sum(episode["success_marker_count"] > 0 for episode in episodes)
    episode_error_then_success_count = sum(
        episode["structured_error_count"] > 0 and episode["success_marker_count"] > 0
        for episode in episodes
    )
    predicted_friction_count = sum(bool(episode["explicit_signal_counts"]) for episode in episodes)
    friction_error_true_positive_count = sum(
        bool(episode["explicit_signal_counts"]) and episode["structured_error_count"] > 0
        for episode in episodes
    )
    friction_false_positive_count = sum(
        bool(episode["explicit_signal_counts"]) and episode["structured_error_count"] == 0
        for episode in episodes
    )
    friction_false_negative_count = sum(
        not bool(episode["explicit_signal_counts"]) and episode["structured_error_count"] > 0
        for episode in episodes
    )

    return {
        "session_id": path.stem,
        "source_sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "user_prompt_count": len(user_prompts),
        "assistant_turn_count": assistant_turns,
        "function_call_count": function_calls,
        "function_call_output_count": function_outputs,
        "custom_tool_call_count": custom_calls,
        "custom_tool_call_output_count": custom_outputs,
        "structured_executor_error_count": structured_errors,
        "keyword_error_marker_count": keyword_errors,
        "success_marker_count": successes,
        "explicit_signal_counts": dict(explicit),
        "repeated_tool_use_count": repeated_tools,
        "repeated_prompt_count": repeated_prompts,
        "rephrase_pair_count": rephrase_pairs,
        "close_prompt_pair_count": close_pairs,
        "episode_count": len(episodes),
        "episodes_with_tool_result": sum(episode["tool_result_count"] > 0 for episode in episodes),
        "episodes_with_structured_error": episode_error_count,
        "episodes_with_success_marker": episode_success_count,
        "episodes_error_then_success": episode_error_then_success_count,
        "episodes_with_unresolved_structured_error": sum(
            episode["structured_error_count"] > 0 and episode["success_marker_count"] == 0
            for episode in episodes
        ),
        "recovery_after_error_prompt_count": recovery_episodes,
        "friction_episode_count": sum(
            bool(episode["explicit_signal_counts"])
            or episode["structured_error_count"] > 0
            for episode in episodes
        ),
        "predicted_friction_count": predicted_friction_count,
        "friction_error_true_positive_count": friction_error_true_positive_count,
        "friction_false_positive_count": friction_false_positive_count,
        "friction_false_negative_count": friction_false_negative_count,
        "distinct_tool_names": len(tool_names),
        "top_tools": tool_names.most_common(10),
        "cwd_count": len(cwd_values),
        "model_count": len(model_values),
        "timestamp_range": [min(timestamps), max(timestamps)] if timestamps else [],
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    explicit = Counter()
    totals = Counter()
    total_fields = (
        "user_prompt_count", "assistant_turn_count", "function_call_count",
        "function_call_output_count", "custom_tool_call_count",
        "custom_tool_call_output_count", "structured_executor_error_count",
        "keyword_error_marker_count", "success_marker_count",
        "repeated_tool_use_count", "repeated_prompt_count",
        "rephrase_pair_count", "close_prompt_pair_count",
        "episode_count", "episodes_with_tool_result", "episodes_with_structured_error",
        "episodes_with_success_marker", "episodes_error_then_success",
        "episodes_with_unresolved_structured_error", "recovery_after_error_prompt_count",
        "friction_episode_count",
        "predicted_friction_count", "friction_error_true_positive_count",
        "friction_false_positive_count", "friction_false_negative_count",
    )
    for row in rows:
        explicit.update(row["explicit_signal_counts"])
        for field in total_fields:
            totals[field] += row[field]
    return {
        "session_count": len(rows),
        "totals": dict(totals),
        "explicit_signal_counts": dict(explicit),
        "sessions_with_any_structured_error": sum(row["structured_executor_error_count"] > 0 for row in rows),
        "sessions_with_rephrase": sum(row["rephrase_pair_count"] > 0 for row in rows),
        "sessions_with_repeated_prompt": sum(row["repeated_prompt_count"] > 0 for row in rows),
        "sessions_with_repeated_tool": sum(row["repeated_tool_use_count"] > 0 for row in rows),
        "friction_detector_confusion": {
            "predicted_friction": totals["predicted_friction_count"],
            "structured_error": totals["episodes_with_structured_error"],
            "true_positive": totals["friction_error_true_positive_count"],
            "false_positive": totals["friction_false_positive_count"],
            "false_negative": totals["friction_false_negative_count"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths: list[Path] = []
    for root in args.input:
        paths.extend(sorted(root.glob("rollout-*.jsonl")) if root.is_dir() else [root])
    rows = [parse_session(path) for path in paths]
    result = {
        "schema_version": SCHEMA_VERSION,
        "adapter": "codex_archive_rollout_jsonl_v1",
        "source": {"path_count": len(paths), "raw_content_committed": False},
        "aggregate": aggregate(rows),
        "claim_boundary": "Content-free screening only; keyword markers are not satisfaction labels, and executor signals are not independent task outcomes or intent labels.",
        "sessions": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path_count": len(paths), "aggregate": result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
