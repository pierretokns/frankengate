from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from jsonschema import Draft202012Validator


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.dto import (  # noqa: E402
    canonical_json_bytes,
    derive_stage_episode_ref,
    encode_base64url,
)
from nl2sql_capabilities.stage_sealer import (  # noqa: E402
    HiddenEnvelopeReplayGuard,
    REPLAY_GUARD_LIMITATION,
    StageSealError,
    StageReplayError,
    build_stage_commitment,
    open_hidden_stage_envelope,
    ordered_episode_commitment_sha256,
    seal_hidden_stage_manifest,
    sign_candidate_artifact_receipt,
    sign_stage_manifest,
    sign_hidden_unseal_authorization,
    verify_stage_commitment,
    verify_stage_manifest,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64
STAGE_ID_KEY = bytes(range(32))
_AUTO_AUTHORIZATION = object()


def _payload(
    *,
    stage_role: str = "hidden_test",
    fold_id: str = "fold-0",
) -> dict[str, object]:
    source_task_id = "source/task/17"
    payload: dict[str, object] = {
        "schema_version": "fg-stage-manifest-v1",
        "experiment_id": "defog-sql-factorial-v3",
        "fold_id": fold_id,
        "stage_role": stage_role,
        "manifest_sequence": 3,
        "created_at_unix_ms": 1_780_000_000_000,
        "parent_design_sha256": SHA_A,
        "cohort_manifest_sha256": SHA_B,
        "dataset_manifest_sha256": SHA_C,
        "prompt_contract_sha256": SHA_D,
        "tool_contract_sha256": SHA_A,
        "model_manifest_sha256": SHA_B,
        "authority_snapshot_sha256": SHA_C,
        "policy_version_sha256": SHA_D,
        "comparator_version_sha256": SHA_A,
        "database_snapshots": [
            {"database_ref": "broker", "snapshot_sha256": SHA_B}
        ],
        "artifact_set_sha256": SHA_C,
        "selection_gate_contract_sha256": SHA_D,
        "episode_count": 1,
        "ordered_episode_commitment_sha256": "0" * 64,
        "episodes": [
            {
                "stage_episode_ref": derive_stage_episode_ref(
                    key=STAGE_ID_KEY,
                    experiment_id="defog-sql-factorial-v3",
                    fold_id=fold_id,
                    stage_role=stage_role,
                    source_task_id=source_task_id,
                ),
                "source_task_id": source_task_id,
                "source_file_sha256": SHA_B,
                "source_row_0based": 11,
                "question_sha256": SHA_C,
                "official_instructions_sha256": SHA_D,
                "gold_sql_sha256": SHA_A,
                "database_ref": "broker",
                "query_category": "advanced",
                "primary_quality_eligible": True,
                "adjudication_ref": None,
                "paired_seed": 123456,
                "arm_order": ["expert", "placebo", "baseline"],
            }
        ],
        "allowed_runtime_roles": ["resolver", "evaluator"],
    }
    payload["ordered_episode_commitment_sha256"] = (
        ordered_episode_commitment_sha256(payload["episodes"])
    )
    return payload


class StageSealerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_signing_key = Ed25519PrivateKey.generate()
        self.gate_signing_key = Ed25519PrivateKey.generate()
        self.recipient_key = X25519PrivateKey.generate()
        self.proposer_keys = {
            "defog-proposer-fold-0": Ed25519PrivateKey.generate(),
            "defog-proposer-fold-1": Ed25519PrivateKey.generate(),
        }

    def test_signed_manifest_is_canonical_closed_and_source_bound(self) -> None:
        payload = _payload()
        signed = sign_stage_manifest(
            payload,
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )
        verified = verify_stage_manifest(
            signed,
            public_key=self.stage_signing_key.public_key(),
            expected_key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
            expected_experiment_id="defog-sql-factorial-v3",
            expected_fold_id="fold-0",
            expected_stage_role="hidden_test",
        )
        self.assertEqual(payload, verified)

        unknown = copy.deepcopy(payload)
        unknown["gold_sql"] = "SELECT enterprise_secret FROM payroll"
        with self.assertRaisesRegex(StageSealError, "unknown field"):
            sign_stage_manifest(
                unknown,
                private_key=self.stage_signing_key,
                key_id="defog-stage-sealer-v1",
                stage_id_key=STAGE_ID_KEY,
            )

        rebound = copy.deepcopy(payload)
        rebound["episodes"][0]["source_task_id"] = "source/task/18"
        with self.assertRaisesRegex(StageSealError, "stage_episode_ref"):
            sign_stage_manifest(
                rebound,
                private_key=self.stage_signing_key,
                key_id="defog-stage-sealer-v1",
                stage_id_key=STAGE_ID_KEY,
            )

    def test_manifest_tamper_wrong_key_and_context_replay_fail_closed(self) -> None:
        signed = sign_stage_manifest(
            _payload(),
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )

        tampered = copy.deepcopy(signed)
        tampered["payload"]["created_at_unix_ms"] += 1
        with self.assertRaisesRegex(StageSealError, "payload hash"):
            verify_stage_manifest(
                tampered,
                public_key=self.stage_signing_key.public_key(),
                expected_key_id="defog-stage-sealer-v1",
            )

        with self.assertRaisesRegex(StageSealError, "signature verification"):
            verify_stage_manifest(
                signed,
                public_key=Ed25519PrivateKey.generate().public_key(),
                expected_key_id="defog-stage-sealer-v1",
            )

        for field, expected in (
            ("expected_experiment_id", "other-experiment"),
            ("expected_fold_id", "fold-1"),
            ("expected_stage_role", "visible_selection"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(StageSealError, "expected context"):
                    verify_stage_manifest(
                        signed,
                        public_key=self.stage_signing_key.public_key(),
                        expected_key_id="defog-stage-sealer-v1",
                        **{field: expected},
                    )

    def test_public_commitment_is_signed_and_content_free(self) -> None:
        signed = sign_stage_manifest(
            _payload(),
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )
        commitment = build_stage_commitment(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            commitment_private_key=self.stage_signing_key,
            commitment_key_id="defog-stage-sealer-v1",
        )
        verified = verify_stage_commitment(
            commitment,
            public_key=self.stage_signing_key.public_key(),
            expected_key_id="defog-stage-sealer-v1",
            expected_experiment_id="defog-sql-factorial-v3",
            expected_fold_id="fold-0",
            expected_stage_role="hidden_test",
        )
        self.assertEqual(1, verified["episode_count"])

        public_bytes = json.dumps(commitment, sort_keys=True).encode("utf-8")
        for forbidden in (
            b"source/task/17",
            b"source_task_id",
            b"source_file",
            b"gold_sql",
            b"query_category",
            b"stage_episode_ref",
            b"episodes",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, public_bytes)

    def test_hidden_manifest_round_trips_only_for_bound_recipient(self) -> None:
        signed = sign_stage_manifest(
            _payload(),
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )
        envelope = seal_hidden_stage_manifest(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            recipient_public_key=self.recipient_key.public_key(),
            recipient_key_id="defog-evaluator-unseal-v1",
            envelope_private_key=self.stage_signing_key,
            envelope_key_id="defog-stage-sealer-v1",
        )
        serialized = json.dumps(envelope, sort_keys=True)
        self.assertNotIn("source/task/17", serialized)
        self.assertNotIn("source_task_id", serialized)
        self.assertNotIn("gold_sql_sha256", serialized)

        opened = self._open(
            envelope, replay_guard=HiddenEnvelopeReplayGuard()
        )
        self.assertEqual(signed, opened)

        with self.assertRaisesRegex(StageSealError, "recipient"):
            self._open(
                envelope,
                recipient_private_key=X25519PrivateKey.generate(),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )

    def test_hidden_envelope_tamper_context_replay_and_reuse_are_rejected(
        self,
    ) -> None:
        signed = sign_stage_manifest(
            _payload(),
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )
        envelope = seal_hidden_stage_manifest(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            recipient_public_key=self.recipient_key.public_key(),
            recipient_key_id="defog-evaluator-unseal-v1",
            envelope_private_key=self.stage_signing_key,
            envelope_key_id="defog-stage-sealer-v1",
        )

        tampered = copy.deepcopy(envelope)
        ciphertext = tampered["payload"]["ciphertext_base64url"]
        tampered["payload"]["ciphertext_base64url"] = (
            ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
        )
        with self.assertRaisesRegex(StageSealError, "ciphertext hash"):
            self._open(tampered, replay_guard=HiddenEnvelopeReplayGuard())

        with self.assertRaisesRegex(StageSealError, "expected context"):
            self._open(
                envelope,
                expected_fold_id="fold-1",
                replay_guard=HiddenEnvelopeReplayGuard(),
            )

        guard = HiddenEnvelopeReplayGuard()
        self._open(envelope, replay_guard=guard)
        with self.assertRaisesRegex(
            StageReplayError, "already been opened"
        ):
            self._open(envelope, replay_guard=guard)

        resealed = seal_hidden_stage_manifest(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            recipient_public_key=self.recipient_key.public_key(),
            recipient_key_id="defog-evaluator-unseal-v1",
            envelope_private_key=self.stage_signing_key,
            envelope_key_id="defog-stage-sealer-v1",
        )
        with self.assertRaisesRegex(
            StageReplayError, "already been opened"
        ):
            self._open(resealed, replay_guard=guard)

        extra = copy.deepcopy(envelope)
        extra["payload"]["header"]["source_task_id"] = "leaked"
        with self.assertRaisesRegex(StageSealError, "unknown field"):
            self._open(extra, replay_guard=HiddenEnvelopeReplayGuard())

    def test_unseal_requires_valid_passed_gate_and_exact_frozen_inputs(
        self,
    ) -> None:
        signed = sign_stage_manifest(
            _payload(),
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )
        envelope = seal_hidden_stage_manifest(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            recipient_public_key=self.recipient_key.public_key(),
            recipient_key_id="defog-evaluator-unseal-v1",
            envelope_private_key=self.stage_signing_key,
            envelope_key_id="defog-stage-sealer-v1",
        )

        with self.assertRaisesRegex(StageSealError, "authorization is required"):
            self._open(
                envelope,
                authorization=None,
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(StageSealError, "did not authorize"):
            self._open(
                envelope,
                authorization=self._authorization(envelope, passed=False),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(StageSealError, "signature verification"):
            self._open(
                envelope,
                authorization=self._authorization(
                    envelope, private_key=Ed25519PrivateKey.generate()
                ),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(StageSealError, "key ID"):
            self._open(
                envelope,
                authorization=self._authorization(
                    envelope, key_id="other-gate"
                ),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(StageSealError, "fold_id does not match"):
            self._open(
                envelope,
                authorization=self._authorization(
                    envelope, fold_id="fold-1"
                ),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(
            StageSealError, "hidden_envelope_sha256 does not match"
        ):
            self._open(
                envelope,
                authorization=self._authorization(
                    envelope, envelope_sha256="0" * 64
                ),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(
            StageSealError, "hidden_stage_commitment_sha256 does not match"
        ):
            self._open(
                envelope,
                expected_hidden_stage_commitment_sha256="9" * 64,
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        with self.assertRaisesRegex(
            StageSealError, "selection manifest hash does not match"
        ):
            self._open(
                envelope,
                expected_selection_manifest_sha256="9" * 64,
                replay_guard=HiddenEnvelopeReplayGuard(),
            )

        mutated_candidates = copy.deepcopy(self._candidate_artifacts())
        mutated_candidates[0]["payload"]["artifact_sha256"] = "9" * 64
        with self.assertRaisesRegex(StageSealError, "candidate artifact"):
            self._open(
                envelope,
                expected_candidate_artifacts=mutated_candidates,
                replay_guard=HiddenEnvelopeReplayGuard(),
            )

        untrusted_proposer_keys = dict(self.proposer_keys)
        untrusted_proposer_keys["defog-proposer-fold-0"] = (
            Ed25519PrivateKey.generate()
        )
        with self.assertRaisesRegex(
            StageSealError, "candidate artifact signer"
        ):
            self._open(
                envelope,
                authorization=self._authorization(
                    envelope,
                    candidate_artifacts=self._candidate_artifacts(
                        private_keys=untrusted_proposer_keys
                    ),
                ),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )

        mutated_bindings = self._bindings()
        mutated_bindings["model_manifest_sha256"] = "9" * 64
        with self.assertRaisesRegex(StageSealError, "runtime bindings"):
            self._open(
                envelope,
                expected_bindings=mutated_bindings,
                replay_guard=HiddenEnvelopeReplayGuard(),
            )

        with self.assertRaisesRegex(StageReplayError, "prior"):
            self._open(
                envelope,
                authorization=self._authorization(
                    envelope, prior_unseal_receipt_sha256="9" * 64
                ),
                replay_guard=HiddenEnvelopeReplayGuard(),
            )
        self.assertIn("not crash-durable", REPLAY_GUARD_LIMITATION)
        self.assertIn("durable receipt ledger", REPLAY_GUARD_LIMITATION)

    def test_all_stage_artifacts_validate_against_recursively_closed_schemas(
        self,
    ) -> None:
        signed = sign_stage_manifest(
            _payload(),
            private_key=self.stage_signing_key,
            key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
        )
        commitment = build_stage_commitment(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            commitment_private_key=self.stage_signing_key,
            commitment_key_id="defog-stage-sealer-v1",
        )
        envelope = seal_hidden_stage_manifest(
            signed,
            manifest_public_key=self.stage_signing_key.public_key(),
            manifest_key_id="defog-stage-sealer-v1",
            recipient_public_key=self.recipient_key.public_key(),
            recipient_key_id="defog-evaluator-unseal-v1",
            envelope_private_key=self.stage_signing_key,
            envelope_key_id="defog-stage-sealer-v1",
        )
        authorization = self._authorization(envelope)
        schema_dir = (
            TRACE_INTELLIGENCE_ROOT
            / "nl2sql_capabilities"
            / "schemas"
        )
        documents = {
            "stage_manifest.schema.json": signed,
            "stage_commitment.schema.json": commitment,
            "hidden_stage_envelope.schema.json": envelope,
            "hidden_unseal_authorization.schema.json": authorization,
        }
        for name, document in documents.items():
            with self.subTest(schema=name):
                schema = json.loads(
                    (schema_dir / name).read_text(encoding="utf-8")
                )
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(document)
                self._assert_object_schemas_closed(schema)

    def _open(
        self,
        envelope: dict[str, object],
        *,
        replay_guard: HiddenEnvelopeReplayGuard,
        expected_fold_id: str = "fold-0",
        recipient_private_key: X25519PrivateKey | None = None,
        authorization: object = _AUTO_AUTHORIZATION,
        expected_candidate_artifacts: list[dict[str, object]] | None = None,
        expected_bindings: dict[str, str] | None = None,
        expected_hidden_stage_commitment_sha256: str = SHA_E,
        expected_selection_manifest_sha256: str = SHA_F,
    ) -> dict[str, object]:
        if authorization is _AUTO_AUTHORIZATION:
            authorization = self._authorization(envelope)
        return open_hidden_stage_envelope(
            envelope,
            unseal_authorization=authorization,
            unseal_authorization_public_key=(
                self.gate_signing_key.public_key()
            ),
            expected_unseal_authorization_key_id=(
                "defog-selection-gate-v1"
            ),
            expected_hidden_stage_commitment_sha256=(
                expected_hidden_stage_commitment_sha256
            ),
            expected_selection_manifest_sha256=(
                expected_selection_manifest_sha256
            ),
            expected_candidate_artifacts=(
                expected_candidate_artifacts or self._candidate_artifacts()
            ),
            candidate_artifact_public_keys={
                key_id: private_key.public_key()
                for key_id, private_key in self.proposer_keys.items()
            },
            expected_bindings=expected_bindings or self._bindings(),
            recipient_private_key=recipient_private_key or self.recipient_key,
            expected_recipient_key_id="defog-evaluator-unseal-v1",
            envelope_public_key=self.stage_signing_key.public_key(),
            expected_envelope_key_id="defog-stage-sealer-v1",
            manifest_public_key=self.stage_signing_key.public_key(),
            expected_manifest_key_id="defog-stage-sealer-v1",
            stage_id_key=STAGE_ID_KEY,
            expected_experiment_id="defog-sql-factorial-v3",
            expected_fold_id=expected_fold_id,
            replay_guard=replay_guard,
        )

    def _assert_object_schemas_closed(self, value: object) -> None:
        if type(value) is dict:
            if value.get("type") == "object":
                self.assertIs(
                    False,
                    value.get("additionalProperties"),
                    msg=f"open object schema: {value}",
                )
            for child in value.values():
                self._assert_object_schemas_closed(child)
        elif type(value) is list:
            for child in value:
                self._assert_object_schemas_closed(child)

    def _authorization(
        self,
        envelope: dict[str, object],
        *,
        passed: bool = True,
        candidate_artifacts: list[dict[str, object]] | None = None,
        private_key: Ed25519PrivateKey | None = None,
        envelope_sha256: str | None = None,
        key_id: str = "defog-selection-gate-v1",
        fold_id: str = "fold-0",
        prior_unseal_receipt_sha256: str | None = None,
    ) -> dict[str, object]:
        payload = {
            "schema_version": "fg-hidden-unseal-authorization-v1",
            "experiment_id": "defog-sql-factorial-v3",
            "fold_id": fold_id,
            "authorization_sequence": 1,
            "authorization_nonce": encode_base64url(bytes(range(32))),
            "authorized_at_unix_ms": 1_780_000_100_000,
            "hidden_envelope_sha256": envelope_sha256
            or hashlib.sha256(canonical_json_bytes(envelope)).hexdigest(),
            "hidden_stage_commitment_sha256": SHA_E,
            "selection_gate_receipt": {
                "schema_version": "fg-selection-gate-receipt-v1",
                "passed": passed,
                "selection_manifest_sha256": SHA_F,
                "selection_result_sha256": SHA_A,
                "preregistered_gate_decision": (
                    "unseal" if passed else "do_not_unseal"
                ),
            },
            "candidate_artifacts": candidate_artifacts
            or self._candidate_artifacts(),
            "bindings": self._bindings(),
            "prior_hidden_unseal_receipt_sha256": (
                prior_unseal_receipt_sha256
            ),
        }
        return sign_hidden_unseal_authorization(
            payload,
            private_key=private_key or self.gate_signing_key,
            key_id=key_id,
        )

    def _candidate_artifacts(
        self,
        *,
        private_keys: dict[str, Ed25519PrivateKey] | None = None,
    ) -> list[dict[str, object]]:
        keys = private_keys or self.proposer_keys
        return [
            sign_candidate_artifact_receipt(
                {
                    "schema_version": "fg-candidate-artifact-receipt-v1",
                    "experiment_id": "defog-sql-factorial-v3",
                    "fold_id": "fold-0",
                    "artifact_sha256": SHA_A,
                    "evidence_manifest_sha256": SHA_C,
                },
                private_key=keys["defog-proposer-fold-0"],
                key_id="defog-proposer-fold-0",
            ),
            sign_candidate_artifact_receipt(
                {
                    "schema_version": "fg-candidate-artifact-receipt-v1",
                    "experiment_id": "defog-sql-factorial-v3",
                    "fold_id": "fold-1",
                    "artifact_sha256": SHA_D,
                    "evidence_manifest_sha256": SHA_F,
                },
                private_key=keys["defog-proposer-fold-1"],
                key_id="defog-proposer-fold-1",
            ),
        ]

    @staticmethod
    def _bindings() -> dict[str, str]:
        return {
            "model_manifest_sha256": SHA_A,
            "prompt_contract_sha256": SHA_B,
            "tool_contract_sha256": SHA_C,
            "policy_version_sha256": SHA_D,
            "comparator_version_sha256": SHA_E,
            "database_snapshots_sha256": SHA_F,
            "authority_snapshot_sha256": SHA_A,
        }
