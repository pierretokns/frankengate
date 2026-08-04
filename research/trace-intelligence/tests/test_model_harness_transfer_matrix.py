from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from model_harness_transfer_matrix import MatrixError, compare


def _receipt(model: str, elapsed: float, match: bool) -> dict:
    return {
        "fixture_manifest_sha256": "fixture",
        "frozen_schedule_sha256": "schedule",
        "frozen_tool_schema_sha256": "tools",
        "request_model_id": model,
        "episode_receipts": [
            {
                "variant": "no_skill",
                "elapsed_ms": elapsed,
                "expected_terminal_match": match,
                "terminal_failure_code": None if match else "text_without_terminal_tool",
            }
        ],
        "variant_results": {"no_skill": {}},
        "claim_boundary": {"natural_trace_skill_benefit_confirmed": False},
    }


class ModelHarnessTransferMatrixTest(unittest.TestCase):
    def test_compares_same_fixture_and_preserves_claim_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            output = root / "aggregate.json"
            first.write_text(json.dumps(_receipt("llama", 10.0, False)))
            second.write_text(json.dumps(_receipt("qwen", 20.0, True)))
            result = compare(
                inputs=[("llama", "openai-native", first), ("qwen", "openai-native", second)],
                output=output,
            )
            self.assertEqual(result["classification"], "same_fixture_model_transfer")
            self.assertFalse(result["claim_boundary"]["causal_skill_benefit_established"])
            self.assertEqual(result["models"][1]["metrics_by_arm"]["no_skill"]["expected_terminal_matches"], 1)

    def test_rejects_fixture_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text(json.dumps(_receipt("llama", 10.0, False)))
            changed = _receipt("qwen", 20.0, True)
            changed["fixture_manifest_sha256"] = "different"
            second.write_text(json.dumps(changed))
            with self.assertRaises(MatrixError):
                compare(
                    inputs=[("llama", "openai-native", first), ("qwen", "openai-native", second)],
                    output=root / "aggregate.json",
                )
