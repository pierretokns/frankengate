#!/usr/bin/env python3
"""Replay changed-system explorer selections against independent SQLite fixtures.

This consumes the frontier receipts from ``changed_system_authority_explorer_probe``
but does not trust the model's selection as proof.  Each selected candidate is
first checked by the typed admission contract and then executed against a
case-specific changed schema.  A name-first baseline intentionally skips the
typed gate to expose the unsafe reuse failure mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from changed_system_authority_explorer_probe import Case, Candidate, cases, typed_allowed


SCHEMA_VERSION = "frankengate-changed-system-authority-replay-bridge-v1"


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def target_layout(case: Case) -> tuple[str, str, str, str]:
    """Return table, customer, status, amount physical names for a case."""
    if case.case_id in {"approved_rename", "temporal_replacement"}:
        return "sales_orders", "account_id", "state", "net_total"
    return "orders", "customer_id", "status", "amount"


def build_db(case: Case) -> tuple[sqlite3.Connection, list[tuple[str, int]]]:
    table, customer, status, amount = target_layout(case)
    connection = sqlite3.connect(":memory:")
    columns = f'"{customer}" TEXT, "{status}" TEXT, "{amount}" INTEGER'
    if case.case_id == "schema_drift":
        columns += ', "region" TEXT'
    connection.execute(f'CREATE TABLE "{table}" ({columns})')
    rows = [("cust-a", "paid", 10), ("cust-a", "paid", 20), ("cust-b", "open", 7)]
    if case.case_id in {"same_surface_ambiguity", "mixed_drift"}:
        rows = [("cust-a", "paid", 0), ("cust-a", "paid", 0), ("cust-b", "open", 1)]
    if case.case_id == "no_safe_candidate":
        rows = [("cust-a", "paid", 90), ("cust-b", "open", 10)]
    if case.case_id == "schema_drift":
        connection.executemany(
            f'INSERT INTO "{table}" ("{customer}", "{status}", "{amount}", "region") VALUES (?, ?, ?, ?)',
            [(a, b, c, "north") for a, b, c in rows],
        )
    else:
        connection.executemany(
            f'INSERT INTO "{table}" ("{customer}", "{status}", "{amount}") VALUES (?, ?, ?)', rows
        )
    expected = [("cust-a", 2)]
    return connection, expected


def candidate_sql(case: Case, item: Candidate) -> tuple[str, str]:
    """Return an artifact body and the physical table used by that body."""
    table, customer, status, amount = target_layout(case)
    # A renamed surface carries the approved physical mapping.  Other
    # candidates retain the old names, which is precisely what changed-system
    # replay must validate rather than silently repair.
    if item.surface_name == "state-filter" and case.case_id in {"approved_rename", "temporal_replacement", "mixed_drift"}:
        return (
            f'SELECT "{customer}", COUNT(*) AS total FROM "{table}" '
            f'WHERE "{status}" = ? GROUP BY "{customer}" ORDER BY "{customer}"',
            table,
        )
    if item.semantic_inputs == ("column:commerce.gross_amount",):
        return (
            f'SELECT "{customer}", COUNT(*) AS total FROM "{table}" '
            f'WHERE "{amount}" = ? GROUP BY "{customer}" ORDER BY "{customer}"',
            table,
        )
    return (
        'SELECT "customer_id", COUNT(*) AS total FROM "orders" '
        'WHERE "status" = ? GROUP BY "customer_id" ORDER BY "customer_id"',
        "orders",
    )


def execute_candidate(case: Case, item: Candidate) -> dict[str, Any]:
    connection, expected = build_db(case)
    sql, _ = candidate_sql(case, item)
    try:
        try:
            rows = connection.execute(sql, ("paid",)).fetchall()
            return {"executed": True, "result_digest": stable_hash(rows), "expected_digest": stable_hash(expected), "semantic_result_match": rows == expected}
        except sqlite3.Error as exc:
            return {"executed": False, "error": type(exc).__name__, "semantic_result_match": False}
    finally:
        connection.close()


def selection(raw_dir: Path, case_index: int, arm: str) -> list[int]:
    path = raw_dir / f"case-{case_index:02d}-{arm}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    value = raw.get("structured_output")
    indices = value.get("selected_indices") if isinstance(value, dict) else None
    if not isinstance(indices, list):
        raise ValueError(f"missing selection for case {case_index} {arm}")
    return [int(item) for item in indices]


def replay_row(case: Case, item: Candidate, *, gate: bool, source: str) -> dict[str, Any]:
    allowed = typed_allowed(case, item) if gate else True
    execution = execute_candidate(case, item) if allowed else {"executed": False, "denied": True, "semantic_result_match": False}
    unsafe = allowed and not typed_allowed(case, item)
    safe_correct = allowed and typed_allowed(case, item) and bool(execution.get("semantic_result_match"))
    return {
        "source": source,
        "artifact_id_hash": stable_hash(item.artifact_id),
        "typed_gate_allowed": typed_allowed(case, item),
        "accepted": allowed,
        "unsafe_accept": unsafe,
        "safe_correct": safe_correct,
        "execution": execution,
    }


def run(result_path: Path, raw_dir: Path, output: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != "frankengate-changed-system-authority-explorer-v1":
        raise ValueError("wrong explorer result schema")
    fixture = cases()
    rows: list[dict[str, Any]] = []
    for case_index, case in enumerate(fixture):
        for arm in ("name_only", "typed_metadata"):
            indices = selection(raw_dir, case_index, arm)
            selected = [case.candidates[index] for index in indices]
            typed_results = [replay_row(case, item, gate=True, source=f"{arm}:typed_gate") for item in selected]
            rows.append({"case_id": case.case_id, "case_index": case_index, "arm": arm, "selected_count": len(selected), "typed_gate": typed_results})
        # Deliberately naive baseline: pick the first name-bearing candidate,
        # execute without authority/schema/semantic checks, and measure what it
        # would have done. This is a control, not a recommended policy.
        naive_index = next((index for index, item in enumerate(case.candidates) if "filter" in item.surface_name or "orders" in item.surface_name), 0)
        rows.append({"case_id": case.case_id, "case_index": case_index, "arm": "naive_name_first", "selected_count": 1, "typed_gate": [replay_row(case, case.candidates[naive_index], gate=False, source="naive_name_first")], "naive_index": naive_index})
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("name_only", "typed_metadata", "naive_name_first"):
        values = [item for row in rows if row["arm"] == arm for item in row["typed_gate"]]
        arms[arm] = {
            "cases": sum(row["arm"] == arm for row in rows),
            "accepted": sum(bool(item["accepted"]) for item in values),
            "executed": sum(bool(item["execution"].get("executed")) for item in values),
            "safe_correct": sum(bool(item["safe_correct"]) for item in values),
            "unsafe_accepts": sum(bool(item["unsafe_accept"]) for item in values),
            "semantic_result_matches": sum(bool(item["execution"].get("semantic_result_match")) for item in values),
        }
    output_value: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"explorer_result_sha256": stable_hash(result), "raw_model_outputs_external": True, "raw_content_committed": False},
        "protocol": {"case_count": len(fixture), "frontier_selection_replayed": True, "independent_sql_execution": True, "typed_gate_reexecuted": True, "naive_name_first_is_control_only": True},
        "arms": arms,
        "rows": rows,
        "claim_boundary": {"changed_system_replay_measured": True, "unsafe_name_control_measured": True, "enterprise_artifact_utility_established": False, "causal_skill_improvement_established": False, "reason": "Synthetic SQLite replay bridge over the authority explorer fixture; no enterprise labels, production system, or user-utility outcome."},
    }
    output_value["result_sha256"] = stable_hash(output_value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": arms}, sort_keys=True))
    return output_value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--explorer-result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.explorer_result.resolve(), args.raw_dir.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
