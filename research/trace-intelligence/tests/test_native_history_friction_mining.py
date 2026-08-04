import json
import tempfile
import unittest
from pathlib import Path

from native_history_friction_mining import parse_session


class NativeHistoryMiningTest(unittest.TestCase):
    def test_prose_error_is_not_structured_failure(self):
        record = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "is_error": False,
                        "content": [{"type": "text", "text": "The error handling code is documented."}],
                    }
                ],
            },
            "toolUseResult": {"stdout": "error handling is documented", "stderr": "", "interrupted": False},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            result = parse_session(path)
        self.assertEqual(result["tool_result_count"], 1)
        self.assertEqual(result["tool_result_structured_error_count"], 0)
        self.assertGreater(result["tool_result_keyword_error_marker_count"], 0)

    def test_explicit_error_stderr_and_interrupt_are_separate(self):
        record = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "is_error": True,
                        "content": [{"type": "text", "text": "command failed"}],
                    }
                ],
            },
            "toolUseResult": {"stdout": "", "stderr": "permission denied", "interrupted": True},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            result = parse_session(path)
        self.assertEqual(result["tool_result_structured_error_count"], 1)
        self.assertEqual(result["tool_result_stderr_count"], 1)
        self.assertEqual(result["tool_result_interrupted_count"], 1)


if __name__ == "__main__":
    unittest.main()
