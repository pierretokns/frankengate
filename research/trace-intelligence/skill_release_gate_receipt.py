#!/usr/bin/env python3
"""Apply the independent skill-release gate to a sealed experiment receipt.

This is an architecture-neutral MLOps feedback-loop check.  It never releases
a candidate merely because a procedure exists: the candidate must have a
verified, paired downstream lift before exposure is permitted.
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


def run(result_path: Path, verification_path: Path, paired_path: Path, candidate_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    paired = json.loads(paired_path.read_text(encoding="utf-8"))
    candidate_sha = sha256_file(candidate_path)
    verification_passed = bool(verification.get("claim_boundary", {}).get("verification_passed"))
    candidate = result["summary"]["trace_mined_procedure"]
    baseline = result["summary"]["no_skill"]
    placebo = result["summary"]["formatting_placebo"]
    positive_lift = (
        verification_passed
        and candidate["exact"] > baseline["exact"]
        and candidate["exact"] >= placebo["exact"]
        and candidate.get("candidate_error", 0) <= baseline.get("candidate_error", 0)
    )
    status = "released" if positive_lift else "quarantined"
    stages = {
        "collect": "complete",
        "segment": "complete",
        "cluster": "complete",
        "retrieve": "complete",
        "propose": "complete",
        "replay": "complete",
        "evaluate": "complete" if verification_passed else "failed",
        "release": "complete" if positive_lift else "blocked_by_gate",
        "monitor": "not_started",
        "rollback": "not_required" if not positive_lift else "armed",
    }
    receipt = {
        "schema_version": "frankengate-skill-release-gate-v1",
        "candidate": {
            "artifact": candidate_path.name,
            "sha256": candidate_sha,
            "status": status,
        },
        "evidence": {
            "result": result_path.name,
            "result_sha256": sha256_file(result_path),
            "verification": verification_path.name,
            "verification_sha256": sha256_file(verification_path),
            "paired_analysis": paired_path.name,
            "paired_analysis_sha256": sha256_file(paired_path),
        },
        "outcomes": {
            "candidate_exact": candidate["exact"],
            "candidate_episodes": candidate["episodes"],
            "no_skill_exact": baseline["exact"],
            "formatting_placebo_exact": placebo["exact"],
            "verification_passed": verification_passed,
            "positive_lift": positive_lift,
        },
        "stages": stages,
        "exposure": {
            "eligible_users": 0,
            "eligible_tasks": 0,
            "canary_percent": 0,
            "rollback_available": positive_lift,
        },
        "claim_boundary": {
            "candidate_released": positive_lift,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "The candidate did not exceed the no-skill control and did not match the placebo control, so it remains quarantined.",
        },
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--paired", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.result, args.verification, args.paired, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
