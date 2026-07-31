import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import program_scope_audit as audit  # noqa: E402


class ProgramScopeAuditTests(unittest.TestCase):
    def test_audit_is_explicitly_incomplete(self):
        result = audit.build_audit()
        self.assertEqual(result["overall_status"], "active_incomplete")
        self.assertFalse(result["claim_boundary"]["completion_confirmed"])
        self.assertGreaterEqual(len(result["requirements"]), 6)

    def test_cmU_and_aurora_gates_are_not_silently_closed(self):
        result = audit.build_audit()
        by_id = {item["id"]: item for item in result["requirements"]}
        self.assertIn("CMU publisher approval", by_id["cmu_and_enterprise_outcomes"]["open_gate"])
        self.assertIn("Aurora", by_id["governed_local_stack"]["open_gate"])


if __name__ == "__main__":
    unittest.main()
