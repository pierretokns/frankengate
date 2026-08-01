import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from integration_promotion_audit import audit  # noqa: E402


class IntegrationPromotionAuditTests(unittest.TestCase):
    def test_no_mechanism_is_automatically_eligible(self):
        result = audit(ROOT / "experiments/results")
        self.assertEqual(
            "no_mechanism_eligible_for_automatic_integration", result["status"]
        )
        self.assertFalse(result["claim_boundary"]["automatic_integration_authorized"])
        self.assertEqual(12, len(result["rows"]))
        self.assertTrue(all(row["receipt_sha256"] for row in result["rows"]))


if __name__ == "__main__":
    unittest.main()
