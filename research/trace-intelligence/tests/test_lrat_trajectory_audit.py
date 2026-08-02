import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lrat_trajectory_audit import audit


def test_lrat_audit_separates_completion_from_outcomes(tmp_path: Path) -> None:
    row = {
        "status": "completed",
        "metadata": {"searcher_type": "bm25"},
        "query": "q",
        "answer": "a",
        "result": [
            {"type": "reasoning", "output": "r"},
            {"type": "tool_call", "tool_name": "search", "arguments": "{}", "output": "results"},
            {"type": "output_text", "output": "a"},
        ],
    }
    (tmp_path / "0.json").write_text(json.dumps(row), encoding="utf-8")
    result = audit(tmp_path)
    assert result["records"]["tool_calls"] == 1
    assert result["field_presence"]["explicit_outcome_fields"] == {}
    assert result["claim_boundary"]["natural_friction_measured"] is False
