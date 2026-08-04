import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traject_bench_field_retrieval import fields, nested_text, weighted_score  # noqa: E402


def test_field_projection_preserves_structured_metadata() -> None:
    tool = {"tool name": "weather", "required_parameters": [{"name": "city"}], "output_info": {"output_format": "json"}}
    projected = fields(tool)
    assert "weather" in projected["name"]
    assert "city" in projected["schema"]
    assert "json" in projected["output"]
    assert nested_text(tool["required_parameters"])
    assert weighted_score({"city"}, projected, {"schema": 1.0}) == 1.0
