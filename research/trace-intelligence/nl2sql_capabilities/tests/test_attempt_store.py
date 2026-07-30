import dataclasses
import inspect
import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest
from unittest import mock


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities import attempt_store  # noqa: E402


EPISODE_A = "episode_AAAAAAAA"
EPISODE_B = "episode_BBBBBBBB"
SQL_A = "a" * 64
SQL_B = "b" * 64
RESULT_A = {
    "schema_version": "fg-query-result-v1",
    "columns": [{"format": "text", "name": "n", "pg_type_oid": 20}],
    "rows": [[{"kind": "int", "value": "2"}]],
    "row_count": 1,
    "result_bytes": 2,
}
RESULT_A["result_content_sha256"] = (
    attempt_store.query_result_content_sha256(RESULT_A)
)


class AttemptStoreTest(unittest.TestCase):
    def make_store(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = attempt_store.AttemptStore(
            pathlib.Path(temporary.name) / "attempt-store"
        )
        self.addCleanup(store.close)
        store.create_episode(EPISODE_A)
        store.create_episode(EPISODE_B)
        return store

    def successful_attempt(self, store, episode=EPISODE_A, sql_sha=SQL_A):
        return store.record_attempt(
            episode_ref=episode,
            candidate_sql_sha256=sql_sha,
            status="executed",
            authority_valid=True,
            policy_accepted=True,
            query_result=RESULT_A,
            bindings={
                "authority_epoch_ref_sha256": "c" * 64,
                "database_snapshot_sha256": "d" * 64,
            },
        )

    def test_canonical_bytes_are_deterministic_and_float_free(self):
        left = {"z": [3, 2, 1], "a": {"β": "value", "n": None}}
        right = {"a": {"n": None, "β": "value"}, "z": (3, 2, 1)}
        self.assertEqual(
            attempt_store.canonical_json_bytes(left),
            attempt_store.canonical_json_bytes(right),
        )
        with self.assertRaises(attempt_store.CanonicalDataError):
            attempt_store.canonical_json_bytes({"latency": 1.5})
        with self.assertRaises(attempt_store.CanonicalDataError):
            attempt_store.canonical_json_bytes({"bad": object()})

    def test_success_is_content_addressed_fsynced_and_read_back(self):
        store = self.make_store()
        receipt = self.successful_attempt(store)
        path = store.blob_path(receipt.attempt_blob_sha256)
        self.assertTrue(path.is_file())
        self.assertEqual(
            stat.S_IMODE(path.stat().st_mode),
            0o440,
        )
        self.assertEqual(
            attempt_store.sha256_bytes(path.read_bytes()),
            receipt.attempt_blob_sha256,
        )
        evidence = store.verify_attempt(
            episode_ref=EPISODE_A,
            attempt_id=receipt.attempt_id,
        )
        self.assertEqual("executed", evidence["status"])
        self.assertEqual(RESULT_A, evidence["query_result"])
        self.assertEqual(
            RESULT_A["result_content_sha256"],
            receipt.result_content_sha256,
        )
        self.assertIn(
            "not signed",
            attempt_store.THREAT_MODEL_LIMIT,
        )

    def test_previous_hash_chain_and_terminal_ledger_preserve_order(self):
        store = self.make_store()
        failed = store.record_attempt(
            episode_ref=EPISODE_A,
            candidate_sql_sha256=SQL_A,
            status="failed",
            authority_valid=True,
            policy_accepted=True,
            error_code="postgres_error",
        )
        successful = self.successful_attempt(
            store,
            sql_sha=SQL_B,
        )
        self.assertIsNone(failed.previous_attempt_blob_sha256)
        self.assertEqual(
            failed.attempt_blob_sha256,
            successful.previous_attempt_blob_sha256,
        )
        receipt = store.submit(
            episode_ref=EPISODE_A,
            attempt_id=successful.attempt_id,
        )
        ledger = store.verify_submission(receipt)
        self.assertEqual(
            [failed.attempt_id, successful.attempt_id],
            [entry["attempt_id"] for entry in ledger["entries"]],
        )
        self.assertEqual(
            failed.attempt_blob_sha256,
            ledger["entries"][1]["previous_attempt_blob_sha256"],
        )
        self.assertEqual(
            receipt.ledger_root_sha256,
            attempt_store.sha256_bytes(
                store.blob_path(receipt.ledger_root_sha256).read_bytes()
            ),
        )

    def test_submission_has_no_sql_or_callback_path(self):
        parameters = inspect.signature(
            attempt_store.AttemptStore.submit
        ).parameters
        self.assertEqual(
            ["self", "episode_ref", "attempt_id"],
            list(parameters),
        )
        store = self.make_store()
        successful = self.successful_attempt(store)
        receipt = store.submit(
            episode_ref=EPISODE_A,
            attempt_id=successful.attempt_id,
        )
        self.assertEqual(
            successful.attempt_blob_sha256,
            receipt.selected_attempt_blob_sha256,
        )

    def test_unknown_cross_episode_failed_duplicate_and_post_terminal_reject(self):
        store = self.make_store()
        failed = store.record_attempt(
            episode_ref=EPISODE_A,
            candidate_sql_sha256=SQL_A,
            status="denied",
            authority_valid=True,
            policy_accepted=False,
            error_code="policy_denied",
        )
        successful = self.successful_attempt(store, sql_sha=SQL_B)
        with self.assertRaises(attempt_store.UnknownAttemptError):
            store.submit(
                episode_ref=EPISODE_A,
                attempt_id="unknown_attempt_capability",
            )
        with self.assertRaises(attempt_store.CrossEpisodeAttemptError):
            store.submit(
                episode_ref=EPISODE_B,
                attempt_id=successful.attempt_id,
            )
        with self.assertRaises(attempt_store.UnsubmittableAttemptError):
            store.submit(
                episode_ref=EPISODE_A,
                attempt_id=failed.attempt_id,
            )
        store.submit(
            episode_ref=EPISODE_A,
            attempt_id=successful.attempt_id,
        )
        with self.assertRaises(attempt_store.EpisodeStateError):
            store.submit(
                episode_ref=EPISODE_A,
                attempt_id=successful.attempt_id,
            )
        with self.assertRaises(attempt_store.EpisodeStateError):
            self.successful_attempt(store, sql_sha="e" * 64)
        with self.assertRaises(attempt_store.EpisodeStateError):
            store.create_episode(EPISODE_A)

    def test_attempt_ids_are_random_and_episode_scoped(self):
        store = self.make_store()
        first = self.successful_attempt(store, EPISODE_A, SQL_A)
        second = self.successful_attempt(store, EPISODE_B, SQL_A)
        self.assertNotEqual(first.attempt_id, second.attempt_id)
        self.assertNotIn(EPISODE_A, first.attempt_id)
        with self.assertRaises(attempt_store.CrossEpisodeAttemptError):
            store.verify_attempt(
                episode_ref=EPISODE_B,
                attempt_id=first.attempt_id,
            )

    def test_create_exclusive_publication_rejects_existing_destination(self):
        store = self.make_store()
        original_link = os.link

        def conflict(*args, **kwargs):
            raise FileExistsError("preexisting destination")

        with mock.patch.object(os, "link", side_effect=conflict):
            with self.assertRaises(attempt_store.PublicationConflict):
                self.successful_attempt(store)
        self.assertEqual([], store._episodes[EPISODE_A].attempts)
        self.assertIs(os.link, original_link)

    def test_publication_uses_exclusive_no_follow_and_fsyncs_boundaries(self):
        store = self.make_store()
        with (
            mock.patch.object(os, "open", wraps=os.open) as open_call,
            mock.patch.object(os, "link", wraps=os.link) as link_call,
            mock.patch.object(os, "fsync", wraps=os.fsync) as fsync_call,
        ):
            self.successful_attempt(store)
        write_open = next(
            call
            for call in open_call.call_args_list
            if call.args[1] & os.O_WRONLY
        )
        flags = write_open.args[1]
        self.assertTrue(flags & os.O_CREAT)
        self.assertTrue(flags & os.O_EXCL)
        if getattr(os, "O_NOFOLLOW", 0):
            self.assertTrue(flags & os.O_NOFOLLOW)
        self.assertEqual(store._private_fd, write_open.kwargs["dir_fd"])
        link_call.assert_called_once()
        self.assertFalse(link_call.call_args.kwargs["follow_symlinks"])
        self.assertEqual(
            store._private_fd,
            link_call.call_args.kwargs["src_dir_fd"],
        )
        self.assertEqual(
            store._blob_fd,
            link_call.call_args.kwargs["dst_dir_fd"],
        )
        self.assertGreaterEqual(fsync_call.call_count, 3)
        fsynced_fds = [call.args[0] for call in fsync_call.call_args_list]
        self.assertIn(store._private_fd, fsynced_fds)
        self.assertIn(store._blob_fd, fsynced_fds)
        self.assertTrue(
            any(
                fd not in {store._private_fd, store._blob_fd}
                for fd in fsynced_fds
            ),
            "the temporary file itself must be fsynced",
        )

    def test_preexisting_regular_or_symlink_destination_is_not_overwritten(self):
        for destination_kind in ("regular", "symlink"):
            with self.subTest(destination_kind=destination_kind):
                store = self.make_store()
                value = {
                    "schema_version": "test-canonical-blob-v1",
                    "value": destination_kind,
                }
                payload = attempt_store.canonical_json_bytes(value)
                digest = attempt_store.sha256_bytes(payload)
                destination = store.blob_path(digest)
                original = b"attacker-controlled-existing-bytes"
                if destination_kind == "regular":
                    destination.write_bytes(original)
                    destination.chmod(0o440)
                else:
                    target = destination.parent / "attacker-target"
                    target.write_bytes(original)
                    destination.symlink_to(target)
                with self.assertRaises(attempt_store.PublicationConflict):
                    store._publish_canonical(value)
                if destination_kind == "regular":
                    self.assertEqual(original, destination.read_bytes())
                else:
                    self.assertTrue(destination.is_symlink())

    def test_overwrite_truncation_substitution_and_symlink_are_detected(self):
        mutations = ("overwrite", "truncate", "substitute", "symlink")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                store = self.make_store()
                receipt = self.successful_attempt(store)
                path = store.blob_path(receipt.attempt_blob_sha256)
                replacement = path.parent / f"replacement-{mutation}"
                if mutation == "overwrite":
                    path.chmod(0o640)
                    path.write_bytes(b"{}")
                    path.chmod(0o440)
                elif mutation == "truncate":
                    path.chmod(0o640)
                    with path.open("r+b") as handle:
                        handle.truncate(1)
                    path.chmod(0o440)
                elif mutation == "substitute":
                    path.unlink()
                    path.write_bytes(
                        attempt_store.canonical_json_bytes(
                            {"substituted": True}
                        )
                    )
                    path.chmod(0o440)
                else:
                    replacement.write_bytes(b"{}")
                    path.unlink()
                    path.symlink_to(replacement)
                with self.assertRaises(attempt_store.IntegrityError):
                    store.verify_attempt(
                        episode_ref=EPISODE_A,
                        attempt_id=receipt.attempt_id,
                    )

    def test_duplicate_keys_and_noncanonical_stored_bytes_are_rejected(self):
        store = self.make_store()
        duplicate = b'{"a":1,"a":2}'
        digest = attempt_store.sha256_bytes(duplicate)
        path = store.blob_path(digest)
        path.write_bytes(duplicate)
        path.chmod(0o440)
        with self.assertRaises(attempt_store.CanonicalDataError):
            store.read_blob(digest)

        noncanonical = b'{"b": 2, "a": 1}'
        digest = attempt_store.sha256_bytes(noncanonical)
        path = store.blob_path(digest)
        path.write_bytes(noncanonical)
        path.chmod(0o440)
        with self.assertRaises(attempt_store.CanonicalDataError):
            store.read_blob(digest)

    def test_reordered_or_forged_ledger_receipt_is_rejected(self):
        store = self.make_store()
        first = self.successful_attempt(store, sql_sha=SQL_A)
        second = self.successful_attempt(store, sql_sha=SQL_B)
        receipt = store.submit(
            episode_ref=EPISODE_A,
            attempt_id=second.attempt_id,
        )
        ledger = dict(store.verify_submission(receipt))
        ledger["entries"] = list(reversed(ledger["entries"]))
        forged_bytes = attempt_store.canonical_json_bytes(ledger)
        forged_hash = attempt_store.sha256_bytes(forged_bytes)
        forged_path = store.blob_path(forged_hash)
        forged_path.write_bytes(forged_bytes)
        forged_path.chmod(0o440)
        forged_receipt = dataclasses.replace(
            receipt,
            ledger_root_sha256=forged_hash,
        )
        with self.assertRaises(attempt_store.IntegrityError):
            store.verify_submission(forged_receipt)

        original_path = store.blob_path(receipt.ledger_root_sha256)
        original_path.chmod(0o640)
        original_path.write_bytes(forged_bytes)
        original_path.chmod(0o440)
        with self.assertRaises(attempt_store.IntegrityError):
            store.verify_submission(receipt)

    def test_invalid_success_and_failure_shapes_reject_before_publication(self):
        store = self.make_store()
        cases = (
            {
                "status": "executed",
                "authority_valid": False,
                "policy_accepted": True,
                "query_result": RESULT_A,
            },
            {
                "status": "executed",
                "authority_valid": True,
                "policy_accepted": True,
                "query_result": None,
            },
            {
                "status": "failed",
                "authority_valid": True,
                "policy_accepted": True,
                "query_result": RESULT_A,
                "error_code": "failure",
            },
            {
                "status": "denied",
                "authority_valid": True,
                "policy_accepted": False,
                "query_result": None,
                "error_code": None,
            },
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    store.record_attempt(
                        episode_ref=EPISODE_A,
                        candidate_sql_sha256=SQL_A,
                        **case,
                    )
        self.assertEqual([], store._episodes[EPISODE_A].attempts)


if __name__ == "__main__":
    unittest.main()
