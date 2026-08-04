from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = ROOT / "research" / "trace-intelligence"


class SkillImprovementAndAtomicLifecycleContractTest(unittest.TestCase):
    def test_skillopt_audit_is_machine_readable_and_claim_bounded(self) -> None:
        path = BASE / "experiments" / "results" / "skill-improvement-strategy-audit-2026-07-30.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "skill-improvement-strategy-audit-v1")
        self.assertEqual(data["local_runs"][0]["baseline_heldout"], 0.3333)
        self.assertTrue(data["local_runs"][0]["gate_blocked_harmful_edit"])
        self.assertEqual(data["existing_frankengate_evidence"]["natural_heldout_skill_intervention"], "not_completed")

    def test_atomic_procedures_lock_and_couple(self) -> None:
        sql = (BASE / "sql" / "009_skill_release_atomic_lifecycle.sql").read_text(encoding="utf-8")
        self.assertIn("for update", sql.lower())
        self.assertIn("update trace_research.release_exposures", sql)
        self.assertIn("insert into trace_research.release_events", sql)
        self.assertIn("status <> 'active'", sql)

    def test_race_fixture_is_content_free_and_has_cleanup(self) -> None:
        sql = (BASE / "sql" / "011_skill_release_atomic_lifecycle_race.sql").read_text(encoding="utf-8")
        self.assertIn("ATOMICC_RACE_CONTRACT_OK", sql)
        self.assertIn("ATOMICC_ZERO_RESIDUE_OK", sql)
        self.assertNotIn("tool_name", sql)
        self.assertNotIn("prompt", sql)
        self.assertNotIn("response", sql)

    def test_race_runner_uses_both_lock_boundaries(self) -> None:
        runner = (BASE / "tests" / "run_skill_release_atomic_lifecycle_race.py").read_text(encoding="utf-8")
        self.assertIn('wait_for("tc-atomicc-expose", "Lock", "advisory")', runner)
        self.assertIn('wait_for("tc-atomicc-withdraw", "Lock", "transactionid")', runner)
        self.assertIn('require(lab.mode("verify_zero"), "ATOMICC_ZERO_RESIDUE_OK")', runner)


if __name__ == "__main__":
    unittest.main()
