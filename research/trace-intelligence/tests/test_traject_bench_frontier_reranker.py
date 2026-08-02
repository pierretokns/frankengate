import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from traject_bench_frontier_reranker import metrics, select_cases  # noqa: E402


def test_metrics_respect_target_set_and_rank() -> None:
    candidates = [{"tool name": "a"}, {"tool name": "b"}, {"tool name": "c"}]
    row = {"tool list": [{"tool name": "b"}]}
    result = metrics(row, candidates, [1, 0, 2])
    assert result["mrr"] == 1.0
    assert result["recall_at_1"] == 1.0


def test_case_selection_rejects_missing_target_manifest(tmp_path: Path) -> None:
    root = tmp_path / "public_data"
    (root / "parallel" / "Demo").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "tools" / "Demo_tool.json").write_text(json.dumps([{"tool name": "known", "tool description": ""}]), encoding="utf-8")
    (root / "parallel" / "Demo" / "hard_ver.json").write_text(json.dumps([{"query": "q", "tool list": [{"tool name": "unknown"}]}]), encoding="utf-8")
    assert select_cases(root, 5) == []


def test_case_selection_can_disable_target_append(tmp_path: Path) -> None:
    root = tmp_path / "public_data"
    (root / "parallel" / "Demo").mkdir(parents=True)
    (root / "tools").mkdir()
    tools = [{"tool name": "known", "tool description": ""}]
    tools.extend({"tool name": f"distractor-{index}", "tool description": ""} for index in range(17))
    tools.append({"tool name": "target", "tool description": ""})
    (root / "tools" / "Demo_tool.json").write_text(json.dumps(tools), encoding="utf-8")
    (root / "parallel" / "Demo" / "hard_ver.json").write_text(
        json.dumps([{"query": "known", "tool list": [{"tool name": "target"}]}]),
        encoding="utf-8",
    )
    cases = select_cases(root, 5, append_targets=False)
    assert len(cases) == 1
    assert "target" not in [item["tool name"] for item in cases[0][2]]
