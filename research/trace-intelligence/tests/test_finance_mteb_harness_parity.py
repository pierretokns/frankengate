import unittest

import finance_mteb_harness_parity as study


class FinanceMTEBHarnessParityTests(unittest.TestCase):
    def test_rejects_projection_mismatch(self):
        base = {
            "dataset": {
                "id": "x",
                "revision": "r",
                "corpus_sha256": "c",
                "queries_sha256": "q",
                "qrels_sha256": "z",
                "evaluated_queries": 1,
                "projection": {"document_max_characters": 1},
            },
            "arms": [{"method": "BalyasnyAI/multilingual-e5-base", "mrr": 1, "recall@1": 1, "recall@5": 1, "recall@10": 1, "recall@20": 1, "model": {}}],
        }
        other = {"dataset": {**base["dataset"], "projection": {"document_max_characters": 2}}, "arm": {}}
        with self.assertRaises(ValueError):
            study.build(base, other)

    def test_relative_receipt_is_bounded(self):
        dataset = {"id": "x", "revision": "r", "corpus_sha256": "c", "queries_sha256": "q", "qrels_sha256": "z", "evaluated_queries": 1, "projection": {}}
        hf = {"dataset": dataset, "arms": [{"method": "BalyasnyAI/multilingual-e5-base", "mrr": 0.8, "recall@1": 0.8, "recall@5": 1, "recall@10": 1, "recall@20": 1, "model": {}}]}
        ollama = {"dataset": dataset, "arm": {"method": "ollama:nomic", "mrr": 0.2, "recall@1": 0.1, "recall@5": 0.4, "recall@10": 0.5, "recall@20": 0.6}, "model": {}}
        result = study.build(hf, ollama)
        self.assertAlmostEqual(result["relative"]["recall20_delta_hf_minus_ollama"], 0.4)
        self.assertFalse(result["claim_boundary"]["automatic_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
