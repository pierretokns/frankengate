#!/usr/bin/env python3
"""Architecture-neutral outcome-aware release gate for any intervention arm.

The gate accepts a sealed result with named candidate/baseline/placebo arms and
an independent verifier receipt. It records the complete MLOps lifecycle and
only permits exposure when the candidate has verified positive success lift,
matches or beats placebo, and does not worsen protocol validity. It is a
decision receipt, not a production release implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _arm(result: dict[str, Any], name: str) -> dict[str, Any]:
    try:
        return result["summary"][name]
    except KeyError as exc:
        raise ValueError(f"result summary is missing arm {name!r}") from exc


def run(result_path: Path, verification_path: Path, candidate_arm: str,
        baseline_arm: str, placebo_arm: str) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    candidate = _arm(result, candidate_arm)
    baseline = _arm(result, baseline_arm)
    placebo = _arm(result, placebo_arm)
    verification_passed = bool(
        verification.get("all_passed") or
        verification.get("verification_passed") or
        verification.get("claim_boundary", {}).get("verification_passed")
    )
    candidate_success = int(candidate.get("wins", 0))
    baseline_success = int(baseline.get("wins", 0))
    placebo_success = int(placebo.get("wins", 0))
    candidate_invalid = int(candidate.get("invalid_actions", 0))
    baseline_invalid = int(baseline.get("invalid_actions", 0))
    placebo_invalid = int(placebo.get("invalid_actions", 0))
    positive_lift = (
        verification_passed
        and candidate_success > baseline_success
        and candidate_success >= placebo_success
        and candidate_invalid <= baseline_invalid
        and candidate_invalid <= placebo_invalid
    )
    status = "released" if positive_lift else "quarantined"
    return {
        "schema_version": "frankengate-outcome-release-gate-v1",
        "candidate": {"arm": candidate_arm, "status": status, "result_sha256": sha256_file(result_path)},
        "controls": {"baseline_arm": baseline_arm, "placebo_arm": placebo_arm},
        "evidence": {
            "result": result_path.name,
            "verification": verification_path.name,
            "verification_sha256": sha256_file(verification_path),
        },
        "outcomes": {
            "candidate_wins": candidate_success,
            "baseline_wins": baseline_success,
            "placebo_wins": placebo_success,
            "candidate_invalid_actions": candidate_invalid,
            "baseline_invalid_actions": baseline_invalid,
            "placebo_invalid_actions": placebo_invalid,
            "verification_passed": verification_passed,
            "positive_lift": positive_lift,
        },
        "stages": {
            "collect": "complete",
            "segment": "complete",
            "cluster": "complete",
            "retrieve": "complete",
            "propose": "complete",
            "replay": "complete" if verification_passed else "failed",
            "evaluate": "complete" if verification_passed else "blocked",
            "release": "complete" if positive_lift else "blocked_by_gate",
            "monitor": "not_started",
            "rollback": "armed" if positive_lift else "not_required",
        },
        "exposure": {
            "eligible_users": 0 if not positive_lift else None,
            "eligible_tasks": 0 if not positive_lift else None,
            "canary_percent": 0 if not positive_lift else None,
            "rollback_available": positive_lift,
        },
        "claim_boundary": {
            "candidate_released": positive_lift,
            "causal_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Candidate did not exceed the baseline with no worse validity while matching or beating placebo; it remains quarantined." if not positive_lift else "Candidate passed this bounded release predicate; production exposure still requires a separately authorized canary.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--candidate-arm", required=True)
    parser.add_argument("--baseline-arm", required=True)
    parser.add_argument("--placebo-arm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.result, args.verification, args.candidate_arm,
                  args.baseline_arm, args.placebo_arm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["candidate"]["status"], "positive_lift": receipt["outcomes"]["positive_lift"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
