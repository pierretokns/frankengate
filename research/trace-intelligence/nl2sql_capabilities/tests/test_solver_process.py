from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import struct
import sys
import tempfile
import unittest


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.dto import (  # noqa: E402
    SolverEpisodeDTO,
    generate_database_handle,
)
from nl2sql_capabilities.solver_process import (  # noqa: E402
    OP_BOOTSTRAP,
    OP_BROKER_CALL,
    OP_BROKER_RESULT,
    OP_FINISH,
    SANITIZED_ENVIRONMENT_KEYS,
    CapturedPeer,
    OneEpisodeSolverHarness,
)


def solver_episode() -> SolverEpisodeDTO:
    artifact = "Use schema inspection before proposing SQL."
    return SolverEpisodeDTO.from_dict(
        {
            "schema_version": "fg-solver-episode-v1",
            "question": "How many active accounts are there?",
            "official_instructions": "Return a scalar count.",
            "authorized_database_handle": {
                "handle": generate_database_handle(),
                "broker_protocol_version": "fg-governed-sql-tool-v1",
                "authorization_epoch_ref_sha256": "a" * 64,
                "authority_snapshot_sha256": "b" * 64,
                "expires_at_unix_ms": 2_000_000_000_000,
            },
            "artifact_exposure": {
                "artifact_id": "expert-procedure-v1",
                "artifact_sha256": hashlib.sha256(
                    artifact.encode("utf-8")
                ).hexdigest(),
                "content": artifact,
            },
            "limits": {
                "max_model_turns": 4,
                "max_schema_calls": 1,
                "max_sql_attempts": 2,
                "max_generated_tokens_per_call": 512,
                "max_generated_tokens_per_episode": 2048,
                "model_wall_ms": 10_000,
                "model_result_max_rows": 20,
                "model_result_max_bytes": 16_384,
            },
        }
    )


class SolverProcessTest(unittest.TestCase):
    def test_fresh_child_uses_only_inherited_sockets_and_leaks_no_canary(
        self,
    ) -> None:
        canaries = {
            "source_id": b"CANARY_SOURCE_ID_7fdcab8a",
            "gold": b"CANARY_GOLD_SQL_899c3a11",
            "hidden_manifest": b"CANARY_HIDDEN_MANIFEST_d7512863",
            "adjudication": b"CANARY_ADJUDICATION_84a9f310",
            "dsn": b"CANARY_POSTGRES_DSN_5de8fb2c",
            "signing_key": b"CANARY_SIGNING_KEY_477af0df",
        }
        parent_secret_name = "FG_TEST_PARENT_ONLY_SECRET"
        old_secret = os.environ.get(parent_secret_name)
        os.environ[parent_secret_name] = canaries["gold"].decode("ascii")
        self.addCleanup(
            lambda: (
                os.environ.pop(parent_secret_name, None)
                if old_secret is None
                else os.environ.__setitem__(parent_secret_name, old_secret)
            )
        )

        secret_file = tempfile.NamedTemporaryFile()
        self.addCleanup(secret_file.close)
        secret_file.write(b"\n".join(canaries.values()))
        secret_file.flush()
        inherited_parent_fd_target = pathlib.Path(secret_file.name)
        episode = solver_episode()
        captured_bootstrap: list[bytes] = []

        def broker_service(peer: CapturedPeer) -> None:
            self.assertEqual(b"bounded-broker-probe", peer.recv_frame())
            peer.send_frame(b"bounded-broker-result")

        def model_service(peer: CapturedPeer) -> None:
            bootstrap = peer.recv_frame()
            captured_bootstrap.append(bootstrap)
            self.assertEqual(OP_BOOTSTRAP, bootstrap[:1])
            model_view = json.loads(bootstrap[1:].decode("utf-8"))
            self.assertNotIn("authorized_database_handle", model_view)
            self.assertNotIn(
                episode.authorized_database_handle.handle.encode(
                    "ascii"
                ),
                bootstrap,
            )
            self.assertNotIn(b"a" * 64, bootstrap)
            self.assertNotIn(b"b" * 64, bootstrap)
            peer.send_frame(OP_BROKER_CALL + b"bounded-broker-probe")
            result = peer.recv_frame()
            self.assertEqual(
                OP_BROKER_RESULT + b"bounded-broker-result",
                result,
            )
            peer.send_frame(OP_FINISH + b"completed")

        result = OneEpisodeSolverHarness().run(
            episode=episode,
            broker_service=broker_service,
            model_service=model_service,
            canaries=canaries,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual((), result.canary_findings)
        self.assertFalse(result.work_root.exists())
        self.assertNotIn(
            parent_secret_name,
            result.child_receipt["environment"],
        )
        self.assertEqual(
            SANITIZED_ENVIRONMENT_KEYS,
            frozenset(result.child_receipt["environment"]),
        )
        self.assertNotIn(
            str(inherited_parent_fd_target),
            result.child_receipt["open_fd_targets"].values(),
        )
        self.assertEqual([], result.child_receipt["initial_home_entries"])
        self.assertEqual([], result.child_receipt["initial_cwd_entries"])
        expected_fds = {
            "0",
            "1",
            "2",
            result.child_receipt["environment"]["FG_SOLVER_BROKER_FD"],
            result.child_receipt["environment"]["FG_SOLVER_MODEL_FD"],
        }
        self.assertEqual(
            expected_fds,
            set(result.child_receipt["open_fd_targets"]),
        )
        self.assertGreaterEqual(len(result.wire_events), 6)
        self.assertEqual(
            list(range(len(result.wire_events))),
            [event.sequence for event in result.wire_events],
        )
        self.assertEqual(
            episode.canonical_bytes(),
            result.episode_stdin[4:],
        )

        def framed(payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + payload

        def aggregate(channel: str, direction: str) -> bytes:
            return b"".join(
                event.data
                for event in result.wire_events
                if event.channel == channel
                and event.direction == direction
            )

        self.assertEqual(
            framed(OP_BROKER_CALL + b"bounded-broker-probe")
            + framed(OP_FINISH + b"completed"),
            aggregate("model", "to_solver"),
        )
        self.assertEqual(
            framed(captured_bootstrap[0])
            + framed(OP_BROKER_RESULT + b"bounded-broker-result"),
            aggregate("model", "from_solver"),
        )
        self.assertEqual(
            framed(b"bounded-broker-probe"),
            aggregate("broker", "from_solver"),
        )
        self.assertEqual(
            framed(b"bounded-broker-result"),
            aggregate("broker", "to_solver"),
        )

    def test_each_run_is_a_fresh_process_with_no_persistent_home_or_cwd(
        self,
    ) -> None:
        episode = solver_episode()

        def run_once():
            def model_service(peer: CapturedPeer) -> None:
                self.assertEqual(OP_BOOTSTRAP, peer.recv_frame()[:1])
                peer.send_frame(OP_FINISH)

            return OneEpisodeSolverHarness().run(
                episode=episode,
                broker_service=lambda peer: None,
                model_service=model_service,
                canaries={
                    "parent_state": b"CANARY_PARENT_STATE_0d1c87ac"
                },
            )

        first = run_once()
        second = run_once()
        self.assertEqual(0, first.returncode)
        self.assertEqual(0, second.returncode)
        self.assertNotEqual(first.pid, second.pid)
        self.assertNotEqual(first.work_root, second.work_root)
        self.assertFalse(first.work_root.exists())
        self.assertFalse(second.work_root.exists())
        for result in (first, second):
            self.assertEqual([], result.child_receipt["initial_home_entries"])
            self.assertEqual([], result.child_receipt["final_home_entries"])
            self.assertEqual([], result.child_receipt["initial_cwd_entries"])
            self.assertEqual([], result.child_receipt["final_cwd_entries"])
            self.assertFalse(
                result.child_receipt["linux_oci_enforcement_verified"]
            )
            self.assertEqual((), result.canary_findings)

    def test_canary_detector_covers_wire_and_derived_hash_leaks(self) -> None:
        leaked = b"CANARY_INTENTIONAL_LEAK_654bdb7a"

        def model_service(peer: CapturedPeer) -> None:
            peer.recv_frame()
            peer.send_frame(OP_FINISH + leaked)

        result = OneEpisodeSolverHarness().run(
            episode=solver_episode(),
            broker_service=lambda peer: None,
            model_service=model_service,
            canaries={"intentional": leaked},
        )
        self.assertEqual(0, result.returncode)
        finding_pairs = {
            (finding.representation, finding.channel)
            for finding in result.canary_findings
        }
        self.assertTrue(
            any(
                representation == "raw"
                and channel.endswith("model:to_solver")
                for representation, channel in finding_pairs
            )
        )
        self.assertTrue(
            any(
                representation == "sha256_hex" and channel == "stdout"
                for representation, channel in finding_pairs
            )
        )

    def test_worker_source_has_no_manifest_gold_or_evaluator_deserializer(
        self,
    ) -> None:
        worker = (
            pathlib.Path(__file__).parents[1] / "solver_process_worker.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(1, worker.count("SolverEpisodeDTO.from_json_bytes"))
        self.assertNotIn("json.loads", worker)
        tree = ast.parse(worker)
        imported_modules: set[str] = set()
        referenced_symbols: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module or "")
                referenced_symbols.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Name):
                referenced_symbols.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced_symbols.add(node.attr)
        self.assertTrue(
            all(
                forbidden not in module
                for module in imported_modules
                for forbidden in (
                    "stage_sealer",
                    "resolver",
                    "evaluator",
                    "psycopg",
                )
            ),
            imported_modules,
        )
        self.assertTrue(
            {
                "RuntimeTask",
                "gold_sql",
                "resolve_gold",
                "adjudication",
                "source_locator",
            }.isdisjoint(referenced_symbols),
            referenced_symbols,
        )


if __name__ == "__main__":
    unittest.main()
