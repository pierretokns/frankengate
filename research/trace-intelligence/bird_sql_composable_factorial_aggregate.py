#!/usr/bin/env python3
"""Aggregate two independent family-disjoint BIRD composition replays."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ARMS = ("no_skill", "formatting_placebo", "composable_subplan_library")


def run(results: tuple[Path, Path], verifications: tuple[Path, Path], output: Path) -> dict[str, Any]:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in results]
    checks = {
        "two_replays": len(payloads) == 2,
        "verifiers_passed": all(json.loads(path.read_text(encoding="utf-8")).get("claim_boundary", {}).get("verification_passed") is True for path in verifications),
        "same_task_count": payloads[0]["protocol"]["task_count"] == payloads[1]["protocol"]["task_count"],
        "same_library": payloads[0]["protocol"]["library_sha256"] == payloads[1]["protocol"]["library_sha256"],
        "same_arms": all(set(item["protocol"]["arms"]) == set(ARMS) for item in payloads),
    }
    if not all(checks.values()):
        raise ValueError(f"incompatible replays: {checks}")
    by_task: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for payload in payloads:
        for row in payload["episodes"]:
            by_task[row["task_hash"]][row["arm"]].append(bool(row["exact"]))
    stable: dict[str, dict[str, int]] = {}
    for control in ("no_skill", "formatting_placebo"):
        wins = losses = ties = 0
        for arms in by_task.values():
            candidate = arms["composable_subplan_library"]
            baseline = arms[control]
            if all(candidate) and not all(baseline):
                wins += 1
            elif all(baseline) and not all(candidate):
                losses += 1
            else:
                ties += 1
        stable[control] = {"unique_tasks": len(by_task), "stable_library_wins": wins, "stable_library_losses": losses, "stable_ties_or_mixed": ties}
    arms: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        rows = [row for payload in payloads for row in payload["episodes"] if row["arm"] == arm]
        arms[arm] = {
            "episodes": len(rows),
            "exact": sum(bool(row["exact"]) for row in rows),
            "candidate_error": sum(row["outcome"] == "candidate_error" for row in rows),
        }
    receipt = {
        "schema_version": "frankengate-bird-sql-composable-factorial-aggregate-v1",
        "source_result_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in results],
        "source_verification_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in verifications],
        "checks": checks,
        "unique_task_count": len(by_task),
        "library_sha256": payloads[0]["protocol"]["library_sha256"],
        "arms": arms,
        "stable_comparisons": stable,
        "claim_boundary": {"repeated_replays_are_not_independent_tasks": True, "causal_subplan_benefit_confirmed": False, "automatic_promotion_authorized": False, "reason": "The same one-run stable win is encouraging but remains a public proxy result without changed-system or enterprise outcome evidence."},
    }
    receipt["result_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--result", action="append", type=Path, required=True); parser.add_argument("--verification", action="append", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    if len(args.result) != 2 or len(args.verification) != 2:
        raise SystemExit("exactly two results and two verifications are required")
    run((args.result[0], args.result[1]), (args.verification[0], args.verification[1]), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

