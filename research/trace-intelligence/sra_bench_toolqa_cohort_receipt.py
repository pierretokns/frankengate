#!/usr/bin/env python3
"""Build a content-minimized receipt for the two-per-family ToolQA cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return {"correct": int(value["metrics"]["correct"]), "total": int(value["metrics"]["total"]), "accuracy": float(value["metrics"]["accuracy"])}


def semantic_summary(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    labels = {}
    for row in value.get("results", []):
        key = f"{row.get('arm')}:{row.get('label')}"
        labels[key] = labels.get(key, 0) + 1
    return {"cases_requested": int(value.get("cases_requested", 0)), "results": len(value.get("results", [])), "failures": len(value.get("failures", [])), "labels": labels, "sha256": sha256(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--external-zip", type=Path, required=True)
    parser.add_argument("--execution-audit", type=Path, required=True)
    parser.add_argument("--semantic", type=Path, required=True)
    parser.add_argument("--skeptical-semantic", type=Path, required=True)
    parser.add_argument("--arm", action="append", nargs=3, metavar=("NAME", "RAW_JSONL", "EVAL_JSON"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    instances = json.loads(args.instances.read_text(encoding="utf-8"))
    arms: dict[str, Any] = {}
    for name, raw_value, evaluation_value in args.arm:
        raw_path, evaluation_path = Path(raw_value), Path(evaluation_value)
        rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        arms[name] = {"metrics": metrics(evaluation_path), "records": len(rows), "raw_sha256": sha256(raw_path), "evaluation_sha256": sha256(evaluation_path)}
    execution = json.loads(args.execution_audit.read_text(encoding="utf-8"))
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-two-per-family-v1",
        "dataset": {"name": "toolqa", "tasks": len(instances), "stratification": "two held-out instances per each of 14 skill families; pilot first instance excluded", "instances_sha256": sha256(args.instances), "external_corpus_zip_sha256": sha256(args.external_zip)},
        "protocol": {"model": "gpt-5.6-luna", "endpoint": "loopback Codex subscription proxy", "engine": "react", "max_steps": 15, "temperature": 0.0, "max_tokens": 512, "tool_corpus_provisioned": True, "raw_outputs_committed": False},
        "arms": arms,
        "execution_audit": {"schema_version": execution["schema_version"], "arms": {name: {key: value for key, value in arm.items() if key not in ("per_task",)} for name, arm in execution["arms"].items()}, "sha256": sha256(args.execution_audit)},
        "semantic_probe": {"normal": semantic_summary(args.semantic), "skeptical": semantic_summary(args.skeptical_semantic)},
        "decision": {"dense_retrieval_improves_strict_terminal_accuracy_over_no_skill": True, "gold_skill_oracle_beats_bge_top1_strict_accuracy": True, "retrieval_and_execution_metrics_must_be_reported_separately": True, "skill_release_authorized": False, "changed_system_replay_measured": False},
        "claim_boundary": "A 28-task, family-disjoint public ToolQA cohort using one frontier Codex subscription model. Strict scoring and deterministic execution diagnostics are not enterprise transfer, causal skill utility, human productivity, or changed-system replay evidence. The 12-case semantic probes are bounded diagnostics, not a full semantic relabeling.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": {name: arm["metrics"] for name, arm in arms.items()}, "execution": result["execution_audit"]["arms"], "semantic_probe": result["semantic_probe"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
