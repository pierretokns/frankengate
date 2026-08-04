import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "temporal_evidence_oracle_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "temporal_evidence_oracle_v2", MODULE_PATH
)
oracle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)


def event(event_id, **overrides):
    values = {
        "event_id": event_id,
        "event_type": "write",
        "succeeded": True,
        "authority_subject": "user-a",
        "project_context": "/srv/project-a",
        "artifact_context": "MEMORY.md",
        "content_sha256": f"digest-{event_id}",
        "valid_at": oracle.instant("2026-01-10T00:00:00Z"),
        "known_at": oracle.instant("2026-01-20T00:00:00Z"),
        "parent_event_ids": (),
    }
    values.update(overrides)
    return oracle.TemporalEvidenceEvent(**values)


def query(**overrides):
    values = {
        "authority_subject": "user-a",
        "project_context": "/srv/project-a",
        "artifact_context": "MEMORY.md",
        "valid_at": oracle.instant("2026-01-10T00:00:00Z"),
        "known_at": oracle.instant("2026-01-20T00:00:00Z"),
        "parent_event_ids": ("write-1",),
    }
    values.update(overrides)
    return oracle.TemporalQuery(**values)


class TemporalEvidenceOracleV2Test(unittest.TestCase):
    def test_valid_time_and_known_time_are_independent(self):
        ledger = oracle.TemporalEvidenceOracle((event("write-1"),))

        not_yet_known = ledger.resolve(
            query(known_at=oracle.instant("2026-01-19T23:59:59Z"))
        )
        historically_visible = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-01-10T00:00:00Z"),
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
            )
        )

        self.assertEqual("insufficient", not_yet_known.status)
        self.assertEqual("no_eligible_evidence", not_yet_known.reason)
        self.assertEqual("resolved", historically_visible.status)
        self.assertEqual(
            "digest-write-1",
            historically_visible.selected_revision.content_sha256,
        )

    def test_successful_write_closes_the_prior_revision_exactly(self):
        first = event(
            "write-1",
            valid_at=oracle.instant("2026-01-10T00:00:00Z"),
            known_at=oracle.instant("2026-01-10T00:00:01Z"),
        )
        second = event(
            "write-2",
            valid_at=oracle.instant("2026-01-20T00:00:00Z"),
            known_at=oracle.instant("2026-01-20T00:00:01Z"),
            parent_event_ids=("write-1",),
        )
        ledger = oracle.TemporalEvidenceOracle((first, second))

        before = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-01-19T23:59:59Z"),
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("write-2",),
            )
        )
        at_boundary = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-01-20T00:00:00Z"),
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("write-2",),
            )
        )

        self.assertEqual("digest-write-1", before.selected_revision.content_sha256)
        self.assertEqual("digest-write-2", at_boundary.selected_revision.content_sha256)
        self.assertEqual(2, len(at_boundary.revisions))
        self.assertEqual(
            oracle.instant("2026-01-20T00:00:00Z"),
            at_boundary.revisions[0].valid_to,
        )
        self.assertEqual("exact", at_boundary.revisions[0].valid_to_precision)

    def test_failed_write_creates_no_revision_and_does_not_close_state(self):
        first = event(
            "write-1",
            known_at=oracle.instant("2026-01-10T00:00:01Z"),
        )
        failed = event(
            "write-failed",
            succeeded=False,
            valid_at=oracle.instant("2026-01-20T00:00:00Z"),
            known_at=oracle.instant("2026-01-20T00:00:01Z"),
            parent_event_ids=("write-1",),
        )
        ledger = oracle.TemporalEvidenceOracle((first, failed))

        result = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-01-21T00:00:00Z"),
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("write-failed",),
            )
        )

        self.assertEqual(1, len(result.revisions))
        self.assertIsNone(result.revisions[0].valid_to)
        self.assertEqual("digest-write-1", result.selected_revision.content_sha256)
        self.assertEqual("last_observed_only", result.status)

    def test_open_gap_returns_only_the_last_observed_state(self):
        ledger = oracle.TemporalEvidenceOracle(
            (
                event(
                    "write-1",
                    known_at=oracle.instant("2026-01-10T00:00:01Z"),
                ),
            )
        )

        result = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-01-11T00:00:00Z"),
                known_at=oracle.instant("2026-01-11T00:00:01Z"),
            )
        )

        self.assertEqual("last_observed_only", result.status)
        self.assertEqual("last_observation_with_open_gap", result.reason)
        self.assertEqual("digest-write-1", result.selected_revision.content_sha256)

    def test_changed_read_creates_an_interval_censored_version_gap(self):
        first = event(
            "write-1",
            known_at=oracle.instant("2026-01-10T00:00:01Z"),
        )
        changed_read = event(
            "read-2",
            event_type="read",
            valid_at=oracle.instant("2026-02-10T00:00:00Z"),
            known_at=oracle.instant("2026-02-10T00:00:01Z"),
            parent_event_ids=("write-1",),
        )
        ledger = oracle.TemporalEvidenceOracle((first, changed_read))

        inside_unknown_window = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-02-01T00:00:00Z"),
                known_at=oracle.instant("2026-03-01T00:00:00Z"),
                parent_event_ids=("read-2",),
            )
        )
        at_read_boundary = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-02-10T00:00:00Z"),
                known_at=oracle.instant("2026-03-01T00:00:00Z"),
                parent_event_ids=("read-2",),
            )
        )

        self.assertEqual("insufficient", inside_unknown_window.status)
        self.assertEqual("interval_censored_gap", inside_unknown_window.reason)
        self.assertEqual(1, len(inside_unknown_window.interval_gaps))
        gap = inside_unknown_window.interval_gaps[0]
        self.assertEqual(
            oracle.instant("2026-01-10T00:00:00Z"),
            gap.lower_exclusive,
        )
        self.assertEqual(
            oracle.instant("2026-02-10T00:00:00Z"),
            gap.upper_inclusive,
        )
        self.assertEqual("interval_censored", at_read_boundary.revisions[0].valid_to_precision)
        self.assertEqual("interval_censored", at_read_boundary.revisions[1].valid_from_precision)
        self.assertEqual("digest-read-2", at_read_boundary.selected_revision.content_sha256)
        self.assertEqual("resolved", at_read_boundary.status)

    def test_unchanged_read_confirms_the_existing_revision(self):
        first = event(
            "write-1",
            known_at=oracle.instant("2026-01-10T00:00:01Z"),
        )
        confirming_read = event(
            "read-confirm",
            event_type="read",
            content_sha256="digest-write-1",
            valid_at=oracle.instant("2026-01-20T00:00:00Z"),
            known_at=oracle.instant("2026-01-20T00:00:01Z"),
            parent_event_ids=("write-1",),
        )
        ledger = oracle.TemporalEvidenceOracle((first, confirming_read))

        result = ledger.resolve(
            query(
                valid_at=oracle.instant("2026-01-15T00:00:00Z"),
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("read-confirm",),
            )
        )

        self.assertEqual("resolved", result.status)
        self.assertEqual(1, len(result.revisions))
        self.assertEqual((), result.interval_gaps)
        self.assertEqual(
            ("write-1", "read-confirm"),
            result.revisions[0].source_event_ids,
        )
        self.assertEqual(
            oracle.instant("2026-01-20T00:00:00Z"),
            result.revisions[0].confirmed_through,
        )

    def test_future_read_does_not_retroactively_change_online_state(self):
        first = event(
            "write-1",
            known_at=oracle.instant("2026-01-10T00:00:01Z"),
        )
        future_read = event(
            "read-future",
            event_type="read",
            valid_at=oracle.instant("2026-02-10T00:00:00Z"),
            known_at=oracle.instant("2026-02-10T00:00:01Z"),
            parent_event_ids=("write-1",),
        )
        ledger = oracle.TemporalEvidenceOracle((first, future_read))
        target_valid_at = oracle.instant("2026-02-01T00:00:00Z")

        online = ledger.resolve(
            query(
                valid_at=target_valid_at,
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("read-future",),
            )
        )
        retrospective = ledger.resolve(
            query(
                valid_at=target_valid_at,
                known_at=oracle.instant("2026-03-01T00:00:00Z"),
                parent_event_ids=("read-future",),
            )
        )

        self.assertEqual("last_observed_only", online.status)
        self.assertEqual("digest-write-1", online.selected_revision.content_sha256)
        self.assertEqual((), online.interval_gaps)
        self.assertEqual("insufficient", retrospective.status)
        self.assertEqual("interval_censored_gap", retrospective.reason)

    def test_authority_project_and_artifact_must_match_exactly(self):
        correct = event(
            "correct",
            content_sha256="right",
            known_at=oracle.instant("2026-01-10T00:00:01Z"),
        )
        wrong_authority = event(
            "wrong-authority",
            authority_subject="User-A",
            content_sha256="leak-authority",
            parent_event_ids=("correct",),
        )
        wrong_project = event(
            "wrong-project",
            project_context="/srv/project-b",
            content_sha256="leak-project",
            parent_event_ids=("wrong-authority",),
        )
        wrong_artifact = event(
            "wrong-artifact",
            artifact_context="memory.md",
            content_sha256="leak-artifact",
            parent_event_ids=("wrong-project",),
        )
        ledger = oracle.TemporalEvidenceOracle(
            (correct, wrong_authority, wrong_project, wrong_artifact)
        )

        result = ledger.resolve(
            query(
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("wrong-artifact",),
            )
        )

        self.assertEqual("right", result.selected_revision.content_sha256)
        self.assertEqual(1, len(result.revisions))

    def test_sibling_and_unordered_lineage_is_excluded(self):
        root = event(
            "root",
            content_sha256="root-state",
            valid_at=oracle.instant("2026-01-01T00:00:00Z"),
            known_at=oracle.instant("2026-01-01T00:00:01Z"),
        )
        selected_branch = event(
            "branch-a",
            content_sha256="branch-a-state",
            parent_event_ids=("root",),
        )
        sibling = event(
            "branch-b",
            content_sha256="branch-b-state",
            parent_event_ids=("root",),
        )
        unordered = event(
            "unrelated-root",
            content_sha256="unrelated-state",
        )
        ledger = oracle.TemporalEvidenceOracle(
            (root, selected_branch, sibling, unordered)
        )

        result = ledger.resolve(
            query(
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("branch-a",),
            )
        )

        self.assertEqual("branch-a-state", result.selected_revision.content_sha256)
        self.assertEqual(
            {"root", "branch-a"},
            {
                event_id
                for revision in result.revisions
                for event_id in revision.source_event_ids
            },
        )

    def test_overlapping_equal_precedence_states_are_a_conflict(self):
        root = event(
            "root",
            content_sha256="root-state",
            valid_at=oracle.instant("2026-01-01T00:00:00Z"),
            known_at=oracle.instant("2026-01-01T00:00:01Z"),
        )
        left = event(
            "left",
            content_sha256="left-state",
            parent_event_ids=("root",),
        )
        right = event(
            "right",
            content_sha256="right-state",
            parent_event_ids=("root",),
        )
        ledger = oracle.TemporalEvidenceOracle((root, left, right))

        result = ledger.resolve(
            query(
                known_at=oracle.instant("2026-02-01T00:00:00Z"),
                parent_event_ids=("left", "right"),
            )
        )

        self.assertEqual("conflict", result.status)
        self.assertEqual("incompatible_overlap", result.reason)
        self.assertIsNone(result.selected_revision)
        self.assertEqual(
            {("left", "right")},
            {item.source_event_ids for item in result.conflicts},
        )


if __name__ == "__main__":
    unittest.main()
