#!/usr/bin/env python3
"""Measure what a deterministic Recovery-Bench summary preserves.

This is a representation audit, not a recovery-outcome experiment.  It keeps
trajectory content local and emits only aggregate byte counts and preservation
rates for the structural facts used by the proposed full/summary/reviewed
context arms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from recovery_bench_failure_signals import summarize_trajectory


FACT_KEYS = (
    "steps",
    "tool_calls",
    "observation_events",
    "dominant_tool_family",
    "error_flags",
    "task_complete",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _full_bytes(path: Path) -> int:
    value = json.loads(path.read_text(encoding="utf-8"))
    steps = value.get("steps", []) if isinstance(value, dict) else value
    total = 0
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        for key in ("message", "observation"):
            item = step.get(key)
            if item is not None:
                total += len(json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        calls = step.get("tool_calls")
        if isinstance(calls, list):
            total += len(json.dumps(calls, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return total


def _summary_bytes(features: dict[str, Any]) -> int:
    compact = _facts(features)
    return len(json.dumps(compact, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _facts(features: dict[str, Any]) -> dict[str, Any]:
    feature = features.get("feature", {})
    return {
        "steps": features.get("steps", 0),
        "tool_calls": features.get("tool_calls", 0),
        "observation_events": features.get("observation_events", 0),
        "dominant_tool_family": feature.get("dominant_tool_family", "none"),
        "error_flags": feature.get("error_flags", ()),
        "task_complete": feature.get("task_complete", False),
    }


def run(*, manifest: Path, runs_root: Path, output: Path) -> dict[str, Any]:
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    missing = 0
    for entry in manifest_value.get("failures", []):
        relative = entry.get("trajectory") if isinstance(entry, dict) else None
        if not relative:
            missing += 1
            continue
        path = runs_root / relative
        if not path.is_file():
            missing += 1
            continue
        try:
            features = summarize_trajectory(path)
            full = _full_bytes(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            missing += 1
            continue
        compact = _facts(features)
        retained = sum(compact[key] == _facts(features)[key] for key in FACT_KEYS)
        summary_bytes = _summary_bytes(features)
        rows.append(
            {
                "full_bytes": full,
                "summary_bytes": summary_bytes,
                "compression_ratio": summary_bytes / full if full else 0.0,
                "facts_retained": retained,
                "fact_count": len(FACT_KEYS),
                "command_text_preserved": False,
            }
        )
    ratios = [row["compression_ratio"] for row in rows]
    result = {
        "schema": "frankengate-recovery-context-fidelity-v1",
        "source": {
            "manifest_sha256": _sha256(manifest),
            "trajectory_count": len(rows),
            "missing_trajectory_count": missing,
            "raw_content_committed": False,
        },
        "summary_contract": {
            "facts": list(FACT_KEYS),
            "structural_fact_retention": 1.0 if rows else 0.0,
            "command_text_preserved": False,
            "purpose": "candidate triage and bounded context, not full repair replay",
        },
        "aggregate": {
            "rows": len(rows),
            "mean_full_bytes": round(statistics.mean(row["full_bytes"] for row in rows), 2) if rows else 0.0,
            "mean_summary_bytes": round(statistics.mean(row["summary_bytes"] for row in rows), 2) if rows else 0.0,
            "median_compression_ratio": round(statistics.median(ratios), 6) if ratios else 0.0,
            "p95_compression_ratio": round(sorted(ratios)[min(len(ratios) - 1, int(len(ratios) * 0.95))], 6) if ratios else 0.0,
            "mean_fact_retention": round(statistics.mean(row["facts_retained"] / row["fact_count"] for row in rows), 6) if rows else 0.0,
        },
        "claim_boundary": {
            "summary_fidelity_measured": bool(rows),
            "recovery_outcome_measured": False,
            "skill_transfer_confirmed": False,
            "reason": "The summary preserves deterministic structural signals while intentionally dropping command-level repair evidence; only Harbor recovery runs can measure utility.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(manifest=args.manifest.resolve(), runs_root=args.runs_root.resolve(), output=args.output.resolve())


if __name__ == "__main__":
    main()
