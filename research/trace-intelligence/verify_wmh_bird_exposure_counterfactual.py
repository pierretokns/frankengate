#!/usr/bin/env python3
"""Independently verify the WMH-BIRD exposure counterfactual receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-exposure-counterfactual-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected exposure counterfactual schema")
    aggregate = result.get("aggregate", {})
    required = (
        "selected_successful_tasks",
        "database_families",
        "counterfactual_pairs",
        "counterfactual_execution_errors",
        "counterfactual_result_mismatches",
        "counterfactual_result_matches",
    )
    if any(not isinstance(aggregate.get(key), int) or aggregate[key] < 0 for key in required):
        raise ValueError("invalid aggregate count")
    if aggregate["counterfactual_pairs"] != sum(aggregate[key] for key in required[3:]):
        raise ValueError("counterfactual categories do not reconcile")
    rows = result.get("rows", [])
    if len(rows) != aggregate["selected_successful_tasks"]:
        raise ValueError("row count does not match selected tasks")
    row_pairs = sum(sum(int(row.get(key, 0)) for key in ("counterfactual_error", "counterfactual_mismatch", "counterfactual_match")) for row in rows)
    if row_pairs != aggregate["counterfactual_pairs"]:
        raise ValueError("row pair counts do not reconcile")
    retrieval = result.get("retrieval", {}).get("arms", {})
    if set(retrieval) != {"lexical", "lexical_plus_termhood_alias"}:
        raise ValueError("unexpected retrieval arms")
    cases = {int(arm.get("cases", -1)) for arm in retrieval.values()}
    if len(cases) != 1 or next(iter(cases)) < 0:
        raise ValueError("retrieval case counts disagree")
    for arm in retrieval.values():
        for key in ("mrr", "recall_at_1", "recall_at_5", "recall_at_10"):
            value = arm.get(key)
            if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError("invalid retrieval metric")
    claim = result.get("claim_boundary", {})
    if claim.get("counterfactual_interchangeability_negatives_measured") is not True:
        raise ValueError("counterfactual measurement is missing")
    if claim.get("semantic_negative_labels_established") is not False or claim.get("enterprise_alias_quality_established") is not False:
        raise ValueError("claim boundary overstates evidence")
    return {
        "schema_version": "frankengate-wmh-bird-exposure-counterfactual-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "selected_tasks_verified": aggregate["selected_successful_tasks"],
        "counterfactual_pairs_verified": aggregate["counterfactual_pairs"],
        "retrieval_arms_verified": sorted(retrieval),
        "reconciliation_verified": True,
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
