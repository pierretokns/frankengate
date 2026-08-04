"""Source-neutral, fail-closed PostgreSQL read-query policy.

This module deliberately imports only the standard library and ``sqlglot``.
It contains no benchmark task, gold SQL, source resolver, database client,
evaluator, or candidate loader.  That import boundary is a security property:
the broker process must not gain access to evaluator-only material merely to
validate a query.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import FrozenSet, Mapping, Sequence

from sqlglot import exp, parse
from sqlglot.errors import ParseError


DEFAULT_ALLOWED_SCHEMAS = frozenset({"public", "main"})
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

# A read-looking root can contain a data-changing CTE.  Reject mutation and
# control nodes at any AST depth, before catalog/function analysis.
FORBIDDEN_AST_TYPES = (
    exp.Alter,
    exp.Analyze,
    exp.Attach,
    exp.Command,
    exp.Commit,
    exp.Copy,
    exp.Create,
    exp.Delete,
    exp.Detach,
    exp.Drop,
    exp.Execute,
    exp.Grant,
    exp.Insert,
    exp.Lock,
    exp.Merge,
    exp.Revoke,
    exp.Rollback,
    exp.Set,
    exp.Transaction,
    exp.TruncateTable,
    exp.Update,
    exp.Use,
)


class SQLPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SQLPolicy:
    catalog: Mapping[str, FrozenSet[str]]
    allowed_schemas: FrozenSet[str] = DEFAULT_ALLOWED_SCHEMAS
    allowed_functions: FrozenSet[str] = DEFAULT_ALLOWED_FUNCTIONS
    reject_sensitive_columns: bool = True
    allowed_sensitive_columns: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class ValidatedSQL:
    statement: exp.Query
    order_sensitive: bool
    referenced_tables: tuple[str, ...]
    referenced_columns: tuple[str, ...]
    referenced_functions: tuple[str, ...]


def _identifier(value: str) -> str:
    return value.strip('"').lower()


def _function_name(function: exp.Func) -> str:
    sql_name = function.sql_name().lower()
    if sql_name == "anonymous":
        explicit = getattr(function, "name", "")
        return _identifier(str(explicit or sql_name))
    return _identifier(sql_name)


def _is_count_star(star: exp.Star) -> bool:
    return isinstance(star.parent, exp.Count)


def _catalog_parts(
    catalog: Mapping[str, FrozenSet[str]],
) -> tuple[dict[str, FrozenSet[str]], FrozenSet[str]]:
    tables: dict[str, FrozenSet[str]] = {}
    all_columns: set[str] = set()
    for table, columns in catalog.items():
        normalized_table = _identifier(table)
        if normalized_table in tables:
            raise SQLPolicyError(
                "ambiguous_catalog", "catalog table names collide"
            )
        normalized_columns = frozenset(
            _identifier(column) for column in columns
        )
        tables[normalized_table] = normalized_columns
        all_columns.update(normalized_columns)
    return tables, frozenset(all_columns)


def _column_is_projected(column: exp.Column) -> bool:
    child: exp.Expression = column
    parent = child.parent
    while parent is not None:
        if isinstance(parent, exp.Select):
            return any(child is projection for projection in parent.expressions)
        child = parent
        parent = child.parent
    return False


def _sensitive_allowed(
    policy: SQLPolicy,
    *,
    column_name: str,
    resolved_reference: str,
) -> bool:
    entitlements = {
        _identifier(value) for value in policy.allowed_sensitive_columns
    }
    return (
        column_name in entitlements
        or _identifier(resolved_reference) in entitlements
    )


def _sensitive_join_allowed(
    policy: SQLPolicy,
    *,
    column_name: str,
    candidate_tables: Sequence[str],
) -> bool:
    entitlements = {
        _identifier(value) for value in policy.allowed_sensitive_columns
    }
    if column_name in entitlements:
        return True
    required = {
        f"{_identifier(table)}.{column_name}" for table in candidate_tables
    }
    return bool(required) and required.issubset(entitlements)


def validate_candidate_sql(sql: str, policy: SQLPolicy) -> ValidatedSQL:
    """Validate exactly one catalog-bound SELECT/CTE query."""

    if not isinstance(sql, str) or not sql.strip():
        raise SQLPolicyError("empty_sql", "candidate SQL is empty")
    try:
        statements = parse(sql, read="postgres")
    except ParseError as exc:
        raise SQLPolicyError("parse_error", "candidate SQL does not parse") from exc
    if len(statements) != 1:
        raise SQLPolicyError(
            "statement_count", "exactly one statement is permitted"
        )
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SQLPolicyError(
            "not_read_query", "only SELECT/CTE queries are permitted"
        )
    if any(
        isinstance(node, FORBIDDEN_AST_TYPES) for node in statement.walk()
    ):
        raise SQLPolicyError(
            "mutating_construct",
            "mutating, locking, control, and copy constructs are forbidden",
        )
    if statement.args.get("into") or statement.args.get("locks"):
        raise SQLPolicyError(
            "query_side_effect",
            "SELECT INTO and locking clauses are forbidden",
        )

    tables, all_columns = _catalog_parts(policy.catalog)
    cte_names = frozenset(
        _identifier(cte.alias_or_name)
        for cte in statement.find_all(exp.CTE)
    )
    derived_qualifiers = set(cte_names)
    derived_qualifiers.update(
        _identifier(subquery.alias_or_name)
        for subquery in statement.find_all(exp.Subquery)
        if subquery.alias_or_name
    )
    alias_to_table: dict[str, str] = {}
    alias_to_tables: dict[str, set[str]] = {}
    referenced_tables: set[str] = set()
    table_occurrences: list[str] = []
    for table in statement.find_all(exp.Table):
        name = _identifier(table.name)
        schema = _identifier(table.db) if table.db else ""
        if name in cte_names and not schema:
            derived_qualifiers.add(_identifier(table.alias_or_name))
            continue
        if schema in SYSTEM_SCHEMAS or schema.startswith("pg_"):
            raise SQLPolicyError(
                "system_schema", "system schemas are forbidden"
            )
        if schema and schema not in policy.allowed_schemas:
            raise SQLPolicyError(
                "schema_not_allowed", "schema is not authorized"
            )
        candidates = (
            (f"{schema}.{name}",)
            if schema
            else (f"public.{name}", f"main.{name}", name)
        )
        resolved = next(
            (candidate for candidate in candidates if candidate in tables),
            None,
        )
        if resolved is None and not schema:
            suffix_matches = [
                candidate
                for candidate in tables
                if candidate.rsplit(".", 1)[-1] == name
            ]
            if len(suffix_matches) == 1:
                resolved = suffix_matches[0]
        if resolved is None:
            raise SQLPolicyError(
                "table_not_allowed", "table is not in the authorized catalog"
            )
        alias = _identifier(table.alias_or_name)
        alias_to_table[alias] = resolved
        alias_to_tables.setdefault(alias, set()).add(resolved)
        referenced_tables.add(resolved)
        table_occurrences.append(resolved)

    implicit_join_columns: set[str] = set()
    if policy.reject_sensitive_columns:
        for join in statement.find_all(exp.Join):
            join_keys = {
                _identifier(identifier.name)
                for identifier in (join.args.get("using") or ())
            }
            if str(join.args.get("method") or "").upper() == "NATURAL":
                frequency: dict[str, int] = {}
                for table in table_occurrences:
                    for column in tables[table]:
                        frequency[column] = frequency.get(column, 0) + 1
                join_keys.update(
                    column
                    for column, count in frequency.items()
                    if count >= 2
                )
            for column in join_keys:
                if not SENSITIVE_NAME_PATTERN.search(column):
                    continue
                candidate_tables = tuple(
                    table
                    for table in sorted(referenced_tables)
                    if column in tables[table]
                )
                if not _sensitive_join_allowed(
                    policy,
                    column_name=column,
                    candidate_tables=candidate_tables,
                ):
                    raise SQLPolicyError(
                        "sensitive_column",
                        "sensitive join key is not authorized",
                    )
                implicit_join_columns.update(
                    f"{table}.{column}" for table in candidate_tables
                )

    for star in statement.find_all(exp.Star):
        if not _is_count_star(star):
            raise SQLPolicyError(
                "wildcard_projection",
                "wildcards are allowed only in COUNT(*)",
            )

    functions: set[str] = set()
    for function in statement.find_all(exp.Func):
        name = _function_name(function)
        if name in DANGEROUS_FUNCTIONS:
            raise SQLPolicyError(
                "dangerous_function", "dangerous function is forbidden"
            )
        if name not in policy.allowed_functions:
            raise SQLPolicyError(
                "function_not_allowed", "function is not allowlisted"
            )
        functions.add(name)

    derived_names = {
        _identifier(projection.alias)
        for select in statement.find_all(exp.Select)
        for projection in select.expressions
        if projection.alias
    }
    referenced_columns: set[str] = set(implicit_join_columns)
    for column in statement.find_all(exp.Column):
        name = _identifier(column.name)
        qualifier = _identifier(column.table) if column.table else ""
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
                    "column qualifier is not authorized",
                )
            if name not in tables[resolved_table]:
                raise SQLPolicyError(
                    "column_not_allowed", "column is not authorized"
                )
            candidates = alias_to_tables.get(qualifier, set())
            resolved_reference = (
                f"{next(iter(candidates))}.{name}"
                if len(candidates) == 1
                else name
            )
            referenced_columns.add(resolved_reference)
        elif name not in all_columns and name not in derived_names:
            raise SQLPolicyError(
                "column_not_allowed", "column is not authorized"
            )
        else:
            matching_tables = tuple(
                table
                for table in referenced_tables
                if name in tables[table]
            )
            resolved_reference = (
                f"{matching_tables[0]}.{name}"
                if len(matching_tables) == 1
                else name
            )
            referenced_columns.add(resolved_reference)
        if (
            policy.reject_sensitive_columns
            and SENSITIVE_NAME_PATTERN.search(name)
            and not _sensitive_allowed(
                policy,
                column_name=name,
                resolved_reference=resolved_reference,
            )
        ):
            code = (
                "sensitive_projection"
                if _column_is_projected(column)
                else "sensitive_column"
            )
            raise SQLPolicyError(code, "sensitive column is not authorized")

    if policy.reject_sensitive_columns:
        for select in statement.find_all(exp.Select):
            for projection in select.expressions:
                output_name = _identifier(projection.alias_or_name or "")
                if (
                    SENSITIVE_NAME_PATTERN.search(output_name)
                    and not _sensitive_allowed(
                        policy,
                        column_name=output_name,
                        resolved_reference=output_name,
                    )
                ):
                    raise SQLPolicyError(
                        "sensitive_projection",
                        "sensitive output name is not authorized",
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


__all__ = [
    "DEFAULT_ALLOWED_FUNCTIONS",
    "DEFAULT_ALLOWED_SCHEMAS",
    "SQLPolicy",
    "SQLPolicyError",
    "ValidatedSQL",
    "validate_candidate_sql",
]
