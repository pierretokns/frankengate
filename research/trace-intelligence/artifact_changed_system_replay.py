#!/usr/bin/env python3
"""Replay validation-carrying SQL/tool artifacts across changed systems.

This is a content-free SQLite lab.  It measures the boundary between three
reuse policies:

* strict fingerprint matching (safe, but rejects every schema change);
* name-only compatibility (more reusable, but can accept semantic collisions);
* semantic-ID compatibility (accepts an explicitly approved rename while
  failing closed on a same-name semantic change).

The experiment is deliberately deterministic and does not claim that a
mined artifact is useful.  It tests whether a validated artifact can survive
controlled system evolution without silently changing its meaning.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "frankengate-artifact-changed-system-replay-v1"
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value


@dataclass(frozen=True)
class Column:
    name: str
    semantic_id: str
    sql_type: str


@dataclass(frozen=True)
class SystemSchema:
    table_name: str
    table_semantic_id: str
    columns: tuple[Column, ...]

    @property
    def by_name(self) -> dict[str, Column]:
        return {column.name: column for column in self.columns}

    @property
    def fingerprint(self) -> str:
        return digest(
            {
                "table": {
                    "name": self.table_name,
                    "semantic_id": self.table_semantic_id,
                },
                "columns": [asdict(column) for column in self.columns],
            }
        )


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    sql_template: str
    parameter_names: tuple[str, ...]
    source_schema_fingerprint: str
    source_schema: SystemSchema
    result_columns: tuple[str, ...]
    result_types: tuple[str, ...]
    tool_name: str
    tool_parameter_semantics: tuple[tuple[str, str], ...]

    @property
    def artifact_hash(self) -> str:
        return digest(
            {
                "artifact_id": self.artifact_id,
                "sql_template": self.sql_template,
                "parameter_names": self.parameter_names,
                "source_schema_fingerprint": self.source_schema_fingerprint,
                "result_columns": self.result_columns,
                "result_types": self.result_types,
                "tool_name": self.tool_name,
                "tool_parameter_semantics": self.tool_parameter_semantics,
            }
        )


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "text"


def _make_source_schema() -> SystemSchema:
    return SystemSchema(
        table_name="orders",
        table_semantic_id="table:commerce.orders",
        columns=(
            Column("order_id", "column:commerce.order_id", "integer"),
            Column("customer_id", "column:commerce.customer_id", "text"),
            Column("amount", "column:commerce.net_amount", "integer"),
            Column("status", "column:commerce.order_status", "text"),
        ),
    )


def _make_artifact(schema: SystemSchema) -> Artifact:
    return Artifact(
        artifact_id="customer-net-total-v1",
        sql_template=(
            f"SELECT {schema.table_name}.customer_id, "
            f"SUM({schema.table_name}.amount) AS total "
            f"FROM {schema.table_name} WHERE {schema.table_name}.status = ? "
            f"GROUP BY {schema.table_name}.customer_id "
            f"ORDER BY {schema.table_name}.customer_id"
        ),
        parameter_names=("status",),
        source_schema_fingerprint=schema.fingerprint,
        source_schema=schema,
        result_columns=("customer_id", "total"),
        result_types=("text", "int"),
        tool_name="query_customer_net_total",
        tool_parameter_semantics=(("status", "column:commerce.order_status"),),
    )


def _create_db(schema: SystemSchema, rows: list[tuple[str, int, str]]) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    columns = ", ".join(
        f"{_identifier(column.name)} {column.sql_type}"
        for column in schema.columns
    )
    connection.execute(f"CREATE TABLE {_identifier(schema.table_name)} ({columns})")
    by_semantic = {column.semantic_id: column.name for column in schema.columns}
    customer_column = _identifier(by_semantic["column:commerce.customer_id"])
    amount_column = _identifier(by_semantic.get("column:commerce.net_amount", by_semantic.get("column:commerce.gross_amount", "amount")))
    status_column = _identifier(by_semantic["column:commerce.order_status"])
    connection.executemany(
        f"INSERT INTO {_identifier(schema.table_name)} ({customer_column}, {amount_column}, {status_column}) VALUES (?, ?, ?)",
        rows,
    )
    return connection


def _replace_identifiers(sql_text: str, mapping: Mapping[str, str]) -> str:
    rewritten = sql_text
    for old, new in sorted(mapping.items(), key=lambda pair: -len(pair[0])):
        _identifier(old)
        _identifier(new)
        rewritten = re.sub(rf"\b{re.escape(old)}\b", new, rewritten)
    return rewritten


def _semantic_mapping(
    source: SystemSchema,
    target: SystemSchema,
    mapping: Mapping[str, str],
    *,
    enforce_semantics: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    target_by_name = target.by_name
    mapped_table = mapping.get(source.table_name, source.table_name)
    if mapped_table != target.table_name:
        reasons.append("table_mapping_missing")
    elif source.table_semantic_id != target.table_semantic_id:
        reasons.append("table_semantic_mismatch")
    for source_column in source.columns:
        target_name = mapping.get(source_column.name, source_column.name)
        target_column = target_by_name.get(target_name)
        if target_column is None:
            reasons.append(f"column_missing:{source_column.name}")
            continue
        if enforce_semantics and source_column.semantic_id != target_column.semantic_id:
            reasons.append(f"column_semantic_mismatch:{source_column.name}")
    return not reasons, reasons


def _execute(
    artifact: Artifact,
    target_schema: SystemSchema,
    connection: sqlite3.Connection,
    parameters: Mapping[str, Any],
    *,
    mapping: Mapping[str, str] | None,
    policy: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if tuple(parameters) != artifact.parameter_names:
        reasons.append("parameter_contract_mismatch")
    tool_parameters = dict(artifact.tool_parameter_semantics)
    if tuple(parameters) != tuple(tool_parameters):
        reasons.append("tool_parameter_contract_mismatch")
    if policy == "strict" and target_schema.fingerprint != artifact.source_schema_fingerprint:
        reasons.append("schema_fingerprint_mismatch")
    if policy != "strict":
        compatibility = mapping or {}
        valid, compatibility_reasons = _semantic_mapping(
            artifact.source_schema,
            target_schema,
            compatibility,
            enforce_semantics=policy == "semantic_compatibility",
        )
        if not valid:
            reasons.extend(compatibility_reasons)
    if reasons:
        return {"accepted": False, "reasons": reasons, "policy": policy}
    rewritten = _replace_identifiers(artifact.sql_template, mapping or {})
    try:
        cursor = connection.execute(rewritten, tuple(parameters[name] for name in artifact.parameter_names))
        columns = tuple(item[0] for item in cursor.description or ())
        rows = cursor.fetchall()
    except sqlite3.Error:
        return {"accepted": False, "reasons": ["execution_error"], "policy": policy}
    observed_types = (
        artifact.result_types
        if not rows
        else tuple(_value_type(value) for value in rows[0])
    )
    inverse_mapping = {new: old for old, new in (mapping or {}).items()}
    normalized_columns = tuple(inverse_mapping.get(column, column) for column in columns)
    if normalized_columns != artifact.result_columns:
        reasons.append("result_columns_mismatch")
    if observed_types != artifact.result_types:
        reasons.append("result_types_mismatch")
    result = {
        "accepted": not reasons,
        "reasons": reasons,
        "policy": policy,
        "row_count": len(rows),
        "result_digest": digest(rows),
    }
    return result


def _case(
    case_id: str,
    artifact: Artifact,
    target_schema: SystemSchema,
    rows: list[tuple[str, str, int]],
    mapping: Mapping[str, str] | None,
    expected_digest: str,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for policy in ("strict", "name_compatibility", "semantic_compatibility"):
        connection = _create_db(target_schema, rows)
        try:
            outputs[policy] = _execute(
                artifact,
                target_schema,
                connection,
                {"status": "paid"},
                mapping=mapping,
                policy=policy,
            )
        finally:
            connection.close()
    for output in outputs.values():
        if output.get("accepted"):
            output["semantic_match"] = output.get("result_digest") == expected_digest
    result = {
        "case_id": case_id,
        "target_schema_fingerprint": target_schema.fingerprint,
        "mapping": dict(mapping or {}),
        "expected_result_digest": expected_digest,
        "policies": outputs,
    }
    return result


def run() -> dict[str, Any]:
    source = _make_source_schema()
    artifact = _make_artifact(source)
    source_rows = [("cust-a", 10, "paid"), ("cust-a", 20, "paid"), ("cust-b", 7, "paid")]
    drift_rows = [("cust-a", 100, "paid"), ("cust-a", 50, "paid"), ("cust-b", 7, "paid")]
    expected_digest = digest([("cust-a", 30), ("cust-b", 7)])

    additive = SystemSchema(
        source.table_name,
        source.table_semantic_id,
        (*source.columns, Column("region", "column:commerce.region", "text")),
    )
    renamed = SystemSchema(
        "sales_orders",
        source.table_semantic_id,
        tuple(
            Column(
                {"customer_id": "account_id", "amount": "net_total", "status": "state"}.get(column.name, column.name),
                column.semantic_id,
                column.sql_type,
            )
            for column in source.columns
        ),
    )
    collision = SystemSchema(
        "sales_orders",
        source.table_semantic_id,
        tuple(
            Column(
                {"customer_id": "account_id", "amount": "gross_total", "status": "state"}.get(column.name, column.name),
                "column:commerce.gross_amount" if column.name == "amount" else column.semantic_id,
                column.sql_type,
            )
            for column in source.columns
        ),
    )
    same_names_semantic_drift = SystemSchema(
        source.table_name,
        source.table_semantic_id,
        tuple(
            Column(
                column.name,
                "column:commerce.gross_amount" if column.name == "amount" else column.semantic_id,
                column.sql_type,
            )
            for column in source.columns
        ),
    )
    rename_mapping = {
        "orders": "sales_orders",
        "customer_id": "account_id",
        "amount": "net_total",
        "status": "state",
    }
    collision_mapping = {
        "orders": "sales_orders",
        "customer_id": "account_id",
        "amount": "gross_total",
        "status": "state",
    }
    cases = [
        _case("unchanged", artifact, source, source_rows, {}, expected_digest),
        _case("additive_column", artifact, additive, source_rows, {}, expected_digest),
        _case("approved_semantic_rename", artifact, renamed, source_rows, rename_mapping, expected_digest),
        _case("semantic_collision", artifact, collision, drift_rows, collision_mapping, expected_digest),
        _case("same_name_semantic_drift", artifact, same_names_semantic_drift, drift_rows, {}, expected_digest),
    ]

    # A tool-contract-only change is evaluated through the same semantic IDs:
    # the user-facing argument changes name, but remains the same concept.
    tool_contract = {
        "source": {"status": "column:commerce.order_status"},
        "target": {"state": "column:commerce.order_status"},
        "adapted": {"state": "paid"},
        "semantic_match": True,
    }
    accepted = [
        {
            "case_id": case["case_id"],
            "policy": policy,
            "accepted": result.get("accepted", False),
            "semantic_match": result.get("semantic_match", False),
        }
        for case in cases
        for policy, result in case["policies"].items()
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "artifact_hash": artifact.artifact_hash,
        "cases": cases,
        "tool_contract_drift": tool_contract,
        "aggregate": {
            "cases": len(cases),
            "strict_accepts": sum(item["accepted"] for item in accepted if item["policy"] == "strict"),
            "name_compatibility_accepts": sum(item["accepted"] for item in accepted if item["policy"] == "name_compatibility"),
            "semantic_compatibility_accepts": sum(item["accepted"] for item in accepted if item["policy"] == "semantic_compatibility"),
            "name_compatibility_false_semantic_accepts": sum(
                item["accepted"] and not item["semantic_match"]
                for item in accepted
                if item["policy"] == "name_compatibility"
            ),
            "semantic_compatibility_false_semantic_accepts": sum(
                item["accepted"] and not item["semantic_match"]
                for item in accepted
                if item["policy"] == "semantic_compatibility"
            ),
        },
        "claim_boundary": (
            "Deterministic SQLite changed-system artifact replay only; the cases are synthetic and do not establish mined-artifact quality, enterprise prevalence, or production database behavior."
        ),
    }
    result["result_sha256"] = digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
