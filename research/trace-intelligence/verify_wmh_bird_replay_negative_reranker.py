#!/usr/bin/env python3
"""Verify the WMH-BIRD replay-negative reranker receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-replay-negative-reranker-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected replay-negative reranker schema")
    arms = result.get("arms", {})
    expected = {"lexical", "termhood_alias", "naive_exposed_negative_ranker", "replay_negative_ranker"}
    if set(arms) != expected:
        raise ValueError("unexpected reranker arms")
    case_counts = {int(value.get("cases", -1)) for value in arms.values()}
    if len(case_counts) != 1 or next(iter(case_counts)) < 0:
        raise ValueError("arm case counts disagree")
    for arm in arms.values():
        for key in ("mrr", "recall_at_1", "recall_at_5", "recall_at_10"):
            value = arm.get(key)
            if not isinstance(value, (float, int)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError("invalid ranking metric")
    folds = result.get("folds", [])
    if not folds:
        raise ValueError("missing fold summaries")
    if any(int(fold.get("train_tasks", -1)) < 0 or int(fold.get("evaluation_tasks", -1)) < 0 for fold in folds):
        raise ValueError("invalid fold counts")
    claim = result.get("claim_boundary", {})
    if claim.get("replay_negative_training_evaluated") is not True:
        raise ValueError("replay-negative training is missing")
    if claim.get("semantic_negative_labels_established") is not False or claim.get("enterprise_quality_established") is not False:
        raise ValueError("claim boundary overstates evidence")
    return {
        "schema_version": "frankengate-wmh-bird-replay-negative-reranker-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "arms_verified": sorted(arms),
        "cases_verified": next(iter(case_counts)),
        "folds_verified": len(folds),
        "claim_boundary_verified": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
