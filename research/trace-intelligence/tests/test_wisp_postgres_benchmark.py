import dataclasses
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wisp_postgres_benchmark import (  # noqa: E402
    AuthoritySnapshot,
    BenchmarkInvariantError,
    PolicyLeakError,
    denial_scenarios,
    latency_summary,
    percentile,
    summarize_plan,
    validate_lineage,
    validate_proposal_lifecycle,
    validate_zero_candidate_matrix,
)


class WispPostgresBenchmarkTest(unittest.TestCase):
    def test_percentile_and_latency_summary(self):
        self.assertEqual(2.0, percentile([1.0, 2.0, 3.0], 0.5))
        self.assertAlmostEqual(1.5, percentile([1.0, 3.0], 0.25))
        calls = []

        def execute():
            calls.append(True)

        summary = latency_summary(execute, 4)
        self.assertEqual(4, summary["iterations"])
        self.assertEqual(4, len(calls))
        self.assertGreaterEqual(summary["p95_ms"], 0.0)
        with self.assertRaises(ValueError):
            percentile([], 0.5)
        with self.assertRaises(ValueError):
            latency_summary(execute, 0)

    def test_denial_scenarios_change_exactly_one_authority_dimension(self):
        base = AuthoritySnapshot(
            tenant="tenant-secret",
            subject="subject-secret",
            epoch=7,
            classification_ceiling=4,
            purpose="purpose-secret",
        )
        scenarios = denial_scenarios(base)

        self.assertEqual(6, scenarios["stale_epoch"].epoch)
        self.assertEqual(
            3, scenarios["insufficient_classification"].classification_ceiling
        )
        for label, scenario in scenarios.items():
            differences = sum(
                left != right
                for left, right in zip(
                    dataclasses.astuple(base),
                    dataclasses.astuple(scenario),
                )
            )
            self.assertEqual(1, differences, label)

        serialized_labels = json.dumps(sorted(scenarios))
        self.assertNotIn("tenant-secret", serialized_labels)
        self.assertNotIn("subject-secret", serialized_labels)

    def test_denied_candidates_must_be_zero_before_ranking(self):
        zero = {
            "history_candidates": 0,
            "structural_event_candidates": 0,
            "controlled_fts_candidates": 0,
            "proposal_candidates": 0,
        }
        checks = validate_zero_candidate_matrix(
            {
                "unauthorized_subject": dict(zero),
                "wrong_tenant": dict(zero),
                "stale_epoch": dict(zero),
                "wrong_purpose": dict(zero),
                "insufficient_classification": dict(zero),
            }
        )
        self.assertTrue(all(checks.values()))

        leaking = dict(zero)
        leaking["controlled_fts_candidates"] = 1
        with self.assertRaises(PolicyLeakError):
            validate_zero_candidate_matrix({"wrong_purpose": leaking})

    def test_query_plan_summary_drops_predicates_and_literals(self):
        raw_plan = {
            "Planning Time": 0.3,
            "Execution Time": 1.2,
            "Plan": {
                "Node Type": "Limit",
                "Actual Rows": 20,
                "Filter": "content_text = 'SECRET PROMPT'",
                "Plans": [
                    {
                        "Node Type": "Index Scan",
                        "Relation Name": "derived_artifacts",
                        "Index Name": "derived_content_tsv_idx",
                        "Index Cond": "SECRET NATIVE IDENTIFIER",
                        "Actual Rows": 20,
                    }
                ],
            },
        }

        summary = summarize_plan(raw_plan)
        serialized = json.dumps(summary)

        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("Filter", serialized)
        self.assertNotIn("Index Cond", serialized)
        self.assertEqual("Limit", summary["nodes"][0]["node_type"])
        self.assertEqual(
            "derived_content_tsv_idx", summary["nodes"][1]["index"]
        )
        self.assertFalse(summary["predicates_and_literals_emitted"])

    def test_proposal_lifecycle_is_fail_closed(self):
        valid = {
            "total_proposals": 10,
            "nonproposal_database_lifecycle": 0,
            "payload_lifecycle_mismatches": 0,
            "release_policy_mismatches": 0,
            "released_proposals": 0,
        }
        self.assertTrue(all(validate_proposal_lifecycle(valid).values()))

        invalid = dict(valid)
        invalid["released_proposals"] = 1
        with self.assertRaises(BenchmarkInvariantError):
            validate_proposal_lifecycle(invalid)

    def test_source_lineage_is_fail_closed(self):
        valid = {
            "events_without_source": 0,
            "artifacts_without_source": 0,
            "source_content_hash_mismatches": 0,
            "missing_evidence_event_references": 0,
            "proposals_without_evidence": 0,
            "source_revisions": 1,
            "adapter_revisions": 1,
        }
        self.assertTrue(all(validate_lineage(valid).values()))

        invalid = dict(valid)
        invalid["missing_evidence_event_references"] = 2
        with self.assertRaises(BenchmarkInvariantError):
            validate_lineage(invalid)


if __name__ == "__main__":
    unittest.main()
