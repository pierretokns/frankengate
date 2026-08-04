import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from sqlglot import parse_one  # noqa: E402

from bird_trace_artifact_reuse import Artifact, Task  # noqa: E402
from bird_trace_retrieval_cascade import cosine, identifiers, jaccard, rank  # noqa: E402


def _artifact(task_id: str, database: str, prompt: str, sql: str) -> Artifact:
    task = Task(task_id, database, prompt, sql, Path("/tmp/unused.sqlite"), 0)
    return Artifact(task, sql, (), sql, (), frozenset(prompt.lower().split()))


def test_identifier_extraction_and_jaccard_are_structure_aware() -> None:
    assert identifiers("SELECT a.id FROM accounts a WHERE a.status = 'paid'") == {"accounts", "id", "status"}
    assert jaccard(frozenset({"a", "b"}), frozenset({"b", "c"})) == 1 / 3


def test_dense_rank_is_deterministic_with_identifier_tiebreak() -> None:
    target = _artifact("target", "db", "count paid orders", "SELECT COUNT(*) FROM orders WHERE status='paid'")
    candidate = _artifact("candidate", "db", "count orders", "SELECT COUNT(*) FROM orders")
    ranked = rank(target, np.array([1.0, 0.0]), [(candidate, np.array([1.0, 0.0]))], "dense")
    assert ranked[0].task.task_id == "candidate"
    assert parse_one(candidate.sql, read="sqlite")


def test_cosine_handles_zero_vectors() -> None:
    assert cosine(np.zeros(2), np.ones(2)) == 0.0
