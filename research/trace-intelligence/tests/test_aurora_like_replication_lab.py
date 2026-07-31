import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
RECEIPT = ROOT / "experiments/results/aurora-like-replication-lab-2026-08-02.json"


class AuroraLikeReplicationReceiptTests(unittest.TestCase):
    def test_receipt_keeps_local_and_managed_claims_separate(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        boundary = receipt["claim_boundary"]
        self.assertTrue(boundary["local_postgresql_mechanics_proven"])
        self.assertFalse(boundary["managed_aurora_behavior_proven"])
        self.assertTrue(receipt["replica_lag"]["marker_visible"])
        self.assertTrue(receipt["rls"]["cross_tenant_isolation_verified"])
        self.assertTrue(receipt["failover"]["post_promotion_write_verified"])


if __name__ == "__main__":
    unittest.main()
