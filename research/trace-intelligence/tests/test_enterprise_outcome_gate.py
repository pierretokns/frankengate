import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import enterprise_outcome_gate as gate  # noqa: E402


class EnterpriseOutcomeGateTest(unittest.TestCase):
    def test_conformance_cases_are_fail_closed_until_consent_and_labels(self):
        cases = gate.conformance_cases()

        self.assertEqual("abstain", cases["missing_consent"].decision)
        self.assertEqual(
            "cross_user_consent_required", cases["missing_consent"].reason
        )
        self.assertEqual(0, cases["missing_consent"].candidate_count)

        self.assertEqual("abstain", cases["wrong_consent_scope"].decision)
        self.assertEqual(
            "row_consent_scope_mismatch", cases["wrong_consent_scope"].reason
        )
        self.assertEqual(0, cases["wrong_consent_scope"].candidate_count)

        self.assertEqual("abstain", cases["cohort_without_labels"].decision)
        self.assertEqual(
            "human_outcome_labels_required",
            cases["cohort_without_labels"].reason,
        )
        self.assertEqual(0, cases["cohort_without_labels"].candidate_count)

        allowed = cases["authorized_labeled_cohort"]
        self.assertEqual("allow", allowed.decision)
        self.assertEqual("scope_and_outcome_gate_passed", allowed.reason)
        self.assertEqual(3, allowed.candidate_count)
        self.assertEqual(3, allowed.distinct_subject_count)
        self.assertEqual(3, allowed.labeled_candidate_count)
        self.assertEqual(3, len(allowed.candidate_digests))

    def test_rls_filters_happen_before_cohort_counts(self):
        rows = [
            gate.TraceRow(
                "visible-a", "tenant-a", "alice", "team", "platform", 1,
                frozenset({"quality-improvement"}), 4,
                cross_user_consent_scope="scope-v1", human_outcome_label="ok",
            ),
            gate.TraceRow(
                "stale-b", "tenant-a", "bob", "team", "platform", 1,
                frozenset({"quality-improvement"}), 3,
                cross_user_consent_scope="scope-v1", human_outcome_label="ok",
            ),
            gate.TraceRow(
                "secret-c", "tenant-a", "carol", "team", "platform", 9,
                frozenset({"quality-improvement"}), 4,
                cross_user_consent_scope="scope-v1", human_outcome_label="ok",
            ),
            gate.TraceRow(
                "other-d", "tenant-b", "dana", "team", "platform", 1,
                frozenset({"quality-improvement"}), 4,
                cross_user_consent_scope="scope-v1", human_outcome_label="ok",
            ),
        ]
        request = gate.ScopeRequest(
            tenant_id="tenant-a",
            subject_id="alice",
            team_ids=frozenset({"platform"}),
            authorization_epoch=4,
            classification_ceiling=2,
            purpose="quality-improvement",
            analysis="skill_gap",
            cross_user_consent=True,
            consent_scope="scope-v1",
            minimum_cohort=2,
        )

        decision = gate.evaluate(rows, request)
        self.assertEqual("abstain", decision.decision)
        self.assertEqual("minimum_cohort_not_met", decision.reason)
        self.assertEqual(0, decision.candidate_count)
        self.assertEqual(0, decision.distinct_subject_count)

    def test_personal_history_does_not_require_cross_user_consent(self):
        row = gate.TraceRow(
            "alice-private", "tenant-a", "alice", "private", None, 1,
            frozenset({"history"}), 7,
        )
        request = gate.ScopeRequest(
            tenant_id="tenant-a",
            subject_id="alice",
            team_ids=frozenset(),
            authorization_epoch=7,
            classification_ceiling=1,
            purpose="history",
            analysis="similar_work",
            minimum_cohort=1,
        )
        decision = gate.evaluate([row], request)
        self.assertEqual("allow", decision.decision)
        self.assertEqual(1, decision.candidate_count)
        self.assertEqual(1, decision.distinct_subject_count)


if __name__ == "__main__":
    unittest.main()
