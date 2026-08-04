from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from trace_mined_skill_candidate import mine


class TraceMinedSkillCandidateTest(unittest.TestCase):
    def test_mines_only_aggregate_signatures_and_seals_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "a.jsonl").write_text(
                "\n".join(
                    json.dumps(row)
                    for row in (
                        {"event": "factorial_task_start"},
                        {"event": "agent_tool_result", "name": "execute_sql", "content": json.dumps({"status": "policy_denied", "code": "column_not_allowed"})},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            result = mine(root)
            self.assertEqual(1, result["source_raw_file_count"])
            self.assertEqual(1, result["source_signature"]["files_without_describe_schema"])
            self.assertEqual(1, result["source_signature"]["files_with_policy_denial"])
            self.assertFalse(result["promotion_authorized"])
            self.assertNotIn("policy_denied", result["candidate_text"])
            self.assertEqual(64, len(result["candidate_text_sha256"]))


if __name__ == "__main__":
    unittest.main()
