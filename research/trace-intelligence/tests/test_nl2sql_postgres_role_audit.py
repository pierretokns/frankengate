from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "nl2sql_postgres_role_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "nl2sql_postgres_role_audit", MODULE_PATH
)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class FakeAdapter:
    def __init__(self, *, drift=None, unsafe=False, deny_writes=True):
        self.calls = []
        self.cleaned = False
        self.drift = drift
        self.unsafe = unsafe
        self.deny_writes = deny_writes
        self.database_snapshot = "a" * 64

    def setup(self, run_token, read_relations):
        self.calls.append(("setup", tuple(read_relations)))
        return {
            "postgres_major": 16,
            "candidate_role_safe": not self.unsafe,
            "evaluator_role_safe": not self.unsafe,
        }

    def audit_identity(self, lane, application_name):
        self.calls.append(("identity", lane, application_name))
        return {
            "current_user_matches": True,
            "application_name_matches": True,
        }

    def database_snapshot_sha256(self):
        self.calls.append(("database_snapshot",))
        return self.database_snapshot

    def assert_write_denied(self, lane):
        self.calls.append(("write_denial", lane))
        return self.deny_writes

    def execute(self, lane, sql, comparison):
        self.calls.append(("execute", lane, sql, comparison))
        digest = "same" if "one" in sql else "other"
        return {
            "ok": True,
            "row_count": 1,
            "result_sha256": digest,
            "raw_rows": [["sensitive-result"]],
        }

    def cleanup(self):
        self.cleaned = True
        self.calls.append(("cleanup",))


def write_fixture(root):
    path = root / "fixture.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nl2sql-role-audit-fixture-v1",
                "read_relations": ["fixture.orders"],
                "tasks": [
                    {
                        "task_id": "secret-task",
                        "candidate_sql": "select one",
                        "gold_sql": "select one",
                        "comparison": "ordered",
                    },
                    {
                        "task_id": "secret-task-two",
                        "candidate_sql": "select two",
                        "gold_sql": "select one",
                        "comparison": "unordered",
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


class NL2SQLPostgresRoleAuditTest(unittest.TestCase):
    def test_candidate_and_gold_are_executed_once_in_separate_lanes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            fixture = write_fixture(root)
            adapter = FakeAdapter()
            result = audit.run_experiment(
                adapter=adapter,
                fixture_path=fixture,
                expected_fixture_sha256=audit.sha256_path(fixture),
                raw_audit_path=root / "raw.jsonl",
            )

        executions = [call for call in adapter.calls if call[0] == "execute"]
        self.assertEqual(
            [
                ("execute", "candidate", "select one", "ordered"),
                ("execute", "evaluator", "select one", "ordered"),
                ("execute", "candidate", "select two", "unordered"),
                ("execute", "evaluator", "select one", "unordered"),
            ],
            executions,
        )
        self.assertTrue(adapter.cleaned)
        self.assertEqual("valid", result["infrastructure_status"])
        self.assertEqual(1, result["outcomes"]["exact_matches"])

    def test_snapshot_drift_is_infrastructure_invalid_and_still_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            fixture = write_fixture(root)

            class DriftingAdapter(FakeAdapter):
                def execute(self, lane, sql, comparison):
                    receipt = super().execute(lane, sql, comparison)
                    fixture.write_text("changed", encoding="utf-8")
                    return receipt

            adapter = DriftingAdapter()
            result = audit.run_experiment(
                adapter=adapter,
                fixture_path=fixture,
                expected_fixture_sha256=audit.sha256_path(fixture),
                raw_audit_path=root / "raw.jsonl",
            )

        self.assertTrue(adapter.cleaned)
        self.assertEqual(
            "infrastructure_invalid", result["infrastructure_status"]
        )
        self.assertIn("fixture_snapshot_drift", result["invalid_reasons"])

    def test_database_drift_between_candidate_and_gold_blocks_gold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            fixture = write_fixture(root)

            class DriftingDatabaseAdapter(FakeAdapter):
                def execute(self, lane, sql, comparison):
                    receipt = super().execute(lane, sql, comparison)
                    if lane == "candidate":
                        self.database_snapshot = "b" * 64
                    return receipt

            adapter = DriftingDatabaseAdapter()
            result = audit.run_experiment(
                adapter=adapter,
                fixture_path=fixture,
                expected_fixture_sha256=audit.sha256_path(fixture),
                raw_audit_path=root / "raw.jsonl",
            )

        executions = [call for call in adapter.calls if call[0] == "execute"]
        self.assertEqual(
            [("execute", "candidate", "select one", "ordered")],
            executions,
        )
        self.assertTrue(adapter.cleaned)
        self.assertEqual(
            "infrastructure_invalid", result["infrastructure_status"]
        )
        self.assertIn("database_snapshot_drift", result["invalid_reasons"])
        self.assertFalse(result["database_snapshot"]["snapshot_unchanged"])

    def test_unsafe_role_or_failed_write_denial_invalidates_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            fixture = write_fixture(root)
            adapter = FakeAdapter(unsafe=True, deny_writes=False)
            result = audit.run_experiment(
                adapter=adapter,
                fixture_path=fixture,
                expected_fixture_sha256=audit.sha256_path(fixture),
                raw_audit_path=root / "raw.jsonl",
            )
        self.assertEqual(
            "infrastructure_invalid", result["infrastructure_status"]
        )
        self.assertIn("unsafe_database_role", result["invalid_reasons"])
        self.assertIn("write_denial_failed", result["invalid_reasons"])

    def test_aggregate_omits_sql_results_ids_paths_and_role_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            fixture = write_fixture(root)
            adapter = FakeAdapter()
            result = audit.run_experiment(
                adapter=adapter,
                fixture_path=fixture,
                expected_fixture_sha256=audit.sha256_path(fixture),
                raw_audit_path=root / "raw.jsonl",
            )
            encoded = json.dumps(result, sort_keys=True)
            raw = (root / "raw.jsonl").read_text(encoding="utf-8")

        for secret in (
            "secret-task",
            "select one",
            "sensitive-result",
            str(fixture),
            "fg_candidate",
            "fixture.orders",
        ):
            self.assertNotIn(secret, encoded)
        self.assertIn("secret-task", raw)
        self.assertIn("select one", raw)

    def test_cleanup_runs_when_execution_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            fixture = write_fixture(root)

            class BrokenAdapter(FakeAdapter):
                def execute(self, lane, sql, comparison):
                    raise RuntimeError("database disappeared")

            adapter = BrokenAdapter()
            result = audit.run_experiment(
                adapter=adapter,
                fixture_path=fixture,
                expected_fixture_sha256=audit.sha256_path(fixture),
                raw_audit_path=root / "raw.jsonl",
            )

        self.assertTrue(adapter.cleaned)
        self.assertEqual(
            "infrastructure_invalid", result["infrastructure_status"]
        )
        self.assertIn("execution_infrastructure_error", result["invalid_reasons"])


if __name__ == "__main__":
    unittest.main()
