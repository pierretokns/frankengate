import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wmh_bird_schema_exposure_audit import audit  # noqa: E402


def test_schema_exposure_counts_unused_tables(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    attrs = [
        {"key": "gen_ai.tool.message", "value": {"stringValue": "CREATE TABLE alpha(id INTEGER); CREATE TABLE beta(id INTEGER);"}},
        {"key": "wmh.trace.metadata", "value": {"stringValue": json.dumps({"final_answer": "SELECT * FROM alpha", "reward": 1.0})}},
    ]
    path.write_text(json.dumps({"traceId": "t1", "attributes": attrs}) + "\n", encoding="utf-8")
    result = audit(path)
    assert result["aggregate"]["schema_table_exposures"] == 2
    assert result["aggregate"]["consumed_table_identifiers"] == 1
    assert result["aggregate"]["exposed_unconsumed_table_identifiers"] == 1
