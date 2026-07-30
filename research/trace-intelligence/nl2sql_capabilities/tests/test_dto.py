from __future__ import annotations

import copy
import hashlib
import hmac
import json
import pathlib
import sys
import unittest


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.dto import (  # noqa: E402
    DTOValidationError,
    SolverEpisodeDTO,
    canonical_json_bytes,
    decode_base64url,
    derive_stage_episode_ref,
    encode_base64url,
    generate_attempt_id,
    generate_database_handle,
    generate_request_nonce,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _valid_solver_episode() -> dict[str, object]:
    artifact = "Use explicit joins and verify aggregate grain."
    return {
        "schema_version": "fg-solver-episode-v1",
        "question": "How many active accounts are there?",
        "official_instructions": "Return one read-only query.",
        "authorized_database_handle": {
            "handle": encode_base64url(bytes(range(32))),
            "broker_protocol_version": "fg-governed-sql-tool-v1",
            "authorization_epoch_ref_sha256": "1" * 64,
            "authority_snapshot_sha256": "2" * 64,
            "expires_at_unix_ms": 1_780_000_000_000,
        },
        "artifact_exposure": {
            "artifact_id": "expert-v1",
            "artifact_sha256": _sha256_text(artifact),
            "content": artifact,
        },
        "limits": {
            "max_model_turns": 6,
            "max_schema_calls": 2,
            "max_sql_attempts": 3,
            "max_generated_tokens_per_call": 1_024,
            "max_generated_tokens_per_episode": 4_096,
            "model_wall_ms": 60_000,
            "model_result_max_rows": 50,
            "model_result_max_bytes": 32_768,
        },
    }


class SolverEpisodeDTOBoundaryTest(unittest.TestCase):
    def test_solver_dto_exact_allowlist(self) -> None:
        payload = _valid_solver_episode()
        parsed = SolverEpisodeDTO.from_dict(payload)
        self.assertEqual(payload, parsed.to_dict())

        forbidden_fields = (
            "task_id",
            "database",
            "db_name",
            "query_category",
            "fold",
            "stage",
            "source",
            "locator",
            "gold",
            "gold_sql",
            "answer",
            "adjudication",
            "outcome",
            "label",
        )
        containers = (
            (),
            ("authorized_database_handle",),
            ("artifact_exposure",),
            ("limits",),
        )
        for container_path in containers:
            for field in forbidden_fields:
                with self.subTest(container=container_path, field=field):
                    candidate = copy.deepcopy(payload)
                    container = candidate
                    for component in container_path:
                        container = container[component]  # type: ignore[index]
                    container[field] = "CANARY"  # type: ignore[index]
                    with self.assertRaises(DTOValidationError):
                        SolverEpisodeDTO.from_dict(candidate)

        candidate = copy.deepcopy(payload)
        candidate["artifact_exposure"]["unknown"] = "CANARY"  # type: ignore[index]
        with self.assertRaisesRegex(DTOValidationError, "unknown field"):
            SolverEpisodeDTO.from_dict(candidate)

    def test_public_task_hash_cannot_link_episode_ref(self) -> None:
        public_task_id = "defog-public-task-0042"
        secret = bytes(range(32))
        episode_ref = derive_stage_episode_ref(
            key=secret,
            experiment_id="defog-sql-factorial-v3",
            fold_id="fold-0",
            stage_role="hidden_test",
            source_task_id=public_task_id,
        )

        public_sha_hex = hashlib.sha256(public_task_id.encode("utf-8")).hexdigest()
        public_sha_b64 = encode_base64url(
            hashlib.sha256(public_task_id.encode("utf-8")).digest()
        )
        self.assertNotEqual(public_sha_hex, episode_ref)
        self.assertNotEqual(public_sha_b64, episode_ref)
        self.assertNotIn(public_task_id, episode_ref)
        self.assertEqual(32, len(decode_base64url(episode_ref)))

        other_key_ref = derive_stage_episode_ref(
            key=b"x" * 32,
            experiment_id="defog-sql-factorial-v3",
            fold_id="fold-0",
            stage_role="hidden_test",
            source_task_id=public_task_id,
        )
        other_stage_ref = derive_stage_episode_ref(
            key=secret,
            experiment_id="defog-sql-factorial-v3",
            fold_id="fold-0",
            stage_role="visible_selection",
            source_task_id=public_task_id,
        )
        self.assertNotEqual(episode_ref, other_key_ref)
        self.assertNotEqual(episode_ref, other_stage_ref)

        expected = hmac.new(
            secret,
            (
                "defog-sql-factorial-v3\0fold-0\0hidden_test\0"
                + public_task_id
            ).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        self.assertEqual(expected, decode_base64url(episode_ref))

    def test_canonical_encoding_and_opaque_token_helpers_are_strict(self) -> None:
        left = {"z": [None, True, 7], "é": "composed", "a": {"b": "x"}}
        right = {"a": {"b": "x"}, "é": "composed", "z": [None, True, 7]}
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        self.assertEqual(
            b'{"a":{"b":"x"},"z":[null,true,7],"\xc3\xa9":"composed"}',
            canonical_json_bytes(left),
        )
        for unsupported in (1.5, {1: "not-a-string-key"}, 2**53):
            with self.subTest(unsupported=unsupported):
                with self.assertRaises(DTOValidationError):
                    canonical_json_bytes(unsupported)

        for generator, expected_bytes in (
            (generate_request_nonce, 16),
            (generate_attempt_id, 24),
            (generate_database_handle, 32),
        ):
            first = generator()
            second = generator()
            self.assertNotEqual(first, second)
            self.assertNotIn("=", first)
            self.assertEqual(expected_bytes, len(decode_base64url(first)))

        for invalid in ("abc=", "a+b", "a/b", "", "A"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(DTOValidationError):
                    decode_base64url(invalid)

    def test_nested_capability_values_and_json_members_are_fail_closed(self) -> None:
        cases: list[tuple[str, dict[str, object]]] = []

        short_handle = copy.deepcopy(_valid_solver_episode())
        short_handle["authorized_database_handle"]["handle"] = encode_base64url(  # type: ignore[index]
            b"x" * 16
        )
        cases.append(("handle size", short_handle))

        padded_handle = copy.deepcopy(_valid_solver_episode())
        padded_handle["authorized_database_handle"]["handle"] += "="  # type: ignore[index,operator]
        cases.append(("handle padding", padded_handle))

        mismatched_artifact = copy.deepcopy(_valid_solver_episode())
        mismatched_artifact["artifact_exposure"]["content"] += " changed"  # type: ignore[index,operator]
        cases.append(("artifact digest", mismatched_artifact))

        boolean_limit = copy.deepcopy(_valid_solver_episode())
        boolean_limit["limits"]["max_model_turns"] = True  # type: ignore[index]
        cases.append(("boolean integer", boolean_limit))

        incoherent_token_limits = copy.deepcopy(_valid_solver_episode())
        incoherent_token_limits["limits"]["max_generated_tokens_per_call"] = 8192  # type: ignore[index]
        cases.append(("token budget relation", incoherent_token_limits))

        for label, candidate in cases:
            with self.subTest(label=label):
                with self.assertRaises(DTOValidationError):
                    SolverEpisodeDTO.from_dict(candidate)

        encoded = json.dumps(_valid_solver_episode(), separators=(",", ":"))
        duplicate_member = encoded.replace(
            '"question":',
            '"question":"shadow value","question":',
            1,
        ).encode("utf-8")
        with self.assertRaisesRegex(DTOValidationError, "duplicate field"):
            SolverEpisodeDTO.from_json_bytes(duplicate_member)


if __name__ == "__main__":
    unittest.main()
