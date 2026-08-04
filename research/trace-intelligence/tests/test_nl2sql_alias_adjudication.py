import json
import tempfile
import unittest
from pathlib import Path

from nl2sql_alias_adjudication import run


class AliasAdjudicationTest(unittest.TestCase):
    def test_requires_complete_candidate_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.json"
            adjudication = root / "adjudication.json"
            cases.write_text(json.dumps({
                "cases": [{
                    "case_id": "c1",
                    "scope_db": "alpha",
                    "gold_identifier": "name",
                    "candidate_same_surface": [["alpha", "name"], ["beta", "name"]],
                }]
            }))
            adjudication.write_text(json.dumps([{
                "case_id": "c1",
                "surface_label": "exact_alias",
                "candidate_labels": [
                    {"db": "alpha", "identifier": "name", "label": "exact_alias"},
                    {"db": "beta", "identifier": "name", "label": "wrong_system"},
                ],
                "confidence": 0.9,
            }]))
            result = run(cases, adjudication, model="test")
        self.assertEqual(result["source"]["cases"], 1)
        self.assertEqual(result["scope_candidate_correct_rate"], 1.0)
        self.assertEqual(result["other_scope_wrong_system_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
