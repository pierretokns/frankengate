from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator

try:
    import sqlglot  # noqa: F401
except ModuleNotFoundError as exc:  # optional NL2SQL parser dependency
    raise unittest.SkipTest("sqlglot is required for evaluator tests") from exc


TRACE_INTELLIGENCE_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.dto import canonical_json_bytes
from nl2sql_capabilities.evaluator import (
    ComparatorConfig,
    EvaluationBindings,
    EvaluationError,
    aggregate_receipts,
    evaluate_stored_results,
    query_result_content_sha256,
)
from nl2sql_capabilities.tests import test_governed_broker as broker_fixture


H = "a" * 64


def result(rows, *, oid=20):
    columns = [{"name": "n", "pg_type_oid": oid, "format": "text"}]
    payload = {
        "schema_version": "fg-query-result-v1",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "result_bytes": len(canonical_json_bytes(rows)),
        "result_content_sha256": query_result_content_sha256(columns, rows),
    }
    return payload


def int_row(value):
    return [{"kind": "int", "value": str(value)}]


def multi_result(cells):
    columns = [
        {"name": f"c{index}", "pg_type_oid": 25, "format": "text"}
        for index in range(len(cells))
    ]
    rows = [cells]
    return {
        "schema_version": "fg-query-result-v1",
        "columns": columns,
        "rows": rows,
        "row_count": 1,
        "result_bytes": len(canonical_json_bytes(rows)),
        "result_content_sha256": query_result_content_sha256(columns, rows),
    }


class Verifier:
    def verify(self, *, purpose, envelope):
        if envelope.get("verified_for") != purpose:
            raise EvaluationError("signature verification failed")
        return copy.deepcopy(envelope["payload"])


class EvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.bindings = EvaluationBindings(
            stage_episode_ref="opaque_episode_123",
            submission_receipt_sha256=H,
            attempt_blob_sha256="b" * 64,
            model_manifest_sha256="c" * 64,
            prompt_contract_sha256="d" * 64,
            artifact_sha256="e" * 64,
            tool_contract_sha256="f" * 64,
            evaluator_build_sha256="1" * 64,
            broker_build_sha256="2" * 64,
            database_snapshot_sha256="3" * 64,
            policy_version_sha256="4" * 64,
            authority_snapshot_sha256="5" * 64,
            stage_manifest_sha256="6" * 64,
            raw_audit_chain_sha256="7" * 64,
        )
        self.comparator = ComparatorConfig(version_sha256="8" * 64)
        self.candidate = {
            "verified_for": "candidate_submission",
            "payload": {
                "schema_version": "fg-candidate-submission-v1",
                "stage_episode_ref": self.bindings.stage_episode_ref,
                "submission_receipt_sha256": H,
                "attempt_blob_sha256": "b" * 64,
                "candidate_execution_count": 1,
                "authority_valid": True,
                "policy_accepted": True,
                "authority_snapshot_sha256": "5" * 64,
                "database_snapshot_sha256": "3" * 64,
                "stage_manifest_sha256": "6" * 64,
                "query_result": result([int_row(2), int_row(1)]),
            },
        }
        self.gold = {
            "verified_for": "gold_result",
            "payload": {
                "schema_version": "fg-gold-result-evidence-v1",
                "stage_episode_ref": self.bindings.stage_episode_ref,
                "database_snapshot_sha256": "3" * 64,
                "stage_manifest_sha256": "6" * 64,
                "adjudication": {
                    "classification": "primary_quality_eligible",
                    "primary_quality_eligible": True,
                },
                "gold_execution_count": 1,
                "alternatives": [
                    {
                        "order_sensitive": False,
                        "query_result": result([int_row(1), int_row(2)]),
                    }
                ],
            },
        }

    def evaluate(self, **overrides):
        args = {
            "candidate_envelope": self.candidate,
            "gold_envelope": self.gold,
            "bindings": self.bindings,
            "comparator": self.comparator,
            "verifier": Verifier(),
            "candidate_execution_count": lambda _: 1,
            "authority_is_current": lambda _episode, _snapshot: True,
        }
        args.update(overrides)
        return evaluate_stored_results(**args)

    def test_unordered_full_results_match_and_validate_schema(self):
        receipt = self.evaluate()
        self.assertTrue(receipt.payload["semantic_correct"])
        self.assertEqual(receipt.payload["reason_code"], "correct")
        self.assertEqual(receipt.payload["matched_gold_alternative"], 0)
        schema_path = (
            Path(__file__).parents[1]
            / "schemas"
            / "evaluation_receipt.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt.to_dict())

    def test_gold_order_and_duplicate_rows_are_preserved(self):
        self.gold["payload"]["alternatives"][0]["order_sensitive"] = True
        receipt = self.evaluate()
        self.assertFalse(receipt.payload["semantic_correct"])
        self.assertEqual(receipt.payload["reason_code"], "result_mismatch")
        self.gold["payload"]["alternatives"][0]["query_result"] = result(
            [int_row(2), int_row(1)]
        )
        self.assertTrue(self.evaluate().payload["semantic_correct"])

        self.gold["payload"]["alternatives"][0]["order_sensitive"] = False
        self.candidate["payload"]["query_result"] = result(
            [int_row(1), int_row(1)]
        )
        self.gold["payload"]["alternatives"][0]["query_result"] = result(
            [int_row(1), int_row(2)]
        )
        self.assertFalse(self.evaluate().payload["semantic_correct"])

    def test_shape_tolerance_and_reason_codes(self):
        decimal_columns = [
            {"name": "n", "pg_type_oid": 1700, "format": "text"}
        ]
        left_rows = [[{"kind": "decimal", "value": "1.0000000001"}]]
        right_rows = [[{"kind": "decimal", "value": "1"}]]
        for envelope, rows in (
            (self.candidate, left_rows),
            (self.gold, right_rows),
        ):
            target = (
                envelope["payload"]["query_result"]
                if envelope is self.candidate
                else envelope["payload"]["alternatives"][0]["query_result"]
            )
            target.update(
                {
                    "columns": decimal_columns,
                    "rows": rows,
                    "row_count": 1,
                    "result_bytes": len(canonical_json_bytes(rows)),
                    "result_content_sha256": query_result_content_sha256(
                        decimal_columns, rows
                    ),
                }
            )
        self.assertTrue(self.evaluate().payload["semantic_correct"])

        self.gold["payload"]["alternatives"][0]["query_result"] = result(
            [int_row(1)], oid=23
        )
        receipt = self.evaluate()
        self.assertEqual(receipt.payload["reason_code"], "strict_shape_mismatch")

    def test_full_typed_result_round_trip_and_invalid_encodings(self):
        cells = [
            {"kind": "null", "value": None},
            {"kind": "bool", "value": True},
            {"kind": "int", "value": "-7"},
            {"kind": "decimal", "value": "123.45"},
            {"kind": "float", "value": "-0x0p+0"},
            {"kind": "float", "value": "inf"},
            {"kind": "text", "value": "snowman ☃"},
            {"kind": "date", "value": "2026-07-30"},
            {"kind": "time", "value": "12:34:56.123456"},
            {"kind": "timestamp", "value": "2026-07-30T12:34:56"},
            {
                "kind": "timestamptz",
                "value": "2026-07-30T12:34:56+00:00",
            },
            {"kind": "bytes", "value": "AAEC"},
            {
                "kind": "uuid",
                "value": "123e4567-e89b-12d3-a456-426614174000",
            },
            {"kind": "json", "value": '{"a":[1,true,null]}'},
            {
                "kind": "array",
                "value": [
                    {"kind": "int", "value": "1"},
                    {"kind": "text", "value": "x"},
                ],
            },
        ]
        typed = multi_result(cells)
        self.candidate["payload"]["query_result"] = typed
        self.gold["payload"]["alternatives"][0]["query_result"] = copy.deepcopy(
            typed
        )
        self.assertTrue(self.evaluate().payload["semantic_correct"])

        for index, bad_cell in enumerate(
            (
                {"kind": "decimal", "value": "1.0"},
                {"kind": "float", "value": "1e3"},
                {"kind": "bytes", "value": "%%%"},
                {"kind": "uuid", "value": "NOT-A-UUID"},
                {"kind": "json", "value": '{"b":1,"a":2}'},
                {
                    "kind": "timestamptz",
                    "value": "2026-07-30T12:34:56",
                },
                {"kind": "unsupported", "value": "x"},
            )
        ):
            bad = copy.deepcopy(self.candidate)
            bad["payload"]["query_result"] = multi_result([bad_cell])
            with self.subTest(index=index), self.assertRaises(EvaluationError):
                self.evaluate(candidate_envelope=bad)

    def test_tamper_cross_binding_and_noncanonical_result_fail_closed(self):
        cases = []
        bad = copy.deepcopy(self.candidate)
        bad["verified_for"] = "wrong"
        cases.append(("candidate_envelope", bad))
        bad = copy.deepcopy(self.candidate)
        bad["payload"]["stage_episode_ref"] = "another_episode_456"
        cases.append(("candidate_envelope", bad))
        bad = copy.deepcopy(self.gold)
        bad["payload"]["database_snapshot_sha256"] = "9" * 64
        cases.append(("gold_envelope", bad))
        bad = copy.deepcopy(self.candidate)
        bad["payload"]["query_result"]["result_content_sha256"] = "0" * 64
        cases.append(("candidate_envelope", bad))
        bad = copy.deepcopy(self.candidate)
        bad["payload"]["unexpected"] = True
        cases.append(("candidate_envelope", bad))
        bad = copy.deepcopy(self.gold)
        bad["payload"]["gold_execution_count"] = 2
        tampered_alternative = copy.deepcopy(
            bad["payload"]["alternatives"][0]
        )
        tampered_alternative["query_result"]["result_content_sha256"] = "0" * 64
        bad["payload"]["alternatives"].append(tampered_alternative)
        cases.append(("gold_envelope", bad))
        for field, value in cases:
            with self.subTest(field=field), self.assertRaises(EvaluationError):
                self.evaluate(**{field: value})

    def test_authority_and_execution_counter_are_release_gates(self):
        receipt = self.evaluate(
            authority_is_current=lambda _episode, _snapshot: False
        )
        self.assertFalse(receipt.payload["semantic_correct"])
        self.assertEqual(receipt.payload["reason_code"], "authority_not_current")

        self.candidate["payload"]["policy_accepted"] = False
        receipt = self.evaluate()
        self.assertFalse(receipt.payload["semantic_correct"])
        self.assertEqual(receipt.payload["reason_code"], "security_not_authorized")
        self.candidate["payload"]["policy_accepted"] = True

        values = iter([1, 2])
        receipt = self.evaluate(
            candidate_execution_count=lambda _: next(values)
        )
        self.assertFalse(receipt.payload["semantic_correct"])
        self.assertEqual(
            receipt.payload["reason_code"],
            "candidate_execution_count_invalid",
        )

    def test_evaluator_has_no_sql_or_database_execution_surface(self):
        import nl2sql_capabilities.evaluator as module

        source = inspect.getsource(module)
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(
            imports
            & {
                "sqlite3",
                "psycopg",
                "psycopg2",
                "sqlalchemy",
                "subprocess",
                "socket",
            }
        )
        signature = inspect.signature(evaluate_stored_results)
        self.assertNotIn("sql", " ".join(signature.parameters))
        self.assertNotIn("executor", " ".join(signature.parameters))
        self.assertNotIn("candidate_sql", source)

    def test_broker_preview_is_ignored_and_candidate_is_not_reexecuted(self):
        harness = broker_fixture.make_harness(preview_rows=0)
        self.addCleanup(harness.close)
        execute = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=broker_fixture.request(
                harness,
                "execute_sql",
                sql=(
                    "SELECT account_id FROM accounts "
                    "ORDER BY account_id"
                ),
            ),
        ).to_dict()
        self.assertEqual([], execute["observation"]["rows"])
        self.assertTrue(execute["observation"]["preview_truncated"])
        submit = harness.broker.dispatch(
            episode_ref="episode_AAAAAAAA",
            principal_id="user-a",
            request=broker_fixture.request(
                harness,
                "submit_sql",
                attempt_id=execute["attempt_id"],
            ),
        ).to_dict()
        terminal = harness.store.submission_receipt(
            episode_ref="episode_AAAAAAAA"
        )
        attempt = harness.store.verify_attempt(
            episode_ref="episode_AAAAAAAA",
            attempt_id=execute["attempt_id"],
        )
        bindings = EvaluationBindings(
            stage_episode_ref="episode_AAAAAAAA",
            submission_receipt_sha256=submit[
                "submission_receipt_sha256"
            ],
            attempt_blob_sha256=terminal.selected_attempt_blob_sha256,
            model_manifest_sha256="c" * 64,
            prompt_contract_sha256="d" * 64,
            artifact_sha256="e" * 64,
            tool_contract_sha256="f" * 64,
            evaluator_build_sha256="1" * 64,
            broker_build_sha256="2" * 64,
            database_snapshot_sha256="3" * 64,
            policy_version_sha256="4" * 64,
            authority_snapshot_sha256=broker_fixture.SNAPSHOT_A,
            stage_manifest_sha256="6" * 64,
            raw_audit_chain_sha256="7" * 64,
        )
        candidate = {
            "verified_for": "candidate_submission",
            "payload": {
                "schema_version": "fg-candidate-submission-v1",
                "stage_episode_ref": "episode_AAAAAAAA",
                "submission_receipt_sha256": submit[
                    "submission_receipt_sha256"
                ],
                "attempt_blob_sha256": (
                    terminal.selected_attempt_blob_sha256
                ),
                "candidate_execution_count": 1,
                "authority_valid": attempt["authority_valid"],
                "policy_accepted": attempt["policy_accepted"],
                "authority_snapshot_sha256": broker_fixture.SNAPSHOT_A,
                "database_snapshot_sha256": "3" * 64,
                "stage_manifest_sha256": "6" * 64,
                "query_result": attempt["query_result"],
            },
        }
        gold = {
            "verified_for": "gold_result",
            "payload": {
                "schema_version": "fg-gold-result-evidence-v1",
                "stage_episode_ref": "episode_AAAAAAAA",
                "database_snapshot_sha256": "3" * 64,
                "stage_manifest_sha256": "6" * 64,
                "adjudication": {
                    "classification": "primary_quality_eligible",
                    "primary_quality_eligible": True,
                },
                "gold_execution_count": 1,
                "alternatives": [
                    {
                        "order_sensitive": True,
                        "query_result": copy.deepcopy(
                            attempt["query_result"]
                        ),
                    }
                ],
            },
        }
        receipt = evaluate_stored_results(
            candidate_envelope=candidate,
            gold_envelope=gold,
            bindings=bindings,
            comparator=self.comparator,
            verifier=Verifier(),
            candidate_execution_count=(
                lambda _episode: harness.adapter.execute_calls
            ),
            authority_is_current=(
                lambda _episode, snapshot: (
                    harness.authority.allowed
                    and harness.authority.epoch == broker_fixture.EPOCH_A
                    and snapshot == harness.authority.snapshot
                )
            ),
        )
        self.assertTrue(receipt.payload["semantic_correct"])
        self.assertEqual(1, harness.adapter.execute_calls)
        self.assertEqual(
            attempt["query_result"]["result_content_sha256"],
            receipt.payload["candidate_result_sha256"],
        )

    def test_aggregate_contains_only_counts_and_hashes(self):
        receipt = self.evaluate()
        aggregate = aggregate_receipts([receipt])
        self.assertEqual(aggregate["episode_count"], 1)
        self.assertEqual(aggregate["semantic_correct_count"], 1)
        serialized = canonical_json_bytes(aggregate)
        self.assertNotIn(b"rows", serialized)
        self.assertNotIn(b"question", serialized)
        self.assertNotIn(b"sql", serialized.lower())
        self.assertEqual(
            aggregate["ordered_receipt_sha256"],
            [hashlib.sha256(canonical_json_bytes(receipt.payload)).hexdigest()],
        )


if __name__ == "__main__":
    unittest.main()
