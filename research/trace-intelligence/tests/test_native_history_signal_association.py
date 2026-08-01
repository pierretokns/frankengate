import unittest

from native_history_signal_association import analyze


class NativeHistorySignalAssociationTest(unittest.TestCase):
    def test_ties_are_ranked_and_claim_boundary_is_preserved(self):
        result = analyze(
            {
                "schema_version": "native-history-friction-result-v1",
                "sessions": [
                    {"tool_result_count": 2, "tool_result_structured_error_count": 0, "explicit_signal_counts": {"dissatisfaction": 0}},
                    {"tool_result_count": 2, "tool_result_structured_error_count": 1, "explicit_signal_counts": {"dissatisfaction": 1}},
                ],
            }
        )
        self.assertEqual(result["session_count"], 2)
        self.assertEqual(result["associations"]["dissatisfaction"]["sessions_with_signal_and_structured_error"], 1)
        self.assertIn("no gold friction", result["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
