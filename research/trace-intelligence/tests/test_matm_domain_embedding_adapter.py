import unittest

import numpy as np

from matm_domain_embedding_adapter import bootstrap_ci, recall_metrics


class MATMDomainEmbeddingAdapterTest(unittest.TestCase):
    def test_bootstrap_is_deterministic(self):
        self.assertEqual(bootstrap_ci([0.0, 0.1, -0.1]), bootstrap_ci([0.0, 0.1, -0.1]))

    def test_recall_and_mrr_use_cross_model_signature(self):
        signatures = ["work", "other", "work"]
        metrics = recall_metrics([1, 0], "work", signatures)
        self.assertEqual(metrics["recall_at_20"], 1.0)
        self.assertEqual(metrics["mrr"], 0.5)
        self.assertTrue(np.isfinite(metrics["mrr"]))


if __name__ == "__main__":
    unittest.main()
