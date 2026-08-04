import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from postgres_loader import event_tool_fields, signal_vector, vector_literal


class PostgresLoaderTest(unittest.TestCase):
    def test_tool_proposal_is_preserved(self) -> None:
        event = {
            "kind": "tool_call_proposal",
            "event_id": "trace:1",
            "command": "search_dir authorization_epoch core",
        }
        self.assertEqual(
            event_tool_fields(event),
            ("trace:1", "search_dir"),
        )

    def test_non_tool_event_does_not_invent_call(self) -> None:
        self.assertEqual(
            event_tool_fields(
                {"kind": "agent_message", "event_id": "trace:2", "command": None}
            ),
            (None, None),
        )

    def test_signal_vector_is_fixed_width_and_normalized(self) -> None:
        signals = {
            "friction_score": 3.0,
            "tool_action_count": 4.0,
            "syntax_error_count": 0.0,
            "not_found_count": 0.0,
            "permission_error_count": 0.0,
            "test_failure_count": 0.0,
            "repeated_action_count": 0.0,
            "edit_rejection_count": 0.0,
        }
        result = signal_vector(signals)
        self.assertEqual(len(result), 8)
        self.assertAlmostEqual(sum(value * value for value in result), 1.0)
        self.assertEqual(vector_literal([1.0, 0.0]), "[1,0]")


if __name__ == "__main__":
    unittest.main()
