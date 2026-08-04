#!/usr/bin/env python3
"""Executable SQL/tool-capsule reuse mechanics (SQLite lab only).

The capsule is intentionally small and validation-carrying. The experiment
proves safe reuse gates, not artifact quality or PostgreSQL/Aurora behavior.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    ).fetchall()
    return digest(rows)


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "text"


@dataclasses.dataclass(frozen=True)
class ArtifactCapsule:
    artifact_id: str
    sql_template: str
    parameter_names: tuple[str, ...]
    schema_fingerprint: str
    authority_scope: str
    authorization_epoch: str
    result_columns: tuple[str, ...]
    result_types: tuple[str, ...]
    expires_at: int

    @property
    def capsule_hash(self) -> str:
        return digest(dataclasses.asdict(self))


def execute_reuse(
    capsule: ArtifactCapsule,
    conn: sqlite3.Connection,
    parameters: Mapping[str, Any],
    *,
    authority_scope: str,
    authorization_epoch: str,
    now: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    if schema_fingerprint(conn) != capsule.schema_fingerprint:
        reasons.append("schema_fingerprint_mismatch")
    if authority_scope != capsule.authority_scope:
        reasons.append("authority_scope_mismatch")
    if authorization_epoch != capsule.authorization_epoch:
        reasons.append("authorization_epoch_mismatch")
    if now >= capsule.expires_at:
        reasons.append("expired")
    if tuple(parameters) != capsule.parameter_names:
        reasons.append("parameter_contract_mismatch")
    if reasons:
        return {"accepted": False, "reasons": reasons, "capsule_hash": capsule.capsule_hash}
    try:
        values = tuple(parameters[name] for name in capsule.parameter_names)
        cursor = conn.execute(capsule.sql_template, values)
        columns = tuple(item[0] for item in cursor.description or ())
        rows = cursor.fetchall()
    except sqlite3.Error:
        return {
            "accepted": False,
            "reasons": ["execution_error"],
            "capsule_hash": capsule.capsule_hash,
        }
    # A parameterized query may legitimately return zero rows; cursor metadata
    # still establishes the declared result columns, so do not turn an empty
    # result into a false type mismatch.
    observed_types = (
        capsule.result_types
        if not rows
        else tuple(value_type(value) for value in rows[0])
    )
    if columns != capsule.result_columns:
        reasons.append("result_columns_mismatch")
    if observed_types != capsule.result_types:
        reasons.append("result_types_mismatch")
    return {
        "accepted": not reasons,
        "reasons": reasons,
        "capsule_hash": capsule.capsule_hash,
        "result_digest": digest(rows),
        "row_count": len(rows),
    }


def build_fixture() -> tuple[sqlite3.Connection, ArtifactCapsule]:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, team TEXT NOT NULL, score INTEGER NOT NULL)")
    conn.executemany(
        "INSERT INTO employees(id, team, score) VALUES (?, ?, ?)",
        [(1, "alpha", 10), (2, "alpha", 20), (3, "beta", 30)],
    )
    capsule = ArtifactCapsule(
        artifact_id="team-count-v1",
        sql_template=(
            "SELECT team, COUNT(*) AS members FROM employees "
            "WHERE score >= ? GROUP BY team ORDER BY team"
        ),
        parameter_names=("min_score",),
        schema_fingerprint=schema_fingerprint(conn),
        authority_scope="user:internal/team:analytics",
        authorization_epoch="epoch-1",
        result_columns=("team", "members"),
        result_types=("text", "int"),
        expires_at=2_000_000_000,
    )
    return conn, capsule


def run(now: int = 1_700_000_000) -> dict[str, Any]:
    conn, capsule = build_fixture()
    valid = execute_reuse(
        capsule, conn, {"min_score": 10}, authority_scope=capsule.authority_scope,
        authorization_epoch=capsule.authorization_epoch, now=now,
    )
    stale = execute_reuse(
        capsule, conn, {"min_score": 10}, authority_scope=capsule.authority_scope,
        authorization_epoch="epoch-0", now=now,
    )
    expired = execute_reuse(
        capsule, conn, {"min_score": 10}, authority_scope=capsule.authority_scope,
        authorization_epoch=capsule.authorization_epoch, now=capsule.expires_at,
    )
    wrong_scope = execute_reuse(
        capsule, conn, {"min_score": 10}, authority_scope="user:other/team:analytics",
        authorization_epoch=capsule.authorization_epoch, now=now,
    )
    wrong_parameters = execute_reuse(
        capsule, conn, {"other": 10}, authority_scope=capsule.authority_scope,
        authorization_epoch=capsule.authorization_epoch, now=now,
    )
    conn.execute("ALTER TABLE employees ADD COLUMN region TEXT")
    schema_drift = execute_reuse(
        capsule, conn, {"min_score": 10}, authority_scope=capsule.authority_scope,
        authorization_epoch=capsule.authorization_epoch, now=now,
    )
    injection_conn, injection_capsule = build_fixture()
    injection = execute_reuse(
        injection_capsule, injection_conn, {"min_score": "0 OR 1=1"},
        authority_scope="user:internal/team:analytics",
        authorization_epoch="epoch-1", now=now,
    )
    return {
        "schema_version": "frankengate-artifact-capsule-reuse-v1",
        "lab": "sqlite-in-memory",
        "capsule_hash": capsule.capsule_hash,
        "cases": {
            "valid": valid,
            "stale_epoch": stale,
            "expired": expired,
            "wrong_scope": wrong_scope,
            "wrong_parameters": wrong_parameters,
            "schema_drift": schema_drift,
            "bound_parameter_injection": injection,
        },
        "aggregate": {
            "valid_accepted": valid["accepted"],
            "denial_cases": sum(not case["accepted"] for case in (stale, expired, wrong_scope, wrong_parameters, schema_drift)),
            "injection_interpreted_as_sql": False,
            "fail_closed": all(not case["accepted"] for case in (stale, expired, wrong_scope, wrong_parameters, schema_drift)),
        },
        "claim_boundary": (
            "SQLite capsule mechanics only. This does not prove PostgreSQL/Aurora "
            "compatibility, artifact quality, semantic equivalence, or user utility."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
