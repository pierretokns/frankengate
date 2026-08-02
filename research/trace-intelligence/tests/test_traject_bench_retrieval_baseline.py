import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from traject_bench_retrieval_baseline import metric_row, rank, run  # noqa: E402


def test_rank_and_metrics_are_deterministic() -> None:
    candidates = [
        {"tool name": "weather lookup", "tool description": "forecast by city"},
        {"tool name": "stock quote", "tool description": "equity price"},
    ]
    row = {"query": "give me the weather forecast for a city", "tool list": [candidates[0]]}
    order = rank(row["query"], candidates, include_description=True)
    values = metric_row(row, candidates, order)
    assert order == [0, 1]
    assert values["recall_at_1"] == 1.0
    assert values["exact_target_set_at_target_count"] == 1.0


def test_run_supports_benchmark_tool_list_variants(tmp_path: Path) -> None:
    public = tmp_path / "public_data"
    (public / "tools").mkdir(parents=True)
    (public / "parallel" / "Demo").mkdir(parents=True)
    tools = [
        {"tool name": "weather lookup", "tool description": "forecast by city"},
        {"tool name": "stock quote", "tool description": "equity price"},
    ]
    rows = [{"query": "weather forecast", "tool_list": [tools[0]]}]
    (public / "tools" / "Demo_tool.json").write_text(json.dumps(tools), encoding="utf-8")
    (public / "parallel" / "Demo" / "simple_ver.json").write_text(json.dumps(rows), encoding="utf-8")
    result = run(public, tmp_path / "result.json")
    assert result["records_evaluated"] == 1
    assert result["arm_record_counts"] == {"name": 1, "name_description": 1}
