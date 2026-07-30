import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import longitudinal_memory_cohort_expansion as expansion  # noqa: E402


class LongitudinalCohortExpansionTests(unittest.TestCase):
    def test_aggregate_gates_preserve_source_scoped_projects(self):
        strata = [
            {
                "project_cluster_gates": {
                    "online_queries": {
                        "cases": 3,
                        "project_contexts": 2,
                        "cases_per_project_desc": [2, 1],
                    },
                    "changed_post_observation_cases": {
                        "cases": 1,
                        "project_contexts": 1,
                        "cases_per_project_desc": [1],
                    },
                    "exact_cross_session_write_to_later_read": {
                        "cases": 1,
                        "project_contexts": 1,
                        "cases_per_project_desc": [1],
                    },
                }
            },
            {
                "project_cluster_gates": {
                    "online_queries": {
                        "cases": 14,
                        "project_contexts": 2,
                        "cases_per_project_desc": [11, 3],
                    },
                    "changed_post_observation_cases": {
                        "cases": 9,
                        "project_contexts": 2,
                        "cases_per_project_desc": [8, 1],
                    },
                    "exact_cross_session_write_to_later_read": {
                        "cases": 4,
                        "project_contexts": 2,
                        "cases_per_project_desc": [2, 2],
                    },
                }
            },
        ]

        result = expansion._aggregate_gates(strata)

        self.assertTrue(result["minimum_count_gates_all_passed"])
        self.assertEqual(17, result["online_queries"]["cases"])
        self.assertEqual(
            [11, 3, 2, 1],
            result["online_queries"][
                "cases_per_source_scoped_project_desc"
            ],
        )
        self.assertEqual(
            3,
            result["independent_project_context_minimum"][
                "source_scoped_project_contexts"
            ],
        )

    def test_result_hash_omits_hash_field_itself(self):
        value = {"schema_version": "fixture", "decision": {"passed": True}}
        digest = expansion.sha256_bytes(
            expansion.stable_json(value).encode("utf-8")
        )
        value["result_sha256"] = digest
        self.assertNotEqual(
            digest,
            expansion.sha256_bytes(
                expansion.stable_json(value).encode("utf-8")
            ),
        )


if __name__ == "__main__":
    unittest.main()
