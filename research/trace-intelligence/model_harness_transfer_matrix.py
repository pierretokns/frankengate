"""Compare content-free native-tool skill results across local model arms.

The matrix deliberately accepts only aggregate/provenance receipts.  It never
reads or emits raw prompts, tool arguments, model messages, or tool results.
This is a model-transfer comparison when the harness identifier is shared; a
true cross-harness comparison requires independently produced receipts with
the same frozen fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any


SCHEMA_VERSION = "frankengate-model-harness-transfer-matrix-v1"


class MatrixError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MatrixError(f"invalid result: {path}") from exc
    if not isinstance(value, dict):
        raise MatrixError(f"result must be an object: {path}")
    if not isinstance(value.get("episode_receipts"), list):
        raise MatrixError(f"missing episode receipts: {path}")
    if not isinstance(value.get("variant_results"), dict):
        raise MatrixError(f"missing variant results: {path}")
    return value


def _episode_metrics(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for receipt in value["episode_receipts"]:
        if not isinstance(receipt, dict):
            raise MatrixError("episode receipt is not an object")
        variant = receipt.get("variant")
        if not isinstance(variant, str):
            raise MatrixError("episode variant is missing")
        by_variant.setdefault(variant, []).append(receipt)
    result: dict[str, dict[str, Any]] = {}
    for variant, receipts in sorted(by_variant.items()):
        elapsed = [float(row["elapsed_ms"]) for row in receipts]
        matches = sum(bool(row.get("expected_terminal_match")) for row in receipts)
        failures = sum(bool(row.get("terminal_failure_code")) for row in receipts)
        result[variant] = {
            "episodes": len(receipts),
            "expected_terminal_matches": matches,
            "expected_terminal_match_rate": matches / len(receipts),
            "terminal_failures": failures,
            "terminal_failure_rate": failures / len(receipts),
            "mean_elapsed_ms": mean(elapsed),
            "max_elapsed_ms": max(elapsed),
        }
    return result


def compare(
    *,
    inputs: list[tuple[str, str, Path]],
    output: Path,
) -> dict[str, Any]:
    if len(inputs) < 2:
        raise MatrixError("at least two model/harness receipts are required")
    loaded = [(model, harness, path, _load(path)) for model, harness, path in inputs]
    fixture_hashes = {value.get("fixture_manifest_sha256") for _, _, _, value in loaded}
    if len(fixture_hashes) != 1 or None in fixture_hashes:
        raise MatrixError("all receipts must use the same frozen fixture")
    schedules = {value.get("frozen_schedule_sha256") for _, _, _, value in loaded}
    if len(schedules) != 1 or None in schedules:
        raise MatrixError("all receipts must use the same frozen schedule")
    tool_schemas = {value.get("frozen_tool_schema_sha256") for _, _, _, value in loaded}
    if len(tool_schemas) != 1 or None in tool_schemas:
        raise MatrixError("all receipts must use the same frozen tool schema")
    variants = [set(value["variant_results"]) for _, _, _, value in loaded]
    if any(item != variants[0] for item in variants[1:]):
        raise MatrixError("model receipts do not expose the same intervention arms")
    matrix = []
    for model, harness, path, value in loaded:
        matrix.append(
            {
                "model_id": model,
                "harness_id": harness,
                "source_result_sha256": _sha256_file(path),
                "request_model_id": value.get("request_model_id", value.get("model", {}).get("request_model_id")),
                "metrics_by_arm": _episode_metrics(value),
                "claim_boundary": value.get("claim_boundary", {}),
            }
        )
    same_harness = len({row["harness_id"] for row in matrix}) == 1
    result = {
        "schema_version": SCHEMA_VERSION,
        "classification": "same_fixture_model_transfer" if same_harness else "same_fixture_cross_harness_transfer",
        "fixture_manifest_sha256": next(iter(fixture_hashes)),
        "frozen_schedule_sha256": next(iter(schedules)),
        "frozen_tool_schema_sha256": next(iter(tool_schemas)),
        "models": matrix,
        "claim_boundary": {
            "same_fixture_compared": True,
            "multiple_models_compared": len({row["model_id"] for row in matrix}) > 1,
            "multiple_harnesses_compared": len({row["harness_id"] for row in matrix}) > 1,
            "causal_skill_benefit_established": False,
            "reason": (
                "This is a content-free protocol transfer matrix. It compares "
                "terminal behavior and latency only; it does not estimate SQL "
                "quality, enterprise benefit, or long-term skill learning."
            ),
            "next_required": "Run the same candidate on family-disjoint held-out tasks with an independent semantic/security verifier and at least two harness implementations.",
        },
        "raw_data_committed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", nargs=3, metavar=("MODEL", "HARNESS", "PATH"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        inputs=[(model, harness, Path(path)) for model, harness, path in args.input],
        output=args.output,
    )
    print(json.dumps({"status": "ok", "classification": result["classification"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
