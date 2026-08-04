#!/usr/bin/env python3
"""Summarize two frontier adjudication passes without committing transcripts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--external-zip", type=Path, required=True)
    parser.add_argument("--pass-one", type=Path, required=True)
    parser.add_argument("--pass-two", type=Path, required=True)
    parser.add_argument("--arm-eval", action="append", nargs=2, metavar=("NAME", "EVAL_JSON"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    p1 = json.loads(args.pass_one.read_text(encoding="utf-8"))["results"]
    p2 = json.loads(args.pass_two.read_text(encoding="utf-8"))["results"]
    labels_one = {row["case_id"]: row["label"] for row in p1}
    labels_two = {row["case_id"]: row["label"] for row in p2}
    if set(labels_one) != set(labels_two):
        raise SystemExit("adjudication passes do not contain the same case IDs")

    def accepted(label: str) -> bool:
        return label in {"correct_semantic", "format_only"}

    by_arm: dict[str, Any] = {}
    for name, evaluation in args.arm_eval:
        details = json.loads(Path(evaluation).read_text(encoding="utf-8"))["details"]
        strict_correct = sum(bool(row["correct"]) for row in details)
        prefix = name + ":"
        cases = [case for case in labels_one if case.startswith(prefix)]
        counter = Counter()
        for case in cases:
            a, b = labels_one[case], labels_two[case]
            if accepted(a) and accepted(b):
                counter["accepted_consensus"] += 1
            elif a == "incorrect" and b == "incorrect":
                counter["incorrect_consensus"] += 1
            else:
                counter["judge_disagreement"] += 1
        by_arm[name] = {
            "tasks": 14,
            "strict_terminal_correct": strict_correct,
            "failed_tasks_adjudicated": len(cases),
            "accepted_consensus_on_strict_failures": counter["accepted_consensus"],
            "incorrect_consensus_on_strict_failures": counter["incorrect_consensus"],
            "judge_disagreements_on_strict_failures": counter["judge_disagreement"],
            "conservative_accepted_lower_bound": strict_correct + counter["accepted_consensus"],
            "adjudication_accepted_upper_bound": strict_correct + counter["accepted_consensus"] + counter["judge_disagreement"],
        }

    result = {
        "schema_version": "frankengate-sra-bench-toolqa-semantic-adjudication-v1",
        "dataset": {"name": "toolqa", "tasks": 14, "instances_sha256": sha256(args.instances), "external_corpus_zip_sha256": sha256(args.external_zip)},
        "protocol": {"model": "gpt-5.6-luna", "passes": ["default rubric", "skeptical rubric"], "failed_tasks_only": True, "raw_judgments_committed": False, "promotion_authorized": False},
        "source_hashes": {"pass_one": sha256(args.pass_one), "pass_two": sha256(args.pass_two)},
        "arms": by_arm,
        "claim_boundary": "Two frontier adjudication passes over strict ToolQA failures. Accepted lower/upper bounds are evaluator diagnostics, not human labels, causal skill utility, changed-system outcomes, or enterprise transfer.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": by_arm}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
