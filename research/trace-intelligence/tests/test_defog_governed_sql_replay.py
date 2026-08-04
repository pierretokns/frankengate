import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest
from decimal import Decimal

try:
    from sqlglot import parse_one
except ModuleNotFoundError as exc:  # optional NL2SQL conformance dependency
    raise unittest.SkipTest("sqlglot is required for Defog SQL conformance") from exc


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "defog_governed_sql_replay.py"
)
SPEC = importlib.util.spec_from_file_location(
    "defog_governed_sql_replay", MODULE_PATH
)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = replay
SPEC.loader.exec_module(replay)

CONFORMANCE_PATH = (
    pathlib.Path(__file__).parents[1] / "defog_sql_replay_conformance.py"
)
CONFORMANCE_SPEC = importlib.util.spec_from_file_location(
    "defog_sql_replay_conformance", CONFORMANCE_PATH
)
conformance = importlib.util.module_from_spec(CONFORMANCE_SPEC)
assert CONFORMANCE_SPEC.loader is not None
sys.modules[CONFORMANCE_SPEC.name] = conformance
CONFORMANCE_SPEC.loader.exec_module(conformance)


CATALOG = {
    "public.orders": frozenset(
        {"id", "customer_id", "total", "created_at", "email"}
    ),
    "public.customers": frozenset({"id", "name", "email"}),
}


class SQLPolicyTest(unittest.TestCase):
    def test_allows_one_catalog_bound_read_query(self):
        validated = replay.validate_candidate_sql(
            """
            WITH totals AS (
                SELECT customer_id, SUM(total) AS spend
                FROM orders
                GROUP BY customer_id
            )
            SELECT customer_id, spend
            FROM totals
            ORDER BY spend DESC
            """,
            replay.SQLPolicy(catalog=CATALOG),
        )
        self.assertTrue(validated.order_sensitive)
        self.assertEqual(("public.orders",), validated.referenced_tables)
        self.assertIn("sum", validated.referenced_functions)

    def test_allows_count_star_but_rejects_projection_star(self):
        replay.validate_candidate_sql(
            "SELECT COUNT(*) AS n FROM orders",
            replay.SQLPolicy(catalog=CATALOG),
        )
        with self.assertRaisesRegex(
            replay.SQLPolicyError, "wildcards are allowed only"
        ):
            replay.validate_candidate_sql(
                "SELECT * FROM orders",
                replay.SQLPolicy(catalog=CATALOG),
            )

    def test_rejects_multiple_statements_and_mutations(self):
        for sql, expected_code in (
            ("SELECT id FROM orders; SELECT id FROM customers", "statement_count"),
            ("DELETE FROM orders", "not_read_query"),
            ("CREATE TABLE leaked(id int)", "not_read_query"),
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(replay.SQLPolicyError) as caught:
                    replay.validate_candidate_sql(
                        sql, replay.SQLPolicy(catalog=CATALOG)
                    )
                self.assertEqual(expected_code, caught.exception.code)

    def test_rejects_unknown_tables_columns_and_functions(self):
        cases = (
            ("SELECT id FROM secrets", "table_not_allowed"),
            ("SELECT password FROM customers", "column_not_allowed"),
            (
                "SELECT pg_read_file('/etc/passwd') FROM orders",
                "dangerous_function",
            ),
            ("SELECT mystery(total) FROM orders", "function_not_allowed"),
        )
        for sql, expected_code in cases:
            with self.subTest(sql=sql):
                with self.assertRaises(replay.SQLPolicyError) as caught:
                    replay.validate_candidate_sql(
                        sql, replay.SQLPolicy(catalog=CATALOG)
                    )
                self.assertEqual(expected_code, caught.exception.code)

    def test_rejects_sensitive_data_projection(self):
        for sql in (
            "SELECT email FROM customers",
            "SELECT email AS contact FROM customers",
            "SELECT name AS account_number FROM customers",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(replay.SQLPolicyError) as caught:
                    replay.validate_candidate_sql(
                        sql, replay.SQLPolicy(catalog=CATALOG)
                    )
                self.assertEqual(
                    "sensitive_projection", caught.exception.code
                )

    def test_allows_only_explicitly_entitled_sensitive_projection(self):
        replay.validate_candidate_sql(
            "SELECT email AS contact FROM customers",
            replay.SQLPolicy(
                catalog=CATALOG,
                allowed_sensitive_projections=frozenset({"email"}),
            ),
        )
        with self.assertRaises(replay.SQLPolicyError) as caught:
            replay.validate_candidate_sql(
                "SELECT email, name AS account_number FROM customers",
                replay.SQLPolicy(
                    catalog=CATALOG,
                    allowed_sensitive_projections=frozenset({"email"}),
                ),
            )
        self.assertEqual("sensitive_projection", caught.exception.code)

    def test_rejects_reproduced_sensitive_where_bypass(self):
        with self.assertRaises(replay.SQLPolicyError) as caught:
            replay.validate_candidate_sql(
                "SELECT COUNT(*) FROM customers "
                "WHERE email = 'target@example.com'",
                replay.SQLPolicy(catalog=CATALOG),
            )
        self.assertEqual("sensitive_column", caught.exception.code)

    def test_rejects_reproduced_sensitive_order_by_bypass(self):
        with self.assertRaises(replay.SQLPolicyError) as caught:
            replay.validate_candidate_sql(
                "SELECT name FROM customers ORDER BY email",
                replay.SQLPolicy(catalog=CATALOG),
            )
        self.assertEqual("sensitive_column", caught.exception.code)

    def test_rejects_reproduced_sensitive_having_bypass(self):
        with self.assertRaises(replay.SQLPolicyError) as caught:
            replay.validate_candidate_sql(
                "SELECT name FROM customers GROUP BY name "
                "HAVING MIN(email) IS NOT NULL",
                replay.SQLPolicy(catalog=CATALOG),
            )
        self.assertEqual("sensitive_column", caught.exception.code)

    def test_rejects_sensitive_join_condition(self):
        with self.assertRaises(replay.SQLPolicyError):
            replay.validate_candidate_sql(
                "SELECT c.name FROM customers AS c "
                "JOIN orders AS o ON c.email = o.email",
                replay.SQLPolicy(catalog=CATALOG),
            )

    def test_rejects_sensitive_using_and_natural_joins(self):
        for sql in (
            "SELECT c.name FROM customers AS c "
            "JOIN orders AS o USING (email)",
            "SELECT name FROM customers NATURAL JOIN orders",
            "SELECT c.name FROM customers AS c "
            "NATURAL JOIN customers AS other_customer",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(replay.SQLPolicyError) as caught:
                    replay.validate_candidate_sql(
                        sql, replay.SQLPolicy(catalog=CATALOG)
                    )
                self.assertEqual("sensitive_column", caught.exception.code)

    def test_rejects_sensitive_window_partition_and_order(self):
        for sql in (
            "SELECT name, ROW_NUMBER() OVER (PARTITION BY email) AS rn "
            "FROM customers",
            "SELECT name, ROW_NUMBER() OVER (ORDER BY email) AS rn "
            "FROM customers",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(replay.SQLPolicyError):
                    replay.validate_candidate_sql(
                        sql, replay.SQLPolicy(catalog=CATALOG)
                    )

    def test_rejects_sensitive_group_function_and_correlated_subquery_uses(self):
        for sql in (
            "SELECT COUNT(*) FROM customers GROUP BY email",
            "SELECT name FROM customers WHERE LOWER(email) = 'target@example.com'",
            "SELECT o.id FROM orders AS o WHERE EXISTS ("
            "SELECT 1 FROM customers AS c WHERE c.email = o.email"
            ")",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(replay.SQLPolicyError):
                    replay.validate_candidate_sql(
                        sql, replay.SQLPolicy(catalog=CATALOG)
                    )

    def test_table_qualified_entitlement_allows_non_projection_use(self):
        replay.validate_candidate_sql(
            "SELECT name FROM customers "
            "WHERE email = 'target@example.com'",
            replay.SQLPolicy(
                catalog=CATALOG,
                allowed_sensitive_columns=frozenset(
                    {"public.customers.email"}
                ),
            ),
        )

    def test_statement_split_preserves_postgres_text_and_literal_semicolons(self):
        statements = replay.split_sql_statements(
            "SELECT ROW(1, 'a;b'); SELECT 2;"
        )
        self.assertEqual(
            ("SELECT ROW(1, 'a;b')", "SELECT 2"),
            statements,
        )
        self.assertNotIn("STRUCT", statements[0])

    def test_repairs_only_brace_struct_to_postgres_row(self):
        repaired, repairs = replay.normalize_source_postgres_sql(
            "SELECT {orders.id, orders.total} FROM orders"
        )
        self.assertEqual(("brace_struct_to_postgres_row",), repairs)
        self.assertIn("ROW(", repaired)
        self.assertNotIn("STRUCT(", repaired)
        unchanged, no_repairs = replay.normalize_source_postgres_sql(
            "SELECT ROW(orders.id, orders.total) FROM orders"
        )
        self.assertEqual(
            "SELECT ROW(orders.id, orders.total) FROM orders",
            unchanged,
        )
        self.assertEqual((), no_repairs)


class AuthorityTest(unittest.TestCase):
    def test_governance_scope_requires_epoch_and_subject(self):
        with self.assertRaises(replay.AuthorizationError):
            replay.GovernanceAuthority(
                governance_scope="team",
                authorization_epoch_ref=None,
                user_id="u1",
            ).validate()
        with self.assertRaises(replay.AuthorizationError):
            replay.GovernanceAuthority(
                governance_scope="team",
                authorization_epoch_ref="epoch-1",
            ).validate()

    def test_receipt_hashes_authority_identifiers(self):
        authority = replay.GovernanceAuthority(
            governance_scope="team",
            authorization_epoch_ref="epoch-1",
            user_id="u1",
            team_id="t1",
            virtual_key_id="vk1",
        )
        receipt = authority.content_free_receipt()
        self.assertNotIn("epoch-1", receipt.values())
        self.assertNotIn("u1", receipt.values())
        self.assertEqual(64, len(receipt["authorization_epoch_ref_sha256"]))

    def test_executor_rejects_system_schema_in_governed_search_path(self):
        with self.assertRaises(ValueError):
            replay.GovernedPostgresExecutor(
                dsn="unused",
                authority=replay.GovernanceAuthority(
                    governance_scope="team",
                    authorization_epoch_ref="epoch-1",
                    team_id="t1",
                ),
                allowed_schemas=frozenset({"public", "pg_catalog"}),
            )

    def test_begin_pins_and_verifies_governed_session(self):
        class FakeCursor:
            def __init__(self):
                self.executions = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def execute(self, query, parameters=None):
                self.executions.append((query, parameters))

            def fetchone(self):
                return (
                    "on",
                    "on",
                    "pg_catalog, public, consumer_div",
                    "fg_replay",
                    "fg_replay",
                    False,
                    False,
                )

        class FakeConnection:
            def __init__(self):
                self.fake_cursor = FakeCursor()

            def cursor(self):
                return self.fake_cursor

        executor = replay.GovernedPostgresExecutor(
            dsn="unused",
            authority=replay.GovernanceAuthority(
                governance_scope="team",
                authorization_epoch_ref="epoch-1",
                team_id="t1",
            ),
        )
        connection = FakeConnection()
        executor._begin(connection)
        self.assertIn(
            (
                "SELECT pg_catalog.set_config('search_path', %s, true)",
                ("pg_catalog, public, consumer_div",),
            ),
            connection.fake_cursor.executions,
        )

    def test_begin_rejects_privileged_or_role_switched_session(self):
        safe_prefix = (
            "on",
            "on",
            "pg_catalog, public, consumer_div",
        )

        class FakeCursor:
            def __init__(self, state):
                self.state = state

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def execute(self, query, parameters=None):
                pass

            def fetchone(self):
                return self.state

        class FakeConnection:
            def __init__(self, state):
                self.state = state

            def cursor(self):
                return FakeCursor(self.state)

        executor = replay.GovernedPostgresExecutor(
            dsn="unused",
            authority=replay.GovernanceAuthority(
                governance_scope="team",
                authorization_epoch_ref="epoch-1",
                team_id="t1",
            ),
        )
        unsafe_states = (
            (
                "off",
                "on",
                "pg_catalog, public, consumer_div",
                "login_role",
                "login_role",
                False,
                False,
            ),
            (
                "on",
                "off",
                "pg_catalog, public, consumer_div",
                "login_role",
                "login_role",
                False,
                False,
            ),
            (
                "on",
                "on",
                "public",
                "login_role",
                "login_role",
                False,
                False,
            ),
            safe_prefix + ("elevated", "login_role", False, False),
            safe_prefix + ("login_role", "login_role", True, False),
            safe_prefix + ("login_role", "login_role", False, True),
        )
        for state in unsafe_states:
            with self.subTest(state=state):
                with self.assertRaises(replay.AuthorizationError):
                    executor._begin(FakeConnection(state))


def result(rows, columns=("value",)):
    return replay.QueryResult(
        columns=tuple(columns),
        rows=tuple(tuple(row) for row in rows),
        elapsed_ms=1.0,
        result_bytes=100,
    )


class ResultComparatorTest(unittest.TestCase):
    def test_benchmark_equivalence_preserves_label_agnostic_behavior(self):
        candidate = result(((1,),), ("answer",))
        gold = result(((1,),), ("expected_label",))
        self.assertTrue(
            replay.benchmark_results_equal(
                candidate, gold, order_sensitive=False
            )
        )
        self.assertTrue(
            replay.results_equal(
                candidate, gold, order_sensitive=False
            )
        )

    def test_strict_answer_shape_requires_matching_column_labels(self):
        candidate = result(((1,),), ("answer",))
        differently_labeled = result(((1,),), ("expected_label",))
        identically_labeled = result(((1,),), ("answer",))
        self.assertFalse(
            replay.strict_answer_shape_results_equal(
                candidate, differently_labeled, order_sensitive=False
            )
        )
        self.assertTrue(
            replay.strict_answer_shape_results_equal(
                candidate, identically_labeled, order_sensitive=False
            )
        )

    def test_ignores_row_order_only_when_not_semantic(self):
        first = result(((1,), (2,)))
        reversed_result = result(((2,), (1,)))
        self.assertTrue(
            replay.results_equal(
                first, reversed_result, order_sensitive=False
            )
        )
        self.assertFalse(
            replay.results_equal(
                first, reversed_result, order_sensitive=True
            )
        )

    def test_preserves_duplicates_and_column_count(self):
        duplicated = result(((1,), (1,)))
        distinct = result(((1,),))
        extra_column = result(((1, 9), (1, 9)), ("value", "extra"))
        self.assertFalse(
            replay.results_equal(
                duplicated, distinct, order_sensitive=False
            )
        )
        self.assertFalse(
            replay.results_equal(
                duplicated, extra_column, order_sensitive=False
            )
        )

    def test_numeric_tolerance_does_not_coerce_bools_or_strings(self):
        self.assertTrue(replay.cells_equal(Decimal("1.0000000001"), 1.0))
        self.assertFalse(replay.cells_equal(True, 1))
        self.assertFalse(replay.cells_equal("1", 1))

    def test_result_hash_keeps_types_and_duplicates(self):
        integer = result(((1,), (1,)))
        decimal = result(((Decimal("1"),), (Decimal("1"),)))
        distinct = result(((1,),))
        self.assertNotEqual(
            replay.result_content_hash(integer),
            replay.result_content_hash(decimal),
        )
        self.assertNotEqual(
            replay.result_content_hash(integer),
            replay.result_content_hash(distinct),
        )

    def test_wildcard_conformance_rewrite_names_every_output(self):
        rewritten = conformance.expand_outer_wildcard(
            parse_one("SELECT * FROM orders", read="postgres"),
            ("id", "total"),
        )
        sql = rewritten.sql(dialect="postgres")
        self.assertNotIn("*", sql)
        self.assertIn('"id"', sql)
        self.assertIn('"total"', sql)


@unittest.skipUnless(
    os.environ.get("FRANKENGATE_DEFOG_REPLAY_DSN"),
    "requires the disposable local governed PostgreSQL fixture",
)
class GovernedPostgresIntegrationTest(unittest.TestCase):
    def executor(self, audit_path=None):
        return replay.GovernedPostgresExecutor(
            dsn=os.environ["FRANKENGATE_DEFOG_REPLAY_DSN"],
            authority=replay.GovernanceAuthority(
                governance_scope="enterprise",
                authorization_epoch_ref="integration-epoch-1",
                user_id="integration-user",
                team_id="integration-team",
                virtual_key_id="integration-vk",
            ),
            audit_path=audit_path,
            limits=replay.ExecutionLimits(
                statement_timeout_ms=5_000,
                lock_timeout_ms=500,
                idle_timeout_ms=5_000,
                max_rows=10_000,
                max_result_bytes=1_000_000,
            ),
        )

    def test_constrained_role_executes_read_and_emits_raw_audit_externally(self):
        with tempfile.TemporaryDirectory() as temporary:
            audit_path = pathlib.Path(temporary) / "raw-audit.jsonl"
            executor = self.executor(audit_path)
            catalog = executor.catalog()
            self.assertTrue(catalog)
            table = sorted(catalog)[0]
            validated, query_result = executor.execute_candidate(
                f'SELECT COUNT(*) AS n FROM "{table.split(".", 1)[1]}"'
            )
            self.assertEqual((table,), validated.referenced_tables)
            self.assertEqual(1, len(query_result.rows))
            audit = audit_path.read_text(encoding="utf-8")
            self.assertIn("schema_inspection_result", audit)
            self.assertIn("candidate_sql_result", audit)
            self.assertIn("candidate_sql", audit)

    def test_policy_denial_is_audited_as_a_tool_outcome(self):
        with tempfile.TemporaryDirectory() as temporary:
            audit_path = pathlib.Path(temporary) / "raw-audit.jsonl"
            executor = self.executor(audit_path)
            with self.assertRaises(replay.SQLPolicyError):
                executor.execute_candidate(
                    "SELECT * FROM must_not_exist"
                )
            audit = audit_path.read_text(encoding="utf-8")
            self.assertIn("schema_inspection_result", audit)
            self.assertIn("candidate_sql_policy_denial", audit)
            self.assertIn("candidate_sql", audit)

    def test_read_role_cannot_mutate_even_below_parser_boundary(self):
        executor = self.executor()
        with self.assertRaises(Exception):
            executor._execute_unchecked(
                "CREATE TABLE must_not_exist(value integer)"
            )


if __name__ == "__main__":
    unittest.main()
