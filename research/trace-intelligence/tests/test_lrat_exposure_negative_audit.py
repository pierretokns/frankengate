import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lrat_exposure_negative_audit import audit  # noqa: E402


def test_exposed_unbrowsed_candidates_are_counted(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"result": [
        {"type": "tool_call", "tool_name": "search", "output": "DocID: a\nDocID: b"},
        {"type": "tool_call", "tool_name": "visit", "arguments": "{\"docid\": \"a\"}", "output": "Document a"},
    ]}), encoding="utf-8")
    result = audit([path])
    assert result["aggregate"]["exposed_documents"] == 2
    assert result["aggregate"]["browsed_documents"] == 1
    assert result["aggregate"]["exposed_unbrowsed_documents"] == 1
