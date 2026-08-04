#!/usr/bin/env python3
"""Re-run the content-minimized Trace Commons analysis and compare aggregates.

The receipt intentionally compares only aggregate structural metrics.  It does
not emit prompts, tool arguments/results, paths, native identifiers, or raw
session rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from real_user_analysis_arms import analyze_corpus


SCHEMA_VERSION = "frankengate-trace-commons-reproducibility-v1"


METRIC_PATHS = (
    "S0_metadata.sessions",
    "S0_metadata.valid_records",
    "S0_metadata.malformed_records",
    "S1_deterministic_signals.candidate_sessions",
    "S1_deterministic_signals.review_selected_sessions",
    "S2_exact_structured_fts_ready.candidate_sessions",
    "S4_temporal_episode_candidates.candidate_episodes",
    "S4_temporal_episode_candidates.candidate_tiers.high",
    "S4_temporal_episode_candidates.candidate_tiers.medium",
    "S4_temporal_episode_candidates.candidate_tiers.low",
    "S6_proposal_records.candidate_records.eval_review",
    "S6_proposal_records.candidate_records.memory_review_motifs",
    "S6_proposal_records.candidate_records.procedure_review_episodes",
    "S6_proposal_records.candidate_records.skill_gap_recommendations",
    "S6_proposal_records.candidate_records.cross_user_collaboration_recommendations",
    "S6_proposal_records.candidate_records.automatic_memory_or_skill_writes",
    "observed_failure_modes.outcome_labels_available",
    "observed_failure_modes.environment_state_snapshots_available",
    "observed_failure_modes.authorization_and_classification_labels_available",
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _path(value: dict[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file_or_value(path: Path, value: Any) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return _sha256_json(value)


def compare(
    *,
    actual: dict[str, Any],
    expected: dict[str, Any],
    expected_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    checks = []
    for path in METRIC_PATHS:
        expected_value = _path(expected, path)
        actual_value = _path(actual, path)
        checks.append(
            {
                "metric": path,
                "expected": expected_value,
                "observed": actual_value,
                "matched": expected_value == actual_value,
            }
        )
    all_passed = all(bool(row["matched"]) for row in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "expected_result": {
            "path": str(expected_path),
            "sha256": _sha256_file_or_value(expected_path, expected),
        },
        "dataset_manifest": {
            "path": str(manifest_path),
            "sha256": _sha256_file_or_value(manifest_path, {}),
        },
        "metrics_compared": len(checks),
        "checks": checks,
        "all_passed": all_passed,
        "actual_aggregate_sha256": _sha256_json(
            {path: _path(actual, path) for path in METRIC_PATHS}
        ),
        "raw_content_emitted": False,
        "claim_boundary": {
            "structural_reproduction_confirmed": all_passed,
            "outcome_labels_available": _path(
                actual, "observed_failure_modes.outcome_labels_available"
            ),
            "causal_skill_benefit_confirmed": False,
            "reason": (
                "This verifies deterministic aggregate replay only. The corpus "
                "has no task outcomes, environment snapshots, or authorization "
                "labels, so it cannot establish memory utility, skill benefit, "
                "or enterprise generalization."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = _read_json(args.manifest)
    expected = _read_json(args.expected)
    actual = analyze_corpus(args.corpus_root.resolve(), manifest)
    receipt = compare(
        actual=actual,
        expected=expected,
        expected_path=args.expected,
        manifest_path=args.manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "all_passed": receipt["all_passed"],
                "metrics_compared": receipt["metrics_compared"],
                "causal_skill_benefit_confirmed": False,
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
