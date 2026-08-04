#!/usr/bin/env python3
"""Run the validation-carrying artifact capsule against real PostgreSQL.

The SQLite lab establishes the capsule state machine cheaply. This companion
lab exercises the same contract through ``GovernedPostgresExecutor`` against a
temporary least-privilege, RLS-enabled PostgreSQL role. It is intentionally a
mechanics experiment: it does not claim that a mined artifact is useful or
semantically equivalent to a newly generated query.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

import psycopg2
from psycopg2 import sql

from artifact_capsule_reuse import ArtifactCapsule, digest, stable_json
from defog_governed_sql_replay import (
    GovernanceAuthority,
    GovernedPostgresExecutor,
    QueryResult,
)


SCHEMA_VERSION = "frankengate-artifact-capsule-postgresql-v1"
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe generated identifier: {value!r}")
    return value


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, (float, Decimal)):
        return "float"
    return "text"


def postgres_schema_fingerprint(
    executor: GovernedPostgresExecutor, schema: str
) -> str:
    """Fingerprint only the catalog visible to the governed role."""
    connection = executor._connect()  # same module; transaction guard is reused
    try:
        executor._begin(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema, table_name, column_name, ordinal_position,
                       data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_schema, table_name, ordinal_position
                """,
                (schema,),
            )
            rows = cursor.fetchall()
        connection.rollback()
        return digest(rows)
    finally:
        connection.close()


def _capsule_result(capsule: ArtifactCapsule, result: QueryResult) -> dict[str, Any]:
    observed_types = (
        capsule.result_types
        if not result.rows
        else tuple(_value_type(value) for value in result.rows[0])
    )
    reasons: list[str] = []
    if result.columns != capsule.result_columns:
        reasons.append("result_columns_mismatch")
    if observed_types != capsule.result_types:
        reasons.append("result_types_mismatch")
    return {
        "accepted": not reasons,
        "reasons": reasons,
        "result_digest": hashlib.sha256(
            stable_json(result.rows).encode("utf-8")
        ).hexdigest(),
        "row_count": len(result.rows),
    }


def execute_reuse(
    capsule: ArtifactCapsule,
    executor: GovernedPostgresExecutor,
    parameters: Mapping[str, Any],
    *,
    schema: str,
    authority_scope: str,
    authorization_epoch: str,
    now: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    if postgres_schema_fingerprint(executor, schema) != capsule.schema_fingerprint:
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
        return {
            "accepted": False,
            "reasons": reasons,
            "capsule_hash": capsule.capsule_hash,
        }
    try:
        _, result = executor.execute_bound_candidate(
            capsule.sql_template,
            tuple(parameters[name] for name in capsule.parameter_names),
        )
    except Exception as exc:  # the governed executor remains fail-closed
        return {
            "accepted": False,
            "reasons": ["execution_error"],
            "error_class": type(exc).__name__,
            "capsule_hash": capsule.capsule_hash,
        }
    return {
        **_capsule_result(capsule, result),
        "capsule_hash": capsule.capsule_hash,
    }


def _dsn_without_role(admin_dsn: str, role: str, password: str) -> str:
    parts = [part for part in admin_dsn.split() if not part.startswith("user=") and not part.startswith("password=")]
    return " ".join([*parts, f"user={role}", f"password={password}"])


def run(admin_dsn: str | None = None) -> dict[str, Any]:
    admin_dsn = admin_dsn or os.environ.get(
        "CAPSULE_ADMIN_DSN",
        "host=127.0.0.1 port=55433 user=research password=research dbname=research",
    )
    suffix = str(os.getpid())
    schema = _identifier(f"capsule_lab_{suffix}")
    role = _identifier(f"capsule_reader_{suffix}")
    password = f"capsule_pw_{suffix}"
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    reader_dsn = _dsn_without_role(admin_dsn, role, password)
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %s").format(sql.Identifier(role)), (password,))
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(role)))
            cursor.execute(sql.SQL("CREATE TABLE {}.employees (id integer PRIMARY KEY, team text NOT NULL, score integer NOT NULL)").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("INSERT INTO {}.employees (id, team, score) VALUES (1, 'alpha', 10), (2, 'alpha', 20), (3, 'beta', 30)").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("ALTER TABLE {}.employees ENABLE ROW LEVEL SECURITY").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("CREATE POLICY capsule_visible ON {}.employees USING (true)").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("GRANT SELECT ON {}.employees TO {}").format(sql.Identifier(schema), sql.Identifier(role)))

        authority = GovernanceAuthority(
            governance_scope="user:internal/team:analytics",
            authorization_epoch_ref="epoch-1",
            user_id="internal",
            team_id="analytics",
            virtual_key_id="xBFEK",
        )
        executor = GovernedPostgresExecutor(
            dsn=reader_dsn,
            authority=authority,
            allowed_schemas=frozenset({schema}),
        )
        # The runner's search path is generated from allowed_schemas, so the
        # capsule SQL is qualified with the temporary schema for clarity.
        template = (
            f"SELECT team, COUNT(*)::bigint AS members FROM {schema}.employees "
            "WHERE team = %s GROUP BY team ORDER BY team"
        )
        capsule = ArtifactCapsule(
            artifact_id="team-count-postgres-v1",
            sql_template=template,
            parameter_names=("team",),
            schema_fingerprint=postgres_schema_fingerprint(executor, schema),
            authority_scope=authority.governance_scope or "",
            authorization_epoch=authority.authorization_epoch_ref or "",
            result_columns=("team", "members"),
            result_types=("text", "int"),
            expires_at=2_000_000_000,
        )
        now = 1_700_000_000
        valid = execute_reuse(capsule, executor, {"team": "alpha"}, schema=schema, authority_scope=capsule.authority_scope, authorization_epoch=capsule.authorization_epoch, now=now)
        stale = execute_reuse(capsule, executor, {"team": "alpha"}, schema=schema, authority_scope=capsule.authority_scope, authorization_epoch="epoch-0", now=now)
        expired = execute_reuse(capsule, executor, {"team": "alpha"}, schema=schema, authority_scope=capsule.authority_scope, authorization_epoch=capsule.authorization_epoch, now=capsule.expires_at)
        wrong_scope = execute_reuse(capsule, executor, {"team": "alpha"}, schema=schema, authority_scope="user:other/team:analytics", authorization_epoch=capsule.authorization_epoch, now=now)
        wrong_parameters = execute_reuse(capsule, executor, {"other": "alpha"}, schema=schema, authority_scope=capsule.authority_scope, authorization_epoch=capsule.authorization_epoch, now=now)
        injection = execute_reuse(capsule, executor, {"team": "alpha' OR '1'='1"}, schema=schema, authority_scope=capsule.authority_scope, authorization_epoch=capsule.authorization_epoch, now=now)

        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("ALTER TABLE {}.employees ADD COLUMN region text").format(sql.Identifier(schema)))
        schema_drift = execute_reuse(capsule, executor, {"team": "alpha"}, schema=schema, authority_scope=capsule.authority_scope, authorization_epoch=capsule.authorization_epoch, now=now)
        version = None
        with admin.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0].split(",", 1)[0]
        return {
            "schema_version": SCHEMA_VERSION,
            "database": "postgresql",
            "postgres_version": version,
            "role": "least_privilege_rls_enabled",
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
                "injection_interpreted_as_sql": injection["accepted"] and injection.get("row_count") != 0,
                "injection_bound_without_error": injection["accepted"] and injection.get("row_count") == 0,
                "fail_closed": all(not case["accepted"] for case in (stale, expired, wrong_scope, wrong_parameters, schema_drift)),
            },
            "claim_boundary": "Real PostgreSQL governed-executor capsule mechanics only; no claim about artifact quality or user utility.",
        }
    finally:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--admin-dsn")
    args = parser.parse_args()
    result = run(args.admin_dsn)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "valid_accepted": result["aggregate"]["valid_accepted"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
