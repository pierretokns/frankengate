import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import prepare_fable5_memory_cohort as prepare  # noqa: E402


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = "".join(json.dumps(item) + "\n" for item in records).encode("utf-8")
    path.write_bytes(raw)
    return raw


class FableCohortPreparationTests(unittest.TestCase):
    def test_content_addresses_top_level_and_excludes_subagents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            top_raw = write_jsonl(
                root / "project-red" / "session-secret.jsonl",
                [{"type": "user", "sessionId": "do-not-emit"}],
            )
            write_jsonl(
                root
                / "project-red"
                / "session-secret"
                / "subagents"
                / "agent-secret.jsonl",
                [{"type": "assistant", "sessionId": "subagent-secret"}],
            )

            manifest, payloads = prepare.build_manifest(root)

            digest = hashlib.sha256(top_raw).hexdigest()
            receipts = manifest["cohort"]["source_files"]
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["path"], f"sha256/{digest}.jsonl")
            self.assertNotIn("session-secret", json.dumps(manifest))
            self.assertEqual(
                manifest["source_selection"][
                    "nested_or_subagent_files_excluded"
                ],
                1,
            )
            self.assertEqual(payloads[digest], top_raw)

    def test_manifest_verification_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write_jsonl(root / "project" / "session.jsonl", [{"x": 1}])
            generated, _ = prepare.build_manifest(root)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(generated), encoding="utf-8")
            write_jsonl(root / "project" / "session.jsonl", [{"x": 2}])
            changed, _ = prepare.build_manifest(root)

            with self.assertRaises(prepare.PreparationError):
                prepare.verify_manifest(changed, manifest_path)

    def test_invalid_top_level_json_blocks_entire_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "project" / "session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text('{"valid": true}\nnot-json\n', encoding="utf-8")

            with self.assertRaises(prepare.PreparationError):
                prepare.build_manifest(root)

    def test_materialized_files_verify_by_content_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = root / "source"
            output = root / "prepared"
            raw = write_jsonl(source / "project" / "session.jsonl", [{"x": 1}])
            manifest, payloads = prepare.build_manifest(source)

            prepare.materialize(
                manifest["cohort"]["source_files"], payloads, output
            )

            digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(
                (output / "sha256" / f"{digest}.jsonl").read_bytes(),
                raw,
            )


if __name__ == "__main__":
    unittest.main()
