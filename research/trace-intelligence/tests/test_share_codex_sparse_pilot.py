import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "share_codex_sparse_pilot.py"
)
SPEC = importlib.util.spec_from_file_location(
    "share_codex_sparse_pilot", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ShareCodexSparsePilotTest(unittest.TestCase):
    def test_analyzer_emits_no_content_or_identifiers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = {
                "num_rows_total": 2,
                "partial": False,
                "rows": [
                    {
                        "row_idx": 0,
                        "row": {
                            "id": "SECRET SESSION",
                            "metadata": {
                                "cwd": "/SECRET/PROJECT",
                                "timestamp": "2026-01-01T00:00:00Z",
                                "source": "codex",
                                "source_entrypoint": "cli",
                            },
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "SECRET PROMPT",
                                    "metadata": {},
                                },
                                {
                                    "role": "assistant",
                                    "content": "SECRET REASONING",
                                    "metadata": {},
                                    "tool_calls": [
                                        {
                                            "id": "call-1",
                                            "type": "function",
                                            "function": {
                                                "name": "exec_command",
                                                "arguments": "SECRET COMMAND",
                                            },
                                        }
                                    ],
                                },
                                {
                                    "role": "tool",
                                    "tool_call_id": "call-1",
                                    "content": "SECRET ERROR",
                                    "metadata": {"is_error": True},
                                },
                                {
                                    "role": "assistant",
                                    "content": "SECRET RETRY",
                                    "metadata": {},
                                    "tool_calls": [
                                        {
                                            "id": "call-2",
                                            "type": "function",
                                            "function": {
                                                "name": "exec_command",
                                                "arguments": "SECRET RETRY COMMAND",
                                            },
                                        }
                                    ],
                                },
                                {
                                    "role": "tool",
                                    "tool_call_id": "call-2",
                                    "content": "SECRET SUCCESS",
                                    "metadata": {"is_error": False},
                                },
                            ],
                        },
                    },
                    {
                        "row_idx": 1,
                        "row": {
                            "id": "ANOTHER SECRET SESSION",
                            "metadata": {
                                "cwd": "/SECRET/PROJECT",
                                "timestamp": "2026-01-02T00:00:00Z",
                                "source": "codex",
                                "source_entrypoint": "cli",
                            },
                            "messages": [],
                        },
                    },
                ],
            }
            (root / "share-codex.rows-0.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            (root / "share-codex.rows-0.headers").write_text(
                "HTTP/2 200\r\nx-revision: revision-1\r\n",
                encoding="utf-8",
            )
            manifest = {
                "dataset_id": "test/share-codex",
                "dataset_revision": "revision-1",
                "license": "CC-BY-4.0",
                "population_rows": 2,
                "sample_design": {
                    "name": "test",
                    "requests": [{"offset": 0, "length": 2}],
                },
            }

            result = MODULE.analyze_sample(root, manifest)
            serialized = json.dumps(result)

            self.assertNotIn("SECRET", serialized)
            self.assertEqual(2, result["coverage"]["sessions"])
            self.assertEqual(1, result["coverage"]["unique_projects"])
            self.assertEqual(2, result["lifecycle"]["tool_proposals"])
            self.assertEqual(2, result["lifecycle"]["matched_tool_results"])
            self.assertEqual(1, result["lifecycle"]["explicit_error_results"])
            self.assertEqual(
                1,
                result["lifecycle"][
                    "error_results_with_later_same_tool_success"
                ],
            )

    def test_revision_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "share-codex.rows-0.json").write_text(
                json.dumps(
                    {
                        "num_rows_total": 1,
                        "partial": False,
                        "rows": [{"row_idx": 0, "row": {}}],
                    }
                ),
                encoding="utf-8",
            )
            (root / "share-codex.rows-0.headers").write_text(
                "x-revision: wrong\n", encoding="utf-8"
            )
            manifest = {
                "dataset_id": "test",
                "dataset_revision": "expected",
                "license": "test",
                "population_rows": 1,
                "sample_design": {
                    "name": "test",
                    "requests": [{"offset": 0, "length": 1}],
                },
            }
            with self.assertRaisesRegex(ValueError, "revision mismatch"):
                MODULE.analyze_sample(root, manifest)


if __name__ == "__main__":
    unittest.main()
