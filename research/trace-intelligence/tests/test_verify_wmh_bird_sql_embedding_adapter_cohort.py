from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_wmh_bird_sql_embedding_adapter_cohort import verify  # noqa: E402


def test_verify_full_odd_half_receipt() -> None:
    root = Path(__file__).resolve().parents[1]
    value = verify(root / "experiments/results/wmh-bird-sql-embedding-adapter-full-2026-08-02.json")
    assert value["evaluation_rows_verified"] == 71
    assert value["aggregate_reconciliation_verified"] is True
    assert value["verification_passed"] is True


def test_verify_original_44_task_receipt() -> None:
    root = Path(__file__).resolve().parents[1]
    value = verify(root / "experiments/results/wmh-bird-sql-embedding-adapter-cohort-2026-08-09.json")
    assert value["evaluation_rows_verified"] == 44
    assert value["aggregate_reconciliation_verified"] is True
    assert value["verification_passed"] is True

