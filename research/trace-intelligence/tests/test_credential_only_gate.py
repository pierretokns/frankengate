import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import credential_only_gate as gate  # noqa: E402


class CredentialOnlyGateTest(unittest.TestCase):
    RECEIPT_KEY = b"test-only-credential-receipt-key-32b"

    def transform(self, source, **kwargs):
        return gate.transform_credentials(
            source,
            receipt_hmac_key=self.RECEIPT_KEY,
            scope_ref="tenant:test",
            purpose="trace_research",
            **kwargs,
        )

    def test_structured_gate_removes_credentials_and_preserves_pii(self):
        source = {
            "email": "person@example.com",
            "phone": "+1 212 555 0100",
            "employee_id": "E-1234",
            "token_count": 4096,
            "git_sha": "a" * 40,
            "Authorization": "Bearer secret-access-token",
            "x-bf-vk": "vk-live-secret",
            "password": "database-password",
        }

        clean, receipt = self.transform(
            source,
            boundary="model_input",
        )

        self.assertEqual("person@example.com", clean["email"])
        self.assertEqual("+1 212 555 0100", clean["phone"])
        self.assertEqual("E-1234", clean["employee_id"])
        self.assertEqual(4096, clean["token_count"])
        self.assertEqual("a" * 40, clean["git_sha"])
        self.assertEqual(
            "[CREDENTIAL:AUTHORIZATION]",
            clean["Authorization"],
        )
        self.assertEqual(
            "[CREDENTIAL:VIRTUAL_KEY]",
            clean["x-bf-vk"],
        )
        self.assertEqual(
            "[CREDENTIAL:PASSWORD]",
            clean["password"],
        )
        self.assertEqual(3, receipt["transformed_values"])
        self.assertNotIn("secret-access-token", str(receipt))

    def test_gate_does_not_use_broad_token_secret_or_id_substrings(self):
        source = {
            "email": "person@example.com",
            "token_usage": 123,
            "tokenizer": "QwenTokenizer",
            "secretary": "Alice",
            "function_signature": "fn(x: string)",
            "signature_algorithm": "ed25519",
            "public_key": "ssh-ed25519 AAAA...",
            "employee_id": "E-123",
            "trace_id": "7f" * 16,
            "internal_url": "https://internal.example/users/alice",
        }

        clean, receipt = self.transform(
            source,
            boundary="capture",
        )

        self.assertEqual(source, clean)
        self.assertEqual("pass", receipt["disposition"])
        self.assertEqual(0, receipt["transformed_values"])

    def test_gate_removes_bearer_credentials_embedded_in_text_only(self):
        source = {
            "transcript": (
                "email person@example.com\n"
                "Authorization: Bearer abcDEF123_-credential\n"
                "keep project tokenization details"
            )
        }

        clean, receipt = self.transform(
            source,
            boundary="tool_output",
        )

        self.assertIn("person@example.com", clean["transcript"])
        self.assertIn("tokenization details", clean["transcript"])
        self.assertNotIn("abcDEF123_-credential", clean["transcript"])
        self.assertIn(
            "[CREDENTIAL:BEARER_TOKEN]",
            clean["transcript"],
        )
        self.assertEqual(
            {"BEARER_TOKEN": 1},
            receipt["counts_by_class"],
        )

    def test_gate_replaces_known_secret_snapshot_values_in_free_text(self):
        source = {
            "message": (
                "person@example.com used sk-live-enterprise-credential "
                "for the internal test"
            )
        }

        clean, receipt = self.transform(
            source,
            boundary="model_input",
            known_secrets={
                "OPENAI_API_KEY": "sk-live-enterprise-credential"
            },
        )

        self.assertIn("person@example.com", clean["message"])
        self.assertNotIn(
            "sk-live-enterprise-credential",
            clean["message"],
        )
        self.assertIn(
            "[CREDENTIAL:OPENAI_API_KEY]",
            clean["message"],
        )
        self.assertEqual(
            {"OPENAI_API_KEY": 1},
            receipt["counts_by_class"],
        )

    def test_gate_preserves_url_shape_and_removes_dsn_password(self):
        source = {
            "database_url": (
                "postgresql://alice:supersecret@db.internal/app"
                "?sslmode=require"
            ),
            "internal_url": "https://internal.example/users/alice",
        }

        clean, receipt = self.transform(
            source,
            boundary="capture",
        )

        self.assertEqual(
            "postgresql://alice:[CREDENTIAL:DSN_PASSWORD]"
            "@db.internal/app?sslmode=require",
            clean["database_url"],
        )
        self.assertEqual(
            "https://internal.example/users/alice",
            clean["internal_url"],
        )
        self.assertEqual(
            {"DSN_PASSWORD": 1},
            receipt["counts_by_class"],
        )

    def test_gate_replaces_entire_private_key_block(self):
        source = {
            "transcript": (
                "owner person@example.com\n"
                "-----BEGIN PRIVATE KEY-----\n"
                "c2VjcmV0LWtleS1ieXRlcw==\n"
                "-----END PRIVATE KEY-----\n"
                "after"
            )
        }

        clean, receipt = self.transform(
            source,
            boundary="tool_output",
        )

        self.assertEqual(
            "owner person@example.com\n"
            "[CREDENTIAL:PRIVATE_KEY]\n"
            "after",
            clean["transcript"],
        )
        self.assertEqual(
            {"PRIVATE_KEY": 1},
            receipt["counts_by_class"],
        )

    def test_gate_is_idempotent(self):
        first, _ = self.transform(
            {
                "Authorization": "Bearer reusable-secret",
                "email": "person@example.com",
            },
            boundary="capture",
        )
        second, receipt = self.transform(
            first,
            boundary="model_input",
        )

        self.assertEqual(first, second)
        self.assertEqual(0, receipt["transformed_values"])

    def test_final_rescan_fails_closed_when_known_secret_survives(self):
        with self.assertRaises(gate.CredentialGateError):
            gate.verify_credential_free(
                {
                    "message": "leaked sk-live-enterprise-credential",
                },
                boundary="model_input",
                receipt_hmac_key=self.RECEIPT_KEY,
                scope_ref="tenant:test",
                purpose="trace_research",
                known_secrets={
                    "OPENAI_API_KEY": "sk-live-enterprise-credential"
                },
            )

    def test_receipt_is_keyed_content_free_and_purpose_bound(self):
        source = {
            "email": "person@example.com",
            "Authorization": "Bearer reusable-secret",
        }

        _, receipt = self.transform(source, boundary="capture")

        self.assertEqual("tenant:test", receipt["scope_ref"])
        self.assertEqual("trace_research", receipt["purpose"])
        self.assertRegex(receipt["input_hmac_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(receipt["rule_set_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("person@example.com", str(receipt))
        self.assertNotIn("reusable-secret", str(receipt))
        with self.assertRaises(gate.CredentialGateError):
            gate.transform_credentials(
                source,
                boundary="capture",
                receipt_hmac_key=b"short",
                scope_ref="tenant:test",
                purpose="trace_research",
            )

    def test_validated_provider_token_grammars_do_not_use_entropy(self):
        source = {
            "message": (
                "github ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij "
                "huggingface hf_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef "
                "anthropic sk-ant-api03-" + "A" * 48 + " "
                "keep sha " + "a" * 64
            )
        }

        clean, receipt = self.transform(
            source,
            boundary="model_input",
        )

        self.assertNotIn("ghp_", clean["message"])
        self.assertNotIn("hf_", clean["message"])
        self.assertNotIn("sk-ant-api03-", clean["message"])
        self.assertIn("a" * 64, clean["message"])
        self.assertEqual(
            {
                "ANTHROPIC_API_KEY": 1,
                "GITHUB_TOKEN": 1,
                "HUGGINGFACE_TOKEN": 1,
            },
            receipt["counts_by_class"],
        )

    def test_signed_urls_preserve_location_and_remove_only_credentials(self):
        source = {
            "aws": (
                "https://bucket.s3.amazonaws.com/report.csv"
                "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                "&X-Amz-Credential=AKIAEXAMPLE%2F20260730%2Fus-east-1%2Fs3%2Faws4_request"
                "&X-Amz-Date=20260730T120000Z"
                "&X-Amz-Signature=" + "a" * 64
            ),
            "azure": (
                "https://account.blob.core.windows.net/c/report.csv"
                "?sv=2025-01-05&se=2026-07-30T13%3A00%3A00Z"
                "&sp=r&sig=abcdefghijklmnopqrstuvwxyz0123456789%2B%2F%3D"
            ),
            "internal": "https://internal.example/report?signature_algorithm=ed25519",
        }

        clean, receipt = self.transform(source, boundary="capture")

        self.assertIn("bucket.s3.amazonaws.com/report.csv", clean["aws"])
        self.assertIn("X-Amz-Algorithm=AWS4-HMAC-SHA256", clean["aws"])
        self.assertIn(
            "X-Amz-Signature=%5BCREDENTIAL%3AAWS_SIGNED_URL_SIGNATURE%5D",
            clean["aws"],
        )
        self.assertIn("account.blob.core.windows.net/c/report.csv", clean["azure"])
        self.assertIn(
            "sig=%5BCREDENTIAL%3AAZURE_SAS_SIGNATURE%5D",
            clean["azure"],
        )
        self.assertEqual(source["internal"], clean["internal"])
        self.assertEqual(
            {
                "AWS_SIGNED_URL_CREDENTIAL": 1,
                "AWS_SIGNED_URL_SIGNATURE": 1,
                "AZURE_SAS_SIGNATURE": 1,
            },
            receipt["counts_by_class"],
        )

    def test_known_secret_encoded_forms_are_replaced_without_broad_decoding(self):
        source = {
            "raw": "alpha-secret-123",
            "url": "alpha-secret-123".replace("-", "%2D"),
            "base64": "YWxwaGEtc2VjcmV0LTEyMw==",
            "hex": "616c7068612d7365637265742d313233",
            "ordinary_base64": "VGhpcyBpcyBhIGRvY3VtZW50Lg==",
        }

        clean, receipt = self.transform(
            source,
            boundary="index",
            known_secrets={"INTERNAL_SECRET": "alpha-secret-123"},
        )

        self.assertEqual(
            "[CREDENTIAL:INTERNAL_SECRET]",
            clean["raw"],
        )
        self.assertEqual(
            "[CREDENTIAL:INTERNAL_SECRET_URLENCODED]",
            clean["url"],
        )
        self.assertEqual(
            "[CREDENTIAL:INTERNAL_SECRET_BASE64]",
            clean["base64"],
        )
        self.assertEqual(
            "[CREDENTIAL:INTERNAL_SECRET_HEX]",
            clean["hex"],
        )
        self.assertEqual(
            "VGhpcyBpcyBhIGRvY3VtZW50Lg==",
            clean["ordinary_base64"],
        )
        self.assertEqual(4, receipt["transformed_values"])

    def test_jsonl_snapshot_is_credential_clean_before_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "raw.jsonl"
            destination = pathlib.Path(tmp) / "clean.jsonl"
            source.write_text(
                '{"email":"person@example.com","Authorization":"Bearer reusable-secret"}\n'
                '{"message":"project Alpha remains internal"}\n',
                encoding="utf-8",
            )

            receipt = gate.transform_jsonl_snapshot(
                source,
                destination,
                receipt_hmac_key=self.RECEIPT_KEY,
                scope_ref="tenant:test",
                purpose="trace_research",
            )

            output = destination.read_text(encoding="utf-8")
            self.assertIn("person@example.com", output)
            self.assertIn("project Alpha remains internal", output)
            self.assertNotIn("reusable-secret", output)
            self.assertEqual(2, receipt["records"])
            self.assertEqual(1, receipt["transformed_values"])
            self.assertNotIn(str(source), str(receipt))
            self.assertNotIn(str(destination), str(receipt))
            gate.verify_jsonl_snapshot(
                destination,
                receipt,
                receipt_hmac_key=self.RECEIPT_KEY,
                scope_ref="tenant:test",
                purpose="trace_research",
            )

    def test_jsonl_snapshot_is_atomic_and_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "raw.jsonl"
            destination = pathlib.Path(tmp) / "clean.jsonl"
            source.write_text('{"email":"person@example.com"}\nnot-json\n')

            with self.assertRaises(gate.CredentialGateError):
                gate.transform_jsonl_snapshot(
                    source,
                    destination,
                    receipt_hmac_key=self.RECEIPT_KEY,
                    scope_ref="tenant:test",
                    purpose="trace_research",
                )
            self.assertFalse(destination.exists())

            source.write_text('{"email":"person@example.com"}\n')
            destination.write_text("do-not-overwrite\n")
            with self.assertRaises(gate.CredentialGateError):
                gate.transform_jsonl_snapshot(
                    source,
                    destination,
                    receipt_hmac_key=self.RECEIPT_KEY,
                    scope_ref="tenant:test",
                    purpose="trace_research",
                )
            self.assertEqual(
                "do-not-overwrite\n",
                destination.read_text(),
            )


if __name__ == "__main__":
    unittest.main()
