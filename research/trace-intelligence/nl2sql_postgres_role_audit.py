#!/usr/bin/env python3
"""Disposable PostgreSQL-16 role separation audit for NL2SQL candidates.

The fixture, DSN, SQL, task identities, returned rows, object names, and raw
audit remain external.  The durable output contains only counts, booleans, and
content hashes.  The candidate SQL runs once as the candidate role; the gold
SQL runs once, and only as the evaluator role.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import secrets
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "frankengate-nl2sql-postgres-role-audit-v1"
FIXTURE_VERSION = "nl2sql-role-audit-fixture-v1"
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
RELATION = re.compile(
    r"^[a-z_][a-z0-9_]{0,62}\.[a-z_][a-z0-9_]{0,62}$"
)
REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]


class AuditInputError(ValueError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def sha256_path(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _validate_external_path(path: pathlib.Path) -> None:
    if _is_within(path, REPOSITORY_ROOT):
        raise AuditInputError("raw audit must remain outside the repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise AuditInputError(
            "raw audit path already exists; refusing overwrite"
        ) from exc
    else:
        os.close(descriptor)


def _load_fixture(
    path: pathlib.Path, expected_sha256: str
) -> tuple[dict[str, Any], str]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise AuditInputError("expected fixture SHA-256 must be 64 lowercase hex")
    observed = sha256_path(path)
    if observed != expected_sha256:
        raise AuditInputError("fixture snapshot does not match expected SHA-256")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != FIXTURE_VERSION:
        raise AuditInputError("unsupported fixture schema")
    relations = value.get("read_relations")
    tasks = value.get("tasks")
    if not isinstance(relations, list) or not all(
        isinstance(item, str) and RELATION.fullmatch(item)
        for item in relations
    ):
        raise AuditInputError("read_relations must be unquoted schema.table names")
    if not isinstance(tasks, list) or not tasks:
        raise AuditInputError("tasks must be non-empty")
    for task in tasks:
        if (
            not isinstance(task, dict)
            or not isinstance(task.get("task_id"), str)
            or not task["task_id"]
            or not isinstance(task.get("candidate_sql"), str)
            or not task["candidate_sql"].strip()
            or not isinstance(task.get("gold_sql"), str)
            or not task["gold_sql"].strip()
            or task.get("comparison") not in {"ordered", "unordered"}
        ):
            raise AuditInputError("each task requires id, SQL pair, and comparison")
    return value, observed


def _append_raw(path: pathlib.Path, value: Mapping[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(stable_json(value) + "\n")


def _safe_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(receipt.get("ok")),
        "row_count": int(receipt.get("row_count", 0)),
        "result_sha256": str(receipt.get("result_sha256", "")),
        "error_class": str(receipt.get("error_class", "")),
    }


def run_experiment(
    *,
    adapter: Any,
    fixture_path: pathlib.Path,
    expected_fixture_sha256: str,
    raw_audit_path: pathlib.Path,
) -> dict[str, Any]:
    _validate_external_path(raw_audit_path)
    fixture, initial_hash = _load_fixture(
        fixture_path, expected_fixture_sha256
    )
    invalid: list[str] = []
    candidate_ok = 0
    gold_ok = 0
    exact_matches = 0
    setup_receipt: Mapping[str, Any] = {}
    identities: dict[str, Mapping[str, Any]] = {}
    write_denials: dict[str, bool] = {}
    run_token = secrets.token_hex(8)
    cleanup_succeeded = False
    candidate_attempts = 0
    gold_attempts = 0
    initial_database_snapshot_sha256 = ""
    final_database_snapshot_sha256 = ""

    try:
        setup_receipt = adapter.setup(run_token, fixture["read_relations"])
        if int(setup_receipt.get("postgres_major", 0)) != 16:
            invalid.append("postgres_major_not_16")
        if not (
            setup_receipt.get("candidate_role_safe")
            and setup_receipt.get("evaluator_role_safe")
        ):
            invalid.append("unsafe_database_role")
        initial_database_snapshot_sha256 = (
            adapter.database_snapshot_sha256()
        )
        final_database_snapshot_sha256 = initial_database_snapshot_sha256

        for lane, application_name in (
            ("candidate", "frankengate_nl2sql_candidate_v1"),
            ("evaluator", "frankengate_nl2sql_evaluator_v1"),
        ):
            identities[lane] = adapter.audit_identity(lane, application_name)
            _append_raw(
                raw_audit_path,
                {
                    "event": "identity",
                    "lane": lane,
                    "receipt": dict(identities[lane]),
                },
            )
            if not (
                identities[lane].get("current_user_matches")
                and identities[lane].get("application_name_matches")
            ):
                invalid.append("identity_assertion_failed")
            write_denials[lane] = bool(adapter.assert_write_denied(lane))
            if not write_denials[lane]:
                invalid.append("write_denial_failed")

        if not invalid:
            for task in fixture["tasks"]:
                before_candidate = adapter.database_snapshot_sha256()
                if before_candidate != initial_database_snapshot_sha256:
                    invalid.append("database_snapshot_drift")
                    break
                candidate_attempts += 1
                candidate = adapter.execute(
                    "candidate", task["candidate_sql"], task["comparison"]
                )
                before_gold = adapter.database_snapshot_sha256()
                if before_gold != initial_database_snapshot_sha256:
                    invalid.append("database_snapshot_drift")
                    _append_raw(
                        raw_audit_path,
                        {
                            "event": "database_snapshot_drift",
                            "phase": "between_candidate_and_gold",
                        },
                    )
                    break
                gold_attempts += 1
                gold = adapter.execute(
                    "evaluator", task["gold_sql"], task["comparison"]
                )
                after_gold = adapter.database_snapshot_sha256()
                if after_gold != initial_database_snapshot_sha256:
                    invalid.append("database_snapshot_drift")
                _append_raw(
                    raw_audit_path,
                    {
                        "event": "task_execution",
                        "task_id": task["task_id"],
                        "comparison": task["comparison"],
                        "candidate_sql": task["candidate_sql"],
                        "gold_sql": task["gold_sql"],
                        "candidate": dict(candidate),
                        "gold": dict(gold),
                    },
                )
                candidate_ok += int(bool(candidate.get("ok")))
                gold_ok += int(bool(gold.get("ok")))
                exact_matches += int(
                    bool(candidate.get("ok"))
                    and bool(gold.get("ok"))
                    and candidate.get("result_sha256")
                    == gold.get("result_sha256")
                    and after_gold == initial_database_snapshot_sha256
                )
                if after_gold != initial_database_snapshot_sha256:
                    break
            final_database_snapshot_sha256 = (
                adapter.database_snapshot_sha256()
            )
            if (
                final_database_snapshot_sha256
                != initial_database_snapshot_sha256
            ):
                invalid.append("database_snapshot_drift")
    except Exception as exc:  # cleanup and aggregate invalidity are mandatory
        invalid.append("execution_infrastructure_error")
        _append_raw(
            raw_audit_path,
            {
                "event": "infrastructure_error",
                "error_class": type(exc).__name__,
            },
        )
    finally:
        try:
            adapter.cleanup()
            cleanup_succeeded = True
        except Exception as exc:
            invalid.append("cleanup_failed")
            _append_raw(
                raw_audit_path,
                {
                    "event": "cleanup_error",
                    "error_class": type(exc).__name__,
                },
            )

    final_hash = sha256_path(fixture_path)
    if final_hash != initial_hash:
        invalid.append("fixture_snapshot_drift")
    invalid = sorted(set(invalid))
    result = {
        "schema_version": SCHEMA_VERSION,
        "infrastructure_status": (
            "infrastructure_invalid" if invalid else "valid"
        ),
        "invalid_reasons": invalid,
        "fixture": {
            "snapshot_sha256": initial_hash,
            "task_count": len(fixture["tasks"]),
            "snapshot_unchanged": final_hash == initial_hash,
        },
        "database_snapshot": {
            "snapshot_sha256": initial_database_snapshot_sha256,
            "snapshot_unchanged": bool(
                initial_database_snapshot_sha256
                and final_database_snapshot_sha256
                == initial_database_snapshot_sha256
            ),
        },
        "database_controls": {
            "postgres_major_16": int(
                setup_receipt.get("postgres_major", 0)
            )
            == 16,
            "candidate_nosuperuser_nobypassrls": bool(
                setup_receipt.get("candidate_role_safe")
            ),
            "evaluator_nosuperuser_nobypassrls": bool(
                setup_receipt.get("evaluator_role_safe")
            ),
            "candidate_identity_asserted": bool(
                identities.get("candidate", {}).get("current_user_matches")
            ),
            "evaluator_identity_asserted": bool(
                identities.get("evaluator", {}).get("current_user_matches")
            ),
            "distinct_application_names_asserted": all(
                identities.get(lane, {}).get("application_name_matches")
                for lane in ("candidate", "evaluator")
            ),
            "candidate_write_denied": write_denials.get("candidate", False),
            "evaluator_write_denied": write_denials.get("evaluator", False),
            "cleanup_attempted": True,
            "cleanup_succeeded": cleanup_succeeded,
        },
        "execution_contract": {
            "candidate_executions": candidate_attempts,
            "gold_only_evaluator_executions": gold_attempts,
            "candidate_sql_executed_once_per_task": (
                candidate_attempts == len(fixture["tasks"])
            ),
            "gold_never_executed_as_candidate": True,
        },
        "outcomes": {
            "candidate_successes": candidate_ok,
            "gold_successes": gold_ok,
            "exact_matches": exact_matches,
        },
        "claim_limits": [
            "single disposable PostgreSQL instance, not Aurora failover",
            "role and read-only-transaction isolation is not a hostile SQL sandbox",
            "exact result equality is not semantic SQL correctness",
            "aggregate excludes SQL, rows, task identities, DSN, and object names",
        ],
    }
    result["result_sha256"] = hashlib.sha256(
        stable_json(result).encode("utf-8")
    ).hexdigest()
    return result


class Psycopg2Adapter:
    """Real adapter; imports psycopg2 only when an actual run is requested."""

    def __init__(self, dsn: str, statement_timeout_ms: int = 30000):
        import psycopg2
        from psycopg2 import sql

        self.psycopg2 = psycopg2
        self.sql = sql
        self.dsn = dsn
        self.statement_timeout_ms = statement_timeout_ms
        self.admin = None
        self.connections: dict[str, Any] = {}
        self.schema = ""
        self.roles: dict[str, str] = {}
        self.read_relations: tuple[str, ...] = ()

    def setup(
        self, run_token: str, read_relations: Sequence[str]
    ) -> dict[str, Any]:
        self.read_relations = tuple(read_relations)
        suffix = run_token[:16]
        self.schema = f"fg_nl2sql_{suffix}"
        self.roles = {
            "candidate": f"fg_cand_{suffix}",
            "evaluator": f"fg_eval_{suffix}",
        }
        self.admin = self.psycopg2.connect(
            self.dsn, application_name="frankengate_nl2sql_setup_v1"
        )
        self.admin.autocommit = True
        with self.admin.cursor() as cursor:
            cursor.execute("show server_version_num")
            major = int(str(cursor.fetchone()[0])[:2])
            if major != 16:
                raise RuntimeError("experiment requires PostgreSQL 16")
            for role in self.roles.values():
                cursor.execute(
                    self.sql.SQL(
                        "create role {} nologin nosuperuser nocreatedb "
                        "nocreaterole noinherit noreplication nobypassrls"
                    ).format(self.sql.Identifier(role))
                )
            cursor.execute(
                self.sql.SQL("create schema {}").format(
                    self.sql.Identifier(self.schema)
                )
            )
            cursor.execute(
                self.sql.SQL(
                    "create table {}.write_probe (marker integer not null)"
                ).format(self.sql.Identifier(self.schema))
            )
            cursor.execute(
                self.sql.SQL(
                    "create function {}.audit_identity() "
                    "returns table(role_name name, app_name text) "
                    "language sql stable security invoker "
                    "set search_path = pg_catalog "
                    "as 'select current_user, "
                    "current_setting(''application_name'')'"
                ).format(self.sql.Identifier(self.schema))
            )
            cursor.execute(
                self.sql.SQL(
                    "create function {}.run_readonly(query_text text) "
                    "returns jsonb language plpgsql stable security invoker "
                    "set search_path = pg_catalog as $$ "
                    "declare answer jsonb; begin "
                    "execute 'select coalesce(jsonb_agg(to_jsonb(q)), "
                    "''[]''::jsonb) from (' || query_text || ') q' into answer; "
                    "return answer; end $$"
                ).format(self.sql.Identifier(self.schema))
            )
            for role in self.roles.values():
                cursor.execute(
                    self.sql.SQL("grant usage on schema {} to {}").format(
                        self.sql.Identifier(self.schema),
                        self.sql.Identifier(role),
                    )
                )
                cursor.execute(
                    self.sql.SQL(
                        "grant select on {}.write_probe to {}"
                    ).format(
                        self.sql.Identifier(self.schema),
                        self.sql.Identifier(role),
                    )
                )
                cursor.execute(
                    self.sql.SQL(
                        "grant execute on function {}.audit_identity(), "
                        "{}.run_readonly(text) to {}"
                    ).format(
                        self.sql.Identifier(self.schema),
                        self.sql.Identifier(self.schema),
                        self.sql.Identifier(role),
                    )
                )
                for relation in read_relations:
                    schema_name, table_name = relation.split(".", 1)
                    cursor.execute(
                        self.sql.SQL("grant usage on schema {} to {}").format(
                            self.sql.Identifier(schema_name),
                            self.sql.Identifier(role),
                        )
                    )
                    cursor.execute(
                        self.sql.SQL("grant select on table {}.{} to {}").format(
                            self.sql.Identifier(schema_name),
                            self.sql.Identifier(table_name),
                            self.sql.Identifier(role),
                        )
                    )
                cursor.execute(
                    self.sql.SQL("grant {} to current_user").format(
                        self.sql.Identifier(role)
                    )
                )
            cursor.execute(
                "select rolname, rolsuper, rolbypassrls "
                "from pg_catalog.pg_roles where rolname = any(%s)",
                (list(self.roles.values()),),
            )
            safety = {
                row[0]: not bool(row[1]) and not bool(row[2])
                for row in cursor.fetchall()
            }
        for lane, role in self.roles.items():
            app = f"frankengate_nl2sql_{lane}_v1"
            connection = self.psycopg2.connect(
                self.dsn, application_name=app
            )
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(
                    self.sql.SQL("set role {}").format(
                        self.sql.Identifier(role)
                    )
                )
            self.connections[lane] = connection
        return {
            "postgres_major": major,
            "candidate_role_safe": safety.get(self.roles["candidate"], False),
            "evaluator_role_safe": safety.get(self.roles["evaluator"], False),
        }

    def database_snapshot_sha256(self) -> str:
        """Hash the authorized relation schemas and row multisets.

        This bounded research adapter reads the disposable fixture through the
        operator connection.  It is intentionally not a production snapshot
        algorithm for large databases.
        """

        if self.admin is None:
            raise RuntimeError("database snapshot requested before setup")
        snapshot: list[dict[str, Any]] = []
        with self.admin.cursor() as cursor:
            for relation in self.read_relations:
                schema_name, table_name = relation.split(".", 1)
                cursor.execute(
                    """
                    select a.attname, a.atttypid, a.attnum
                    from pg_catalog.pg_attribute a
                    join pg_catalog.pg_class c on c.oid = a.attrelid
                    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
                    where n.nspname = %s and c.relname = %s
                      and a.attnum > 0 and not a.attisdropped
                    order by a.attnum
                    """,
                    (schema_name, table_name),
                )
                columns = [
                    {
                        "name": row[0],
                        "pg_type_oid": int(row[1]),
                        "ordinal": int(row[2]),
                    }
                    for row in cursor.fetchall()
                ]
                if not columns:
                    raise RuntimeError(
                        "authorized snapshot relation is absent or empty-schema"
                    )
                cursor.execute(
                    self.sql.SQL(
                        "select to_jsonb(snapshot_row) from {}.{} "
                        "as snapshot_row"
                    ).format(
                        self.sql.Identifier(schema_name),
                        self.sql.Identifier(table_name),
                    )
                )
                rows = sorted(
                    stable_json(row[0]) for row in cursor.fetchall()
                )
                snapshot.append(
                    {
                        "relation": relation,
                        "columns": columns,
                        "rows": rows,
                    }
                )
        return hashlib.sha256(
            stable_json(snapshot).encode("utf-8")
        ).hexdigest()

    def audit_identity(
        self, lane: str, application_name: str
    ) -> dict[str, Any]:
        with self.connections[lane].cursor() as cursor:
            cursor.execute(
                self.sql.SQL("select * from {}.audit_identity()").format(
                    self.sql.Identifier(self.schema)
                )
            )
            role_name, app_name = cursor.fetchone()
        return {
            "current_user_matches": role_name == self.roles[lane],
            "application_name_matches": app_name == application_name,
            "observed_role": role_name,
            "observed_application_name": app_name,
        }

    def assert_write_denied(self, lane: str) -> bool:
        connection = self.connections[lane]
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    self.sql.SQL(
                        "insert into {}.write_probe(marker) values (1)"
                    ).format(self.sql.Identifier(self.schema))
                )
        except self.psycopg2.Error as exc:
            return exc.pgcode == "42501"
        return False

    def execute(
        self, lane: str, query: str, comparison: str
    ) -> dict[str, Any]:
        connection = self.connections[lane]
        try:
            with connection.cursor() as cursor:
                cursor.execute("begin transaction read only")
                cursor.execute(
                    "set local statement_timeout = %s",
                    (str(self.statement_timeout_ms),),
                )
                cursor.execute(
                    self.sql.SQL("select {}.run_readonly(%s)").format(
                        self.sql.Identifier(self.schema)
                    ),
                    (query,),
                )
                rows = cursor.fetchone()[0] or []
                cursor.execute("rollback")
            normalized = [stable_json(row) for row in rows]
            if comparison == "unordered":
                normalized.sort()
            digest = hashlib.sha256(
                stable_json(normalized).encode("utf-8")
            ).hexdigest()
            return {
                "ok": True,
                "row_count": len(rows),
                "result_sha256": digest,
                "raw_rows": rows,
            }
        except self.psycopg2.Error as exc:
            try:
                connection.rollback()
            except self.psycopg2.Error:
                pass
            return {
                "ok": False,
                "row_count": 0,
                "result_sha256": "",
                "error_class": exc.pgcode or type(exc).__name__,
                "raw_rows": [],
            }

    def cleanup(self) -> None:
        errors = []
        for connection in self.connections.values():
            try:
                connection.close()
            except Exception as exc:
                errors.append(exc)
        self.connections.clear()
        cleanup = self.admin
        if cleanup is None or cleanup.closed:
            cleanup = self.psycopg2.connect(
                self.dsn, application_name="frankengate_nl2sql_cleanup_v1"
            )
            cleanup.autocommit = True
        with cleanup.cursor() as cursor:
            if self.schema:
                try:
                    cursor.execute(
                        self.sql.SQL("drop schema if exists {} cascade").format(
                            self.sql.Identifier(self.schema)
                        )
                    )
                except Exception as exc:
                    errors.append(exc)
            for role in self.roles.values():
                try:
                    cursor.execute(
                        self.sql.SQL("drop owned by {}").format(
                            self.sql.Identifier(role)
                        )
                    )
                except Exception as exc:
                    errors.append(exc)
                try:
                    cursor.execute(
                        self.sql.SQL("drop role if exists {}").format(
                            self.sql.Identifier(role)
                        )
                    )
                except Exception as exc:
                    errors.append(exc)
        cleanup.close()
        if self.admin is not None and not self.admin.closed:
            self.admin.close()
        if errors:
            raise RuntimeError("one or more disposable objects failed cleanup")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--fixture-json", type=pathlib.Path, required=True)
    parser.add_argument("--fixture-sha256", required=True)
    parser.add_argument("--raw-audit-jsonl", type=pathlib.Path, required=True)
    parser.add_argument("--output-json", type=pathlib.Path, required=True)
    parser.add_argument("--statement-timeout-ms", type=int, default=30000)
    args = parser.parse_args()
    result = run_experiment(
        adapter=Psycopg2Adapter(args.dsn, args.statement_timeout_ms),
        fixture_path=args.fixture_json,
        expected_fixture_sha256=args.fixture_sha256,
        raw_audit_path=args.raw_audit_jsonl,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return int(result["infrastructure_status"] != "valid")


if __name__ == "__main__":
    raise SystemExit(main())
