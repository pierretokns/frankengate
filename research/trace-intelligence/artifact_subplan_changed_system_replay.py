#!/usr/bin/env python3
"""Test validated subplan reuse across a changed schema and changed intent."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


SCHEMA = "frankengate-artifact-subplan-changed-system-v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Column:
    name: str
    semantic_id: str


@dataclass(frozen=True)
class Subplan:
    name: str
    sql_fragment: str
    semantic_inputs: tuple[str, ...]


@dataclass(frozen=True)
class Target:
    case_id: str
    table_name: str
    columns: tuple[Column, ...]
    mapping: dict[str, str]
    rows: tuple[tuple[str, str], ...]


def _connection(target: Target) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    definitions = ", ".join(f'"{column.name}" TEXT' for column in target.columns)
    connection.execute(f'CREATE TABLE "{target.table_name}" ({definitions})')
    customer_name = target.mapping.get("customer_id", "customer_id")
    status_name = target.mapping.get("status", "status")
    connection.executemany(
        f'INSERT INTO "{target.table_name}" ("{customer_name}", "{status_name}") VALUES (?, ?)',
        [(customer, status) for customer, status in target.rows],
    )
    return connection


def _target_query(target: Target, filter_fragment: str) -> list[tuple[str, int]]:
    connection = _connection(target)
    customer = next(column.name for column in target.columns if column.semantic_id == "column:commerce.customer_id")
    try:
        cursor = connection.execute(
            f'SELECT "{customer}", COUNT(*) AS total FROM "{target.table_name}" {filter_fragment} GROUP BY "{customer}" ORDER BY "{customer}"',
            ("paid",),
        )
        return cursor.fetchall()
    finally:
        connection.close()


def _semantic_filter_allowed(target: Target, subplan: Subplan, policy: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    source_inputs = set(subplan.semantic_inputs)
    target_inputs = {column.semantic_id for column in target.columns}
    if policy == "semantic_subplan" and not source_inputs <= target_inputs:
        reasons.append("semantic_input_missing")
    if policy == "semantic_subplan" and target.columns[0].semantic_id == "column:commerce.gross_amount":
        reasons.append("semantic_collision")
    return not reasons, reasons


def run(output: Path) -> dict[str, Any]:
    subplan = Subplan(
        name="status-filter",
        sql_fragment="WHERE status = ?",
        semantic_inputs=("column:commerce.order_status",),
    )
    source_columns = (
        Column("customer_id", "column:commerce.customer_id"),
        Column("status", "column:commerce.order_status"),
    )
    base_rows = (("cust-a", "paid"), ("cust-a", "paid"), ("cust-b", "paid"), ("cust-b", "open"))
    targets = [
        Target("unchanged", "orders", source_columns, {}, base_rows),
        Target("additive", "orders", source_columns + (Column("region", "column:commerce.region"),), {}, base_rows),
        Target("approved_rename", "sales_orders", (Column("account_id", "column:commerce.customer_id"), Column("state", "column:commerce.order_status")), {"orders": "sales_orders", "customer_id": "account_id", "status": "state"}, base_rows),
        Target("semantic_collision", "sales_orders", (Column("account_id", "column:commerce.customer_id"), Column("state", "column:commerce.gross_amount")), {"orders": "sales_orders", "customer_id": "account_id", "status": "state"}, base_rows),
        Target("same_name_drift", "orders", (Column("customer_id", "column:commerce.customer_id"), Column("status", "column:commerce.gross_amount")), {}, base_rows),
    ]
    expected = [
        ("cust-a", 2),
        ("cust-b", 1),
    ]
    rows: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, int]] = {policy: {"accepted": 0, "semantic_correct": 0, "unsafe_accept": 0} for policy in ("name_only_subplan", "semantic_subplan")}
    for target in targets:
        for policy in aggregate:
            allowed, reasons = _semantic_filter_allowed(target, subplan, policy)
            filter_column = target.mapping.get("status", "status")
            result = _target_query(target, f'WHERE "{filter_column}" = ?') if allowed else []
            target_semantics = {column.semantic_id for column in target.columns}
            semantic_mismatch = not set(subplan.semantic_inputs) <= target_semantics
            semantic_correct = allowed and result == expected and not semantic_mismatch
            unsafe_accept = allowed and policy == "name_only_subplan" and semantic_mismatch
            aggregate[policy]["accepted"] += int(allowed)
            aggregate[policy]["semantic_correct"] += int(semantic_correct)
            aggregate[policy]["unsafe_accept"] += int(unsafe_accept)
            rows.append({"case_id": target.case_id, "policy": policy, "accepted": allowed, "semantic_correct": semantic_correct, "unsafe_accept": unsafe_accept, "reasons": reasons})
    result = {
        "schema": SCHEMA,
        "source": {"subplan_hash": digest(asdict(subplan)), "target_count": len(targets), "raw_content_committed": False},
        "aggregate": aggregate,
        "rows": rows,
        "claim_boundary": "Deterministic changed-system subplan mechanics only; no mined-artifact quality, enterprise prevalence, or causal user benefit is established.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())


if __name__ == "__main__":
    main()
