"""Compare content-free governed Defog receipts across harnesses."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any


SCHEMA_VERSION = "frankengate-defog-family-transfer-analysis-v1"


class AnalysisError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("task_runs"), list):
        raise AnalysisError(f"invalid content-free result: {path}")
    return value


def _task_arm_map(value: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {}
    for row in value["task_runs"]:
        if not isinstance(row, dict):
            raise AnalysisError("task receipt is not an object")
        key = (str(row["task_id_sha256"]), str(row["arm"]))
        if key in rows:
            raise AnalysisError("duplicate task/arm receipt")
        rows[key] = row
    return rows


def analyze(*, inputs: list[tuple[str, Path]], output: Path) -> dict[str, Any]:
    if len(inputs) < 2:
        raise AnalysisError("at least two harness results are required")
    loaded = [(harness, path, _load(path)) for harness, path in inputs]
    maps = [(harness, path, _task_arm_map(value)) for harness, path, value in loaded]
    keys = set(maps[0][2])
    if any(set(item[2]) != keys for item in maps[1:]):
        raise AnalysisError("harness results do not share the same task/arm set")
    task_families = {value.get("dataset", {}).get("database_family") for _, _, value in loaded}
    if len(task_families) != 1 or None in task_families:
        raise AnalysisError("database family is missing or differs")
    arm_metrics: dict[str, dict[str, dict[str, Any]]] = {}
    for harness, _, rows in maps:
        by_arm: dict[str, list[dict[str, Any]]] = {}
        for (_, arm), row in rows.items():
            by_arm.setdefault(arm, []).append(row)
        arm_metrics[harness] = {}
        for arm, values in sorted(by_arm.items()):
            valid = sum(bool(row.get("authority_valid")) for row in values)
            terminal = sum(row.get("terminal_action") != "none" for row in values)
            semantic = sum(bool(row.get("semantic_correct")) for row in values)
            unauthorized = sum(bool(row.get("unauthorized_observation")) for row in values)
            arm_metrics[harness][arm] = {
                "tasks": len(values),
                "authority_valid": valid,
                "terminal_submissions": terminal,
                "semantic_correct": semantic,
                "unauthorized_observation": unauthorized,
                "successful_sql_attempts": sum(int(row.get("successful_sql_attempts", 0)) for row in values),
                "mean_elapsed_ms": mean(float(row.get("elapsed_ms", 0.0)) for row in values),
            }
    result = {
        "schema_version": SCHEMA_VERSION,
        "classification": "family_disjoint_governed_harness_transfer",
        "database_family": next(iter(task_families)),
        "task_count": len({task for task, _ in keys}),
        "task_id_hashes": sorted({task for task, _ in keys}),
        "harnesses": [
            {"id": harness, "source_result_sha256": _sha256_file(path)}
            for harness, path, _ in loaded
        ],
        "arm_metrics": arm_metrics,
        "claim_boundary": {
            "all_authority_valid": all(
                metrics["authority_valid"] == metrics["tasks"]
                for by_arm in arm_metrics.values()
                for metrics in by_arm.values()
            ),
            "unauthorized_observations": sum(
                metrics["unauthorized_observation"]
                for by_arm in arm_metrics.values()
                for metrics in by_arm.values()
            ),
            "causal_skill_benefit_established": False,
            "semantic_quality_estimated": False,
            "reason": "Every arm failed the terminal protocol on this Llama family-transfer slice; no submitted answer exists to score semantically.",
            "next_required": "Repair or replace the model/tool protocol before a held-out semantic skill comparison; then evaluate all required proposal arms with an independent verifier.",
        },
        "raw_data_committed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", nargs=2, metavar=("HARNESS", "PATH"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(inputs=[(name, Path(path)) for name, path in args.input], output=args.output)
    print(json.dumps({"status": "ok", "classification": result["classification"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
