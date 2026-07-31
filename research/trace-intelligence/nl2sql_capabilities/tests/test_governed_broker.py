from __future__ import annotations

from dataclasses import dataclass
import copy
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

try:
    import sqlglot  # noqa: F401
except ModuleNotFoundError as exc:  # optional NL2SQL parser dependency
    raise unittest.SkipTest("sqlglot is required for governed broker tests") from exc


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.attempt_store import (  # noqa: E402
    AttemptStore,
    query_result_content_sha256,
)
from nl2sql_capabilities.broker_protocol import (  # noqa: E402
    TOOL_REQUEST_SCHEMA_VERSION,
    ToolRequestDTO,
)
from nl2sql_capabilities.dto import (  # noqa: E402
    AuthorizedDatabaseHandleDTO,
    BROKER_PROTOCOL_VERSION,
    SolverLimitsDTO,
    generate_database_handle,
    generate_request_nonce,
)
from nl2sql_capabilities.governed_broker import (  # noqa: E402
    AuthorityCheck,
    AuthorityDecision,
    BrokerEpisodeBinding,
    DatabaseColumn,
    DatabaseResult,
    GovernedSQLBroker,
)


EPOCH_A = "a" * 64
SNAPSHOT_A = "b" * 64


class MutableAuthority:
    def __init__(self) -> None:
        self.epoch = EPOCH_A
        self.snapshot = SNAPSHOT_A
        self.allowed = True
        self.calls: list[AuthorityCheck] = []
        self.principal_id = "user-a"
        self.database_id = "database-a"
        self.expires_at_unix_ms = 2_000_000
        self.allowed_operations = frozenset(
            {
                "describe_schema",
                "execute_sql",
                "submit_sql",
                "abstain",
            }
        )

    def revalidate(self, check: AuthorityCheck) -> AuthorityDecision:
        self.calls.append(check)
        return AuthorityDecision(
            allowed=self.allowed,
            principal_id=self.principal_id,
            database_id=self.database_id,
            authorization_epoch_ref_sha256=self.epoch,
            authority_snapshot_sha256=self.snapshot,
            expires_at_unix_ms=self.expires_at_unix_ms,
            allowed_operations=self.allowed_operations,
        )


class SQLiteAdapter:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("PRAGMA query_only = OFF")
        self.connection.executescript(
            """
            CREATE TABLE accounts (
                account_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL
            );
            INSERT INTO accounts(account_id, status)
            VALUES (1, 'active'), (2, 'inactive'), (3, 'active');
            """
        )
        self.connection.execute("PRAGMA query_only = ON")
        self.describe_calls = 0
        self.execute_calls = 0
        self.database_ids: list[str] = []

    def describe_schema(self, database_id: str):
        self.describe_calls += 1
        self.database_ids.append(database_id)
        return {"accounts": ("account_id", "status")}

    def execute_read_only(
        self,
        database_id: str,
        sql: str,
        *,
        max_rows: int,
        max_bytes: int,
    ) -> DatabaseResult:
        self.execute_calls += 1
        self.database_ids.append(database_id)
        cursor = self.connection.execute(sql)
        rows = tuple(cursor.fetchmany(max_rows + 1))
        return DatabaseResult(
            columns=tuple(
                DatabaseColumn(
                    name=item[0],
                    pg_type_oid=0,
                    format="text",
                )
                for item in cursor.description or ()
            ),
            rows=rows,
        )


@dataclass
class Harness:
    broker: GovernedSQLBroker
    store: AttemptStore
    authority: MutableAuthority
    adapter: SQLiteAdapter
    handle: str
    temporary: tempfile.TemporaryDirectory[str]

    def close(self) -> None:
        self.store.close()
        self.adapter.connection.close()
        self.temporary.cleanup()


def make_limits(
    *,
    schema_calls: int = 2,
    sql_attempts: int = 3,
    model_turns: int = 16,
    result_rows: int = 100,
    result_bytes: int = 1024 * 1024,
) -> SolverLimitsDTO:
    return SolverLimitsDTO(
        max_model_turns=model_turns,
        max_schema_calls=schema_calls,
        max_sql_attempts=sql_attempts,
        max_generated_tokens_per_call=1024,
        max_generated_tokens_per_episode=16_384,
        model_wall_ms=60_000,
        model_result_max_rows=result_rows,
        model_result_max_bytes=result_bytes,
    )


def make_harness(
    *,
    preview_rows: int = 2,
    limits: SolverLimitsDTO | None = None,
) -> Harness:
    temporary = tempfile.TemporaryDirectory()
    store = AttemptStore(pathlib.Path(temporary.name) / "attempts")
    authority = MutableAuthority()
    adapter = SQLiteAdapter()
    handle = generate_database_handle()
    broker = GovernedSQLBroker(
        authority=authority,
        database=adapter,
        attempt_store=store,
        now_unix_ms=lambda: 1_000_000,
        preview_max_rows=preview_rows,
        preview_max_bytes=64 * 1024,
    )
    broker.open_episode(
        BrokerEpisodeBinding(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            database_id="database-a",
            authorized_database_handle=AuthorizedDatabaseHandleDTO(
                handle=handle,
                broker_protocol_version=BROKER_PROTOCOL_VERSION,
                authorization_epoch_ref_sha256=EPOCH_A,
                authority_snapshot_sha256=SNAPSHOT_A,
                expires_at_unix_ms=2_000_000,
            ),
            limits=limits or make_limits(),
            catalog={"accounts": ("account_id", "status")},
        )
    )
    return Harness(broker, store, authority, adapter, handle, temporary)


def request(
    harness: Harness,
    operation: str,
    *,
    nonce: str | None = None,
    sql: str | None = None,
    attempt_id: str | None = None,
    reason_code: str | None = None,
    handle: str | None = None,
) -> ToolRequestDTO:
    if operation == "describe_schema":
        arguments: dict[str, object] = {}
    elif operation == "execute_sql":
        arguments = {"sql": sql or "SELECT account_id FROM accounts ORDER BY account_id"}
    elif operation == "submit_sql":
        assert attempt_id is not None
        arguments = {"attempt_id": attempt_id}
    elif operation == "abstain":
        arguments = {"reason_code": reason_code or "insufficient_schema"}
    else:
        arguments = {}
    return ToolRequestDTO.from_dict(
        {
            "schema_version": TOOL_REQUEST_SCHEMA_VERSION,
            "request_nonce": nonce or generate_request_nonce(),
            "database_handle": handle or harness.handle,
            "operation": operation,
            "arguments": arguments,
        }
    )


class GovernedBrokerTest(unittest.TestCase):
    def test_execute_persists_full_typed_evidence_and_submit_never_reexecutes(
        self,
    ) -> None:
        harness = make_harness(preview_rows=2)
        self.addCleanup(harness.close)

        execute_request = request(harness, "execute_sql")
        execute = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=execute_request,
        ).to_dict()
        self.assertEqual("ok", execute["status"])
        self.assertEqual(2, len(execute["observation"]["rows"]))
        self.assertEqual(3, execute["observation"]["row_count"])
        self.assertTrue(execute["observation"]["preview_truncated"])

        evidence = harness.store.verify_attempt(
            episode_ref="episode_AAAAAAAA",
            attempt_id=execute["attempt_id"],
        )
        self.assertEqual(3, len(evidence["query_result"]["rows"]))
        self.assertEqual(
            {"kind": "int", "value": "1"},
            evidence["query_result"]["rows"][0][0],
        )
        self.assertEqual(
            evidence["query_result"]["result_content_sha256"],
            evidence["result_content_sha256"],
        )
        self.assertEqual(
            evidence["query_result"]["result_content_sha256"],
            execute["observation"]["result_sha256"],
        )
        calls_before_submit = harness.adapter.execute_calls

        submit = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "submit_sql",
                attempt_id=execute["attempt_id"],
            ),
        ).to_dict()
        self.assertEqual("accepted", submit["status"])
        self.assertTrue(submit["terminal"])
        self.assertEqual(calls_before_submit, harness.adapter.execute_calls)
        self.assertEqual(
            "database-a",
            harness.adapter.database_ids[0],
            "the adapter receives the internal database binding, not the handle",
        )

    def test_every_operation_revalidates_current_authority_before_replay_checks(
        self,
    ) -> None:
        harness = make_harness()
        self.addCleanup(harness.close)
        nonce = generate_request_nonce()
        original = request(
            harness,
            "execute_sql",
            nonce=nonce,
            sql="SELECT COUNT(*) AS n FROM accounts",
        )

        first = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=original,
        ).to_dict()
        self.assertEqual("ok", first["status"])
        self.assertEqual(1, len(harness.authority.calls))

        replay = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=original,
        ).to_dict()
        self.assertEqual("invalid_arguments", replay["status"])
        self.assertEqual("request_nonce_replayed", replay["code"])
        self.assertEqual(2, len(harness.authority.calls))
        self.assertEqual(1, harness.adapter.execute_calls)

        harness.authority.epoch = "c" * 64
        stale = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(harness, "describe_schema"),
        ).to_dict()
        self.assertEqual("authority_denied", stale["status"])
        self.assertEqual("current_authority_mismatch", stale["code"])
        self.assertEqual(3, len(harness.authority.calls))
        self.assertEqual(0, harness.adapter.describe_calls)

    def test_principal_handle_and_attempt_capabilities_cannot_cross_episodes(
        self,
    ) -> None:
        harness = make_harness()
        self.addCleanup(harness.close)
        executed = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "execute_sql",
                sql="SELECT COUNT(*) AS n FROM accounts",
            ),
        ).to_dict()
        self.assertEqual("ok", executed["status"])

        wrong_user = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-b",
            request=request(harness, "describe_schema"),
        ).to_dict()
        self.assertEqual("authority_denied", wrong_user["status"])

        handle_b = generate_database_handle()
        harness.broker.open_episode(
            BrokerEpisodeBinding(
                episode_ref="episode_BBBBBBBB",
                principal_id="user-b",
                database_id="database-b",
                authorized_database_handle=AuthorizedDatabaseHandleDTO(
                    handle=handle_b,
                    broker_protocol_version=BROKER_PROTOCOL_VERSION,
                    authorization_epoch_ref_sha256=EPOCH_A,
                    authority_snapshot_sha256=SNAPSHOT_A,
                    expires_at_unix_ms=2_000_000,
                ),
                limits=make_limits(),
                catalog={"accounts": ("account_id", "status")},
            )
        )
        harness.authority.principal_id = "user-b"
        harness.authority.database_id = "database-b"

        crossed_attempt = harness.broker.dispatch(
            episode_ref="episode_BBBBBBBB",
            principal_id="user-b",
            request=request(
                harness,
                "submit_sql",
                attempt_id=executed["attempt_id"],
                handle=handle_b,
            ),
        ).to_dict()
        self.assertEqual("invalid_arguments", crossed_attempt["status"])
        self.assertEqual(
            "attempt_capability_invalid", crossed_attempt["code"]
        )

        crossed_handle = harness.broker.dispatch(
            episode_ref="episode_BBBBBBBB",
            principal_id="user-b",
            request=request(
                harness,
                "describe_schema",
                handle=harness.handle,
            ),
        ).to_dict()
        self.assertEqual("authority_denied", crossed_handle["status"])
        self.assertEqual(1, harness.adapter.execute_calls)

    def test_revoked_expired_and_stale_authority_all_fail_before_database_access(
        self,
    ) -> None:
        mutations = (
            ("revoked", lambda authority: setattr(authority, "allowed", False)),
            (
                "expired",
                lambda authority: setattr(
                    authority, "expires_at_unix_ms", 999_999
                ),
            ),
            (
                "stale_epoch",
                lambda authority: setattr(authority, "epoch", "c" * 64),
            ),
            (
                "stale_snapshot",
                lambda authority: setattr(authority, "snapshot", "d" * 64),
            ),
            (
                "operation_revoked",
                lambda authority: setattr(
                    authority,
                    "allowed_operations",
                    frozenset({"describe_schema", "abstain"}),
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                harness = make_harness()
                try:
                    mutate(harness.authority)
                    response = harness.broker.dispatch(
                        episode_ref="episode_AAAAAAAA",
                        principal_id="user-a",
                        request=request(
                            harness,
                            "execute_sql",
                            sql="SELECT COUNT(*) AS n FROM accounts",
                        ),
                    ).to_dict()
                    self.assertEqual("authority_denied", response["status"])
                    self.assertEqual(0, harness.adapter.execute_calls)
                    self.assertEqual(1, len(harness.authority.calls))
                finally:
                    harness.close()

    def test_mutations_multistatements_and_unsafe_constructs_never_reach_adapter(
        self,
    ) -> None:
        harness = make_harness(
            limits=make_limits(sql_attempts=12, model_turns=16)
        )
        self.addCleanup(harness.close)
        unsafe = (
            "SELECT account_id FROM accounts; DELETE FROM accounts",
            (
                "WITH erased AS (DELETE FROM accounts RETURNING account_id) "
                "SELECT account_id FROM erased"
            ),
            "SELECT account_id INTO dumped FROM accounts",
            "SELECT account_id FROM accounts FOR UPDATE",
            "SELECT pg_read_file('/etc/passwd')",
            "SELECT account_id FROM pg_catalog.pg_user",
            "SELECT * FROM accounts",
            "DELETE FROM accounts RETURNING account_id",
        )
        for sql in unsafe:
            with self.subTest(sql=sql):
                response = harness.broker.dispatch(
                    episode_ref="episode_AAAAAAAA",
                    principal_id="user-a",
                    request=request(
                        harness,
                        "execute_sql",
                        sql=sql,
                    ),
                ).to_dict()
                self.assertEqual("policy_denied", response["status"])
        self.assertEqual(0, harness.adapter.execute_calls)

    def test_budgets_and_terminal_state_fail_closed(self) -> None:
        harness = make_harness(
            limits=make_limits(
                schema_calls=1,
                sql_attempts=1,
                model_turns=8,
            )
        )
        self.addCleanup(harness.close)
        first_schema = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(harness, "describe_schema"),
        ).to_dict()
        self.assertEqual("ok", first_schema["status"])
        exhausted_schema = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(harness, "describe_schema"),
        ).to_dict()
        self.assertEqual("resource_limit", exhausted_schema["status"])
        self.assertEqual(1, harness.adapter.describe_calls)

        executed = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "execute_sql",
                sql="SELECT COUNT(*) AS n FROM accounts",
            ),
        ).to_dict()
        self.assertEqual("ok", executed["status"])
        exhausted_sql = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "execute_sql",
                sql="SELECT COUNT(*) AS n FROM accounts",
            ),
        ).to_dict()
        self.assertEqual("resource_limit", exhausted_sql["status"])
        self.assertEqual(1, harness.adapter.execute_calls)

        submitted = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "submit_sql",
                attempt_id=executed["attempt_id"],
            ),
        ).to_dict()
        self.assertEqual("accepted", submitted["status"])
        authority_calls_before = len(harness.authority.calls)
        post_terminal = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(harness, "describe_schema"),
        ).to_dict()
        self.assertEqual("invalid_arguments", post_terminal["status"])
        self.assertEqual(
            authority_calls_before + 1,
            len(harness.authority.calls),
            "post-terminal calls still require current authority",
        )
        self.assertEqual(1, harness.adapter.describe_calls)

        one_turn = make_harness(
            limits=make_limits(model_turns=1)
        )
        try:
            self.assertEqual(
                "ok",
                one_turn.broker.dispatch(
                    episode_ref="episode_AAAAAAAA",
                    principal_id="user-a",
                    request=request(one_turn, "describe_schema"),
                ).status,
            )
            turn_exhausted = one_turn.broker.dispatch(
                episode_ref="episode_AAAAAAAA",
                principal_id="user-a",
                request=request(
                    one_turn,
                    "execute_sql",
                    sql="SELECT COUNT(*) AS n FROM accounts",
                ),
            ).to_dict()
            self.assertEqual("resource_limit", turn_exhausted["status"])
            self.assertEqual(0, one_turn.adapter.execute_calls)
        finally:
            one_turn.close()

    def test_abstention_is_terminal_and_submit_failures_execute_zero_sql(
        self,
    ) -> None:
        harness = make_harness()
        self.addCleanup(harness.close)
        # The request DTO enforces a 24-byte capability, so use a capability
        # produced by a distinct store episode rather than a fabricated shape.
        other_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(other_temporary.cleanup)
        other_store = AttemptStore(
            pathlib.Path(other_temporary.name) / "other-attempts"
        )
        self.addCleanup(other_store.close)
        other_store.create_episode("episode_CCCCCCCC")
        foreign_result = {
            "schema_version": "fg-query-result-v1",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "result_bytes": 24,
        }
        foreign_result["result_content_sha256"] = (
            query_result_content_sha256(foreign_result)
        )
        foreign = other_store.record_attempt(
            episode_ref="episode_CCCCCCCC",
            candidate_sql_sha256="e" * 64,
            status="executed",
            authority_valid=True,
            policy_accepted=True,
            query_result=foreign_result,
        )
        failed = harness.store.record_attempt(
            episode_ref="episode_AAAAAAAA",
            candidate_sql_sha256="f" * 64,
            status="denied",
            authority_valid=True,
            policy_accepted=False,
            error_code="policy_denied",
        )
        before = harness.adapter.execute_calls
        failed_submission = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "submit_sql",
                attempt_id=failed.attempt_id,
            ),
        ).to_dict()
        self.assertEqual("invalid_arguments", failed_submission["status"])
        self.assertEqual(before, harness.adapter.execute_calls)

        unknown_attempt = request(
            harness,
            "submit_sql",
            attempt_id=foreign.attempt_id,
        )
        rejected = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=unknown_attempt,
        ).to_dict()
        self.assertEqual("invalid_arguments", rejected["status"])
        self.assertEqual(before, harness.adapter.execute_calls)
        replayed_rejection = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=unknown_attempt,
        ).to_dict()
        self.assertEqual("invalid_arguments", replayed_rejection["status"])
        self.assertEqual(
            "request_nonce_replayed", replayed_rejection["code"]
        )
        self.assertEqual(before, harness.adapter.execute_calls)

        abstained = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(harness, "abstain"),
        ).to_dict()
        self.assertEqual("accepted", abstained["status"])
        self.assertTrue(abstained["terminal"])
        after_terminal = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "submit_sql",
                attempt_id=foreign.attempt_id,
            ),
        ).to_dict()
        self.assertEqual("invalid_arguments", after_terminal["status"])
        self.assertEqual(before, harness.adapter.execute_calls)

    def test_query_result_schema_is_closed_and_accepts_durable_evidence(
        self,
    ) -> None:
        harness = make_harness()
        self.addCleanup(harness.close)
        executed = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=request(
                harness,
                "execute_sql",
                sql="SELECT COUNT(*) AS n FROM accounts",
            ),
        ).to_dict()
        evidence = harness.store.verify_attempt(
            episode_ref="episode_AAAAAAAA",
            attempt_id=executed["attempt_id"],
        )["query_result"]
        schema_path = (
            pathlib.Path(__file__).parents[1]
            / "schemas"
            / "query_result.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertEqual([], list(validator.iter_errors(evidence)))
        leaked = copy.deepcopy(evidence)
        leaked["gold_sql"] = "SELECT secret"
        self.assertNotEqual([], list(validator.iter_errors(leaked)))

    def test_catalog_drift_and_full_result_limits_fail_closed(self) -> None:
        limited = make_harness(
            limits=make_limits(result_rows=1)
        )
        try:
            oversized = limited.broker.dispatch(
                episode_ref="episode_AAAAAAAA",
                principal_id="user-a",
                request=request(
                    limited,
                    "execute_sql",
                    sql="SELECT account_id FROM accounts ORDER BY account_id",
                ),
            ).to_dict()
            self.assertEqual("resource_limit", oversized["status"])
            self.assertEqual("database_result_limit", oversized["code"])
            self.assertEqual(1, limited.adapter.execute_calls)
        finally:
            limited.close()

        drifted = make_harness()
        try:
            drifted.adapter.describe_schema = lambda database_id: {
                "accounts": ("account_id", "status", "unsealed_column")
            }
            response = drifted.broker.dispatch(
                episode_ref="episode_AAAAAAAA",
                principal_id="user-a",
                request=request(drifted, "describe_schema"),
            ).to_dict()
            self.assertEqual("database_error", response["status"])
            self.assertEqual("database_catalog_drift", response["code"])
        finally:
            drifted.close()

    def test_broker_import_closure_contains_no_gold_source_or_evaluator_code(
        self,
    ) -> None:
        script = f"""
import inspect
import sys
sys.path.insert(0, {str(TRACE_INTELLIGENCE_ROOT)!r})
import nl2sql_capabilities.governed_broker as broker
import nl2sql_capabilities.sql_read_policy as policy
forbidden_modules = {{
    "defog_governed_sql_replay",
    "nl2sql_capabilities.evaluator",
    "psycopg2",
}}
loaded = forbidden_modules.intersection(sys.modules)
forbidden_attributes = {{
    "RuntimeTask",
    "gold_sql",
    "SourceResolver",
    "Evaluator",
}}
attributes = forbidden_attributes.intersection(
    set(vars(broker)) | set(vars(policy))
)
if loaded or attributes:
    raise SystemExit("forbidden import closure: " + repr((loaded, attributes)))
"""
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            0,
            completed.returncode,
            completed.stdout + completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
