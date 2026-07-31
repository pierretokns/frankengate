import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import enterprise_outcome_analysis as analysis  # noqa: E402
import enterprise_outcome_analysis_conformance as conformance  # noqa: E402
import enterprise_outcome_gate as gate  # noqa: E402


class EnterpriseOutcomeAnalysisTest(unittest.TestCase):
    def test_all_four_enterprise_questions_run_after_scope_gate(self):
        rows = conformance.fixture()
        for kind in ("similar_work", "friction_recovery", "skill_gap", "collaboration"):
            with self.subTest(kind=kind):
                result = analysis.analyze(rows, conformance.request(kind))
                self.assertEqual("allow", result["decision"])
                self.assertEqual(4, result["candidate_count"])
                self.assertTrue(result["payload"])

    def test_missing_consent_abstains_without_analysis_payload(self):
        rows = conformance.fixture()
        request = gate.ScopeRequest(
            tenant_id="tenant-a",
            subject_id="alice",
            team_ids=frozenset({"platform"}),
            authorization_epoch=9,
            classification_ceiling=2,
            purpose="quality-improvement",
            analysis="skill_gap",
            cross_user_consent=False,
            consent_scope=None,
            minimum_cohort=3,
            require_human_outcomes=True,
        )
        result = analysis.analyze(rows, request)
        self.assertEqual("abstain", result["decision"])
        self.assertEqual("cross_user_consent_required", result["reason"])
        self.assertEqual({}, result["payload"])

    def test_skill_gap_has_no_capability_claim_without_reviewed_labels(self):
        rows = conformance.fixture()
        unlabeled = [
            analysis.OutcomeTrace(
                authority=gate.TraceRow(
                    trace_id=row.authority.trace_id,
                    tenant_id=row.authority.tenant_id,
                    owner_subject_id=row.authority.owner_subject_id,
                    audience=row.authority.audience,
                    team_id=row.authority.team_id,
                    classification=row.authority.classification,
                    allowed_purposes=row.authority.allowed_purposes,
                    authorization_epoch=row.authority.authorization_epoch,
                    cross_user_consent_scope=row.authority.cross_user_consent_scope,
                    human_outcome_label=None,
                ),
                task_family=row.task_family,
                observed_capabilities=row.observed_capabilities,
                required_capabilities=row.required_capabilities,
                friction_events=row.friction_events,
                recovery_events=row.recovery_events,
                collaboration_opt_in=row.collaboration_opt_in,
            )
            for row in rows
        ]
        result = analysis.analyze(unlabeled, conformance.request("skill_gap"))
        self.assertEqual("abstain", result["decision"])
        self.assertEqual("human_outcome_labels_required", result["reason"])
        self.assertEqual({}, result["payload"])


if __name__ == "__main__":
    unittest.main()
