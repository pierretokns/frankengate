import dataclasses
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import codetracebench_empirical as MODULE  # noqa: E402


def make_row(
    traj_id,
    task_name,
    source_relpath,
    *,
    step_count=10,
    incorrect=(),
    unuseful=(),
    stage_id=2,
    with_refs=True,
):
    steps = []
    for step_id in sorted(set(incorrect) | set(unuseful)):
        labels = []
        if step_id in incorrect:
            labels.append("incorrect")
        if step_id in unuseful:
            labels.append("unuseful")
        steps.append(
            {
                "step_id": step_id,
                "labels": labels,
                "action_ref": {"content": f"action-{step_id}"} if with_refs else None,
                "observation_ref": (
                    {"content": f"observation-{step_id}"} if with_refs else None
                ),
            }
        )
    incorrect_stages = []
    if steps:
        incorrect_stages.append(
            {
                "stage_id": stage_id,
                "incorrect_step_ids": list(incorrect),
                "unuseful_step_ids": list(unuseful),
                "steps": steps,
            }
        )
    return {
        "traj_id": traj_id,
        "agent": "agent",
        "model": "model",
        "task_name": task_name,
        "difficulty": "medium",
        "category": "software-engineering",
        "solved": False,
        "step_count": step_count,
        "stages": [
            {"stage_id": 1, "start_step_id": 1, "end_step_id": 3},
            {"stage_id": 2, "start_step_id": 4, "end_step_id": 7},
            {"stage_id": 3, "start_step_id": 8, "end_step_id": step_count},
        ],
        "incorrect_stages": incorrect_stages,
        "source_relpath": source_relpath,
    }


class RecordAndSplitTest(unittest.TestCase):
    def test_record_preserves_labels_and_reference_hashes(self):
        record = MODULE.record_from_mapping(
            make_row(
                "t1",
                "org__repo-123",
                "swe_raw/openhands__verified/org__repo-123",
                incorrect=(5,),
                unuseful=(6,),
            )
        )
        self.assertEqual("swe-bench-verified", record.source_family)
        self.assertEqual("org__repo", record.repository_family)
        self.assertEqual((5,), record.incorrect_step_ids)
        self.assertEqual((6,), record.unuseful_step_ids)
        self.assertEqual(("incorrect",), record.labeled_steps[0].labels)
        self.assertIsNotNone(record.labeled_steps[0].action_hash)

    def test_blocked_split_never_separates_repository_or_task(self):
        rows = []
        for source in ("verified", "pro", "multi"):
            for repo in range(8):
                for task in range(3):
                    rows.append(
                        MODULE.record_from_mapping(
                            make_row(
                                f"{source}-{repo}-{task}",
                                f"org{repo}__repo-{100 + task}",
                                f"swe_raw/openhands__{source}/path",
                            )
                        )
                    )
        assignments = MODULE.assign_blocked_splits(rows)
        by_group = {}
        for row in rows:
            by_group.setdefault(row.group_key, set()).add(assignments[row.group_key])
        self.assertTrue(all(len(splits) == 1 for splits in by_group.values()))
        self.assertEqual(assignments, MODULE.assign_blocked_splits(list(reversed(rows))))

    def test_verified_parent_overlap_is_not_treated_as_independent(self):
        verified = [
            MODULE.record_from_mapping(
                make_row(
                    "same-id",
                    "org__repo-1",
                    "swe_raw/openhands__verified/path",
                )
            )
        ]
        full = list(verified)
        assignments = MODULE.assign_blocked_splits(verified)
        audit = MODULE.build_split_audit(full, verified, assignments)
        self.assertEqual(1, audit["verified_to_full_parent_overlap"])
        self.assertEqual(0, audit["verified_missing_full_parent"])
        self.assertEqual(0, audit["parent_split_mismatches"])


class SignalsTest(unittest.TestCase):
    def setUp(self):
        self.train = [
            MODULE.record_from_mapping(
                make_row(
                    f"train-{index}",
                    f"org{index}__repo-1",
                    "swe_raw/openhands__verified/path",
                    step_count=10 + index,
                )
            )
            for index in range(8)
        ]

    def test_structural_score_is_label_and_outcome_blind(self):
        scaler = MODULE.fit_structural_scaler(self.train)
        base = MODULE.record_from_mapping(
            make_row(
                "target",
                "org__repo-2",
                "swe_raw/openhands__verified/path",
                incorrect=(),
            )
        )
        labeled = MODULE.record_from_mapping(
            make_row(
                "target",
                "org__repo-2",
                "swe_raw/openhands__verified/path",
                incorrect=(5,),
            )
        )
        labeled = dataclasses.replace(labeled, solved=True)
        self.assertEqual(
            MODULE.structural_signal_score(base, scaler),
            MODULE.structural_signal_score(labeled, scaler),
        )

    def test_e1_is_deterministic_and_budget_matched(self):
        test = [
            MODULE.record_from_mapping(
                make_row(
                    f"test-{index}",
                    f"testorg{index}__repo-1",
                    "swe_raw/openhands__verified/path",
                    step_count=10 + index,
                    incorrect=(5,) if index % 2 else (),
                )
            )
            for index in range(20)
        ]
        first = MODULE.run_e1(self.train, test, seed=7, random_repetitions=20)
        second = MODULE.run_e1(self.train, test, seed=7, random_repetitions=20)
        self.assertEqual(first, second)
        self.assertEqual(4, first["budget"])
        for arm in (
            "trace_length",
            "stage_count",
            "structural_signal",
            "structural_signal_plus_random_audit",
        ):
            self.assertEqual(4, first["arms"][arm]["selected"])


class DiagnosisTest(unittest.TestCase):
    def test_diagnosis_metrics_use_human_incorrect_set(self):
        record = MODULE.record_from_mapping(
            make_row(
                "diagnosis",
                "org__repo-1",
                "swe_raw/openhands__verified/path",
                step_count=10,
                incorrect=(10,),
            )
        )
        reverse = MODULE._diagnosis_metrics([record], "reverse_chronology", 1)
        forward = MODULE._diagnosis_metrics([record], "forward_chronology", 1)
        self.assertEqual(1.0, reverse["top1_accuracy"])
        self.assertEqual(0.0, forward["top1_accuracy"])
        self.assertAlmostEqual(0.1, forward["mean_reciprocal_rank"])

    def test_stage_oracle_is_explicitly_separate_from_blind_methods(self):
        record = MODULE.record_from_mapping(
            make_row(
                "diagnosis",
                "org__repo-1",
                "swe_raw/openhands__verified/path",
                incorrect=(4,),
                stage_id=2,
            )
        )
        result = MODULE.run_e3([record], seed=1)
        self.assertIn(
            "critical_stage_start_oracle",
            result["annotation_consuming_upper_bounds"],
        )
        self.assertNotIn(
            "critical_stage_start_oracle",
            result["blind_methods"],
        )
        self.assertEqual(
            1.0,
            result["methods"]["critical_stage_start_oracle"]["top1_accuracy"],
        )


class MutationTest(unittest.TestCase):
    def setUp(self):
        self.record = MODULE.record_from_mapping(
            make_row(
                "mutation",
                "org__repo-1",
                "swe_raw/openhands__verified/path",
                incorrect=(4, 6),
            )
        )
        self.expected = MODULE._audit_events(self.record)

    def test_combined_kills_supported_harmful_mutations(self):
        for mutation in (
            "remove_required",
            "duplicate_required",
            "reorder_required",
            "alter_action_reference",
            "alter_observation_reference",
            "relabel_required",
        ):
            with self.subTest(mutation=mutation):
                observed = MODULE.mutate_audit(
                    self.expected,
                    mutation,
                    irrelevant_step_id=self.record.step_count + 1,
                )
                self.assertIsNotNone(observed)
                self.assertFalse(
                    MODULE.evaluate_assertion("combined", self.expected, observed)
                )

    def test_combined_allows_irrelevant_injection_but_exact_rejects_it(self):
        observed = MODULE.mutate_audit(
            self.expected,
            "inject_irrelevant",
            irrelevant_step_id=self.record.step_count + 1,
        )
        self.assertTrue(MODULE.evaluate_assertion("combined", self.expected, observed))
        self.assertFalse(
            MODULE.evaluate_assertion("exact_sequence", self.expected, observed)
        )

    def test_mutation_support_is_reported_not_fabricated(self):
        no_refs = MODULE.record_from_mapping(
            make_row(
                "no-refs",
                "org__repo-2",
                "swe_raw/openhands__verified/path",
                incorrect=(4,),
                with_refs=False,
            )
        )
        result = MODULE.run_e4([self.record, no_refs], seed=7)
        action = result["mutation_matrix"]["alter_action_reference"]
        self.assertEqual(1, action["supported_traces"])
        self.assertEqual(
            0.0,
            result["aggregate_by_assertion"]["combined"][
                "allowed_variation_false_positive_rate"
            ],
        )


if __name__ == "__main__":
    unittest.main()
