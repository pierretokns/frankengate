import hashlib
import json
import pathlib
import sys
import tempfile
import threading
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import local_runtime_attestation as attestation  # noqa: E402


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LocalRuntimeAttestationTest(unittest.TestCase):
    def test_manifest_loader_rejects_duplicate_json_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "runtime.json"
            valid = (
                ROOT
                / "configs"
                / "models"
                / "qwen3.5-9b-optiq-4bit-mlx-runtime-v2.json"
            ).read_text(encoding="utf-8")
            path.write_text(
                valid.replace(
                    '"schema_version":',
                    (
                        '"schema_version": "shadowed",\n'
                        '  "schema_version":'
                    ),
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(attestation.AttestationError):
                attestation.load_runtime_manifest(path)

    def test_manifest_loader_rejects_unrecognized_runtime_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "runtime.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "frankengate-model-runtime-manifest-v2"
                        ),
                        "model_id": "example/model",
                        "request_model_id": "default_model",
                        "source_url": "https://example.invalid/model",
                        "revision": "a" * 40,
                        "snapshot": {},
                        "runtime": {
                            "python_version": "3.14.2",
                            "python_executable_sha256": "a" * 64,
                            "mlx_lm_console_script_sha256": "b" * 64,
                            "distributions": {"mlx": "0.31.1"},
                            "critical_source_sha256": {
                                "mlx_lm_server_py": "c" * 64,
                            },
                            "unverified_loader": "accepted",
                        },
                        "server_contract": {},
                        "claim_boundary": {},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(attestation.AttestationError):
                attestation.load_runtime_manifest(path)

    def test_manifest_loader_rejects_unrecognized_top_level_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = json.loads(
                (
                    ROOT
                    / "configs"
                    / "models"
                    / "qwen3.5-9b-optiq-4bit-mlx-runtime-v2.json"
                ).read_text(encoding="utf-8")
            )
            manifest["unverified_override"] = True
            path = pathlib.Path(directory) / "runtime.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(attestation.AttestationError):
                attestation.load_runtime_manifest(path)

    def test_runtime_manifest_verification_covers_snapshot_and_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "config.json").write_text("{}", encoding="utf-8")
            (snapshot / "weights.bin").write_bytes(b"weights")
            python = root / "python"
            python.write_bytes(b"python-runtime")
            console = root / "mlx_lm.server"
            console.write_bytes(b"console-script")
            server_source = root / "server.py"
            server_source.write_bytes(b"server-source")

            snapshot_receipt = attestation.snapshot_tree_receipt(
                snapshot,
                expected_paths={"config.json", "weights.bin"},
            )
            manifest = {
                "schema_version": "frankengate-model-runtime-manifest-v2",
                "model_id": "example/model",
                "request_model_id": "default_model",
                "source_url": "https://example.invalid/model",
                "revision": "a" * 40,
                "snapshot": snapshot_receipt,
                "runtime": {
                    "python_version": "3.14.2",
                    "python_executable_sha256": sha256_file(python),
                    "mlx_lm_console_script_sha256": sha256_file(console),
                    "distributions": {"mlx": "0.31.1"},
                    "critical_source_sha256": {
                        "mlx_lm_server_py": sha256_file(server_source),
                    },
                },
                "server_contract": {"offline_only": True},
                "claim_boundary": {"frontier_model": False},
            }
            manifest_path = root / "runtime.json"
            manifest_path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            receipt = attestation.verify_runtime_manifest(
                manifest_path,
                snapshot_root=snapshot,
                python_executable=python,
                mlx_lm_console_script=console,
                python_version="3.14.2",
                installed_distributions={"mlx": "0.31.1"},
                critical_source_paths={
                    "mlx_lm_server_py": server_source,
                },
            )

            self.assertEqual(
                "frankengate-model-runtime-attestation-v2",
                receipt["schema_version"],
            )
            self.assertEqual(2, receipt["snapshot_files_verified"])
            self.assertEqual(1, receipt["distributions_verified"])
            self.assertEqual(1, receipt["critical_sources_verified"])
            self.assertNotIn(str(root), json.dumps(receipt))
            self.assertNotIn("file_receipts", receipt)

    def test_snapshot_tree_receipt_requires_exact_file_census(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "config.json").write_text("{}", encoding="utf-8")
            (root / "weights.bin").write_bytes(b"weights")

            receipt = attestation.snapshot_tree_receipt(
                root,
                expected_paths={"config.json", "weights.bin"},
            )

            self.assertEqual(2, receipt["files"])
            self.assertEqual(9, receipt["bytes"])
            self.assertRegex(
                receipt["snapshot_tree_sha256"],
                r"^[0-9a-f]{64}$",
            )
            (root / "unexpected.txt").write_text(
                "extra",
                encoding="utf-8",
            )
            with self.assertRaises(attestation.AttestationError):
                attestation.snapshot_tree_receipt(
                    root,
                    expected_paths={"config.json", "weights.bin"},
                )

    def test_hash_chain_requires_preflight_before_model_request(self):
        chain = attestation.AttestationChain()
        chain.append(
            "preflight_verified",
            {"run_plan_sha256": "a" * 64},
        )
        chain.append(
            "model_request",
            {"request_sha256": "b" * 64},
        )

        receipt = chain.receipt()
        self.assertEqual(2, receipt["events"])
        self.assertTrue(attestation.verify_event_chain(chain.events))
        self.assertEqual(
            chain.events[-1]["event_sha256"],
            receipt["event_chain_root_sha256"],
        )
        invalid = attestation.AttestationChain()
        with self.assertRaises(attestation.AttestationError):
            invalid.append(
                "model_request",
                {"request_sha256": "b" * 64},
            )

    def test_fsynced_jsonl_chain_is_restart_safe_and_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            log = attestation.FsyncedAttestationLog(path)
            log.append(
                "preflight_verified",
                {"run_plan_sha256": "a" * 64},
            )
            resumed = attestation.FsyncedAttestationLog(path)
            resumed.append(
                "model_request",
                {"request_sha256": "b" * 64},
            )

            events = attestation.read_attestation_log(path)

            self.assertEqual(2, len(events))
            self.assertTrue(attestation.verify_event_chain(events))
            self.assertEqual(0, events[0]["sequence"])
            self.assertEqual(1, events[1]["sequence"])
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_attestation_writer_serializes_concurrent_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            attestation.FsyncedAttestationLog(path).append(
                "preflight_verified",
                {"run_plan_sha256": "a" * 64},
            )
            barrier = threading.Barrier(12)
            failures = []

            def append_event(index):
                try:
                    writer = attestation.FsyncedAttestationLog(path)
                    barrier.wait()
                    writer.append(
                        "model_request",
                        {"request_sha256": f"{index:064x}"},
                    )
                except Exception as error:  # pragma: no cover - asserted below
                    failures.append(error)

            threads = [
                threading.Thread(target=append_event, args=(index,))
                for index in range(12)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual([], failures)
            self.assertEqual(
                13,
                len(attestation.read_attestation_log(path)),
            )

    def test_attestation_reader_rejects_ambiguous_duplicate_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            log = attestation.FsyncedAttestationLog(path)
            log.append(
                "preflight_verified",
                {"run_plan_sha256": "a" * 64},
            )
            ambiguous = path.read_text(encoding="utf-8").replace(
                '"event_type":',
                '"event_type":"shadowed","event_type":',
                1,
            )
            path.write_text(ambiguous, encoding="utf-8")

            with self.assertRaises(attestation.AttestationError):
                attestation.read_attestation_log(path)

    def test_attestation_writer_refuses_events_after_run_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            log = attestation.FsyncedAttestationLog(path)
            log.append(
                "preflight_verified",
                {"run_plan_sha256": "a" * 64},
            )
            log.append(
                "run_completed",
                {
                    "requests_completed": 0,
                    "result_sha256": "b" * 64,
                },
            )

            with self.assertRaises(attestation.AttestationError):
                log.append(
                    "model_request",
                    {"request_sha256": "c" * 64},
                )

    def test_completed_attestation_requires_paired_requests_and_postflight(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            log = attestation.FsyncedAttestationLog(path)
            log.append(
                "preflight_verified",
                {
                    "runtime_manifest_sha256": "a" * 64,
                    "snapshot_tree_sha256": "b" * 64,
                    "run_plan_sha256": "c" * 64,
                },
            )
            log.append(
                "model_request",
                {
                    "request_id_sha256": "d" * 64,
                    "request_sha256": "e" * 64,
                },
            )
            log.append(
                "model_response",
                {
                    "request_id_sha256": "d" * 64,
                    "response_sha256": "f" * 64,
                },
            )
            log.append(
                "postflight_verified",
                {"snapshot_tree_sha256": "b" * 64},
            )
            log.append(
                "run_completed",
                {
                    "requests_completed": 1,
                    "result_sha256": "1" * 64,
                },
            )

            receipt = attestation.verify_completed_attestation(path)

            self.assertEqual(
                "frankengate-completed-runtime-attestation-v2",
                receipt["schema_version"],
            )
            self.assertEqual(1, receipt["model_requests_verified"])
            self.assertEqual(5, receipt["events"])
            self.assertEqual("a" * 64, receipt["runtime_manifest_sha256"])
            self.assertNotIn(str(path), json.dumps(receipt))

    def test_completed_attestation_rejects_duplicate_request_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            log = attestation.FsyncedAttestationLog(path)
            log.append(
                "preflight_verified",
                {
                    "runtime_manifest_sha256": "a" * 64,
                    "snapshot_tree_sha256": "b" * 64,
                    "run_plan_sha256": "c" * 64,
                },
            )
            for suffix in ("e", "f"):
                log.append(
                    "model_request",
                    {
                        "request_id_sha256": "d" * 64,
                        "request_sha256": suffix * 64,
                    },
                )
                log.append(
                    "model_response",
                    {
                        "request_id_sha256": "d" * 64,
                        "response_sha256": "1" * 64,
                    },
                )
            log.append(
                "postflight_verified",
                {"snapshot_tree_sha256": "b" * 64},
            )
            log.append(
                "run_completed",
                {
                    "requests_completed": 2,
                    "result_sha256": "2" * 64,
                },
            )

            with self.assertRaises(attestation.AttestationError):
                attestation.verify_completed_attestation(path)

    def test_completed_attestation_rejects_zero_request_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attestation.jsonl"
            log = attestation.FsyncedAttestationLog(path)
            log.append(
                "preflight_verified",
                {
                    "runtime_manifest_sha256": "a" * 64,
                    "snapshot_tree_sha256": "b" * 64,
                    "run_plan_sha256": "c" * 64,
                },
            )
            log.append(
                "postflight_verified",
                {"snapshot_tree_sha256": "b" * 64},
            )
            log.append(
                "run_completed",
                {
                    "requests_completed": 0,
                    "result_sha256": "d" * 64,
                },
            )

            with self.assertRaises(attestation.AttestationError):
                attestation.verify_completed_attestation(path)


if __name__ == "__main__":
    unittest.main()
