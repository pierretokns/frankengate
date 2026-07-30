import importlib.util
import json
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "defog_sql_factorial_design.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location(
    "defog_sql_factorial_design", MODULE_PATH
)
design = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = design
SPEC.loader.exec_module(design)


class DefogSQLFactorialDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = pathlib.Path(__file__).parents[1]
        cls.cohort_path = (
            cls.root
            / "experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json"
        )
        cls.cohort = json.loads(cls.cohort_path.read_text(encoding="utf-8"))
        cls.model_manifest_path = (
            cls.root
            / "configs/models/qwen3.5-9b-optiq-4bit-mlx.json"
        )
        cls.authority_manifest_path = (
            cls.root
            / "configs/governance/"
            "defog-factorial-authority-epoch-2026-07-30.json"
        )
        cls.value = design.build_design(
            cls.cohort,
            model_manifest_sha256=design.hashlib.sha256(
                cls.model_manifest_path.read_bytes()
            ).hexdigest(),
            authority_manifest_sha256=design.hashlib.sha256(
                cls.authority_manifest_path.read_bytes()
            ).hexdigest(),
        )

    def test_rotates_each_database_through_hidden_and_selection_once(self):
        hidden = [
            fold["hidden_test_database_family"]
            for fold in self.value["folds"]
        ]
        selection = [
            fold["visible_selection_database_family"]
            for fold in self.value["folds"]
        ]
        self.assertEqual(sorted(design.DATABASES), sorted(hidden))
        self.assertEqual(sorted(design.DATABASES), sorted(selection))
        for fold in self.value["folds"]:
            roles = (
                set(fold["evidence_database_families"])
                | {fold["visible_selection_database_family"]}
                | {fold["hidden_test_database_family"]}
            )
            self.assertEqual(set(design.DATABASES), roles)
            self.assertEqual(2, len(fold["evidence_database_families"]))

    def test_pilot_is_selection_only_and_stratified(self):
        task_index = {
            task["task_id"]: task for task in self.cohort["tasks"]
        }
        for fold in self.value["folds"]:
            task_ids = fold["pilot_selection_task_ids"]
            self.assertEqual(4, len(task_ids))
            self.assertEqual(4, len(set(task_ids)))
            tasks = [task_index[task_id] for task_id in task_ids]
            self.assertTrue(
                all(
                    task["db_name"]
                    == fold["visible_selection_database_family"]
                    for task in tasks
                )
            )
            strata = [
                design._source_stratum(task["source_file"])
                for task in tasks
            ]
            self.assertEqual(1, strata.count("general"))
            self.assertEqual(1, strata.count("basic"))
            self.assertEqual(2, strata.count("advanced"))
            self.assertFalse(
                set(task_ids) & set(design.POLICY_ADJUDICATIONS)
            )
            self.assertEqual(
                task_ids,
                fold["mechanics_smoke_task_ids"],
            )
            self.assertEqual(
                self.value["primary_quality_counts"][
                    fold["visible_selection_database_family"]
                ],
                len(fold["visible_selection_task_ids"]),
            )
            self.assertEqual(
                self.value["primary_quality_counts"][
                    fold["hidden_test_database_family"]
                ],
                len(fold["hidden_test_task_ids"]),
            )

    def test_policy_controls_are_outside_primary_denominator(self):
        self.assertEqual(93, self.value["primary_quality_tasks"])
        adjudications = self.value["policy_adjudications"]
        self.assertEqual(3, len(adjudications))
        self.assertTrue(
            all(not item["primary_quality_eligible"] for item in adjudications)
        )

    def test_arm_contracts_do_not_claim_trace_learning(self):
        for arm in self.value["arm_contracts"].values():
            self.assertFalse(arm["learned_from_traces"])
        self.assertEqual(
            "expert_seed_not_trace_mined",
            self.value["arm_contracts"]["expert_schema_navigation_seed"][
                "classification"
            ],
        )

    def test_frozen_prompt_tool_and_analysis_contract(self):
        prompt = self.value["prompt_contract"]
        self.assertEqual(
            design.sha256_text(prompt["base_system_prompt"]),
            prompt["base_system_prompt_sha256"],
        )
        self.assertEqual(
            {"abstain", "submit_sql"},
            set(self.value["tool_contract"]["terminal_tools"]),
        )
        self.assertFalse(
            self.value["tool_contract"]["implicit_last_query_submission"]
        )
        self.assertFalse(
            self.value["tool_contract"]["submission_reexecutes_sql"]
        )
        self.assertEqual(
            "task",
            self.value["analysis_plan"]["independent_unit"],
        )
        self.assertFalse(
            self.value["stages"]["mechanics_smoke"][
                "effect_estimate_allowed"
            ]
        )

    def test_balanced_arm_orders_cover_every_task_once(self):
        expected = set(self.value["arm_contracts"])
        for fold in self.value["folds"]:
            stage_to_tasks = {
                "mechanics_smoke": fold["mechanics_smoke_task_ids"],
                "visible_selection_effect_screen": (
                    fold["visible_selection_task_ids"]
                ),
                "hidden_test": fold["hidden_test_task_ids"],
            }
            for stage, task_ids in stage_to_tasks.items():
                schedule = fold["arm_order"][stage]
                self.assertEqual(set(task_ids), set(schedule))
                for order in schedule.values():
                    self.assertEqual(expected, set(order))
                    self.assertEqual(len(expected), len(order))

    def test_design_is_content_free(self):
        payload = design.canonical_bytes(self.value)
        self.assertNotIn(b'"question"', payload)
        self.assertNotIn(b'"query"', payload)
        self.assertNotIn(b'"instructions"', payload)
        # Frozen generic prompts/tools are allowed; benchmark questions, SQL,
        # instructions, results, and gold labels are not.
        self.assertNotIn(b'"gold_sql"', payload)
        self.assertNotIn(b'"result_rows"', payload)


if __name__ == "__main__":
    unittest.main()
