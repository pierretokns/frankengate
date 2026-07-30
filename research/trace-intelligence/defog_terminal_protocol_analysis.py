#!/usr/bin/env python3
"""Compare the original and terminal-remediated Defog P0 receipts."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "frankengate-defog-terminal-protocol-analysis-v1"
ARMS = (
    "no_skill",
    "unrelated_formatting_placebo",
    "expert_schema_navigation_seed",
)
STABLE_SOURCE_RECEIPTS = (
    "cohort_manifest_sha256",
    "dataset_manifest_sha256",
    "design_manifest_sha256",
    "model_manifest_sha256",
    "authority_manifest_sha256",
)


class AnalysisError(RuntimeError):
    """Raised when the comparison is incomplete or not paired."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"invalid result: {path}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"result must be an object: {path}")
    return value


def _matrix(
    result: Mapping[str, Any],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    receipts = result.get("task_receipts")
    if not isinstance(receipts, list) or not receipts:
        raise AnalysisError("task receipts are missing")
    matrix: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise AnalysisError("task receipt is not an object")
        task = receipt.get("task_id_sha256")
        arm = receipt.get("arm")
        if not isinstance(task, str) or arm not in ARMS:
            raise AnalysisError("task receipt identity is invalid")
        if arm in matrix[task]:
            raise AnalysisError(f"duplicate task/arm receipt: {task}/{arm}")
        matrix[task][arm] = receipt
    for task, by_arm in matrix.items():
        if set(by_arm) != set(ARMS):
            raise AnalysisError(f"incomplete paired task: {task}")
    return dict(matrix)


def _protocol_failure(receipt: Mapping[str, Any]) -> bool:
    return (
        receipt.get("terminal_action") == "none"
        or receipt.get("protocol_failure_code") is not None
    )


def _endpoint(receipt: Mapping[str, Any]) -> bool:
    return bool(
        receipt.get("semantic_correct") is True
        and receipt.get("policy_accepted") is True
        and receipt.get("unauthorized_observation") is False
    )


def _rates(
    matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, float]:
    denominator = len(matrix)
    return {
        arm: sum(
            _protocol_failure(by_arm[arm])
            for by_arm in matrix.values()
        )
        / denominator
        for arm in ARMS
    }


def _paired(
    matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    treatment: str,
    control: str,
) -> dict[str, int | float]:
    wins = losses = ties = 0
    treatment_passes = control_passes = 0
    for by_arm in matrix.values():
        treated = _endpoint(by_arm[treatment])
        controlled = _endpoint(by_arm[control])
        treatment_passes += int(treated)
        control_passes += int(controlled)
        if treated and not controlled:
            wins += 1
        elif controlled and not treated:
            losses += 1
        else:
            ties += 1
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "risk_difference": (
            treatment_passes - control_passes
        )
        / len(matrix),
    }


def analyze(
    *,
    original_path: Path,
    repaired_path: Path,
) -> dict[str, Any]:
    original = _load(original_path)
    repaired = _load(repaired_path)
    original_matrix = _matrix(original)
    repaired_matrix = _matrix(repaired)
    if set(original_matrix) != set(repaired_matrix):
        raise AnalysisError("original and repaired task sets differ")

    original_sources = original.get("source_receipts") or {}
    repaired_sources = repaired.get("source_receipts") or {}
    source_matches = {
        key: original_sources.get(key) == repaired_sources.get(key)
        for key in STABLE_SOURCE_RECEIPTS
    }
    prompt_receipts_match = (
        original.get("prompt_receipts")
        == repaired.get("prompt_receipts")
    )
    arm_order_matches = all(
        list(original_matrix[task]) == list(repaired_matrix[task])
        for task in original_matrix
    )
    original_rates = _rates(original_matrix)
    repaired_rates = _rates(repaired_matrix)
    paired_effects = {
        (
            "expert_schema_navigation_seed_vs_"
            "unrelated_formatting_placebo"
        ): _paired(
            repaired_matrix,
            treatment="expert_schema_navigation_seed",
            control="unrelated_formatting_placebo",
        ),
        "expert_schema_navigation_seed_vs_no_skill": _paired(
            repaired_matrix,
            treatment="expert_schema_navigation_seed",
            control="no_skill",
        ),
    }
    unauthorized = sum(
        receipt.get("unauthorized_observation") is True
        for by_arm in repaired_matrix.values()
        for receipt in by_arm.values()
    )
    complete_receipts = (
        sum(len(by_arm) for by_arm in repaired_matrix.values())
        == len(repaired_matrix) * len(ARMS)
    )
    protocol_passed = bool(
        complete_receipts
        and unauthorized == 0
        and max(repaired_rates.values()) <= 0.10
    )
    primary = paired_effects[
        "expert_schema_navigation_seed_vs_"
        "unrelated_formatting_placebo"
    ]
    sensitivity_passed = (
        int(primary["wins"]) - int(primary["losses"]) >= 2
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "experiment_date": "2026-07-30",
        "inputs": {
            "original_result_sha256": sha256_file(original_path),
            "repaired_result_sha256": sha256_file(repaired_path),
            "analyzer_sha256": sha256_file(Path(__file__).resolve()),
        },
        "contract_invariants": {
            "stable_source_receipts_match": source_matches,
            "prompt_receipts_match": prompt_receipts_match,
            "paired_task_set_match": True,
            "arm_iteration_order_match": arm_order_matches,
            "all_match": (
                all(source_matches.values())
                and prompt_receipts_match
                and arm_order_matches
            ),
        },
        "protocol": {
            "original_failure_rate_by_arm": original_rates,
            "repaired_failure_rate_by_arm": repaired_rates,
            "original_missing_terminal_count": sum(
                _protocol_failure(receipt)
                for by_arm in original_matrix.values()
                for receipt in by_arm.values()
            ),
            "repaired_missing_terminal_count": sum(
                _protocol_failure(receipt)
                for by_arm in repaired_matrix.values()
                for receipt in by_arm.values()
            ),
            "repaired_unauthorized_observation_count": unauthorized,
            "remediation": repaired.get("protocol_remediation"),
        },
        "paired_effects": paired_effects,
        "gates": {
            "complete_task_arm_receipts": complete_receipts,
            "zero_unauthorized_observations": unauthorized == 0,
            "terminal_protocol_passed": protocol_passed,
            "paired_sensitivity_passed": sensitivity_passed,
            "p1_effect_screen_unsealed": (
                protocol_passed and sensitivity_passed
            ),
        },
        "claim_boundary": {
            "terminal_protocol_repaired_on_four_task_p0": protocol_passed,
            "expert_skill_benefit_observed": sensitivity_passed,
            "trace_mined_skill_tested": False,
            "hidden_test_touched": False,
            "adequate_sample_for_quality_claim": False,
        },
    }
    result["result_sha256_excluding_self"] = hashlib.sha256(
        canonical_json_bytes(result)
    ).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--repaired", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(
        original_path=args.original,
        repaired_path=args.repaired,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["gates"], sort_keys=True))


if __name__ == "__main__":
    main()
