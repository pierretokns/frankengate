import unittest

import skill_optimization_meta_analysis as study


class SkillOptimizationMetaAnalysisTests(unittest.TestCase):
    def test_paired_effect_counts_wins_losses_and_ties(self):
        result = study.paired_effect(
            [(False, True), (True, False), (True, True), (False, False)]
        )
        self.assertEqual(result["candidate_wins"], 1)
        self.assertEqual(result["candidate_losses"], 1)
        self.assertEqual(result["ties"], 2)
        self.assertEqual(result["risk_difference"], 0.0)
        self.assertEqual(result["mcnemar_exact_two_sided_p"], 1.0)

    def test_no_discordance_is_not_reported_as_missing(self):
        result = study.paired_effect([(True, True), (False, False)])
        self.assertEqual(result["mcnemar_exact_two_sided_p"], 1.0)
        self.assertEqual(result["bootstrap_95_percent_ci"], [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
