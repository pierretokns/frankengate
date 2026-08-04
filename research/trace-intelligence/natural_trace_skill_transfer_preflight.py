"""Audit a bounded NatureBench outcome matrix before a causal skill run.

This deliberately consumes only content-free ``result.json`` files.  It proves
that multiple harness/model arms and a family-disjoint task split are available;
it does *not* treat a successful historical run as evidence that a mined skill
caused the outcome.  A benefit claim requires re-running the same tasks with a
candidate injected, a no-skill control, a placebo, and an independent outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-natural-trace-skill-transfer-preflight-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"result is not an object: {path}")
    return value


def run(manifest_path: Path, results_root: Path) -> dict[str, Any]:
    manifest = _load(manifest_path)
    tasks = manifest["bounded_tasks"]
    arms = manifest["protocol"]["source_arms"]
    by_arm: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for arm in arms:
        for task in tasks:
            candidates = (
                results_root / f"{arm.replace('__', '-') }__{task}.json",
                results_root / f"{arm.rsplit('__', 1)[-1]}__{task}.json",
            )
            path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
            if not path.is_file():
                missing.append(str(path))
                continue
            result = _load(path)
            status = str(result.get("status", "unknown"))
            by_arm[arm][status] += 1
            rows.append(
                {
                    "arm": arm,
                    "task": task,
                    "status": status,
                    "model": result.get("model"),
                    "result_sha256": _sha256(path),
                }
            )
    summary: dict[str, Any] = {}
    for arm in arms:
        counts = dict(sorted(by_arm[arm].items()))
        observed = sum(counts.values())
        summary[arm] = {
            "observed_tasks": observed,
            "successes": counts.get("success", 0),
            "timeouts": counts.get("timeout", 0),
            "other_statuses": sum(v for k, v in counts.items() if k not in {"success", "timeout"}),
            "status_counts": counts,
            "success_rate": (counts.get("success", 0) / observed if observed else None),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": manifest["dataset"],
        "protocol": manifest["protocol"],
        "bounded_task_count": len(tasks),
        "arm_count": len(arms),
        "observed_result_count": len(rows),
        "missing_result_count": len(missing),
        "missing_results": missing,
        "arms": summary,
        "rows": rows,
        "claim_boundary": {
            "historical_outcome_matrix_available": bool(rows) and not missing,
            "natural_trace_skill_benefit_confirmed": False,
            "causal_intervention_run": False,
            "reason": "These are historical outcomes from the source harnesses. No candidate was injected into a replay with no-skill/placebo controls.",
            "next_required_run": "same family-disjoint tasks with no-skill, placebo, mined, SkillOpt/SkillGen/RHO arms, paired repair/regression outcomes, and an independent verifier",
        },
        "raw_trace_policy": manifest["raw_trace_policy"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.manifest.resolve(strict=True), args.results_root.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "observed_result_count": receipt["observed_result_count"], "missing_result_count": receipt["missing_result_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
