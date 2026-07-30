import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "aggregate_sensitive_token_scan.py"
)
SPEC = importlib.util.spec_from_file_location(
    "aggregate_sensitive_token_scan",
    MODULE_PATH,
)
scan = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = scan
SPEC.loader.exec_module(scan)


def write_cohort(root, records):
    source = root / "sessions" / "cohort.jsonl"
    source.parent.mkdir(parents=True)
    raw = "".join(
        json.dumps(record, sort_keys=True) + "\n"
        for record in records
    ).encode("utf-8")
    source.write_bytes(raw)
    manifest = {
        "schema_version": "trace-dataset-manifest-v1",
        "dataset_id": "fixture/private",
        "dataset_revision": "fixture-v1",
        "download_policy": {"raw_data_committed": False},
        "cohort": {
            "source_files": [
                {
                    "path": "sessions/cohort.jsonl",
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "records": len(records),
                }
            ]
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, source


class AggregateSensitiveTokenScanTest(unittest.TestCase):
    def test_fixed_classes_are_counted_without_emitting_values(self):
        bearer = "Bearer " + "z" * 24
        openai = "sk-proj-" + "a" * 24
        huggingface = "hf_" + "b" * 24
        github = "ghp_" + "c" * 24
        aws = "AKIA" + "D" * 16
        jwt = (
            "eyJ" + "e" * 8
            + ".eyJ" + "f" * 8
            + "." + "g" * 12
        )
        private_key = "-----BEGIN PRIVATE KEY-----"
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest, _ = write_cohort(
                root,
                [
                    {
                        "nested": [
                            "<REDACTED>",
                            "<API_KEY_1>",
                            "[PRIVATE_DOMAIN_ABC]",
                            bearer,
                            openai,
                            huggingface,
                            github,
                            aws,
                            jwt,
                            private_key,
                        ]
                    }
                ],
            )
            result = scan.scan_manifest(manifest, root)

        aggregate = result["aggregate_scan"]
        self.assertEqual(10, aggregate["strings_scanned"])
        self.assertEqual(3, aggregate["redaction_evidence_total"])
        self.assertEqual(
            7,
            aggregate["possible_secret_regex_candidate_total"],
        )
        serialized = json.dumps(result)
        for value in (
            bearer,
            openai,
            huggingface,
            github,
            aws,
            jwt,
            private_key,
        ):
            self.assertNotIn(value, serialized)
        self.assertFalse(result["candidate_values_emitted"])

    def test_result_and_receipts_are_deterministic_and_path_free(self):
        private_name = "private-customer-history.jsonl"
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest, source = write_cohort(root, [{"safe": "value"}])
            renamed = source.with_name(private_name)
            source.rename(renamed)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["cohort"]["source_files"][0]["path"] = (
                "sessions/" + private_name
            )
            manifest.write_text(json.dumps(value), encoding="utf-8")

            first = scan.scan_manifest(manifest, root)
            second = scan.scan_manifest(manifest, root)

        self.assertEqual(first, second)
        serialized = json.dumps(first)
        self.assertNotIn(private_name, serialized)
        receipt = first["input_receipts"]
        self.assertEqual(1, receipt["source_file_count"])
        self.assertEqual(1, receipt["source_records"])
        self.assertEqual(
            first["result_sha256"],
            scan.sha256_bytes(
                scan.stable_json(
                    {
                        key: value
                        for key, value in first.items()
                        if key != "result_sha256"
                    }
                ).encode("utf-8")
            ),
        )

    def test_invalid_json_fails_without_writing_a_partial_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest, source = write_cohort(root, [{"safe": "value"}])
            raw = source.read_bytes() + b"{not-json\n"
            source.write_bytes(raw)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            receipt = value["cohort"]["source_files"][0]
            receipt["bytes"] = len(raw)
            receipt["sha256"] = hashlib.sha256(raw).hexdigest()
            receipt["records"] = 2
            manifest.write_text(json.dumps(value), encoding="utf-8")
            output = root / "must-not-exist.json"

            with mock.patch.object(
                sys,
                "argv",
                [
                    "scanner",
                    "--manifest",
                    str(manifest),
                    "--source-root",
                    str(root),
                    "--output",
                    str(output),
                ],
            ):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    status = scan.main()

            self.assertEqual(2, status)
            self.assertFalse(output.exists())
            self.assertNotIn("not-json", stderr.getvalue())

    def test_hash_mismatch_fails_before_scanning(self):
        secret = "Bearer " + "q" * 24
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest, source = write_cohort(root, [{"value": secret}])
            source.write_text(
                json.dumps({"value": secret + "changed"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(scan.SensitiveScanError):
                scan.scan_manifest(manifest, root)

    def test_symlink_source_is_rejected(self):
        if not hasattr(pathlib.Path, "symlink_to"):
            self.skipTest("symbolic links unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest, source = write_cohort(root, [{"safe": "value"}])
            target = source.with_name("target.jsonl")
            source.rename(target)
            source.symlink_to(target.name)
            with self.assertRaises(scan.SensitiveScanError):
                scan.scan_manifest(manifest, root)

    def test_manifest_must_prohibit_committed_raw_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest, _ = write_cohort(root, [{"safe": "value"}])
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["download_policy"]["raw_data_committed"] = True
            manifest.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(scan.SensitiveScanError):
                scan.scan_manifest(manifest, root)


if __name__ == "__main__":
    unittest.main()
