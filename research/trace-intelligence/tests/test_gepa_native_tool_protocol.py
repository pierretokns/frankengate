import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import gepa_native_tool_protocol as study  # noqa: E402
import native_tool_protocol_compliance as protocol  # noqa: E402


class GepaNativeToolProtocolTests(unittest.TestCase):
    def test_receipt_is_claim_bounded_and_pinned(self) -> None:
        path = ROOT / "experiments" / "results" / "gepa-native-tool-protocol-2026-08-02-r2.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], study.SCHEMA_VERSION)
        self.assertEqual(value["optimizer"]["tag"], "v0.1.4")
        self.assertEqual(value["optimizer"]["source_revision"], study.GEPA_REVISION)
        self.assertTrue(value["claim_boundary"]["holdout_split_used"])
        self.assertFalse(value["claim_boundary"]["enterprise_skill_benefit_confirmed"])
        self.assertFalse(value["claim_boundary"]["automatic_promotion_authorized"])
        self.assertEqual(value["selected"]["holdout"]["match_rate"], 2 / 3)

    def test_content_free_fixture_projection(self) -> None:
        fixture = protocol.Fixture("fixture", "success", "submit", 17, ())
        value = study._content_free_fixture(fixture)
        self.assertEqual(set(value), {"fixture_id_sha256", "executor_mode", "expected_terminal_action", "seed"})
        self.assertNotIn("prompt", value)
        self.assertNotIn("content", value)


if __name__ == "__main__":
    unittest.main()
