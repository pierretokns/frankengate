import copy
import unittest

import postgres_planner_statistics_experiment as experiment


def run_fixture(fts_p50: float, *, analyzed: bool) -> dict:
    return {
        "environment": {
            "database": "local_postgresql",
            "server_version": "16.12",
            "vector_extension_version": "0.8.1",
            "iterations": 250,
        },
        "authorized_counts": {
            "trajectories": 104,
            "events": 17_505,
            "derived_artifacts": 122,
        },
        "denied_pre_ranking_candidate_matrix": {
            "all_zero": True,
            "counts": {
                "wrong_tenant": {
                    "history_candidates": 0,
                    "proposal_candidates": 0,
                }
            },
        },
        "latency": {
            "controlled_fts": {
                "iterations": 250,
                "mean_ms": fts_p50 * 1.03,
                "p50_ms": fts_p50,
                "p95_ms": fts_p50 * 1.08,
                "max_ms": fts_p50 * 1.12,
            },
            "personal_history_page": {
                "iterations": 250,
                "mean_ms": 1.1,
                "p50_ms": 1.0,
                "p95_ms": 1.3,
                "max_ms": 1.5,
            },
        },
        "query_plans": {
            "controlled_fts": {
                "predicates_and_literals_emitted": False,
                "nodes": (
                    [
                        {
                            "depth": 0,
                            "node_type": "Nested Loop",
                            "relation": "trajectories",
                        },
                        {
                            "depth": 1,
                            "node_type": "Seq Scan",
                            "relation": "derived_artifacts",
                        },
                    ]
                    if not analyzed
                    else [
                        {
                            "depth": 0,
                            "node_type": "Seq Scan",
                            "relation": "derived_artifacts",
                        },
                        {
                            "depth": 1,
                            "node_type": "Index Scan",
                            "relation": "trajectories",
                            "index": "trajectories_pkey",
                        },
                    ]
                ),
            },
            "personal_history_page": {
                "predicates_and_literals_emitted": False,
                "nodes": [
                    {
                        "depth": 0,
                        "node_type": "Index Scan",
                        "relation": "trajectories",
                        "index": "trajectories_task_idx",
                    }
                ],
            },
        },
    }


class PostgresPlannerStatisticsExperimentTest(unittest.TestCase):
    def test_reports_paired_latency_and_plan_change(self) -> None:
        result = experiment.compare_runs(
            run_fixture(57.0, analyzed=False),
            run_fixture(2.2, analyzed=True),
            runtime_receipt={
                "image_ref": "pgvector/pgvector:0.8.1-pg16",
                "image_digest": "sha256:" + "a" * 64,
            },
        )

        fts = result["queries"]["controlled_fts"]
        self.assertAlmostEqual(25.909091, fts["p50_speedup_ratio"])
        self.assertTrue(fts["plan_signature_changed"])
        self.assertEqual("statistics_refresh", result["intervention"])
        self.assertRegex(
            result["input_receipts"]["before_sha256"],
            r"^[0-9a-f]{64}$",
        )
        self.assertNotEqual(
            result["input_receipts"]["before_sha256"],
            result["input_receipts"]["after_sha256"],
        )
        self.assertEqual(
            "sha256:" + "a" * 64,
            result["runtime_receipt"]["image_digest"],
        )
        self.assertTrue(experiment.verify_result(result))

    def test_runtime_digest_must_be_pinned_when_supplied(self) -> None:
        with self.assertRaisesRegex(experiment.ExperimentError, "digest"):
            experiment.compare_runs(
                run_fixture(57.0, analyzed=False),
                run_fixture(2.2, analyzed=True),
                runtime_receipt={
                    "image_ref": "pgvector/pgvector:latest",
                    "image_digest": "mutable",
                },
            )

    def test_latency_query_may_have_no_explain_receipt(self) -> None:
        before = run_fixture(57.0, analyzed=False)
        after = run_fixture(2.2, analyzed=True)
        for run in (before, after):
            run["latency"]["proposal_queue"] = {
                "iterations": 250,
                "mean_ms": 1.0,
                "p50_ms": 0.9,
                "p95_ms": 1.2,
                "max_ms": 1.4,
            }

        result = experiment.compare_runs(before, after)

        self.assertIsNone(
            result["queries"]["proposal_queue"]["plan_signature_changed"]
        )
        self.assertIsNone(
            result["queries"]["proposal_queue"]["before_plan_signature"]
        )

    def test_counts_must_be_identical_for_paired_comparison(self) -> None:
        after = run_fixture(2.2, analyzed=True)
        after["authorized_counts"]["events"] += 1

        with self.assertRaisesRegex(experiment.ExperimentError, "counts"):
            experiment.compare_runs(
                run_fixture(57.0, analyzed=False),
                after,
            )

    def test_any_denied_candidate_invalidates_the_run(self) -> None:
        after = run_fixture(2.2, analyzed=True)
        after["denied_pre_ranking_candidate_matrix"]["counts"][
            "wrong_tenant"
        ]["history_candidates"] = 1

        with self.assertRaisesRegex(experiment.ExperimentError, "denied"):
            experiment.compare_runs(
                run_fixture(57.0, analyzed=False),
                after,
            )

    def test_environment_must_match(self) -> None:
        after = run_fixture(2.2, analyzed=True)
        after["environment"]["server_version"] = "17"

        with self.assertRaisesRegex(experiment.ExperimentError, "environment"):
            experiment.compare_runs(
                run_fixture(57.0, analyzed=False),
                after,
            )

    def test_redacted_plans_are_required(self) -> None:
        before = run_fixture(57.0, analyzed=False)
        before["query_plans"]["controlled_fts"][
            "predicates_and_literals_emitted"
        ] = True

        with self.assertRaisesRegex(experiment.ExperimentError, "redacted"):
            experiment.compare_runs(before, run_fixture(2.2, analyzed=True))

    def test_digest_detects_tampering(self) -> None:
        result = experiment.compare_runs(
            run_fixture(57.0, analyzed=False),
            run_fixture(2.2, analyzed=True),
        )
        changed = copy.deepcopy(result)
        changed["queries"]["controlled_fts"]["after_p50_ms"] = 999

        self.assertFalse(experiment.verify_result(changed))


if __name__ == "__main__":
    unittest.main()
