import unittest

import finance_governed_retrieval_replay as study


class FinanceGovernedRetrievalReplayTests(unittest.TestCase):
    def test_vector_literal_requires_native_dimension(self):
        with self.assertRaises(ValueError):
            study.vector_literal([0.0] * 767)
        literal = study.vector_literal([0.0] * 768)
        self.assertTrue(literal.startswith("[0,0,0"))
        self.assertEqual(literal.count(","), 767)

    def test_quality_metrics_respects_multi_positive_relevance(self):
        result = study.quality_metrics(
            {"q": ["d2", "d1", "d3"]},
            {"q": {"d1", "d3"}},
        )
        self.assertAlmostEqual(result["mrr"], 0.5)
        self.assertEqual(result["recall@1"], 0.0)
        self.assertEqual(result["recall@5"], 1.0)


if __name__ == "__main__":
    unittest.main()
