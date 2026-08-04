from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wmh_bird_step_fault_audit import fault_category, table_names  # noqa: E402


def test_fault_category_identifies_table_mismatch() -> None:
    assert fault_category("SELECT * FROM wrong", "SELECT * FROM right") == "table_selection"


def test_table_names_parse_join() -> None:
    assert table_names("SELECT * FROM alpha JOIN beta ON alpha.id=beta.id") == {"alpha", "beta"}
