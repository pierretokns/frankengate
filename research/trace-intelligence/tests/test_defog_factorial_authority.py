import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
MODULE_PATH = ROOT / "defog_factorial_authority.py"
SPEC = importlib.util.spec_from_file_location(
    "defog_factorial_authority", MODULE_PATH
)
authority = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = authority
SPEC.loader.exec_module(authority)


class DefogFactorialAuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = (
            ROOT
            / "configs/governance/"
            "defog-factorial-authority-epoch-2026-07-30.json"
        )
        cls.store = authority.StaticAuthorityEpochStore.from_path(cls.path)
        cls.valid = {
            "database": "broker",
            "governance_scope": "enterprise",
            "authorization_epoch_ref": "defog-factorial-authority-v1",
            "user_id": "factorial-pilot-user",
            "team_id": "factorial-pilot-team",
            "virtual_key_id": "factorial-pilot-vk",
        }

    def test_exact_current_binding_is_admitted_with_content_free_receipt(self):
        receipt = self.store.validate(**self.valid)
        self.assertTrue(receipt.authority_valid)
        self.assertEqual(64, len(receipt.binding_sha256))
        self.assertEqual(64, len(receipt.epoch_ref_sha256))
        self.assertEqual(64, len(receipt.authority_snapshot_sha256))
        self.assertNotIn(
            "factorial-pilot",
            json.dumps(receipt.__dict__, sort_keys=True),
        )

    def test_stale_epoch_fails_closed(self):
        values = {**self.valid, "authorization_epoch_ref": "stale-epoch"}
        with self.assertRaisesRegex(
            authority.AuthorityEpochError, "stale or unknown"
        ):
            self.store.validate(**values)

    def test_cross_database_or_subject_binding_fails_closed(self):
        for field, value in (
            ("database", "unknown_database"),
            ("user_id", "different-user"),
            ("team_id", "different-team"),
            ("virtual_key_id", "different-vk"),
        ):
            with self.subTest(field=field):
                values = {**self.valid, field: value}
                with self.assertRaisesRegex(
                    authority.AuthorityEpochError, "not present"
                ):
                    self.store.validate(**values)

    def test_missing_authority_field_fails_closed(self):
        for field in (
            "governance_scope",
            "authorization_epoch_ref",
            "user_id",
            "team_id",
            "virtual_key_id",
        ):
            with self.subTest(field=field):
                values = {**self.valid, field: None}
                with self.assertRaisesRegex(
                    authority.AuthorityEpochError, "incomplete"
                ):
                    self.store.validate(**values)

    def test_duplicate_binding_snapshot_is_rejected(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload["bindings"].append(dict(payload["bindings"][0]))
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "duplicate.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                authority.AuthorityEpochError, "duplicate"
            ):
                authority.StaticAuthorityEpochStore.from_path(path)


if __name__ == "__main__":
    unittest.main()
