import unittest

from codex_history_friction_mining import parse_session


class CodexHistoryMiningTest(unittest.TestCase):
    def test_exit_code_is_structured_and_prose_is_screening_only(self):
        rows = [
            {"type": "event_msg", "timestamp": "2026-01-01T00:00:00Z", "payload": {"type": "user_message", "message": "Please fix this"}},
            {"type": "response_item", "payload": {"type": "function_call", "name": "shell", "arguments": {"command": "true"}}},
            {"type": "response_item", "payload": {"type": "function_call_output", "exit_code": 0, "output": "error handling is documented"}},
            {"type": "response_item", "payload": {"type": "function_call_output", "exit_code": 1, "output": "command failed"}},
        ]
        result = parse_session("test", rows)
        self.assertEqual(result["structured_executor_error_count"], 1)
        self.assertEqual(result["keyword_error_marker_count"], 2)
        self.assertEqual(result["user_prompt_count"], 1)
        self.assertEqual(result["explicit_signal_counts"]["retry_or_repair"], 1)


if __name__ == "__main__":
    unittest.main()
