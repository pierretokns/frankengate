from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from defog_receipt_independent_verifier import verify, canonical_json_bytes


class DefogReceiptIndependentVerifierTest(unittest.TestCase):
    def _fixture(self, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        raw_dir = root / "raw"
        raw_dir.mkdir()
        task_id = "task-1"
        task_hash = hashlib.sha256(task_id.encode()).hexdigest()
        attempts: list[dict[str, object]] = []
        end = {
            "event": "factorial_task_end",
            "task_id": task_id,
            "arm": "no_skill",
            "authority_valid": True,
            "unauthorized_observation": False,
            "attempt_receipts": attempts,
            "outcome": "abstained:tool_budget_exhausted",
            "semantic_correct": False,
            "terminal_action": "abstain",
        }
        start = {
            "event": "factorial_task_start",
            "task_id": task_id,
            "arm": "no_skill",
            "authority_receipt": {
                "authority_valid": True,
                "binding_sha256": "b" * 64,
                "epoch_ref_sha256": "e" * 64,
            },
        }
        path = raw_dir / f"{task_hash[:16]}-no_skill.jsonl"
        path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in (start, end))
            + "\n",
            encoding="utf-8",
        )
        result = {
            "task_runs": [
                {
                    "task_id_sha256": task_hash,
                    "arm": "no_skill",
                    "raw_audit_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "attempt_receipt_chain_sha256": hashlib.sha256(
                        canonical_json_bytes(attempts)
                    ).hexdigest(),
                    "terminal_fallback_used": False,
                }
            ]
        }
        result_path = root / "result.json"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        return result_path, raw_dir

    def test_passes_and_is_explicitly_not_semantic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result, raw = self._fixture(pathlib.Path(directory))
            value = verify(result, raw)
            self.assertTrue(value["security_and_protocol_verification"])
            self.assertFalse(value["semantic_claim_authorized"])
            self.assertEqual(
                "not_run_without_pinned_database_executor",
                value["semantic_recomputation"],
            )

    def test_detects_raw_audit_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result, raw = self._fixture(pathlib.Path(directory))
            path = next(raw.glob("*.jsonl"))
            path.write_text(path.read_text() + "\n", encoding="utf-8")
            value = verify(result, raw)
            self.assertFalse(value["security_and_protocol_verification"])
            self.assertIn("raw_hash_mismatch", " ".join(value["failures"]))


if __name__ == "__main__":
    unittest.main()
