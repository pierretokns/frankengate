#!/usr/bin/env python3
"""Aggregate-only Signals-style selection study for a pinned OTel shard."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rows(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist()


def _features(row: dict[str, Any]) -> dict[str, float | bool]:
    spans = row.get("spans") or []
    errors = sum((s.get("status") or {}).get("code") == 2 for s in spans)
    tools = sum(
        "tool" in str(s.get("name", "")).lower()
        or bool((s.get("attributes") or {}).get("gen_ai.tool.definitions"))
        for s in spans
    )
    timestamps = [
        (s.get("start_time"), s.get("end_time"))
        for s in spans
        if s.get("start_time") and s.get("end_time")
    ]
    return {
        "span_count": float(len(spans)),
        "tool_count": float(tools),
        "error_count": float(errors),
        "has_error": bool(errors),
        "timestamp_coverage": len(timestamps) / max(1, len(spans)),
        "total_tokens": float(row.get("total_tokens") or 0),
    }


def _metrics(selected: list[int], labels: list[bool], population: int) -> dict[str, Any]:
    positives = sum(labels)
    selected_positive = sum(labels[i] for i in selected)
    return {
        "selected": len(selected),
        "population": population,
        "population_prevalence": positives / max(1, population),
        "selected_positive": selected_positive,
        "precision": selected_positive / max(1, len(selected)),
        "recall": selected_positive / max(1, positives),
    }


def study(path: Path, *, dataset_revision: str, seed: int = 20260731) -> dict[str, Any]:
    rows = _rows(path)
    features = [_features(row) for row in rows]
    labels = [bool(item["has_error"]) for item in features]
    budget = max(1, len(rows) // 5)
    rng = random.Random(seed)
    random_precisions: list[float] = []
    for _ in range(1000):
        picks = rng.sample(range(len(rows)), budget)
        random_precisions.append(_metrics(picks, labels, len(rows))["precision"])
    rankings = {
        "signals_error_and_tools": sorted(
            range(len(rows)),
            key=lambda i: (features[i]["error_count"], features[i]["tool_count"]),
            reverse=True,
        ),
        "trace_length": sorted(
            range(len(rows)), key=lambda i: features[i]["span_count"], reverse=True
        ),
        "uniform_random_seeded": rng.sample(range(len(rows)), len(rows)),
    }
    arms = {
        name: _metrics(order[:budget], labels, len(rows))
        for name, order in rankings.items()
    }
    arms["uniform_random_seeded"]["precision_mean_1000"] = sum(random_precisions) / len(random_precisions)
    arms["uniform_random_seeded"]["precision_min_1000"] = min(random_precisions)
    arms["uniform_random_seeded"]["precision_max_1000"] = max(random_precisions)
    return {
        "schema_version": "fg-hf-otel-signals-selector-v1",
        "dataset_id": "DiscoPosse/agent-llm-traces",
        "dataset_revision": dataset_revision,
        "source_sha256": _sha256(path),
        "rows": len(rows),
        "budget": budget,
        "label_proxy": "at_least_one_otel_error_status_code_2",
        "label_is_human_informative": False,
        "arms": arms,
        "raw_content_emitted": False,
        "enterprise_behavior_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(study(args.input, dataset_revision=args.dataset_revision), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
