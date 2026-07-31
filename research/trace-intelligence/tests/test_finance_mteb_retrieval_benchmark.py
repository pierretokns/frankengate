import unittest

import finance_mteb_retrieval_benchmark as study


class FinanceMTEBRetrievalBenchmarkTests(unittest.TestCase):
    def test_multi_positive_recall_is_not_first_positive_only(self):
        scores = [[0.9, 0.8, 0.1]]
        result = study._metrics(
            scores,
            query_ids=["q"],
            document_ids=["a", "b", "c"],
            relevant={"q": {"b", "c"}},
            method="fixture",
        )
        self.assertEqual(result["mrr"], 0.5)
        self.assertEqual(result["recall@1"], 0.0)
        self.assertEqual(result["recall@5"], 1.0)

    def test_defaults_are_pinned_and_local_only(self):
        self.assertEqual(study.DATASET_ID, "FinanceMTEB/FinanceBench")
        self.assertEqual(len(study.DEFAULT_MODELS), 2)
        self.assertTrue(study.SCHEMA_VERSION.endswith("v1"))


if __name__ == "__main__":
    unittest.main()
