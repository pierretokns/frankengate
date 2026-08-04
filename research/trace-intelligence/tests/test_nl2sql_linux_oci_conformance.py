from __future__ import annotations

import errno
import json
import pathlib
import stat
import sys
import tempfile
import unittest


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_linux_oci_conformance import (  # noqa: E402
    ABSENT_SENSITIVE_PATHS,
    EXPECTED_ENV_KEYS,
    EXPECTED_STAGED_FILES,
    PROBE_PREFIX,
    PROBE_SCHEMA_VERSION,
    _exclusive_private_write,
    _json_bytes,
    classify_enforcement,
    classify_runtime_stderr,
    minimize_decision,
    parse_probe,
    scan_canaries,
)


def conformant_probe() -> dict[str, object]:
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "uid": 65532,
        "euid": 65532,
        "gid": 65532,
        "egid": 65532,
        "cwd": "/work",
        "environment": {
            key: (
                "3"
                if key == "FG_SOLVER_BROKER_FD"
                else "4"
                if key == "FG_SOLVER_MODEL_FD"
                else "value"
            )
            for key in EXPECTED_ENV_KEYS
        },
        "fds": {
            "0": "pipe:[1]",
            "1": "pipe:[2]",
            "2": "pipe:[3]",
            "3": "socket:[4]",
            "4": "socket:[5]",
        },
        "proc_status": {
            "NoNewPrivs": "1",
            "Seccomp": "2",
            "CapBnd": "0000000000000000",
            "CapEff": "0000000000000000",
            "CapInh": "0000000000000000",
            "CapPrm": "0000000000000000",
            "CapAmb": "0000000000000000",
        },
        "root_write": {"ok": False, "errno": errno.EROFS},
        "tmpfs": {
            destination: {
                "uid": 65532,
                "gid": 65532,
                "mode": 0o700,
                "mount_type": "tmpfs",
                "write": {"ok": True, "errno": None},
            }
            for destination in ("/home", "/tmp", "/work")
        },
        "network": {
            "AF_INET": {"created": False, "errno": errno.EPERM},
            "AF_INET6": {"created": False, "errno": errno.EPERM},
        },
        "staged_files": list(EXPECTED_STAGED_FILES),
        "sensitive_path_presence": {
            path: False for path in ABSENT_SENSITIVE_PATHS
        },
    }


class LinuxOCIConformanceUnitTest(unittest.TestCase):
    def test_conformant_probe_passes_every_gate(self) -> None:
        result = classify_enforcement(
            returncode=0,
            probe=conformant_probe(),
            child_receipt={"schema_version": "receipt"},
            peer_errors=[],
            canary_findings=[],
        )
        self.assertTrue(result["passed"])
        self.assertEqual("enforcement_conformant", result["classification"])
        self.assertTrue(
            all(item["passed"] for item in result["gates"].values())
        )

    def test_network_or_fd_weakening_is_exactly_classified(self) -> None:
        probe = conformant_probe()
        probe["network"]["AF_INET"]["created"] = True
        probe["network"]["AF_INET"]["errno"] = None
        probe["fds"]["5"] = "/host/source-manifest.json"
        result = classify_enforcement(
            returncode=0,
            probe=probe,
            child_receipt={"schema_version": "receipt"},
            peer_errors=[],
            canary_findings=[],
        )
        self.assertFalse(result["passed"])
        self.assertEqual("enforcement_nonconformant", result["classification"])
        self.assertFalse(result["gates"]["deny_af_inet_socket"]["passed"])
        self.assertFalse(result["gates"]["exact_descriptors"]["passed"])

    def test_missing_probe_is_startup_failure_not_enforcement_pass(self) -> None:
        result = classify_enforcement(
            returncode=1,
            probe=None,
            child_receipt=None,
            peer_errors=["model:closed"],
            canary_findings=[],
        )
        self.assertFalse(result["passed"])
        self.assertEqual(
            "profile_startup_or_probe_failure", result["classification"]
        )

    def test_diagnostic_variant_can_never_pass_release_gate(self) -> None:
        result = classify_enforcement(
            returncode=0,
            probe=conformant_probe(),
            child_receipt={"schema_version": "receipt"},
            peer_errors=[],
            canary_findings=[],
            profile_variant="diagnostic_nonrelease",
        )
        self.assertFalse(result["passed"])
        self.assertEqual("enforcement_nonconformant", result["classification"])
        self.assertFalse(result["gates"]["frozen_profile"]["passed"])

    def test_cleanup_failure_can_never_publish_an_unqualified_pass(self) -> None:
        result = classify_enforcement(
            returncode=0,
            probe=conformant_probe(),
            child_receipt={"schema_version": "receipt"},
            peer_errors=[],
            canary_findings=[],
            cleanup_status={"passed": False, "reason": "forced_delete_failed"},
        )
        self.assertFalse(result["passed"])
        self.assertEqual("enforcement_nonconformant", result["classification"])
        self.assertFalse(result["gates"]["runtime_cleanup"]["passed"])

    def test_peer_or_receipt_failure_is_classified_as_startup_failure(self) -> None:
        result = classify_enforcement(
            returncode=0,
            probe=conformant_probe(),
            child_receipt=None,
            peer_errors=["model:closed"],
            canary_findings=[],
        )
        self.assertFalse(result["passed"])
        self.assertEqual(
            "profile_startup_or_probe_failure", result["classification"]
        )

    def test_known_preserved_fd_runtime_failure_is_classified(self) -> None:
        self.assertEqual(
            [
                "preserved_fd_procfs_validation_denied_likely_missing_fstatfs"
            ],
            classify_runtime_stderr(
                b"ensure /proc/self/fd is on procfs: operation not permitted\n"
            ),
        )
        self.assertEqual(
            ["python_exec_eagain_likely_rlimit_nproc"],
            classify_runtime_stderr(
                b"exec /usr/local/bin/python3: resource temporarily unavailable\n"
            ),
        )

    def test_probe_parser_preserves_non_probe_stderr(self) -> None:
        encoded = json.dumps(conformant_probe(), separators=(",", ":")).encode()
        probe, errors = parse_probe(
            b"runtime diagnostic\n"
            + PROBE_PREFIX.encode()
            + encoded
            + b"\nworker diagnostic\n"
        )
        self.assertEqual([], errors)
        self.assertEqual(PROBE_SCHEMA_VERSION, probe["schema_version"])

    def test_canary_scanner_covers_exact_and_derived_representations(self) -> None:
        secret = b"source-canary-is-at-least-sixteen"
        digest = __import__("hashlib").sha256(secret).hexdigest().encode()
        findings = scan_canaries(
            {"source_id": secret},
            {"dto": b"safe", "argv": b"prefix:" + digest},
        )
        self.assertEqual(
            [
                {
                    "canary": "source_id",
                    "representation": "sha256_hex",
                    "channel": "argv",
                }
            ],
            findings,
        )

    def test_raw_evidence_is_exact_private_and_never_overwritten(self) -> None:
        content = _json_bytes({"evidence": "exact"})
        with tempfile.TemporaryDirectory() as temporary:
            target = pathlib.Path(temporary) / "raw.json"
            _exclusive_private_write(target, content)
            self.assertEqual(content, target.read_bytes())
            self.assertEqual(0o600, stat.S_IMODE(target.stat().st_mode))
            with self.assertRaises(FileExistsError):
                _exclusive_private_write(target, b"replacement")
            self.assertEqual(content, target.read_bytes())

    def test_aggregate_decision_removes_paths_and_descriptor_targets(self):
        raw = classify_enforcement(
            returncode=0,
            probe=conformant_probe(),
            child_receipt={"schema_version": "receipt"},
            peer_errors=[],
            canary_findings=[],
        )
        minimized = minimize_decision(raw)
        encoded = json.dumps(minimized, sort_keys=True)
        self.assertNotIn("/home/", encoded)
        self.assertNotIn("socket:[", encoded)
        self.assertNotIn("pipe:[", encoded)
        self.assertEqual(
            {"checked_path_count": len(ABSENT_SENSITIVE_PATHS), "present_path_count": 0},
            minimized["gates"]["sensitive_paths_absent"]["observed"],
        )
        self.assertEqual(
            ["3", "4"],
            minimized["gates"]["exact_descriptors"]["observed"][
                "socket_fd_numbers"
            ],
        )


if __name__ == "__main__":
    unittest.main()
