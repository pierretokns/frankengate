import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traject_bench_query_planning_probe import diverse_cases, planned_rank  # noqa: E402


def test_planned_rank_unions_query_matches() -> None:
    candidates = [
        {"tool name": "weather_lookup", "tool description": "weather by city"},
        {"tool name": "flight_search", "tool description": "find flights"},
        {"tool name": "calendar", "tool description": "manage events"},
    ]
    order, seen = planned_rank(["weather", "find a flight"], candidates)
    assert set(order[:2]) == {0, 1}
    assert seen == {"weather_lookup", "flight_search"}


def test_diverse_cases_round_robin_domains(tmp_path: Path) -> None:
    root = tmp_path / "public_data"
    for domain in ("A", "B"):
        (root / "parallel" / domain).mkdir(parents=True)
        (root / "tools").mkdir(exist_ok=True)
        (root / "tools" / f"{domain}_tool.json").write_text(json.dumps([{"tool name": "known"}]), encoding="utf-8")
        (root / "parallel" / domain / "hard_ver.json").write_text(json.dumps([{"query": "known", "tool list": [{"tool name": "known"}]}]), encoding="utf-8")
    selected = diverse_cases(root, 2)
    assert [case[0].split("/", 1)[0] for case in selected] == ["A", "B"]
