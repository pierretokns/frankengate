#!/usr/bin/env python3
"""Audit a stratified sample of the public multi-harness DataClaw corpus.

The Hugging Face rows API is used so the 7+ GB source file is never copied into
the repository. The receipt contains only aggregate counts, category digests,
and structural coverage. It intentionally emits no prompts, commands,
tool-output text, paths, session IDs, or project names.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DATASET = "zhiyaowang/dataclaw-zhiyaowang"
REVISION = "f5157333cbc22489661122a9bc5347b137144900"
ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"
TOKEN_RE = re.compile(r"[^a-z0-9]+", re.I)


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def category_digest(value: Any) -> str:
    return digest(str(value).strip().lower())


def request_row(offset: int, timeout: int) -> tuple[int, dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"dataset": DATASET, "config": "default", "split": "train", "offset": offset, "length": 1}
    )
    with urllib.request.urlopen(f"{ROWS_ENDPOINT}?{query}", timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    total = int(payload.get("num_rows_total", 0))
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f"offset {offset}: malformed rows response")
    row = rows[0].get("row")
    if not isinstance(row, dict):
        raise ValueError(f"offset {offset}: missing row object")
    return total, row


def tool_family(name: Any) -> str:
    text = str(name or "").lower()
    if any(token in text for token in ("bash", "shell", "terminal", "command", "exec", "run_")):
        return "shell"
    if any(token in text for token in ("read", "cat", "list", "glob", "search", "grep", "find")):
        return "read_search"
    if any(token in text for token in ("edit", "write", "patch", "replace", "file")):
        return "file_mutation"
    if any(token in text for token in ("web", "http", "browser", "fetch")):
        return "external_retrieval"
    if any(token in text for token in ("task", "agent", "delegate", "workflow")):
        return "delegation"
    return "other"


def normalized_call(call: dict[str, Any]) -> str:
    """Return a content-free repeat key for a tool call."""
    tool = str(call.get("tool") or call.get("name") or "").lower()
    input_value = call.get("input")
    if isinstance(input_value, dict):
        keys = sorted(str(key).lower() for key in input_value)
    else:
        keys = []
    return digest({"tool": tool, "input_keys": keys})


def inspect_row(row: dict[str, Any]) -> dict[str, Any]:
    messages = row.get("messages") if isinstance(row.get("messages"), list) else []
    message_roles = collections.Counter()
    tools = collections.Counter()
    tool_status = collections.Counter()
    call_keys: list[str] = []
    user_text_count = 0
    content_parts = 0
    output_text_count = 0
    output_raw_count = 0
    error_tool_count = 0
    timestamps = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "missing").lower()
        message_roles[role] += 1
        if isinstance(message.get("timestamp"), str) and message["timestamp"]:
            timestamps += 1
        if role == "user" and isinstance(message.get("content"), str) and message["content"].strip():
            user_text_count += 1
        if isinstance(message.get("content_parts"), list):
            content_parts += len(message["content_parts"])
        uses = message.get("tool_uses") if isinstance(message.get("tool_uses"), list) else []
        for call in uses:
            if not isinstance(call, dict):
                continue
            family = tool_family(call.get("tool") or call.get("name"))
            tools[family] += 1
            call_keys.append(normalized_call(call))
            output = call.get("output")
            if isinstance(output, dict):
                if isinstance(output.get("text"), str):
                    output_text_count += 1
                if "raw" in output:
                    output_raw_count += 1
                status = str(call.get("status") or output.get("status") or "unknown").lower()
                tool_status[status] += 1
                raw = output.get("raw")
                raw_stderr = raw.get("stderr") if isinstance(raw, dict) else None
                if status in {"error", "failed", "failure", "interrupted"} or raw_stderr:
                    error_tool_count += 1
    repeats = len(call_keys) - len(set(call_keys))
    return {
        "session_id_digest": category_digest(row.get("session_id")),
        "project_digest": category_digest(row.get("project")),
        "source_digest": category_digest(row.get("source")),
        "model_digest": category_digest(row.get("model")),
        "message_count": len(messages),
        "message_roles": dict(message_roles),
        "user_text_count": user_text_count,
        "tool_use_count": sum(tools.values()),
        "tool_family_counts": dict(tools),
        "tool_status_counts": dict(tool_status),
        "error_tool_count": error_tool_count,
        "tool_call_repeat_count": repeats,
        "distinct_call_shape_count": len(set(call_keys)),
        "output_text_count": output_text_count,
        "output_raw_count": output_raw_count,
        "content_part_count": content_parts,
        "timestamp_count": timestamps,
        "has_branch": bool(row.get("git_branch")),
    }


def run(*, sample_count: int, timeout: int, output: Path) -> dict[str, Any]:
    if sample_count < 2:
        raise ValueError("sample_count must be >= 2")
    offsets: list[int] = []
    total = 0
    rows_by_offset: dict[int, dict[str, Any]] = {}
    # Discover total from offset zero, then use evenly spaced row positions.
    total, first = request_row(0, timeout)
    offsets = sorted({round(index * (total - 1) / (sample_count - 1)) for index in range(sample_count)})
    rows_by_offset[0] = first
    errors: dict[str, int] = collections.Counter()
    for offset in offsets:
        if offset == 0:
            continue
        try:
            discovered_total, row = request_row(offset, timeout)
            if discovered_total != total:
                errors["row_count_changed"] += 1
            rows_by_offset[offset] = row
        except Exception as exc:  # receipt records sampling gaps without leaking content
            errors[type(exc).__name__] += 1
    inspected = [inspect_row(rows_by_offset[offset]) for offset in sorted(rows_by_offset)]
    role_totals: collections.Counter[str] = collections.Counter()
    family_totals: collections.Counter[str] = collections.Counter()
    status_totals: collections.Counter[str] = collections.Counter()
    source_totals: collections.Counter[str] = collections.Counter()
    model_totals: collections.Counter[str] = collections.Counter()
    project_totals: collections.Counter[str] = collections.Counter()
    for item in inspected:
        role_totals.update(item["message_roles"])
        family_totals.update(item["tool_family_counts"])
        status_totals.update(item["tool_status_counts"])
        source_totals[item["source_digest"]] += 1
        model_totals[item["model_digest"]] += 1
        project_totals[item["project_digest"]] += 1
    mean = lambda key: round(sum(float(item[key]) for item in inspected) / len(inspected), 3) if inspected else 0.0
    result = {
        "schema": "frankengate-dataclaw-zhiyaowang-audit-v1",
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "license": "mit",
            "rows_total": total,
            "sample_offsets": offsets,
            "rows_sampled": len(inspected),
            "sampling_errors": dict(errors),
            "raw_content_committed": False,
        },
        "coverage": {
            "role_counts": dict(role_totals),
            "tool_family_counts": dict(family_totals),
            "tool_status_counts": dict(status_totals),
            "sessions_with_tool_output_text": sum(item["output_text_count"] > 0 for item in inspected),
            "sessions_with_raw_tool_output": sum(item["output_raw_count"] > 0 for item in inspected),
            "sessions_with_branch": sum(item["has_branch"] for item in inspected),
            "sessions_with_explicit_error": sum(item["error_tool_count"] > 0 for item in inspected),
            "sessions_with_repeated_call_shapes": sum(item["tool_call_repeat_count"] > 0 for item in inspected),
            "distinct_source_digest_count": len(source_totals),
            "distinct_model_digest_count": len(model_totals),
            "distinct_project_digest_count": len(project_totals),
        },
        "aggregates": {
            "mean_messages": mean("message_count"),
            "mean_user_text_messages": mean("user_text_count"),
            "mean_tool_uses": mean("tool_use_count"),
            "mean_error_tools": mean("error_tool_count"),
            "mean_repeated_call_shapes": mean("tool_call_repeat_count"),
            "mean_distinct_call_shapes": mean("distinct_call_shape_count"),
            "mean_output_texts": mean("output_text_count"),
            "mean_raw_outputs": mean("output_raw_count"),
            "mean_content_parts": mean("content_part_count"),
        },
        "claim_boundary": {
            "complete_history_structure_verified_on_sample": True,
            "cross_user_identity_verified": False,
            "task_outcome_verified": False,
            "skill_transfer_verified": False,
            "reason": "The corpus supplies richer multi-harness messages and tool outputs than the earlier flattened export, enabling artifact/friction mining pilots; it still has no independent task-success labels or organizational identity, and this is a stratified sample rather than a full-corpus causal study.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows_total": total, "rows_sampled": len(inspected), "coverage": result["coverage"]}, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-count", type=int, default=32)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(sample_count=args.sample_count, timeout=args.timeout, output=args.output)


if __name__ == "__main__":
    main()
