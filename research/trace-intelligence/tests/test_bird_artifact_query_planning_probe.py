import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bird_artifact_query_planning_probe import choose_targets  # noqa: E402


def test_choose_targets_round_robin_database_families() -> None:
    class Task:
        def __init__(self, database: str, task_id: str) -> None:
            self.database = database
            self.task_id = task_id

    class Artifact:
        def __init__(self, database: str, task_id: str) -> None:
            self.task = Task(database, task_id)

    selected = choose_targets([Artifact("a", "a1"), Artifact("a", "a2"), Artifact("b", "b1")], 2)
    assert [item.task.database for item in selected] == ["a", "b"]
