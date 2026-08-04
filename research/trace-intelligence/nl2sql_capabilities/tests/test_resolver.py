from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.dto import (  # noqa: E402
    SolverEpisodeDTO,
    canonical_json_bytes,
    encode_base64url,
)
from nl2sql_capabilities.resolver import (  # noqa: E402
    Ed25519GoldSigner,
    EvaluatorGoldRequestDTO,
    ResolverCore,
    ResolverEpisodeBinding,
    ResolverError,
    SupervisorEpisodeRequestDTO,
    verify_evaluator_gold_envelope,
)


NOW_MS = 1_780_000_000_000
EXPIRES_MS = NOW_MS + 60_000
STAGE_EPISODE_REF = encode_base64url(bytes(range(32)))
EVALUATOR_DB_HANDLE = encode_base64url(bytes(range(32, 64)))
H = {
    "stage": "1" * 64,
    "database": "2" * 64,
    "cohort": "3" * 64,
    "dataset": "4" * 64,
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _solver_episode() -> SolverEpisodeDTO:
    artifact = "Use explicit joins and verify aggregate grain."
    return SolverEpisodeDTO.from_dict(
        {
            "schema_version": "fg-solver-episode-v1",
            "question": "How many active accounts are there?",
            "official_instructions": "Return one read-only query.",
            "authorized_database_handle": {
                "handle": encode_base64url(bytes(range(64, 96))),
                "broker_protocol_version": "fg-governed-sql-tool-v1",
                "authorization_epoch_ref_sha256": "5" * 64,
                "authority_snapshot_sha256": "6" * 64,
                "expires_at_unix_ms": EXPIRES_MS,
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
    )


def _gold_material() -> dict[str, object]:
    alternatives = [
        "SELECT COUNT(*) AS n FROM accounts WHERE status = 'active'"
    ]
    return {
        "source_task_id": "SOURCE_TASK_CANARY",
        "source_locator": {
            "source_file_sha256": "7" * 64,
            "source_row_0based": 24,
        },
        "question_sha256": _sha256_text(
            "How many active accounts are there?"
        ),
        "official_instructions_sha256": _sha256_text(
            "Return one read-only query."
        ),
        "gold_sql_alternatives": alternatives,
        "gold_sql_sha256": hashlib.sha256(
            canonical_json_bytes(alternatives)
        ).hexdigest(),
        "evaluator_database_handle": EVALUATOR_DB_HANDLE,
        "adjudication": {
            "classification": "primary_quality_eligible",
            "primary_quality_eligible": True,
            "required_sensitive_entitlements": [],
        },
        "cohort_manifest_sha256": H["cohort"],
        "dataset_manifest_sha256": H["dataset"],
    }


def _binding(
    solver_factory,
    gold_factory,
) -> ResolverEpisodeBinding:
    return ResolverEpisodeBinding(
        experiment_id="defog-sql-factorial-v3",
        fold_id="fold-0",
        stage_role="hidden_test",
        stage_manifest_sha256=H["stage"],
        stage_episode_ref=STAGE_EPISODE_REF,
        database_snapshot_sha256=H["database"],
        question_sha256=_sha256_text(
            "How many active accounts are there?"
        ),
        official_instructions_sha256=_sha256_text(
            "Return one read-only query."
        ),
        expires_at_unix_ms=EXPIRES_MS,
        solver_episode_factory=solver_factory,
        evaluator_gold_factory=gold_factory,
    )


def _request_payload(schema_version: str, nonce_byte: int) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "request_nonce": encode_base64url(bytes([nonce_byte]) * 16),
        "experiment_id": "defog-sql-factorial-v3",
        "fold_id": "fold-0",
        "stage_role": "hidden_test",
        "stage_manifest_sha256": H["stage"],
        "stage_episode_ref": STAGE_EPISODE_REF,
        "database_snapshot_sha256": H["database"],
    }


class ResolverCoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.signing_key = Ed25519PrivateKey.generate()
        self.now_ms = NOW_MS
        self.solver_calls = 0
        self.gold_calls = 0

        def solver_factory():
            self.solver_calls += 1
            return _solver_episode()

        def gold_factory():
            self.gold_calls += 1
            return _gold_material()

        self.resolver = ResolverCore(
            gold_signer=Ed25519GoldSigner(
                private_key=self.signing_key,
                key_id="defog-resolver-research-v1",
            ),
            clock_unix_ms=lambda: self.now_ms,
        )
        self.capabilities = self.resolver.register_episode(
            _binding(solver_factory, gold_factory)
        )

    def supervisor_request(self, nonce_byte: int = 1):
        return SupervisorEpisodeRequestDTO.from_dict(
            _request_payload("fg-resolver-solver-request-v1", nonce_byte)
        )

    def evaluator_request(self, nonce_byte: int = 2):
        return EvaluatorGoldRequestDTO.from_dict(
            _request_payload("fg-resolver-gold-request-v1", nonce_byte)
        )

    def test_authorized_methods_return_only_their_closed_content(self) -> None:
        solver_episode = self.resolver.issue_solver_episode(
            peer_role="supervisor",
            capability_token=self.capabilities.supervisor_token,
            request=self.supervisor_request(),
        )
        self.assertIs(type(solver_episode), SolverEpisodeDTO)
        solver_bytes = solver_episode.canonical_bytes()
        for canary in (
            b"SOURCE_TASK_CANARY",
            b"gold_sql",
            b"evaluator_database_handle",
            b"adjudication",
            STAGE_EPISODE_REF.encode("ascii"),
        ):
            self.assertNotIn(canary, solver_bytes)
        self.assertEqual((1, 0), (self.solver_calls, self.gold_calls))

        gold = self.resolver.resolve_gold(
            peer_role="evaluator",
            capability_token=self.capabilities.evaluator_token,
            request=self.evaluator_request(),
        )
        verified = verify_evaluator_gold_envelope(
            gold,
            public_key=self.signing_key.public_key(),
            expected_key_id="defog-resolver-research-v1",
        )
        self.assertEqual("SOURCE_TASK_CANARY", verified["source_task_id"])
        self.assertEqual(STAGE_EPISODE_REF, verified["stage_episode_ref"])
        gold_bytes = canonical_json_bytes(gold)
        for token in (
            self.capabilities.supervisor_token,
            self.capabilities.evaluator_token,
        ):
            self.assertNotIn(token.encode("ascii"), solver_bytes)
            self.assertNotIn(token.encode("ascii"), gold_bytes)
        self.assertEqual((1, 1), (self.solver_calls, self.gold_calls))

    def test_roles_and_method_tokens_reject_before_materializing_content(
        self,
    ) -> None:
        for role in ("evaluator", "broker", "solver"):
            with self.subTest(method="issue", role=role):
                with self.assertRaisesRegex(ResolverError, "peer role"):
                    self.resolver.issue_solver_episode(
                        peer_role=role,
                        capability_token=self.capabilities.supervisor_token,
                        request=self.supervisor_request(),
                    )
        for role in ("supervisor", "broker", "solver"):
            with self.subTest(method="gold", role=role):
                with self.assertRaisesRegex(ResolverError, "peer role"):
                    self.resolver.resolve_gold(
                        peer_role=role,
                        capability_token=self.capabilities.evaluator_token,
                        request=self.evaluator_request(),
                    )

        for method, token in (
            ("issue", self.capabilities.evaluator_token),
            ("gold", self.capabilities.supervisor_token),
            ("issue", encode_base64url(b"x" * 32)),
            ("gold", encode_base64url(b"y" * 32)),
        ):
            with self.subTest(method=method):
                with self.assertRaisesRegex(
                    ResolverError, "unknown or belongs to another method"
                ):
                    if method == "issue":
                        self.resolver.issue_solver_episode(
                            peer_role="supervisor",
                            capability_token=token,
                            request=self.supervisor_request(),
                        )
                    else:
                        self.resolver.resolve_gold(
                            peer_role="evaluator",
                            capability_token=token,
                            request=self.evaluator_request(),
                        )
        with self.assertRaisesRegex(ResolverError, "exact request DTO"):
            self.resolver.issue_solver_episode(
                peer_role="supervisor",
                capability_token=self.capabilities.supervisor_token,
                request=self.evaluator_request(),  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ResolverError, "exact request DTO"):
            self.resolver.resolve_gold(
                peer_role="evaluator",
                capability_token=self.capabilities.evaluator_token,
                request=self.supervisor_request(),  # type: ignore[arg-type]
            )
        self.assertNotEqual(
            self.capabilities.supervisor_token,
            self.capabilities.evaluator_token,
        )
        self.assertFalse(hasattr(self.resolver, "dispatch"))
        self.assertFalse(hasattr(self.resolver, "handle"))
        self.assertEqual((0, 0), (self.solver_calls, self.gold_calls))

    def test_nonce_stage_episode_snapshot_and_expiry_are_bound(self) -> None:
        invalid_bindings = (
            ("experiment_id", "other-experiment"),
            ("fold_id", "fold-1"),
            ("stage_role", "visible_selection"),
            ("stage_manifest_sha256", "9" * 64),
            (
                "stage_episode_ref",
                encode_base64url(bytes(range(1, 33))),
            ),
            ("database_snapshot_sha256", "8" * 64),
        )
        for index, (field, value) in enumerate(invalid_bindings, start=10):
            with self.subTest(field=field):
                payload = _request_payload(
                    "fg-resolver-solver-request-v1", index
                )
                payload[field] = value
                request = SupervisorEpisodeRequestDTO.from_dict(payload)
                with self.assertRaisesRegex(
                    ResolverError, f"request {field}"
                ):
                    self.resolver.issue_solver_episode(
                        peer_role="supervisor",
                        capability_token=self.capabilities.supervisor_token,
                        request=request,
                    )
        self.assertEqual((0, 0), (self.solver_calls, self.gold_calls))

        request = self.supervisor_request(nonce_byte=20)
        self.resolver.issue_solver_episode(
            peer_role="supervisor",
            capability_token=self.capabilities.supervisor_token,
            request=request,
        )
        with self.assertRaisesRegex(ResolverError, "nonce"):
            self.resolver.issue_solver_episode(
                peer_role="supervisor",
                capability_token=self.capabilities.supervisor_token,
                request=request,
            )
        self.assertEqual((1, 0), (self.solver_calls, self.gold_calls))

        self.now_ms = EXPIRES_MS
        with self.assertRaisesRegex(ResolverError, "expired"):
            self.resolver.resolve_gold(
                peer_role="evaluator",
                capability_token=self.capabilities.evaluator_token,
                request=self.evaluator_request(nonce_byte=21),
            )
        self.assertEqual((1, 0), (self.solver_calls, self.gold_calls))

    def test_gold_envelope_is_closed_signed_and_request_bound(self) -> None:
        request = self.evaluator_request(nonce_byte=30)
        envelope = self.resolver.resolve_gold(
            peer_role="evaluator",
            capability_token=self.capabilities.evaluator_token,
            request=request,
        )
        payload = verify_evaluator_gold_envelope(
            envelope,
            public_key=self.signing_key.public_key(),
            expected_key_id="defog-resolver-research-v1",
        )
        self.assertEqual(request.request_nonce, payload["request_nonce"])
        self.assertEqual(
            "defog-sql-factorial-v3", payload["experiment_id"]
        )
        self.assertEqual("fold-0", payload["fold_id"])
        self.assertEqual("hidden_test", payload["stage_role"])
        self.assertEqual(H["stage"], payload["stage_manifest_sha256"])
        self.assertEqual(H["database"], payload["database_snapshot_sha256"])
        self.assertEqual(
            EXPIRES_MS,
            payload["resolver_capability_expires_at_unix_ms"],
        )

        schema_path = (
            TRACE_INTELLIGENCE_ROOT
            / "nl2sql_capabilities"
            / "schemas"
            / "evaluator_gold.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(envelope)

        tampered = copy.deepcopy(envelope)
        tampered["payload"]["source_task_id"] = "REPLACED"
        with self.assertRaisesRegex(ResolverError, "payload hash"):
            verify_evaluator_gold_envelope(
                tampered,
                public_key=self.signing_key.public_key(),
                expected_key_id="defog-resolver-research-v1",
            )
        with self.assertRaisesRegex(ResolverError, "verification failed"):
            verify_evaluator_gold_envelope(
                envelope,
                public_key=Ed25519PrivateKey.generate().public_key(),
                expected_key_id="defog-resolver-research-v1",
            )
        unknown = copy.deepcopy(envelope)
        unknown["payload"]["raw_database_dsn"] = "CANARY"
        with self.assertRaisesRegex(ResolverError, "unknown field"):
            verify_evaluator_gold_envelope(
                unknown,
                public_key=self.signing_key.public_key(),
                expected_key_id="defog-resolver-research-v1",
            )

        class ExpiringSigner:
            def sign(inner_self, signed_payload):
                self.now_ms = EXPIRES_MS
                return Ed25519GoldSigner(
                    private_key=self.signing_key,
                    key_id="defog-resolver-research-v1",
                ).sign(signed_payload)

        expiring_resolver = ResolverCore(
            gold_signer=ExpiringSigner(),
            clock_unix_ms=lambda: self.now_ms,
        )
        self.now_ms = NOW_MS
        expiring_capabilities = expiring_resolver.register_episode(
            _binding(_solver_episode, _gold_material)
        )
        with self.assertRaisesRegex(ResolverError, "expired"):
            expiring_resolver.resolve_gold(
                peer_role="evaluator",
                capability_token=expiring_capabilities.evaluator_token,
                request=self.evaluator_request(nonce_byte=31),
            )

    def test_request_and_response_schemas_are_recursively_closed(self) -> None:
        schema_dir = (
            TRACE_INTELLIGENCE_ROOT
            / "nl2sql_capabilities"
            / "schemas"
        )
        documents = {
            "supervisor_episode_request.schema.json": (
                self.supervisor_request().to_dict()
            ),
            "evaluator_gold_request.schema.json": (
                self.evaluator_request().to_dict()
            ),
            "evaluator_gold.schema.json": self.resolver.resolve_gold(
                peer_role="evaluator",
                capability_token=self.capabilities.evaluator_token,
                request=self.evaluator_request(nonce_byte=50),
            ),
        }
        for name, document in documents.items():
            with self.subTest(schema=name):
                schema = json.loads(
                    (schema_dir / name).read_text(encoding="utf-8")
                )
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(document)
                self._assert_object_schemas_closed(schema)

        unknown = self.supervisor_request().to_dict()
        unknown["method"] = "resolve_gold"
        with self.assertRaisesRegex(ResolverError, "unknown field"):
            SupervisorEpisodeRequestDTO.from_dict(unknown)

    def test_protected_content_must_match_the_registered_episode(self) -> None:
        bad_gold = _gold_material()
        bad_gold["question_sha256"] = "9" * 64
        gold_resolver = ResolverCore(
            gold_signer=Ed25519GoldSigner(
                private_key=self.signing_key,
                key_id="defog-resolver-research-v1",
            ),
            clock_unix_ms=lambda: NOW_MS,
        )
        gold_capabilities = gold_resolver.register_episode(
            _binding(_solver_episode, lambda: bad_gold)
        )
        with self.assertRaisesRegex(
            ResolverError, "gold question_sha256.*episode binding"
        ):
            gold_resolver.resolve_gold(
                peer_role="evaluator",
                capability_token=gold_capabilities.evaluator_token,
                request=self.evaluator_request(nonce_byte=40),
            )

        changed_solver = _solver_episode().to_dict()
        changed_solver["question"] = "A different question"
        solver_resolver = ResolverCore(
            gold_signer=Ed25519GoldSigner(
                private_key=self.signing_key,
                key_id="defog-resolver-research-v1",
            ),
            clock_unix_ms=lambda: NOW_MS,
        )
        solver_capabilities = solver_resolver.register_episode(
            _binding(
                lambda: SolverEpisodeDTO.from_dict(changed_solver),
                _gold_material,
            )
        )
        with self.assertRaisesRegex(
            ResolverError, "solver question_sha256.*episode binding"
        ):
            solver_resolver.issue_solver_episode(
                peer_role="supervisor",
                capability_token=solver_capabilities.supervisor_token,
                request=self.supervisor_request(nonce_byte=41),
            )

        unknown_gold = _gold_material()
        unknown_gold["raw_dsn"] = "postgres://CANARY"
        strict_resolver = ResolverCore(
            gold_signer=Ed25519GoldSigner(
                private_key=self.signing_key,
                key_id="defog-resolver-research-v1",
            ),
            clock_unix_ms=lambda: NOW_MS,
        )
        strict_capabilities = strict_resolver.register_episode(
            _binding(_solver_episode, lambda: unknown_gold)
        )
        with self.assertRaisesRegex(ResolverError, "unknown field"):
            strict_resolver.resolve_gold(
                peer_role="evaluator",
                capability_token=strict_capabilities.evaluator_token,
                request=self.evaluator_request(nonce_byte=42),
            )

    def _assert_object_schemas_closed(self, value: object) -> None:
        if type(value) is dict:
            if value.get("type") == "object":
                self.assertIs(False, value.get("additionalProperties"))
            for child in value.values():
                self._assert_object_schemas_closed(child)
        elif type(value) is list:
            for child in value:
                self._assert_object_schemas_closed(child)
