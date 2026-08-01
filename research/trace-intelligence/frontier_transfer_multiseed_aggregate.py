#!/usr/bin/env python3
"""Aggregate matched frontier family-transfer receipts across seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
from itertools import combinations


SCHEMA_VERSION = "frankengate-frontier-transfer-multiseed-aggregate-v1"


def _mcnemar_p(discordant_a: int, discordant_b: int) -> float:
    total = discordant_a + discordant_b
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(min(discordant_a, discordant_b) + 1)) / (2 ** total)
    return min(1.0, 2 * tail)


def _pairwise(rows: dict[tuple[int, str], dict[str, bool]], left: str, right: str) -> dict[str, Any]:
    left_wins = right_wins = ties = 0
    for values in rows.values():
        l = values.get(left)
        r = values.get(right)
        if l is None or r is None:
            continue
        if l and not r:
            left_wins += 1
        elif r and not l:
            right_wins += 1
        else:
            ties += 1
    total = left_wins + right_wins + ties
    return {
        "left": left,
        "right": right,
        "paired_episodes": total,
        "left_wins": left_wins,
        "right_wins": right_wins,
        "ties": ties,
        "risk_difference": round((left_wins - right_wins) / total, 6) if total else 0.0,
        "mcnemar_exact_two_sided_p": round(_mcnemar_p(left_wins, right_wins), 6),
    }


def run(result_paths: list[Path], verification_paths: list[Path]) -> dict[str, Any]:
    if not result_paths:
        raise ValueError("at least one result is required")
    if len(result_paths) != len(verification_paths):
        raise ValueError("each result needs one independent verification receipt")
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    verifications = [json.loads(path.read_text(encoding="utf-8")) for path in verification_paths]
    for verification in verifications:
        if not verification.get("semantic_verification_passed"):
            raise ValueError("independent verification did not pass")
    expected_tasks = tuple(results[0]["dataset"]["task_id_sha256"])
    expected_arms = set(results[0].get("arms", {}))
    if not expected_arms:
        raise ValueError("result has no arms")
    rows: dict[tuple[int, str], dict[str, bool]] = {}
    aggregate: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    seed_bases: list[int] = []
    source_receipts: list[str] = []
    for result_path, result in zip(result_paths, results):
        if tuple(result["dataset"]["task_id_sha256"]) != expected_tasks:
            raise ValueError("task set differs across seeds")
        arms = set(result.get("arms", {}))
        if arms != expected_arms:
            raise ValueError(f"arm set differs: {arms}")
        protocol = result.get("protocol_remediation", {})
        seed_base = int(protocol.get("seed_base", -1))
        if seed_base < 0:
            raise ValueError(f"missing seed_base in {result_path}")
        seed_bases.append(seed_base)
        source_receipts.append(hashlib.sha256(result_path.read_bytes()).hexdigest())
        for row in result.get("task_runs", []):
            key = (seed_base, str(row["task_id_sha256"]))
            arm = str(row["arm"])
            rows.setdefault(key, {})[arm] = bool(row.get("semantic_correct"))
            aggregate[arm]["episodes"] += 1
            aggregate[arm]["semantic_correct"] += int(bool(row.get("semantic_correct")))
            aggregate[arm]["submitted"] += int(row.get("terminal_action") == "submit_sql")
            aggregate[arm]["unauthorized_observation"] += int(bool(row.get("unauthorized_observation")))
            aggregate[arm]["authority_valid"] += int(bool(row.get("authority_valid")))
            aggregate[arm]["sql_attempts"] += int(row.get("sql_attempts") or 0)
            aggregate[arm]["tool_calls"] += int(row.get("tool_calls") or 0)
    if len(set(seed_bases)) != len(seed_bases):
        raise ValueError("duplicate seed base")
    for arm, values in aggregate.items():
        values["semantic_correct_rate"] = round(values["semantic_correct"] / values["episodes"], 6)
        values["submission_rate"] = round(values["submitted"] / values["episodes"], 6)
    result = {
        "schema_version": SCHEMA_VERSION,
        "seeds": sorted(seed_bases),
        "tasks_per_seed": len(expected_tasks),
        "episodes": len(rows),
        "dataset_task_hashes": list(expected_tasks),
        "source_result_sha256": source_receipts,
        "independent_verifications": len(verifications),
        "aggregate_by_arm": {arm: dict(values) for arm, values in sorted(aggregate.items())},
        "paired_comparisons": [
            _pairwise(rows, left, right)
            for left, right in combinations(sorted(expected_arms), 2)
        ],
        "claim_boundary": "Matched frontier family-transfer aggregate with independent semantic verification. It estimates this protocol/sample only; it does not establish universal skill utility, embedding benefit, or promotion eligibility without larger preregistered samples and artifact adjudication.",
    }
    result["aggregate_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--verification", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.result, args.verification)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "seeds": result["seeds"], "episodes": result["episodes"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
