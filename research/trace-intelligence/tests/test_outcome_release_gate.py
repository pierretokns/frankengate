from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "outcome_release_gate", ROOT / "outcome_release_gate.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OutcomeReleaseGateTests(unittest.TestCase):
    def _write(self, directory: Path, name: str, value: dict) -> Path:
        path = directory / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_null_is_quarantined_and_has_zero_exposure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            result = self._write(
                directory,
                "result.json",
                {"summary": {
                    "candidate": {"wins": 0, "invalid_actions": 0},
                    "baseline": {"wins": 0, "invalid_actions": 0},
                    "placebo": {"wins": 0, "invalid_actions": 0},
                }},
            )
            verification = self._write(directory, "verification.json", {"all_passed": True})
            receipt = MODULE.run(result, verification, "candidate", "baseline", "placebo")
            self.assertEqual(receipt["candidate"]["status"], "quarantined")
            self.assertFalse(receipt["outcomes"]["positive_lift"])
            self.assertEqual(receipt["exposure"]["canary_percent"], 0)

    def test_positive_lift_requires_validity_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            result = self._write(
                directory,
                "result.json",
                {"summary": {
                    "candidate": {"wins": 3, "invalid_actions": 0},
                    "baseline": {"wins": 1, "invalid_actions": 1},
                    "placebo": {"wins": 2, "invalid_actions": 1},
                }},
            )
            verification = self._write(directory, "verification.json", {"all_passed": True})
            receipt = MODULE.run(result, verification, "candidate", "baseline", "placebo")
            self.assertEqual(receipt["candidate"]["status"], "released")
            self.assertTrue(receipt["outcomes"]["positive_lift"])

            failed = self._write(directory, "failed.json", {"all_passed": False})
            blocked = MODULE.run(result, failed, "candidate", "baseline", "placebo")
            self.assertEqual(blocked["candidate"]["status"], "quarantined")


if __name__ == "__main__":
    unittest.main()
