from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wisp_recovery_adjudication_packet as packet  # noqa: E402


BLIND_KEY = b"blind-key-for-tests-" + b"x" * 32
RECEIPT_KEY = b"receipt-key-for-tests-" + b"y" * 32


def recovery_records(suffix="a"):
    failed = f"failed-{suffix}"
    recovered = f"recovered-{suffix}"
    return [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": (
                    "alice@example.com is working on "
                    "CLASSIFIED-PROJECT-ORION"
                ),
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": failed,
                        "name": "Bash",
                        "input": {
                            "command": "deploy orion",
                            "authorization": (
                                "Bearer abcdefghijklmnopqrstuvwxyz"
                            ),
                        },
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": failed,
                        "is_error": True,
                        "content": "permission denied for alice@example.com",
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "I will use the approved internal role.",
                    },
                    {
                        "type": "tool_use",
                        "id": recovered,
                        "name": "Bash",
                        "input": {"command": "deploy orion --approved"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": recovered,
                        "is_error": False,
                        "content": "deployment accepted",
                    }
                ],
            },
        },
    ]


class WispRecoveryAdjudicationPacketTest(unittest.TestCase):
    def test_label_contract_covers_episode_not_person_judgments(self) -> None:
        contract = packet.label_contract()

        self.assertEqual(
            {
                "relation",
                "outcome",
                "cause",
                "evidence_strength",
                "productive_exploration",
                "usefulness",
            },
            set(contract),
        )
        encoded = json.dumps(contract, sort_keys=True).casefold()
        self.assertNotIn("skill_gap", encoded)
        self.assertNotIn("person_skill", encoded)
        self.assertIn("insufficient_evidence", encoded)

    def test_packet_is_blinded_tool_complete_and_strips_only_credentials(self) -> None:
        raw_packet, manifest = packet.build_packet_from_sessions(
            {
                "-home-me/project-a/session-a.jsonl": recovery_records(),
            },
            dataset_id="crispwisp/wisp-claude-code-sessions",
            dataset_revision="revision-fixture",
            blind_key=BLIND_KEY,
            receipt_hmac_key=RECEIPT_KEY,
            seed="fixed-order",
            scope_ref="tenant:internal",
            purpose="recovery-adjudication",
        )

        self.assertEqual(1, len(raw_packet["candidates"]))
        candidate = raw_packet["candidates"][0]
        self.assertRegex(candidate["blind_id"], r"^C-[0-9a-f]{24}$")
        packet.assert_tool_complete_candidate(candidate)
        encoded = json.dumps(raw_packet, sort_keys=True)
        self.assertIn("alice@example.com", encoded)
        self.assertIn("CLASSIFIED-PROJECT-ORION", encoded)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", encoded)
        self.assertIn("[CREDENTIAL:AUTHORIZATION]", encoded)
        self.assertNotIn("session-a.jsonl", encoded)
        self.assertNotIn("failed-a", encoded)
        self.assertFalse(manifest["raw_packet_committed"])
        self.assertEqual(1, manifest["candidate_count"])

    def test_adjudication_requires_exact_labels_and_local_evidence_refs(self) -> None:
        raw_packet, _ = packet.build_packet_from_sessions(
            {"session.jsonl": recovery_records()},
            dataset_id="fixture",
            dataset_revision="revision",
            blind_key=BLIND_KEY,
            receipt_hmac_key=RECEIPT_KEY,
            scope_ref="tenant:internal",
            purpose="recovery-adjudication",
        )
        candidate = raw_packet["candidates"][0]
        evidence_ref = candidate["context"][0]["evidence_ref"]
        labels = {
            name: {
                "label": values[0],
                "evidence_refs": [evidence_ref],
            }
            for name, values in raw_packet["label_contract"].items()
        }
        submission = {
            "blind_id": candidate["blind_id"],
            "labels": labels,
        }

        normalized = packet.validate_adjudication(candidate, submission)
        self.assertEqual(submission, normalized)

        bad_label = json.loads(json.dumps(submission))
        bad_label["labels"]["cause"]["label"] = "user_lacks_skill"
        with self.assertRaisesRegex(packet.PacketError, "cause label"):
            packet.validate_adjudication(candidate, bad_label)

        bad_ref = json.loads(json.dumps(submission))
        bad_ref["labels"]["outcome"]["evidence_refs"] = ["E-not-in-packet"]
        with self.assertRaisesRegex(packet.PacketError, "evidence_ref"):
            packet.validate_adjudication(candidate, bad_ref)

        person_inference = {
            **submission,
            "person_skill_gap": "cloud",
        }
        with self.assertRaisesRegex(packet.PacketError, "exact fields"):
            packet.validate_adjudication(candidate, person_inference)

    def test_blind_ids_and_order_are_deterministic_across_input_order(self) -> None:
        left = {
            "z/session-z.jsonl": recovery_records("z"),
            "a/session-a.jsonl": recovery_records("a"),
        }
        right = dict(reversed(list(left.items())))
        kwargs = {
            "dataset_id": "fixture",
            "dataset_revision": "revision",
            "blind_key": BLIND_KEY,
            "receipt_hmac_key": RECEIPT_KEY,
            "seed": "fixed-order",
            "scope_ref": "tenant:internal",
            "purpose": "recovery-adjudication",
        }

        first_packet, first_manifest = packet.build_packet_from_sessions(
            left,
            **kwargs,
        )
        second_packet, second_manifest = packet.build_packet_from_sessions(
            right,
            **kwargs,
        )

        self.assertEqual(first_packet, second_packet)
        self.assertEqual(first_manifest, second_manifest)
        blind_ids = [
            candidate["blind_id"]
            for candidate in first_packet["candidates"]
        ]
        self.assertEqual(2, len(set(blind_ids)))
        self.assertNotIn("session-a", json.dumps(first_packet))
        self.assertNotIn("session-z", json.dumps(first_packet))

    def test_context_is_whole_event_bounded_and_never_partial_tool_data(self) -> None:
        raw_packet, manifest = packet.build_packet_from_sessions(
            {"session.jsonl": recovery_records()},
            dataset_id="fixture",
            dataset_revision="revision",
            blind_key=BLIND_KEY,
            receipt_hmac_key=RECEIPT_KEY,
            scope_ref="tenant:internal",
            purpose="recovery-adjudication",
            max_context_events=4,
        )

        self.assertEqual([], raw_packet["candidates"])
        self.assertEqual(1, manifest["structural_candidate_count"])
        self.assertEqual(
            {"context_event_bound": 1},
            manifest["excluded_candidate_counts"],
        )

    def test_raw_packet_writer_refuses_every_path_outside_private_tmp(self) -> None:
        raw_packet, manifest = packet.build_packet_from_sessions(
            {"session.jsonl": recovery_records()},
            dataset_id="fixture",
            dataset_revision="revision",
            blind_key=BLIND_KEY,
            receipt_hmac_key=RECEIPT_KEY,
            scope_ref="tenant:internal",
            purpose="recovery-adjudication",
        )
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            output = pathlib.Path(directory) / "packet.json"
            receipt = packet.write_raw_packet(raw_packet, output)
            self.assertEqual(
                receipt["sha256"],
                packet.sha256_file(output),
            )
            self.assertEqual(
                manifest["raw_packet_sha256"],
                receipt["sha256"],
            )
            self.assertEqual(0o600, output.stat().st_mode & 0o777)

        with self.assertRaisesRegex(packet.PacketError, "/private/tmp"):
            packet.write_raw_packet(
                raw_packet,
                ROOT / "forbidden-raw-packet.json",
            )

    def test_committed_manifest_contains_no_candidate_content_or_ids(self) -> None:
        _, manifest = packet.build_packet_from_sessions(
            {"secret/session.jsonl": recovery_records()},
            dataset_id="fixture",
            dataset_revision="revision",
            blind_key=BLIND_KEY,
            receipt_hmac_key=RECEIPT_KEY,
            scope_ref="tenant:internal",
            purpose="recovery-adjudication",
        )
        encoded = json.dumps(manifest, sort_keys=True)

        self.assertNotIn("alice@example.com", encoded)
        self.assertNotIn("CLASSIFIED-PROJECT-ORION", encoded)
        self.assertNotIn("session.jsonl", encoded)
        self.assertNotIn('"blind_id"', encoded)
        self.assertNotIn('"context"', encoded)
        packet.assert_content_free_manifest(manifest)

    def test_loader_preserves_objects_and_receipts_malformed_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = pathlib.Path(directory)
            nested = root / "nested"
            nested.mkdir()
            source = nested / "session.jsonl"
            source.write_text(
                "".join(
                    json.dumps(record, sort_keys=True) + "\n"
                    for record in recovery_records()
                ),
                encoding="utf-8",
            )

            sessions = packet.load_wisp_sessions(root)
            self.assertEqual(
                {"nested/session.jsonl"},
                set(sessions),
            )
            self.assertEqual(len(recovery_records()), len(next(iter(sessions.values()))))

            source.write_text("{malformed\n", encoding="utf-8")
            malformed = packet.load_wisp_sessions(root)
            loss = next(iter(malformed.values()))[0][
                "_packet_source_loss"
            ]
            self.assertEqual("malformed_json_record", loss["category"])
            self.assertEqual(1, loss["line_number"])
            self.assertEqual(11, loss["byte_length"])
            self.assertRegex(loss["raw_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("raw_bytes", loss)


if __name__ == "__main__":
    unittest.main()
