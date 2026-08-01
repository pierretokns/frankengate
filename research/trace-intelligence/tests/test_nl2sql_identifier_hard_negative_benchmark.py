import csv
import tempfile
import unittest
from pathlib import Path

from nl2sql_identifier_hard_negative_benchmark import run


class IdentifierHardNegativeBenchmarkTest(unittest.TestCase):
    def test_scope_filter_is_measurable_and_receipt_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fixture.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["question", "query", "db_name", "query_category", "instructions"],
                )
                writer.writeheader()
                writer.writerow({
                    "question": "List customer names",
                    "query": "SELECT customer.name FROM customer",
                    "db_name": "alpha",
                    "query_category": "basic",
                    "instructions": "",
                })
                writer.writerow({
                    "question": "List customer names",
                    "query": "SELECT customer.name FROM customer",
                    "db_name": "beta",
                    "query_category": "basic",
                    "instructions": "",
                })
            result = run([source], endpoint="http://127.0.0.1:1", batch_size=2, with_embeddings=False)
        self.assertEqual(result["corpus"]["links"], 2)
        self.assertEqual(result["corpus"]["cross_scope_collision_classes"], 2)
        self.assertEqual(result["protocol"]["embedding_model"]["status"], "not_run")
        self.assertGreaterEqual(
            result["arms"]["surface_exact_unfiltered"]["hard_negative_before_target_rate"],
            result["arms"]["surface_exact_db_filtered"]["hard_negative_before_target_rate"],
        )
        self.assertNotIn("question", result)


if __name__ == "__main__":
    unittest.main()
