import json
import pathlib
import tempfile
import unittest

import retrieval_backend_parity as study


class RetrievalBackendParityTests(unittest.TestCase):
    def test_emits_nulls_for_unrun_backends(self):
        with tempfile.TemporaryDirectory() as directory:
            out = pathlib.Path(directory) / "result.json"
            summary = pathlib.Path(directory) / "summary.md"
            self.assertEqual(study.main.__name__, "main")
            import sys

            old = sys.argv
            try:
                sys.argv = ["study", "--output", str(out), "--summary", str(summary)]
                self.assertEqual(study.main(), 0)
            finally:
                sys.argv = old
            result = json.loads(out.read_text())
            by_name = {row["system"]: row for row in result["systems"]}
            for name in ("Frankensearch", "pg_textsearch", "pgContext", "TurboVec", "Turbopuffer"):
                self.assertIsNone(by_name[name]["ranking"])
                self.assertFalse(by_name[name]["same_corpus_run"])
            self.assertTrue(result["policy"]["missing_runs_are_null"])

    def test_pinned_corpus_receipts_are_present(self):
        self.assertTrue(study.E2.exists())
        self.assertTrue(study.PG.exists())
        self.assertGreater(study.load(study.E2)["cohort"]["documents"], 0)
        self.assertGreater(study.load(study.PG)["cohort"]["documents"], 0)


if __name__ == "__main__":
    unittest.main()
