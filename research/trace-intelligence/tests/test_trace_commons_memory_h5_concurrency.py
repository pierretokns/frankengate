from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SQL_PATH = (
    ROOT
    / "research"
    / "trace-intelligence"
    / "sql"
    / "008_trace_commons_memory_h5_concurrency.sql"
)
RUNNER_PATH = pathlib.Path(__file__).with_name(
    "run_trace_commons_memory_h5_concurrency.py"
)


def load_runner():
    spec = importlib.util.spec_from_file_location("h5c_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load H5C runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TraceCommonsMemoryH5ConcurrencyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL_PATH.read_text(encoding="utf-8")
        cls.runner = RUNNER_PATH.read_text(encoding="utf-8")

    def test_sql_is_on_error_stop_and_content_free(self) -> None:
        self.assertTrue(self.sql.startswith("\\set ON_ERROR_STOP on\n"))
        self.assertIn("raw_payload, content_sha256", self.sql)
        self.assertGreaterEqual(self.sql.count("'{}'"), 2)
        self.assertNotIn("/Users/", self.sql)
        self.assertNotIn("tool_name", self.sql)
        self.assertNotIn("content_text from trace_research.events", self.sql)

    def test_all_persisted_literal_fixture_ids_use_h5c_prefix(self) -> None:
        literals = set(re.findall(r"'(tc-[a-z0-9_-]+)'", self.sql))
        exceptions = {
            "tc-h5c deterministic withdrawal race",
            "tc-h5c concurrent exposure withdrawal",
        }
        fixture_literals = {
            value for value in literals
            if " " not in value and value not in exceptions
        }
        self.assertTrue(fixture_literals)
        self.assertTrue(
            all(value.startswith("tc-h5c-") for value in fixture_literals),
            sorted(value for value in fixture_literals if not value.startswith("tc-h5c-")),
        )

    def test_sql_has_failure_race_cleanup_and_zero_residue_modes(self) -> None:
        required_modes = {
            "setup",
            "failed_job",
            "assert_failed_job",
            "promote_a",
            "promote_b",
            "withdraw_a",
            "promote_c",
            "expose_c",
            "withdraw_c",
            "epoch_reader_rc",
            "epoch_reader_rr",
            "membership_reader_rc",
            "membership_reader_rr",
            "deletion_reader_rc",
            "deletion_reader_rr",
            "delete_provenance_source",
            "cleanup",
            "verify_zero",
        }
        declared = set(
            re.findall(r":'mode' = '([^']+)' as mode_[a-z0-9_]+", self.sql)
        )
        self.assertTrue(required_modes <= declared, required_modes - declared)
        self.assertIn("H5C_ZERO_RESIDUE_OK", self.sql)

    def test_runner_refuses_non_colima_context(self) -> None:
        self.assertIn('if context != "colima"', self.runner)
        self.assertIn("refusing to run H5C concurrency suite", self.runner)

    def test_runner_uses_explicit_observed_barriers(self) -> None:
        for lock_id in range(85001, 85010):
            self.assertIn(str(lock_id), self.sql)
            self.assertIn(str(lock_id), self.runner)
        self.assertIn("pg_stat_activity", self.runner)
        self.assertIn('wait_event="transactionid"', self.runner)
        self.assertIn('wait_event="advisory"', self.runner)

    def test_visibility_parser_requires_before_and_after(self) -> None:
        module = load_runner()
        result = module.CommandResult(
            mode="fixture",
            returncode=0,
            stdout="H5C_BEFORE|1\nH5C_AFTER|0\n",
            stderr="",
            elapsed_ms=1,
        )
        self.assertEqual(module.parse_visibility(result), (1, 0))

    def test_runner_always_cleans_and_verifies_zero(self) -> None:
        self.assertRegex(
            self.runner,
            r"finally:\s+cleanup = lab\.run_mode\(\"cleanup\"\)\s+"
            r"zero = lab\.run_mode\(\"verify_zero\"\)",
        )
        self.assertIn("H5C_ZERO_RESIDUE_OK", self.runner)


if __name__ == "__main__":
    unittest.main()
