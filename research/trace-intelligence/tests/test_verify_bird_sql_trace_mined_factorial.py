import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verify_bird_sql_trace_mined_factorial import sql_candidate, unordered  # noqa: E402


def test_sql_candidate_extracts_one_read_only_statement() -> None:
    assert sql_candidate("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert sql_candidate("answer: SELECT 1; SELECT 2") is None


def test_unordered_result_keeps_column_order_but_ignores_row_order() -> None:
    gold = (("value",), ((1,), (2,)))
    candidate = (("value",), ((2,), (1,)))
    assert unordered(candidate, gold)
    assert not unordered((("other",), ((1,), (2,))), gold)
