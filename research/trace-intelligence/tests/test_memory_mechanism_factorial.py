import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
MODULE_PATH = ROOT / "memory_mechanism_factorial.py"
SPEC = importlib.util.spec_from_file_location(
    "memory_mechanism_factorial", MODULE_PATH
)
memory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = memory
SPEC.loader.exec_module(memory)


class MemoryMechanismFactorialTest(unittest.TestCase):
    def test_derived_artifact_must_release_strictly_before_query(self):
        fixture = memory.build_deterministic_fixture()
        first_query = fixture.queries[0]
        first_item = fixture.catalogs["released_dream"][0]
        tampered = memory.replace_item(
            fixture,
            mechanism="released_dream",
            item_ref=first_item.item_ref,
            released_at=first_query.query_at,
        )

        with self.assertRaises(memory.ExperimentProtocolError):
            memory.run_experiment(tampered)

    def test_full_factorial_contains_zero_six_isolation_and_composed_arms(self):
        result = memory.run_experiment(memory.build_deterministic_fixture())

        self.assertEqual(6, len(result["mechanisms"]))
        self.assertEqual(64, result["design"]["arm_count"])
        self.assertEqual(1, result["design"]["zero_mechanism_arms"])
        self.assertEqual(6, result["design"]["single_mechanism_arms"])
        self.assertEqual(57, result["design"]["composed_arms"])
        self.assertEqual(64 * result["design"]["query_count"], result["design"]["case_count"])
        self.assertTrue(result["design"]["all_blind_payloads_passed"])
        self.assertEqual(
            [],
            result["design"]["forbidden_blind_payload_fields_observed"],
        )

    def test_all_six_catalogs_are_frozen_and_derived_releases_are_query_independent(self):
        fixture = memory.build_deterministic_fixture()
        result = memory.run_experiment(fixture)

        self.assertEqual(4, result["design"]["query_count"])
        self.assertEqual(
            {
                "latest_snapshot": 3,
                "bitemporal_ledger": 6,
                "evidence_retrieval": 6,
                "released_dream": 1,
                "verbatim_state": 6,
                "released_procedure": 1,
            },
            result["catalog_item_counts"],
        )
        self.assertTrue(result["release_protocol"]["all_released_before_queries"])
        self.assertTrue(result["release_protocol"]["dream_query_independent"])
        self.assertTrue(result["release_protocol"]["dream_independently_verified"])
        self.assertTrue(result["release_protocol"]["procedure_query_independent"])
        self.assertTrue(result["release_protocol"]["procedure_independently_verified"])
        self.assertEqual(0, result["release_protocol"]["post_query_source_count"])

    def test_blinded_scoring_reports_independent_and_composed_fixture_outcomes(self):
        result = memory.run_experiment(memory.build_deterministic_fixture())

        by_set = {
            tuple(arm["mechanisms"]): arm
            for arm in result["arms"]
        }
        self.assertEqual(0, by_set[()]["exact_decisions"])
        self.assertEqual(
            {
                "latest_snapshot": 2,
                "bitemporal_ledger": 4,
                "evidence_retrieval": 4,
                "released_dream": 1,
                "verbatim_state": 4,
                "released_procedure": 1,
            },
            {
                mechanism: by_set[(mechanism,)]["exact_decisions"]
                for mechanism in result["mechanisms"]
            },
        )
        self.assertEqual(
            4,
            by_set[tuple(result["mechanisms"])]["exact_decisions"],
        )
        self.assertEqual(
            ["decision", "memory_ref", "epistemic_status"],
            result["design"]["blinded_decision_fields"],
        )
        self.assertEqual(
            ["decision", "gold_status", "gold_value", "pack"],
            result["design"]["scoring_interface_fields"],
        )

    def test_gold_is_rederived_outside_the_resolver_from_temporal_and_outcome_evidence(self):
        result = memory.run_experiment(memory.build_deterministic_fixture())

        self.assertEqual(3, result["oracle"]["temporal_queries_rederived"])
        self.assertEqual(3, result["oracle"]["temporal_gold_agreements"])
        self.assertTrue(
            result["oracle"]["procedure_supported_by_successful_episode"]
        )
        self.assertFalse(result["oracle"]["gold_labels_seen_by_resolver"])
        self.assertEqual(
            4,
            result["oracle"]["all_query_gold_agreements"],
        )

    def test_result_is_deterministic_and_refuses_empirical_utility_claims(self):
        first = memory.run_experiment(memory.build_deterministic_fixture())
        second = memory.run_experiment(memory.build_deterministic_fixture())

        self.assertEqual(first, second)
        self.assertTrue(memory.verify_result(first))
        self.assertEqual(0, first["empirical_scope"]["natural_trace_units"])
        self.assertEqual(0, first["empirical_scope"]["enterprise_users"])
        self.assertEqual(0, first["empirical_scope"]["model_calls"])
        self.assertFalse(first["empirical_scope"]["causal_effect_estimated"])
        self.assertEqual(
            "not_established",
            first["claim_boundary"]["empirical_utility"],
        )
        self.assertIn(
            "pre_query_release_enforcement",
            first["claim_boundary"]["mechanics_established"],
        )
        self.assertGreaterEqual(
            len(first["claim_boundary"]["required_utility_falsifiers"]),
            4,
        )

    def test_composition_summary_exposes_redundancy_instead_of_claiming_synergy(self):
        result = memory.run_experiment(memory.build_deterministic_fixture())

        self.assertEqual(
            [
                "bitemporal_ledger",
                "evidence_retrieval",
                "verbatim_state",
            ],
            result["composition_summary"][
                "perfect_single_mechanism_arms"
            ],
        )
        self.assertEqual(
            4,
            result["composition_summary"]["strongest_singleton_exact"],
        )
        self.assertEqual(
            4,
            result["composition_summary"]["all_mechanisms_exact"],
        )
        self.assertEqual(
            0,
            result["composition_summary"][
                "all_minus_strongest_singleton"
            ],
        )
        self.assertEqual(
            "fixture_redundancy_not_empirical_equivalence",
            result["composition_summary"]["interpretation"],
        )


if __name__ == "__main__":
    unittest.main()
