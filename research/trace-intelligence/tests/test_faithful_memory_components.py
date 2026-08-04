import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import faithful_memory_components as faithful  # noqa: E402


class Candidate:
    def __init__(self, content, observed_at):
        self.content = content
        self.observed_at = observed_at


class Query:
    def __init__(
        self,
        *,
        source_label,
        query_private,
        target_content_sha256,
        candidates,
    ):
        self.source_label = source_label
        self.query_private = query_private
        self.target_content_sha256 = target_content_sha256
        self.candidates = tuple(candidates)


class FaithfulMemoryComponentTests(unittest.TestCase):
    def test_selects_smallest_changed_and_unchanged_case_per_source(self):
        rows = [
            Query(
                source_label="wisp",
                query_private="large-change",
                target_content_sha256="target",
                candidates=[Candidate("x" * 90, 2), Candidate("old", 1)],
            ),
            Query(
                source_label="wisp",
                query_private="small-change",
                target_content_sha256="target",
                candidates=[Candidate("new", 2), Candidate("old", 1)],
            ),
            Query(
                source_label="wisp",
                query_private="same",
                target_content_sha256=faithful.sha256_text("current"),
                candidates=[Candidate("current", 1)],
            ),
            Query(
                source_label="fable5",
                query_private="fable-same",
                target_content_sha256=faithful.sha256_text("fable"),
                candidates=[Candidate("fable", 1)],
            ),
        ]

        selected = faithful.select_natural_contrast_queries(rows)

        self.assertEqual(
            [(row.source_label, row.changed) for row in selected],
            [
                ("fable5", False),
                ("wisp", False),
                ("wisp", True),
            ],
        )
        self.assertEqual(selected[-1].query.query_private, "small-change")
        self.assertEqual(selected[-1].projected_revision_count, 2)

    def test_identifier_score_preserves_corporate_exact_terms(self):
        source = (
            "Use authorization_epoch_ref with alerting.v1 and "
            "virtualKeyId at /work/plugins/governance/cache.go. "
            "Ordinary prose must not dominate."
        )
        extracted = (
            "The memory keeps authorization_epoch_ref, alerting.v1, "
            "virtualKeyId, and /work/plugins/governance/cache.go."
        )

        score = faithful.score_identifier_preservation(source, extracted)

        self.assertEqual(score.reference_identifiers, 4)
        self.assertEqual(score.matched_identifiers, 4)
        self.assertEqual(score.recall, 1.0)
        self.assertEqual(score.precision, 1.0)

    def test_component_result_reports_increment_without_overclaim(self):
        rows = [
            faithful.ComponentCaseResult(
                source_label="wisp",
                changed=True,
                baseline_exact=True,
                graphiti_retrieval_exact=False,
                graphiti_temporal_edges=2,
                graphiti_invalidated_edges=1,
                graphiti_identifier_recall=0.5,
                langmem_identifier_recall=0.75,
                langmem_memory_count=2,
                langmem_updated_existing=True,
                combined_retrieval_exact=False,
                graphiti_node_count=4,
                graphiti_edge_count=3,
            ),
            faithful.ComponentCaseResult(
                source_label="fable5",
                changed=False,
                baseline_exact=True,
                graphiti_retrieval_exact=True,
                graphiti_temporal_edges=1,
                graphiti_invalidated_edges=0,
                graphiti_identifier_recall=1.0,
                langmem_identifier_recall=0.5,
                langmem_memory_count=1,
                langmem_updated_existing=False,
                combined_retrieval_exact=True,
                graphiti_node_count=2,
                graphiti_edge_count=1,
            ),
        ]

        summary = faithful.aggregate_component_results(rows)

        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["baseline_exact"], 2)
        self.assertEqual(summary["graphiti_retrieval_exact"], 1)
        self.assertEqual(summary["graphiti_minus_baseline_exact"], -1)
        self.assertEqual(summary["combined_minus_baseline_exact"], -1)
        self.assertEqual(summary["graphiti_invalidated_edges"], 1)
        self.assertEqual(summary["graphiti_node_count"], 6)
        self.assertEqual(summary["graphiti_edge_count"], 4)
        self.assertEqual(summary["langmem_updated_existing_cases"], 1)
        self.assertEqual(
            summary["claim_boundary"],
            "component_mechanics_and_natural_prequery_retrieval_only",
        )

    def test_durable_result_rejects_content_and_paths(self):
        safe = {
            "summary": {"cases": 2},
            "content_policy": {
                "raw_content_emitted": False,
                "artifact_paths_emitted": False,
                "native_identifiers_emitted": False,
                "per_case_identifiers_emitted": False,
            },
        }
        faithful.assert_durable_result(safe)

        unsafe = json.loads(json.dumps(safe))
        unsafe["content_policy"]["artifact_paths_emitted"] = True
        with self.assertRaisesRegex(
            faithful.FaithfulComponentError,
            "durable output policy",
        ):
            faithful.assert_durable_result(unsafe)

    def test_incomplete_components_do_not_receive_zero_effect_scores(self):
        rows = [
            faithful.ComponentCaseResult(
                source_label="fable5",
                changed=False,
                baseline_exact=True,
                graphiti_retrieval_exact=False,
                graphiti_temporal_edges=0,
                graphiti_invalidated_edges=0,
                graphiti_identifier_recall=None,
                langmem_identifier_recall=None,
                langmem_memory_count=0,
                langmem_updated_existing=False,
                combined_retrieval_exact=False,
                graphiti_status="aborted_at_ceiling",
                langmem_status="not_durably_evidenced",
                combined_status="not_executed",
            )
        ]

        summary = faithful.aggregate_component_results(rows)

        self.assertEqual(summary["baseline_exact"], 1)
        self.assertEqual(summary["graphiti_executed_cases"], 0)
        self.assertIsNone(summary["graphiti_minus_baseline_exact"])
        self.assertIsNone(summary["combined_minus_baseline_exact"])

    def test_result_digest_detects_tampering(self):
        result = {
            "schema_version": "test",
            "content_policy": {
                "raw_content_emitted": False,
                "artifact_paths_emitted": False,
                "native_identifiers_emitted": False,
                "per_case_identifiers_emitted": False,
            },
        }
        result["result_sha256"] = faithful.result_digest(result)
        self.assertTrue(faithful.verify_result(result))
        result["schema_version"] = "changed"
        self.assertFalse(faithful.verify_result(result))


if __name__ == "__main__":
    unittest.main()
