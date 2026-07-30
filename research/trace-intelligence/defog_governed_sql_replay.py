#!/usr/bin/env python3
"""Governed, content-audited PostgreSQL replay for the Defog SQL cohort.

This is research infrastructure, not a production query service. It separates
four concerns that the upstream evaluator combines or omits:

* content is resolved only from a hash-pinned external checkout;
* authorization is fail-closed and requires an epoch reference;
* candidate SQL is parsed and policy-checked before PostgreSQL sees it;
* semantic correctness and security compliance are independent verdicts.

Raw questions, SQL, and tool calls may be written only to an explicitly
supplied external audit file. Returned and committed receipts contain hashes
and aggregates, never source content or database rows.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import psycopg2
from psycopg2.extensions import connection as PGConnection
from sqlglot import exp, parse
from sqlglot.errors import ParseError
from sqlglot.tokens import TokenType, Tokenizer


SCHEMA_VERSION = "frankengate-defog-governed-replay-v1"
DEFAULT_STATEMENT_TIMEOUT_MS = 5_000
DEFAULT_LOCK_TIMEOUT_MS = 500
DEFAULT_IDLE_TIMEOUT_MS = 5_000
DEFAULT_MAX_ROWS = 10_000
DEFAULT_MAX_RESULT_BYTES = 8 * 1024 * 1024
DEFAULT_ALLOWED_SCHEMAS = frozenset({"public", "consumer_div"})
SYSTEM_SCHEMAS = frozenset(
    {"information_schema", "pg_catalog", "pg_toast", "pg_temp"}
)
SENSITIVE_NAME_PATTERN = re.compile(
    r"(^|_)(email|e_mail|phone|mobile|address|street|postal|zip|"
    r"ip|ip_address|user_agent|ssn|social_security|passport|"
    r"credit_card|card_number|account_number)(_|$)",
    re.IGNORECASE,
)
DANGEROUS_FUNCTIONS = frozenset(
    {
        "current_setting",
        "dblink",
        "dblink_connect",
        "dblink_exec",
        "lo_export",
        "lo_import",
        "pg_ls_dir",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_sleep",
        "pg_stat_file",
        "set_config",
    }
)
# Fail-closed function allowlist. SQLGlot models boolean operators and CASE-like
# expressions as functions too, so they appear here alongside SQL functions.
DEFAULT_ALLOWED_FUNCTIONS = frozenset(
    {
        "abs",
        "age",
        "and",
        "anonymous",
        "array_agg",
        "avg",
        "case",
        "cast",
        "ceil",
        "coalesce",
        "concat",
        "concat_ws",
        "count",
        "current_date",
        "date",
        "date_add",
        "date_diff",
        "date_sub",
        "date_trunc",
        "dense_rank",
        "exp",
        "exploding_generate_series",
        "extract",
        "floor",
        "greatest",
        "if",
        "lag",
        "lead",
        "least",
        "length",
        "ln",
        "log",
        "lower",
        "max",
        "min",
        "nullif",
        "or",
        "percentile_cont",
        "power",
        "rank",
        "replace",
        "round",
        "row_number",
        "sqrt",
        "str_to_date",
        "struct",
        "substr",
        "substring",
        "sum",
        "time_to_str",
        "timestamp_trunc",
        "trim",
        "upper",
    }
)


class ReplayError(RuntimeError):
    """Base class for deterministic replay failures."""


class SourceIntegrityError(ReplayError):
    """A source checkout or content-free manifest failed verification."""


class AuthorizationError(ReplayError):
    """The governance authority envelope is absent, incomplete, or stale."""


class SQLPolicyError(ReplayError):
    """Candidate SQL violates the fail-closed read policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ResultLimitError(ReplayError):
    """A result exceeded a configured row or byte boundary."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _normalized_identifier(value: str) -> str:
    return value.strip('"').lower()


@dataclass(frozen=True)
class GovernanceAuthority:
    governance_scope: str | None
    authorization_epoch_ref: str | None
    user_id: str | None = None
    team_id: str | None = None
    virtual_key_id: str | None = None

    def validate(self) -> None:
        if self.governance_scope and not self.authorization_epoch_ref:
            raise AuthorizationError(
                "governance scope requires authorization_epoch_ref"
            )
        if self.governance_scope and not (self.user_id or self.team_id):
            raise AuthorizationError(
                "governance scope requires a user_id or team_id"
            )

    def content_free_receipt(self) -> dict[str, Any]:
        self.validate()
        return {
            "governance_scope": self.governance_scope,
            "authorization_epoch_ref_sha256": (
                sha256_text(self.authorization_epoch_ref)
                if self.authorization_epoch_ref
                else None
            ),
            "user_id_sha256": sha256_text(self.user_id) if self.user_id else None,
            "team_id_sha256": sha256_text(self.team_id) if self.team_id else None,
            "virtual_key_id_sha256": (
                sha256_text(self.virtual_key_id) if self.virtual_key_id else None
            ),
        }


@dataclass(frozen=True)
class RuntimeTask:
    task_id: str
    database: str
    query_category: str
    question: str
    instructions: str
    gold_sql: str


class PinnedTaskResolver:
    """Resolve task content from an external checkout after hash verification."""

    def __init__(
        self,
        *,
        source_root: Path,
        manifest_path: Path,
        dataset_manifest_path: Path,
    ) -> None:
        self.source_root = source_root.resolve(strict=True)
        self.manifest_path = manifest_path.resolve(strict=True)
        self.dataset_manifest_path = dataset_manifest_path.resolve(strict=True)
        self.manifest_bytes = self.manifest_path.read_bytes()
        self.manifest = json.loads(self.manifest_bytes)
        self.dataset_manifest = json.loads(
            self.dataset_manifest_path.read_text(encoding="utf-8")
        )
        expected_manifest = self.dataset_manifest["cohort"]["manifest_sha256"]
        actual_manifest = sha256_bytes(self.manifest_bytes)
        if actual_manifest != expected_manifest:
            raise SourceIntegrityError(
                f"cohort manifest hash {actual_manifest} != {expected_manifest}"
            )
        self.tasks = {
            task["task_id"]: task for task in self.manifest.get("tasks", [])
        }
        if len(self.tasks) != len(self.manifest.get("tasks", [])):
            raise SourceIntegrityError("cohort manifest has duplicate task IDs")
        self._rows: dict[str, list[dict[str, str]]] = {}
        self._verify_sources()

    def _verify_sources(self) -> None:
        for relative_path, descriptor in self.dataset_manifest[
            "source_files"
        ].items():
            path = self.source_root / relative_path
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise SourceIntegrityError(f"cannot read {path}: {exc}") from exc
            actual = sha256_bytes(payload)
            if actual != descriptor["sha256"]:
                raise SourceIntegrityError(
                    f"source hash mismatch for {relative_path}: {actual}"
                )

    def _source_rows(self, relative_path: str) -> list[dict[str, str]]:
        if relative_path not in self._rows:
            path = self.source_root / relative_path
            with path.open("r", encoding="utf-8", newline="") as handle:
                self._rows[relative_path] = list(csv.DictReader(handle))
        return self._rows[relative_path]

    def resolve(self, task_id: str) -> RuntimeTask:
        descriptor = self.tasks.get(task_id)
        if descriptor is None:
            raise SourceIntegrityError(f"unknown cohort task_id: {task_id}")
        rows = self._source_rows(descriptor["source_file"])
        row_number = descriptor["source_row_0based"]
        try:
            row = rows[row_number]
        except IndexError as exc:
            raise SourceIntegrityError(
                f"{task_id}: source row {row_number} is absent"
            ) from exc
        fields = {
            "question": row.get("question", ""),
            "query": row.get("query", ""),
            "instructions": row.get("instructions", ""),
        }
        for field, manifest_field in (
            ("question", "question_sha256"),
            ("query", "query_sha256"),
            ("instructions", "instructions_sha256"),
        ):
            if sha256_text(fields[field]) != descriptor[manifest_field]:
                raise SourceIntegrityError(
                    f"{task_id}: {field} does not match content-free manifest"
                )
        return RuntimeTask(
            task_id=task_id,
            database=descriptor["db_name"],
            query_category=descriptor["query_category"],
            question=fields["question"],
            instructions=fields["instructions"],
            gold_sql=fields["query"],
        )


@dataclass(frozen=True)
class SQLPolicy:
    catalog: Mapping[str, frozenset[str]]
    allowed_schemas: frozenset[str] = DEFAULT_ALLOWED_SCHEMAS
    allowed_functions: frozenset[str] = DEFAULT_ALLOWED_FUNCTIONS
    reject_sensitive_projections: bool = True
    allowed_sensitive_projections: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ValidatedSQL:
    statement: exp.Query
    order_sensitive: bool
    referenced_tables: tuple[str, ...]
    referenced_columns: tuple[str, ...]
    referenced_functions: tuple[str, ...]


def _function_name(function: exp.Func) -> str:
    sql_name = function.sql_name().lower()
    if sql_name == "anonymous":
        explicit = getattr(function, "name", "")
        return _normalized_identifier(str(explicit or sql_name))
    return _normalized_identifier(sql_name)


def _is_count_star(star: exp.Star) -> bool:
    parent = star.parent
    return isinstance(parent, exp.Count)


def _catalog_parts(
    catalog: Mapping[str, frozenset[str]],
) -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    tables: dict[str, frozenset[str]] = {}
    all_columns: set[str] = set()
    for table, columns in catalog.items():
        normalized = _normalized_identifier(table)
        tables[normalized] = frozenset(
            _normalized_identifier(column) for column in columns
        )
        all_columns.update(tables[normalized])
    return tables, frozenset(all_columns)


def validate_candidate_sql(sql: str, policy: SQLPolicy) -> ValidatedSQL:
    """Parse and validate exactly one read-only query.

    The validator intentionally fails closed on unknown functions, tables,
    columns, system schemas, wildcard projections, and sensitive projections.
    PostgreSQL's read-only transaction and constrained role remain the second
    and third enforcement layers.
    """

    if not isinstance(sql, str) or not sql.strip():
        raise SQLPolicyError("empty_sql", "candidate SQL is empty")
    try:
        statements = parse(sql, read="postgres")
    except ParseError as exc:
        raise SQLPolicyError("parse_error", str(exc)) from exc
    if len(statements) != 1:
        raise SQLPolicyError(
            "statement_count", "exactly one SQL statement is permitted"
        )
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SQLPolicyError("not_read_query", "only SELECT/CTE queries are permitted")
    if any(
        statement.args.get(name)
        for name in ("into", "locks")
    ):
        raise SQLPolicyError(
            "query_side_effect", "SELECT INTO and locking clauses are forbidden"
        )

    tables, all_columns = _catalog_parts(policy.catalog)
    cte_names = frozenset(
        _normalized_identifier(cte.alias_or_name)
        for cte in statement.find_all(exp.CTE)
    )
    derived_qualifiers = set(cte_names)
    derived_qualifiers.update(
        _normalized_identifier(subquery.alias_or_name)
        for subquery in statement.find_all(exp.Subquery)
        if subquery.alias_or_name
    )
    alias_to_table: dict[str, str] = {}
    referenced_tables: set[str] = set()
    for table in statement.find_all(exp.Table):
        name = _normalized_identifier(table.name)
        schema = _normalized_identifier(table.db) if table.db else ""
        if name in cte_names and not schema:
            derived_qualifiers.add(
                _normalized_identifier(table.alias_or_name)
            )
            continue
        if schema in SYSTEM_SCHEMAS or schema.startswith("pg_"):
            raise SQLPolicyError(
                "system_schema", f"schema {schema!r} is forbidden"
            )
        if schema and schema not in policy.allowed_schemas:
            raise SQLPolicyError(
                "schema_not_allowed", f"schema {schema!r} is not allowed"
            )
        candidate_keys = (
            (f"{schema}.{name}",) if schema else (f"public.{name}", name)
        )
        resolved = next((key for key in candidate_keys if key in tables), None)
        if resolved is None:
            suffix_matches = [
                key for key in tables if key.rsplit(".", 1)[-1] == name
            ]
            if len(suffix_matches) == 1 and not schema:
                resolved = suffix_matches[0]
        if resolved is None:
            raise SQLPolicyError(
                "table_not_allowed", f"table {table.sql()!r} is not allowed"
            )
        alias_to_table[_normalized_identifier(table.alias_or_name)] = resolved
        referenced_tables.add(resolved)

    for star in statement.find_all(exp.Star):
        if not _is_count_star(star):
            raise SQLPolicyError(
                "wildcard_projection", "wildcards are allowed only in COUNT(*)"
            )

    functions: set[str] = set()
    for function in statement.find_all(exp.Func):
        name = _function_name(function)
        if name in DANGEROUS_FUNCTIONS:
            raise SQLPolicyError(
                "dangerous_function", f"function {name!r} is forbidden"
            )
        if name not in policy.allowed_functions:
            raise SQLPolicyError(
                "function_not_allowed", f"function {name!r} is not allowed"
            )
        functions.add(name)

    derived_names = {
        _normalized_identifier(projection.alias)
        for select in statement.find_all(exp.Select)
        for projection in select.expressions
        if projection.alias
    }
    referenced_columns: set[str] = set()
    for column in statement.find_all(exp.Column):
        name = _normalized_identifier(column.name)
        qualifier = _normalized_identifier(column.table) if column.table else ""
        if name == "*":
            continue
        if qualifier in derived_qualifiers:
            referenced_columns.add(f"{qualifier}.{name}")
            continue
        if qualifier:
            resolved_table = alias_to_table.get(qualifier)
            if resolved_table is None:
                raise SQLPolicyError(
                    "column_qualifier_not_allowed",
                    f"column qualifier {qualifier!r} is not allowed",
                )
            if name not in tables[resolved_table]:
                raise SQLPolicyError(
                    "column_not_allowed",
                    f"column {qualifier}.{name} is not allowed",
                )
            referenced_columns.add(f"{resolved_table}.{name}")
        elif name not in all_columns and name not in derived_names:
            raise SQLPolicyError(
                "column_not_allowed", f"column {name!r} is not allowed"
            )
        else:
            referenced_columns.add(name)

    if policy.reject_sensitive_projections:
        for select in statement.find_all(exp.Select):
            for projection in select.expressions:
                output_name = _normalized_identifier(
                    projection.alias_or_name or ""
                )
                projected_columns = {
                    _normalized_identifier(column.name)
                    for column in projection.find_all(exp.Column)
                }
                if (
                    (
                        SENSITIVE_NAME_PATTERN.search(output_name)
                        and output_name
                        not in policy.allowed_sensitive_projections
                    )
                    or any(
                        SENSITIVE_NAME_PATTERN.search(column)
                        and column
                        not in policy.allowed_sensitive_projections
                        for column in projected_columns
                    )
                ):
                    raise SQLPolicyError(
                        "sensitive_projection",
                        "projecting sensitive columns is forbidden",
                    )

    return ValidatedSQL(
        statement=statement,
        order_sensitive=any(
            bool(select.args.get("order"))
            for select in statement.find_all(exp.Select)
        ),
        referenced_tables=tuple(sorted(referenced_tables)),
        referenced_columns=tuple(sorted(referenced_columns)),
        referenced_functions=tuple(sorted(functions)),
    )


def split_sql_statements(sql: str) -> tuple[str, ...]:
    """Split top-level statements without corrupting semicolons in literals.

    SQLGlot's AST serializer is deliberately not used for execution because
    cross-dialect normalization can change PostgreSQL constructs (for example,
    ``ROW(...)`` may be rendered as ``STRUCT(...)``).
    """

    tokens = Tokenizer(dialect="postgres").tokenize(sql)
    statements: list[str] = []
    start = 0
    for token in tokens:
        if token.token_type is TokenType.SEMICOLON:
            statement = sql[start : token.start].strip()
            if statement:
                statements.append(statement)
            start = token.end + 1
    remainder = sql[start:].strip()
    if remainder:
        statements.append(remainder)
    return tuple(statements)


def normalize_source_postgres_sql(sql: str) -> tuple[str, tuple[str, ...]]:
    """Apply narrowly-scoped, auditable repairs to mislabeled source SQL.

    Defog's PostgreSQL file contains one brace-struct expression. SQLGlot parses
    it as ``Struct`` but renders ``STRUCT(...)`` for PostgreSQL, which PostgreSQL
    does not implement. The intended native construct is ``ROW(...)``. No other
    AST normalization is performed.
    """

    if "{" not in sql or "}" not in sql:
        return sql, ()
    try:
        statements = parse(sql, read="postgres")
    except ParseError as exc:
        raise SourceIntegrityError(
            f"source SQL requiring dialect repair cannot be parsed: {exc}"
        ) from exc
    if len(statements) != 1:
        raise SourceIntegrityError(
            "dialect repair accepts exactly one source statement"
        )
    repairs = 0

    def replace(node: exp.Expression) -> exp.Expression:
        nonlocal repairs
        if isinstance(node, exp.Struct):
            repairs += 1
            return exp.Anonymous(
                this="ROW",
                expressions=[child.copy() for child in node.expressions],
            )
        return node

    repaired = statements[0].transform(replace, copy=True)
    if repairs == 0:
        raise SourceIntegrityError(
            "brace source SQL did not contain a parsed struct expression"
        )
    return repaired.sql(dialect="postgres"), ("brace_struct_to_postgres_row",)


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    elapsed_ms: float
    result_bytes: int


def _canonical_cell(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": format(value, "f")}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if math.isnan(value):
            rendered = "nan"
        elif math.isinf(value):
            rendered = "inf" if value > 0 else "-inf"
        else:
            rendered = value.hex()
        return {"type": "float", "value": rendered}
    if isinstance(value, (datetime, date, time)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    return {"type": type(value).__name__, "value": str(value)}


def result_content_hash(result: QueryResult) -> str:
    payload = {
        "columns": list(result.columns),
        "rows": [
            [_canonical_cell(value) for value in row]
            for row in result.rows
        ],
    }
    return sha256_bytes(canonical_json_bytes(payload))


def _numeric(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float) and math.isfinite(value):
        return Decimal(str(value))
    return None


def cells_equal(
    left: Any,
    right: Any,
    *,
    relative_tolerance: Decimal = Decimal("1e-9"),
    absolute_tolerance: Decimal = Decimal("1e-12"),
) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left == right
    left_numeric = _numeric(left)
    right_numeric = _numeric(right)
    if left_numeric is not None and right_numeric is not None:
        difference = abs(left_numeric - right_numeric)
        scale = max(abs(left_numeric), abs(right_numeric))
        return difference <= max(absolute_tolerance, relative_tolerance * scale)
    if isinstance(left, (datetime, date, time)) or isinstance(
        right, (datetime, date, time)
    ):
        return type(left) is type(right) and left == right
    return type(left) is type(right) and left == right


def rows_equal(left: Sequence[Any], right: Sequence[Any]) -> bool:
    return len(left) == len(right) and all(
        cells_equal(lvalue, rvalue)
        for lvalue, rvalue in zip(left, right)
    )


def results_equal(
    candidate: QueryResult,
    gold: QueryResult,
    *,
    order_sensitive: bool,
) -> bool:
    if len(candidate.columns) != len(gold.columns):
        return False
    if len(candidate.rows) != len(gold.rows):
        return False
    if order_sensitive:
        return all(
            rows_equal(candidate_row, gold_row)
            for candidate_row, gold_row in zip(candidate.rows, gold.rows)
        )
    unmatched = list(gold.rows)
    for candidate_row in candidate.rows:
        match = next(
            (
                index
                for index, gold_row in enumerate(unmatched)
                if rows_equal(candidate_row, gold_row)
            ),
            None,
        )
        if match is None:
            return False
        unmatched.pop(match)
    return not unmatched


@dataclass(frozen=True)
class ExecutionLimits:
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS
    idle_timeout_ms: int = DEFAULT_IDLE_TIMEOUT_MS
    max_rows: int = DEFAULT_MAX_ROWS
    max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES

    def validate(self) -> None:
        values = asdict(self)
        if any(not isinstance(value, int) or value <= 0 for value in values.values()):
            raise ValueError("all execution limits must be positive integers")


def _append_jsonl(path: Path | None, record: Mapping[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        )


class GovernedPostgresExecutor:
    def __init__(
        self,
        *,
        dsn: str,
        authority: GovernanceAuthority,
        limits: ExecutionLimits = ExecutionLimits(),
        audit_path: Path | None = None,
        allowed_schemas: frozenset[str] = DEFAULT_ALLOWED_SCHEMAS,
        allowed_sensitive_projections: frozenset[str] = frozenset(),
    ) -> None:
        authority.validate()
        limits.validate()
        self.dsn = dsn
        self.authority = authority
        self.limits = limits
        self.audit_path = audit_path
        self.allowed_schemas = allowed_schemas
        self.allowed_sensitive_projections = allowed_sensitive_projections

    def _connect(self) -> PGConnection:
        connection = psycopg2.connect(self.dsn)
        connection.autocommit = False
        return connection

    def _begin(self, connection: PGConnection) -> None:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN READ ONLY")
            cursor.execute("SET LOCAL row_security = on")
            cursor.execute(
                "SET LOCAL statement_timeout = %s",
                (f"{self.limits.statement_timeout_ms}ms",),
            )
            cursor.execute(
                "SET LOCAL lock_timeout = %s",
                (f"{self.limits.lock_timeout_ms}ms",),
            )
            cursor.execute(
                "SET LOCAL idle_in_transaction_session_timeout = %s",
                (f"{self.limits.idle_timeout_ms}ms",),
            )

    def catalog(self) -> dict[str, frozenset[str]]:
        connection = self._connect()
        try:
            self._begin(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_schema, table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = ANY(%s)
                    ORDER BY table_schema, table_name, ordinal_position
                    """,
                    (list(sorted(self.allowed_schemas)),),
                )
                catalog: dict[str, set[str]] = {}
                for schema, table, column in cursor.fetchall():
                    catalog.setdefault(
                        f"{_normalized_identifier(schema)}."
                        f"{_normalized_identifier(table)}",
                        set(),
                    ).add(_normalized_identifier(column))
            connection.rollback()
            frozen_catalog = {
                table: frozenset(columns)
                for table, columns in sorted(catalog.items())
            }
            _append_jsonl(
                self.audit_path,
                {
                    "event": "schema_inspection_result",
                    "schema_version": SCHEMA_VERSION,
                    "authority": self.authority.content_free_receipt(),
                    "catalog": {
                        table: sorted(columns)
                        for table, columns in frozen_catalog.items()
                    },
                    "catalog_sha256": sha256_bytes(
                        canonical_json_bytes(
                            {
                                table: sorted(columns)
                                for table, columns in frozen_catalog.items()
                            }
                        )
                    ),
                    "table_count": len(frozen_catalog),
                    "column_count": sum(
                        len(columns)
                        for columns in frozen_catalog.values()
                    ),
                },
            )
            return frozen_catalog
        finally:
            connection.close()

    def _execute_unchecked(self, sql: str) -> QueryResult:
        import time as time_module

        connection = self._connect()
        started = time_module.perf_counter()
        try:
            self._begin(connection)
            with connection.cursor() as cursor:
                cursor.execute(sql)
                if cursor.description is None:
                    raise SQLPolicyError(
                        "no_result_set", "query did not return a result set"
                    )
                columns = tuple(
                    descriptor.name for descriptor in cursor.description
                )
                rows = tuple(cursor.fetchmany(self.limits.max_rows + 1))
                if len(rows) > self.limits.max_rows:
                    raise ResultLimitError(
                        f"result exceeded {self.limits.max_rows} rows"
                    )
                result_bytes = len(
                    canonical_json_bytes(
                        [
                            [_canonical_cell(value) for value in row]
                            for row in rows
                        ]
                    )
                )
                if result_bytes > self.limits.max_result_bytes:
                    raise ResultLimitError(
                        "result exceeded configured byte limit"
                    )
            elapsed_ms = (time_module.perf_counter() - started) * 1_000
            connection.rollback()
            return QueryResult(
                columns=columns,
                rows=rows,
                elapsed_ms=elapsed_ms,
                result_bytes=result_bytes,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute_candidate(self, sql: str) -> tuple[ValidatedSQL, QueryResult]:
        policy = SQLPolicy(
            catalog=self.catalog(),
            allowed_schemas=self.allowed_schemas,
            allowed_sensitive_projections=self.allowed_sensitive_projections,
        )
        try:
            validated = validate_candidate_sql(sql, policy)
        except SQLPolicyError as exc:
            _append_jsonl(
                self.audit_path,
                {
                    "event": "candidate_sql_policy_denial",
                    "schema_version": SCHEMA_VERSION,
                    "authority": self.authority.content_free_receipt(),
                    "candidate_sql": sql,
                    "candidate_sql_sha256": sha256_text(sql),
                    "policy_error_code": exc.code,
                    "policy_error_sha256": sha256_text(str(exc)),
                },
            )
            raise
        try:
            result = self._execute_unchecked(sql)
        except Exception as exc:
            _append_jsonl(
                self.audit_path,
                {
                    "event": "candidate_sql_error",
                    "schema_version": SCHEMA_VERSION,
                    "authority": self.authority.content_free_receipt(),
                    "candidate_sql": sql,
                    "candidate_sql_sha256": sha256_text(sql),
                    "error_class": type(exc).__name__,
                    "error_sha256": sha256_text(str(exc)),
                },
            )
            raise
        _append_jsonl(
            self.audit_path,
            {
                "event": "candidate_sql_result",
                "schema_version": SCHEMA_VERSION,
                "authority": self.authority.content_free_receipt(),
                "candidate_sql": sql,
                "candidate_sql_sha256": sha256_text(sql),
                "referenced_tables": list(validated.referenced_tables),
                "referenced_columns": list(validated.referenced_columns),
                "referenced_functions": list(validated.referenced_functions),
                "result_sha256": result_content_hash(result),
                "row_count": len(result.rows),
                "column_count": len(result.columns),
                "elapsed_ms": result.elapsed_ms,
                "result_bytes": result.result_bytes,
            },
        )
        return validated, result

    def execute_gold_alternatives(
        self, gold_sql: str
    ) -> list[tuple[exp.Query, QueryResult]]:
        statement_sql = split_sql_statements(gold_sql)
        if not statement_sql:
            raise SourceIntegrityError("gold SQL is empty")
        parsed: list[exp.Query] = []
        executable_sql: list[str] = []
        for sql in statement_sql:
            normalized_sql, _ = normalize_source_postgres_sql(sql)
            try:
                statements = parse(normalized_sql, read="postgres")
            except ParseError as exc:
                raise SourceIntegrityError(
                    f"gold SQL cannot be parsed: {exc}"
                ) from exc
            if len(statements) != 1 or not isinstance(statements[0], exp.Query):
                raise SourceIntegrityError(
                    "gold SQL must contain only read-only queries"
                )
            parsed.append(statements[0])
            executable_sql.append(normalized_sql)
        return [
            (statement, self._execute_unchecked(sql))
            for statement, sql in zip(parsed, executable_sql)
        ]


@dataclass(frozen=True)
class EvaluationReceipt:
    schema_version: str
    task_id: str
    candidate_sql_sha256: str
    semantic_correct: bool
    security_authorized: bool
    matched_gold_alternative: int | None
    candidate_result_sha256: str | None
    row_count: int | None
    column_count: int | None
    order_sensitive: bool | None
    error_class: str | None
    policy_error_code: str | None
    authority: Mapping[str, Any]


def evaluate_candidate(
    *,
    task: RuntimeTask,
    candidate_sql: str,
    executor: GovernedPostgresExecutor,
) -> EvaluationReceipt:
    authority_receipt = executor.authority.content_free_receipt()
    try:
        candidate_validation, candidate_result = executor.execute_candidate(
            candidate_sql
        )
    except SQLPolicyError as exc:
        return EvaluationReceipt(
            schema_version=SCHEMA_VERSION,
            task_id=task.task_id,
            candidate_sql_sha256=sha256_text(candidate_sql),
            semantic_correct=False,
            security_authorized=False,
            matched_gold_alternative=None,
            candidate_result_sha256=None,
            row_count=None,
            column_count=None,
            order_sensitive=None,
            error_class=type(exc).__name__,
            policy_error_code=exc.code,
            authority=authority_receipt,
        )
    except Exception as exc:
        return EvaluationReceipt(
            schema_version=SCHEMA_VERSION,
            task_id=task.task_id,
            candidate_sql_sha256=sha256_text(candidate_sql),
            semantic_correct=False,
            security_authorized=True,
            matched_gold_alternative=None,
            candidate_result_sha256=None,
            row_count=None,
            column_count=None,
            order_sensitive=None,
            error_class=type(exc).__name__,
            policy_error_code=None,
            authority=authority_receipt,
        )

    gold_results = executor.execute_gold_alternatives(task.gold_sql)
    matched_index: int | None = None
    order_sensitive = candidate_validation.order_sensitive
    for index, (gold_statement, gold_result) in enumerate(gold_results):
        gold_order_sensitive = any(
            bool(select.args.get("order"))
            for select in gold_statement.find_all(exp.Select)
        )
        if results_equal(
            candidate_result,
            gold_result,
            order_sensitive=gold_order_sensitive,
        ):
            matched_index = index
            order_sensitive = gold_order_sensitive
            break
    return EvaluationReceipt(
        schema_version=SCHEMA_VERSION,
        task_id=task.task_id,
        candidate_sql_sha256=sha256_text(candidate_sql),
        semantic_correct=matched_index is not None,
        security_authorized=True,
        matched_gold_alternative=matched_index,
        candidate_result_sha256=result_content_hash(candidate_result),
        row_count=len(candidate_result.rows),
        column_count=len(candidate_result.columns),
        order_sensitive=order_sensitive,
        error_class=None,
        policy_error_code=None,
        authority=authority_receipt,
    )


def _receipt_json(receipt: EvaluationReceipt) -> str:
    return json.dumps(asdict(receipt), sort_keys=True, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--candidate-sql-file", type=Path, required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--audit-path", type=Path)
    parser.add_argument("--governance-scope", required=True)
    parser.add_argument("--authorization-epoch-ref", required=True)
    parser.add_argument("--user-id")
    parser.add_argument("--team-id")
    parser.add_argument("--virtual-key-id")
    args = parser.parse_args()

    resolver = PinnedTaskResolver(
        source_root=args.source_root,
        manifest_path=args.manifest,
        dataset_manifest_path=args.dataset_manifest,
    )
    task = resolver.resolve(args.task_id)
    candidate_sql = args.candidate_sql_file.read_text(encoding="utf-8")
    executor = GovernedPostgresExecutor(
        dsn=args.dsn,
        authority=GovernanceAuthority(
            governance_scope=args.governance_scope,
            authorization_epoch_ref=args.authorization_epoch_ref,
            user_id=args.user_id,
            team_id=args.team_id,
            virtual_key_id=args.virtual_key_id,
        ),
        audit_path=args.audit_path,
    )
    print(
        _receipt_json(
            evaluate_candidate(
                task=task,
                candidate_sql=candidate_sql,
                executor=executor,
            )
        )
    )


if __name__ == "__main__":
    main()
