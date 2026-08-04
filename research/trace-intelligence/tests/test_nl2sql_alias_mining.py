import csv
import tempfile
import unittest
from pathlib import Path

from nl2sql_alias_mining import analyze, canonical_identifiers, normalize


class NL2SQLAliasMiningTest(unittest.TestCase):
    def test_morphology_and_identifier_extraction(self):
        self.assertEqual(normalize("customers"), "customer")
        self.assertEqual(canonical_identifiers("SELECT c.id FROM customers c JOIN orders o ON c.id=o.customer_id"), {"customers", "orders", "c", "o", "id", "customer_id"})

    def test_result_is_hash_only_and_counts_collision(self):
        rows = [
            {"db_name": "a", "question": "List customers", "query": "SELECT customer_id FROM customers"},
            {"db_name": "b", "question": "List customers", "query": "SELECT customer_id FROM customers"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["db_name", "question", "query"])
                writer.writeheader()
                writer.writerows(rows)
            result = analyze(path)
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["cross_db_ambiguity_hashes"], 1)
        self.assertNotIn("customers", str(result))
        self.assertIn("Hashes", result["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
