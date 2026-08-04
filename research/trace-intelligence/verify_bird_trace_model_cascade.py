#!/usr/bin/env python3
"""Independently verify the public BIRD model-cascade receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_json_response(value: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", value, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    required = {"artifact_matches_task", "replayability", "validator_type", "confidence"}
    return parsed if isinstance(parsed, dict) and required <= set(parsed) else None


def verify(result_path: Path, raw_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))
    expected_episodes = {
        (row.get("arm"), row.get("case_hash")): row
        for row in result.get("episodes", [])
    }
    aggregate: dict[str, Counter[str]] = {}
    errors: Counter[str] = Counter()
    for raw in raw_rows:
        key = (raw.get("arm"), raw.get("case_hash"))
        episode = expected_episodes.get(key)
        arm = str(raw.get("arm"))
        bucket = aggregate.setdefault(arm, Counter())
        bucket["episodes"] += 1
        response = str(raw.get("response", ""))
        if episode is None:
            errors["episode_missing"] += 1
            continue
        if episode.get("response_sha256") != sha256_text(response):
            errors["response_hash_mismatch"] += 1
        parsed = parse_json_response(response)
        bucket["valid_json"] += parsed is not None
        truth = bool(episode.get("gold_correctness_hidden_truth"))
        prediction = parsed.get("artifact_matches_task") if parsed else None
        if prediction is True:
            bucket["predicted_true"] += 1
            bucket["correct_true_positive" if truth else "correct_false_positive"] += 1
        elif prediction is False:
            bucket["predicted_false"] += 1
            bucket["correct_true_negative" if not truth else "correct_false_negative"] += 1
        else:
            bucket["abstain"] += 1
        if parsed:
            bucket["validator_" + str(parsed.get("validator_type"))] += 1
            bucket["replayability_" + str(parsed.get("replayability"))] += 1
    recomputed = {arm: dict(sorted(values.items())) for arm, values in aggregate.items()}
    expected = {
        arm: {key: value for key, value in values.items() if key != "elapsed_ms_total"}
        for arm, values in result.get("summary", {}).items()
    }
    return {
        "schema_version": "frankengate-bird-trace-model-cascade-verification-v1",
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "rows_verified": len(raw_rows),
        "recomputed_summary": recomputed,
        "receipt_summary_without_latency": expected,
        "receipt_summary_matches": recomputed == expected,
        "errors": dict(sorted(errors.items())),
        "claim_boundary": {
            "verification_passed": recomputed == expected and not errors,
            "semantic_model_utility_confirmed": False,
            "automatic_artifact_promotion_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verified = verify(args.result, args.raw)
    args.output.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verified, sort_keys=True))
    return 0 if verified["claim_boundary"]["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
