import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import faithful_diagnosis_concept_audit as audit  # noqa: E402


class FaithfulDiagnosisConceptAuditTest(unittest.TestCase):
    def test_empty_corpus_rejected(self):
        with self.assertRaises(ValueError):
            audit.run_audit(
                pathlib.Path("/does/not/exist"),
                receipt_hmac_key=b"x" * 32,
                scope_ref="test",
                dataset_id="test",
                dataset_revision="test",
                review_budget=2,
                run_date="2026-07-30",
            )

    def test_summary_keeps_openrca_blocked_and_no_causal_claim(self):
        result = {
            "run_date": "2026-07-30",
            "concept_execution": {
                "signals": {
                    "queue": {"selected": 1, "selected_tool_error_traces": 1},
                    "baselines": {
                        "length": {"selected_tool_error_traces": 0},
                        "seeded_random": {"selected_tool_error_traces": 0},
                    },
                },
                "agentrx": {"hypotheses": 1, "abstentions": 0},
                "openrca": {"status": "not_executable_on_source"},
            },
        }
        summary = audit.render_summary(result)
        self.assertIn("not_executable_on_source", summary)
        self.assertIn("precision or recall", summary)
        self.assertIn("root-cause claims: 0", summary)


if __name__ == "__main__":
    unittest.main()
