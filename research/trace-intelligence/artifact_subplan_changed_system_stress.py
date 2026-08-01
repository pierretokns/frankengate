#!/usr/bin/env python3
"""Stress the changed-system subplan admission rule on a fixed synthetic grid."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from artifact_subplan_changed_system_replay import (
    SCHEMA as BASE_SCHEMA,
    Column,
    Subplan,
    Target,
    _semantic_filter_allowed,
    _target_query,
    digest,
)


SCHEMA = "frankengate-artifact-subplan-changed-system-stress-v1"


def _targets(repeats: int) -> list[tuple[str, Target]]:
    source_columns = (
        Column("customer_id", "column:commerce.customer_id"),
        Column("status", "column:commerce.order_status"),
    )
    rows = (("cust-a", "paid"), ("cust-a", "paid"), ("cust-b", "paid"), ("cust-b", "open"))
    cases: list[tuple[str, tuple[Column, ...], dict[str, str]]] = [
        ("unchanged", source_columns, {}),
        (
            "additive",
            source_columns + (Column("region", "column:commerce.region"),),
            {},
        ),
        (
            "approved_semantic_rename",
            (Column("account_id", "column:commerce.customer_id"), Column("state", "column:commerce.order_status")),
            {"customer_id": "account_id", "status": "state"},
        ),
        (
            "same_name_semantic_drift",
            (Column("customer_id", "column:commerce.customer_id"), Column("status", "column:commerce.gross_amount")),
            {},
        ),
        (
            "renamed_wrong_semantics",
            (Column("account_id", "column:commerce.customer_id"), Column("state", "column:commerce.gross_amount")),
            {"customer_id": "account_id", "status": "state"},
        ),
    ]
    targets: list[tuple[str, Target]] = []
    for category, columns, mapping in cases:
        for index in range(repeats):
            targets.append(
                (
                    category,
                    Target(
                        case_id=f"{category}-{index:03d}",
                        table_name=f"orders_{category}_{index:03d}",
                        columns=columns,
                        mapping=mapping,
                        rows=rows,
                    ),
                )
            )
    return targets


def run(output: Path, repeats: int = 20) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    subplan = Subplan(
        name="status-filter",
        sql_fragment="WHERE status = ?",
        semantic_inputs=("column:commerce.order_status",),
    )
    expected = [("cust-a", 2), ("cust-b", 1)]
    policies = ("name_only_subplan", "semantic_subplan")
    aggregate = {
        policy: {"accepted": 0, "semantic_correct": 0, "unsafe_accept": 0, "rejected": 0}
        for policy in policies
    }
    by_category: dict[str, dict[str, dict[str, int]]] = {}
    for category, target in _targets(repeats):
        by_category.setdefault(category, {})
        for policy in policies:
            allowed, reasons = _semantic_filter_allowed(target, subplan, policy)
            filter_column = target.mapping.get("status", "status")
            result = _target_query(target, f'WHERE "{filter_column}" = ?') if allowed else []
            semantic_mismatch = not set(subplan.semantic_inputs) <= {
                column.semantic_id for column in target.columns
            }
            semantic_correct = allowed and result == expected and not semantic_mismatch
            unsafe_accept = allowed and policy == "name_only_subplan" and semantic_mismatch
            aggregate[policy]["accepted"] += int(allowed)
            aggregate[policy]["semantic_correct"] += int(semantic_correct)
            aggregate[policy]["unsafe_accept"] += int(unsafe_accept)
            aggregate[policy]["rejected"] += int(not allowed)
            category_result = by_category[category].setdefault(
                policy, {"accepted": 0, "semantic_correct": 0, "unsafe_accept": 0, "rejected": 0}
            )
            category_result["accepted"] += int(allowed)
            category_result["semantic_correct"] += int(semantic_correct)
            category_result["unsafe_accept"] += int(unsafe_accept)
            category_result["rejected"] += int(not allowed)
            # Keep the reason computation exercised without emitting target content.
            if not allowed and not reasons:
                raise AssertionError("a rejected target must have an admission reason")
    result = {
        "schema": SCHEMA,
        "source": {
            "base_schema": BASE_SCHEMA,
            "subplan_hash": digest(asdict(subplan)),
            "repeats_per_category": repeats,
            "target_count": repeats * 5,
            "category_count": 5,
            "raw_content_committed": False,
        },
        "aggregate": aggregate,
        "by_category": by_category,
        "claim_boundary": (
            "Deterministic synthetic admission and verification mechanics only; "
            "no mined-artifact quality, enterprise prevalence, or causal user benefit."
        ),
        "result_sha256": hashlib.sha256(
            json.dumps({"aggregate": aggregate, "by_category": by_category}, sort_keys=True).encode()
        ).hexdigest(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    run(args.output.resolve(), args.repeats)


if __name__ == "__main__":
    main()
