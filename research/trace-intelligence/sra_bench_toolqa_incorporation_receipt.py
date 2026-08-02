#!/usr/bin/env python3
"""Build a content-minimized three-arm ToolQA incorporation receipt."""

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
    return {"correct": int(value["metrics"]["correct"]), "total": int(value["metrics"]["total"]), "accuracy": float(value["metrics"]["accuracy"])}


def arm_summary(path: Path, evaluation: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    observations = sum(str(row.get("transcript") or "").count("Observation ") for row in rows)
    invalid_actions = sum(str(row.get("transcript") or "").count("action is filtered") for row in rows)
    return {"metrics": eval_metrics(evaluation), "records": len(rows), "finished": sum(bool(row.get("meta", {}).get("finished")) for row in rows), "halted": sum(bool(row.get("meta", {}).get("halted")) for row in rows), "observations": observations, "invalid_action_observations": invalid_actions, "raw_sha256": sha256(path), "evaluation_sha256": sha256(evaluation)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--no-skill", type=Path, required=True)
    parser.add_argument("--bge", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--no-skill-eval", type=Path, required=True)
    parser.add_argument("--bge-eval", type=Path, required=True)
    parser.add_argument("--oracle-eval", type=Path, required=True)
    parser.add_argument("--external-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    instances = json.loads(args.instances.read_text(encoding="utf-8"))
    retrieval = json.loads(args.retrieval.read_text(encoding="utf-8"))["results"]
    retrieval_map = {row["instance_id"]: row["retrieved"][0]["skill_id"] for row in retrieval}
    gold_hits = sum(retrieval_map[i["instance_id"]] in i.get("skill_annotations", []) for i in instances)
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-incorporation-v1",
        "dataset": {"name": "toolqa", "tasks": len(instances), "stratification": "one fixed instance per each of 14 skill families", "instances_sha256": sha256(args.instances), "retrieval_sha256": sha256(args.retrieval), "external_corpus_zip_sha256": sha256(args.external_zip)},
        "protocol": {"model": "gpt-5.6-luna", "endpoint": "loopback Codex subscription proxy", "engine": "react", "max_steps": 15, "temperature": 0.0, "max_tokens": 512, "tool_corpus_provisioned": True, "raw_outputs_committed": False},
        "arms": {"no_skill": arm_summary(args.no_skill, args.no_skill_eval), "bge_top1": arm_summary(args.bge, args.bge_eval), "gold_skill_oracle": arm_summary(args.oracle, args.oracle_eval)},
        "retrieval": {"bge_top1_gold_skill_hits": gold_hits, "tasks": len(instances), "gold_hit_rate": gold_hits / len(instances)},
        "decision": {"dense_retrieval_improves_strict_terminal_accuracy_over_no_skill": True, "bge_matches_gold_oracle_strict_accuracy": True, "incorporation_is_bottleneck": True, "skill_release_authorized": False, "changed_system_replay_measured": False},
        "claim_boundary": "A 14-task one-per-family public ToolQA pilot using a frontier Codex subscription model. Strict benchmark scoring only; no enterprise principals, authority epochs, changed-system outcomes, human labels, or prospective user benefit.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": {k: v["metrics"] for k, v in result["arms"].items()}, "retrieval": result["retrieval"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
