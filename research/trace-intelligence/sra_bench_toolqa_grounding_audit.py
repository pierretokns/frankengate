#!/usr/bin/env python3
"""Audit whether ToolQA gold answers appeared in tool observations before failure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import string
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize(value: str) -> str:
    text = "".join(ch for ch in value.lower() if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the|usd)\b", " ", text)
    return " ".join(text.split())


def observations(transcript: str) -> str:
    chunks = re.findall(r"Observation \d+: (.*?)(?=\nThought \d+:|\nAction \d+:|\Z)", transcript, flags=re.S)
    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--external-zip", type=Path, required=True)
    parser.add_argument("--arm", action="append", nargs=3, metavar=("NAME", "RAW_JSONL", "EVAL_JSON"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    instances = json.loads(args.instances.read_text(encoding="utf-8"))
    by_id = {row["instance_id"]: row for row in instances}
    arms: dict[str, Any] = {}
    for name, raw_value, eval_value in args.arm:
        raw_path, eval_path = Path(raw_value), Path(eval_value)
        rows = load_jsonl(raw_path)
        details = {row["instance_id"]: row for row in json.loads(eval_path.read_text(encoding="utf-8"))["details"]}
        records = []
        for row in rows:
            instance_id = row["instance_id"]
            gold = str(by_id[instance_id]["eval_data"]["answer"])
            obs = observations(str(row.get("transcript") or ""))
            gold_norm = normalize(gold)
            in_obs = bool(gold_norm) and gold_norm in normalize(obs)
            correct = bool(details[instance_id]["correct"])
            records.append({"instance_id": instance_id, "terminal_correct": correct, "gold_in_observation": in_obs, "gold_observed_but_terminal_wrong": in_obs and not correct})
        arms[name] = {
            "records": len(records),
            "terminal_correct": sum(row["terminal_correct"] for row in records),
            "gold_in_observation": sum(row["gold_in_observation"] for row in records),
            "gold_observed_but_terminal_wrong": sum(row["gold_observed_but_terminal_wrong"] for row in records),
            "per_task": records,
            "raw_sha256": sha256(raw_path),
            "evaluation_sha256": sha256(eval_path),
        }
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-grounding-audit-v1",
        "dataset": {"name": "toolqa", "tasks": len(instances), "instances_sha256": sha256(args.instances), "external_corpus_zip_sha256": sha256(args.external_zip)},
        "protocol": {"grounding_rule": "normalized gold answer substring in parsed Observation sections", "semantic_inference": False, "promotion_authorized": False},
        "arms": arms,
        "claim_boundary": "Observation-grounding diagnostic over the completed 14-task public ToolQA arms. A gold substring in an observation is a candidate evidence signal, not a semantic label or independent terminal outcome.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": {name: {key: arm[key] for key in ("records", "terminal_correct", "gold_in_observation", "gold_observed_but_terminal_wrong")} for name, arm in arms.items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
