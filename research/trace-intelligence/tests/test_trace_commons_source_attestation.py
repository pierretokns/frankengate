from __future__ import annotations

import hashlib
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from trace_commons_source_attestation import attest


class TraceCommonsSourceAttestationTest(unittest.TestCase):
    def test_attests_inventory_hashes_and_records_without_emitting_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "sessions" / "claude_code" / "one.jsonl"
            source.parent.mkdir(parents=True)
            raw = b'{"type":"user"}\n{"type":"assistant"}\n'
            source.write_bytes(raw)
            manifest = {
                "dataset_id": "example/dataset",
                "dataset_revision": "rev",
                "license": "MIT",
                "source_files": [
                    {
                        "path": "sessions/claude_code/one.jsonl",
                        "bytes": len(raw),
                        "records": 2,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ],
            }
            result = attest(root, manifest)
            self.assertEqual("passed", result["attestation"])
            self.assertEqual(2, result["total_records"])
            self.assertFalse(result["raw_content_emitted"])
            self.assertNotIn("user", json_text := str(result))


if __name__ == "__main__":
    unittest.main()
