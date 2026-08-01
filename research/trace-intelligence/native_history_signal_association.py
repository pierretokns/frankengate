#!/usr/bin/env python3
"""Content-free association checks for native-history screening signals."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[order[end + 1]] == values[order[start]]:
            end += 1
        value = (start + end) / 2 + 1
        for index in range(start, end + 1):
            result[order[index]] = value
        start = end + 1
    return result


def spearman(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_rank, right_rank = rank(left), rank(right)
    left_mean = sum(left_rank) / len(left_rank)
    right_mean = sum(right_rank) / len(right_rank)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left_rank, right_rank))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left_rank)
        * sum((b - right_mean) ** 2 for b in right_rank)
    )
    return numerator / denominator if denominator else 0.0


def analyze(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("sessions", [])
    error_rate = [
        row["tool_result_structured_error_count"] / row["tool_result_count"]
        if row.get("tool_result_count")
        else 0.0
        for row in rows
    ]
    signals = ["dissatisfaction", "correction", "retry_or_repair", "clarification"]
    associations: dict[str, Any] = {}
    for signal in signals:
        values = [row.get("explicit_signal_counts", {}).get(signal, 0) for row in rows]
        associations[signal] = {
            "spearman_error_rate_vs_signal_count": round(spearman(error_rate, values), 6),
            "sessions_with_signal": sum(value > 0 for value in values),
            "sessions_with_signal_and_structured_error": sum(
                value > 0 and row.get("tool_result_structured_error_count", 0) > 0
                for value, row in zip(values, rows)
            ),
        }
    return {
        "schema_version": "native-history-signal-association-v1",
        "source_schema_version": result.get("schema_version"),
        "session_count": len(rows),
        "associations": associations,
        "claim_boundary": (
            "Descriptive association only; this cohort has no gold friction, satisfaction, "
            "task-success, or intent labels. Negative association must not be interpreted "
            "as evidence that errors improve outcomes."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
