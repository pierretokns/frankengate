from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from defog_family_transfer_analysis import analyze


class DefogFamilyTransferAnalysisTest(unittest.TestCase):
    def test_requires_matching_task_arm_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = {
                "dataset": {"database_family": "broker"},
                "task_runs": [{
                    "task_id_sha256": "task",
                    "arm": "no_skill",
                    "authority_valid": True,
                    "terminal_action": "none",
                    "semantic_correct": False,
                    "unauthorized_observation": False,
                    "successful_sql_attempts": 0,
                    "elapsed_ms": 1,
                }],
            }
            left = root / "left.json"; right = root / "right.json"
            left.write_text(json.dumps(base)); right.write_text(json.dumps(base))
            result = analyze(inputs=[("openai", left), ("ollama", right)], output=root / "out.json")
            self.assertFalse(result["claim_boundary"]["semantic_quality_estimated"])
