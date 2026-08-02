import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bird_sql_trace_mined_factorial import choose_eligible_tasks, choose_tasks  # noqa: E402


def test_choose_tasks_preserves_family_disjoint_selection() -> None:
    rows = [
        {"task_id": "a-0", "data": {"db_name": "a"}},
        {"task_id": "a-1", "data": {"db_name": "a"}},
        {"task_id": "b-0", "data": {"db_name": "b"}},
    ]
    selected = choose_tasks(rows, ["b"], 1)
    assert [row["task_id"] for row in selected] == ["b-0"]


def test_choose_eligible_tasks_excludes_unexecutable_gold_queries(tmp_path: Path) -> None:
    import json
    import sqlite3

    database_dir = tmp_path / "databases"
    gold_dir = tmp_path / "gold"
    database_dir.mkdir()
    gold_dir.mkdir()
    connection = sqlite3.connect(database_dir / "a.sqlite")
    connection.execute("create table values_table (value integer)")
    connection.executemany("insert into values_table values (?)", [(1,), (2,)])
    connection.commit()
    connection.close()
    rows = [
        {"task_id": "a-invalid", "data": {"db_name": "a"}},
        {"task_id": "a-valid", "data": {"db_name": "a"}},
    ]
    (gold_dir / "a-invalid.json").write_text(
        json.dumps({"gold_sql": "select missing from values_table"})
    )
    (gold_dir / "a-valid.json").write_text(
        json.dumps({"gold_sql": "select count(*) from values_table"})
    )
    selected, excluded = choose_eligible_tasks(rows, ["a"], 1, database_dir, gold_dir)
    assert [row["task_id"] for row in selected] == ["a-valid"]
    assert excluded == {"a": 1}
