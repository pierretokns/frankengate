import unittest

from artifact_capsule_reuse import build_fixture, execute_reuse, run


class ArtifactCapsuleReuseTest(unittest.TestCase):
    def test_valid_reuse_and_fail_closed_authority(self):
        conn, capsule = build_fixture()
        valid = execute_reuse(
            capsule, conn, {"min_score": 10},
            authority_scope=capsule.authority_scope,
            authorization_epoch=capsule.authorization_epoch,
            now=1_700_000_000,
        )
        denied = execute_reuse(
            capsule, conn, {"min_score": 10},
            authority_scope="user:other/team:analytics",
            authorization_epoch=capsule.authorization_epoch,
            now=1_700_000_000,
        )
        self.assertTrue(valid["accepted"])
        self.assertFalse(denied["accepted"])
        self.assertIn("authority_scope_mismatch", denied["reasons"])

    def test_complete_lab_receipt(self):
        result = run()
        self.assertTrue(result["aggregate"]["valid_accepted"])
        self.assertTrue(result["aggregate"]["fail_closed"])
        self.assertFalse(result["aggregate"]["injection_interpreted_as_sql"])
        self.assertEqual(result["aggregate"]["denial_cases"], 5)


if __name__ == "__main__":
    unittest.main()
