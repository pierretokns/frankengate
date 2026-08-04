import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wisp_adapter_conformance import run_conformance  # noqa: E402


class WispAdapterConformanceTest(unittest.TestCase):
    def test_aggregate_output_excludes_content_and_identifiers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "-home-me" / "session.jsonl"
            path.parent.mkdir()
            path.write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "SECRET-UUID",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "SECRET-CALL",
                                    "name": "FixtureTool",
                                    "input": {"secret": "SECRET-ARGUMENT"},
                                }
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = {
                "schema_version": "trace-dataset-manifest-v1",
                "dataset_id": "fixture",
                "dataset_revision": "revision",
                "license": "MIT",
            }

            result = run_conformance(root, manifest)
            serialized = json.dumps(result)
            self.assertNotIn("SECRET", serialized)
            self.assertEqual(1, result["counts"]["files"])
            self.assertEqual(0, result["counts"]["silently_dropped_records"])
            self.assertEqual(0, result["counts"]["silently_dropped_blocks"])


if __name__ == "__main__":
    unittest.main()
