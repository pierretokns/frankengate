from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from skillgen_codex_frontier_reproduction import _extract_json


def test_extract_json_accepts_plain_and_fenced_objects() -> None:
    assert _extract_json('{"pass": true}') == {"pass": True}
    assert _extract_json('```json\n{"score": 1}\n```') == {"score": 1}


def test_frontier_receipt_is_explicit_about_no_failure_signal() -> None:
    receipt = Path(__file__).parents[1] / "experiments/results/skillgen-codex-frontier-mini-2026-08-02.json"
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert data["baseline_trajectories"] == 8
    assert data["baseline_failures"] == 0
    assert data["generated_skill"] is False
    assert data["embedding_substitution"] == "deterministic hashed-256; not semantic"
