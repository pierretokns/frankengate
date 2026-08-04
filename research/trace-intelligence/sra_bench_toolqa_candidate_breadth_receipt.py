#!/usr/bin/env python3
"""Build a content-minimized ToolQA candidate-breadth receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def eval_metrics(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    metrics = value["metrics"]
    return {
        "correct": int(metrics["correct"]),
        "total": int(metrics["total"]),
        "accuracy": float(metrics["accuracy"]),
    }


def arm_summary(path: Path, evaluation: Path, gold_by_instance: dict[str, set[str]]) -> dict[str, Any]:
    rows = load_jsonl(path)
    loaded = [list(row.get("skill_ids_used") or []) for row in rows]
    exact_gold_loaded = sum(bool(set(ids) & gold_by_instance.get(row["instance_id"], set())) for row, ids in zip(rows, loaded))
    return {
        "metrics": eval_metrics(evaluation),
        "records": len(rows),
        "finished": sum(bool(row.get("meta", {}).get("finished")) for row in rows),
        "halted": sum(bool(row.get("meta", {}).get("halted")) for row in rows),
        "observations": sum(str(row.get("transcript") or "").count("Observation ") for row in rows),
        "loaded_skill_count_total": sum(len(ids) for ids in loaded),
        "loaded_skill_count_mean": (sum(len(ids) for ids in loaded) / len(rows)) if rows else 0.0,
        "exact_gold_skill_loaded": exact_gold_loaded,
        "raw_sha256": sha256(path),
        "evaluation_sha256": sha256(evaluation),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--no-skill", type=Path, required=True)
    parser.add_argument("--bge-top1", type=Path, required=True)
    parser.add_argument("--bge-top5", type=Path, required=True)
    parser.add_argument("--bge-progressive", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--no-skill-eval", type=Path, required=True)
    parser.add_argument("--bge-top1-eval", type=Path, required=True)
    parser.add_argument("--bge-top5-eval", type=Path, required=True)
    parser.add_argument("--bge-progressive-eval", type=Path, required=True)
    parser.add_argument("--oracle-eval", type=Path, required=True)
    parser.add_argument("--external-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    instances = json.loads(args.instances.read_text(encoding="utf-8"))
    retrieval = json.loads(args.retrieval.read_text(encoding="utf-8"))["results"]
    retrieval_map = {row["instance_id"]: row["retrieved"] for row in retrieval}
    gold_by_instance = {row["instance_id"]: set(row.get("gold_skill_ids", [])) for row in retrieval}
    selected = [row for row in instances if row["instance_id"] in retrieval_map]
    top1_hits = sum(bool(retrieval_map[row["instance_id"]][:1] and retrieval_map[row["instance_id"]][0]["skill_id"] in gold_by_instance[row["instance_id"]]) for row in selected)
    top5_hits = sum(any(item["skill_id"] in gold_by_instance[row["instance_id"]] for item in retrieval_map[row["instance_id"]][:5]) for row in selected)

    arms = {
        "no_skill": arm_summary(args.no_skill, args.no_skill_eval, gold_by_instance),
        "bge_top1": arm_summary(args.bge_top1, args.bge_top1_eval, gold_by_instance),
        "bge_top5_full_injection": arm_summary(args.bge_top5, args.bge_top5_eval, gold_by_instance),
        "bge_progressive_disclosure": arm_summary(args.bge_progressive, args.bge_progressive_eval, gold_by_instance),
        "gold_skill_oracle": arm_summary(args.oracle, args.oracle_eval, gold_by_instance),
    }
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-candidate-breadth-v1",
        "dataset": {
            "name": "toolqa",
            "tasks": len(instances),
            "stratification": "one fixed instance per each of 14 skill families",
            "instances_sha256": sha256(args.instances),
            "retrieval_sha256": sha256(args.retrieval),
            "external_corpus_zip_sha256": sha256(args.external_zip),
        },
        "protocol": {
            "model": "gpt-5.6-luna",
            "endpoint": "loopback Codex subscription proxy",
            "engine": "react; progressive arm uses react_progressive_disclosure",
            "max_steps": 15,
            "temperature": 0.0,
            "max_tokens": 512,
            "tool_corpus_provisioned": True,
            "raw_outputs_committed": False,
        },
        "arms": arms,
        "retrieval": {
            "tasks": len(selected),
            "bge_top1_gold_skill_hits": top1_hits,
            "bge_top5_candidate_gold_skill_hits": top5_hits,
            "bge_top1_gold_hit_rate": top1_hits / len(selected),
            "bge_top5_candidate_gold_hit_rate": top5_hits / len(selected),
        },
        "decision": {
            "dense_retrieval_improves_over_no_skill": arms["bge_top1"]["metrics"]["correct"] > arms["no_skill"]["metrics"]["correct"],
            "top5_full_injection_hurts_vs_top1": arms["bge_top5_full_injection"]["metrics"]["correct"] < arms["bge_top1"]["metrics"]["correct"],
            "progressive_matches_top1": arms["bge_progressive_disclosure"]["metrics"]["correct"] == arms["bge_top1"]["metrics"]["correct"],
            "top1_matches_gold_oracle": arms["bge_top1"]["metrics"]["correct"] == arms["gold_skill_oracle"]["metrics"]["correct"],
            "skill_release_authorized": False,
            "changed_system_replay_measured": False,
        },
        "claim_boundary": "A 14-task one-per-family public ToolQA pilot using a frontier Codex subscription model. Strict benchmark scoring only; no enterprise principals, authority epochs, changed-system outcomes, human labels, or prospective user benefit.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": {key: value["metrics"] for key, value in arms.items()}, "retrieval": result["retrieval"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
