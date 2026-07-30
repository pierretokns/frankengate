import copy
import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "matm_pilot.py"
SPEC = importlib.util.spec_from_file_location("matm_pilot", MODULE_PATH)
matm_pilot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(matm_pilot)


def fixture_row(condition, success=False, model="model-a", task_id="task-a"):
    rank = matm_pilot.EXPECTED_RANK[condition]
    steps = [
        {
            "action": "look",
            "observation": "room",
            "reasoning": "inspect",
            "isCompleted": success,
            "inventory": "",
            "reward": float(success),
            "score": float(success),
            "url": "",
        }
    ]
    return {
        "environment": "alfworld",
        "source_type": "eval",
        "cohort": (
            "population_34" if condition == "no_retrieval" else "population_34_ltr"
        ),
        "model": model,
        "task_type": "pick_and_place_simple",
        "task_id": task_id,
        "fold": "test",
        "goal": "put the book on the desk",
        "retrieval_strategy": condition,
        "rank_retrieve": rank,
        "num_steps": 1,
        "final_score": float(success),
        "success": success,
        "max_steps": 15,
        "done": success,
        "trajectory": matm_pilot.stable_json(steps),
        "trajectory_id": "NA",
        "source_type_detail": "NA",
        "text_actions": None,
        "pddl_params": None,
        "high_level_descriptions": None,
        "metadata_info": None,
    }


class MatmPilotTest(unittest.TestCase):
    def test_adapter_preserves_source_record_and_source_step(self):
        source = fixture_row("no_retrieval")
        canonical = matm_pilot.canonicalize_matm(source)
        self.assertEqual(source, canonical["source_record"])
        self.assertEqual(
            matm_pilot.parse_trajectory(source)[0],
            canonical["events"][0]["source_step"],
        )
        self.assertEqual(0, canonical["loss_receipt"]["silently_dropped_event_count"])
        self.assertEqual(
            "environment_interaction_step", canonical["events"][0]["kind"]
        )

    def test_condition_rank_must_match(self):
        source = fixture_row("rerank_5")
        source["rank_retrieve"] = 10
        with self.assertRaises(ValueError):
            matm_pilot.condition_for(source)

    def test_complete_blocks_are_required(self):
        rows = [fixture_row(condition) for condition in matm_pilot.CONDITIONS[:-1]]
        with self.assertRaises(ValueError):
            matm_pilot.analyze_rows(rows, "sha", 1, bootstrap_replicates=10)

    def test_paired_effect_counts_direction_and_is_reproducible(self):
        rows = []
        for task_id, baseline, treatment in (
            ("task-a", False, True),
            ("task-b", True, False),
            ("task-c", False, False),
        ):
            for condition in matm_pilot.CONDITIONS:
                success = baseline if condition == "no_retrieval" else treatment
                rows.append(
                    fixture_row(
                        condition,
                        success=success,
                        model="model-" + task_id[-1],
                        task_id=task_id,
                    )
                )
        left = matm_pilot.analyze_rows(
            rows, "sha", 1, bootstrap_replicates=100, bootstrap_seed=7
        )
        right = matm_pilot.analyze_rows(
            copy.deepcopy(rows),
            "sha",
            1,
            bootstrap_replicates=100,
            bootstrap_seed=7,
        )
        self.assertEqual(left, right)
        first = left["paired_effects"][0]
        self.assertEqual(1, first["improved_pairs"])
        self.assertEqual(1, first["worsened_pairs"])
        self.assertEqual(0.0, first["success_rate_difference"])
        self.assertEqual(1.0, first["exact_two_sided_sign_p"])

    def test_exact_sign_test_handles_one_sided_discordance(self):
        self.assertEqual(0.0625, matm_pilot.exact_two_sided_sign_p(5, 0))
        self.assertEqual(1.0, matm_pilot.exact_two_sided_sign_p(0, 0))


if __name__ == "__main__":
    unittest.main()
