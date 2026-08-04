import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "bird_sql_trace_replay.py"
SPEC = importlib.util.spec_from_file_location("bird_sql_trace_replay", MODULE_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(replay)


class BirdSQLTraceReplayTest(unittest.TestCase):
    def test_extracts_select_from_fenced_answer(self):
        self.assertEqual(
            "SELECT 1",
            replay.sql_candidate("```sql\nSELECT 1;\n```"),
        )

    def test_rejects_multiple_statements(self):
        self.assertIsNone(replay.sql_candidate("SELECT 1; SELECT 2"))

    def test_rejects_non_read_query(self):
        self.assertIsNone(replay.sql_candidate("DELETE FROM accounts"))

    def test_exact_and_unordered_verdicts_preserve_columns_and_multiplicity(self):
        ordered = replay.row_key(("x",), [(1,), (2,)])
        reversed_rows = replay.row_key(("x",), [(2,), (1,)])
        self.assertNotEqual(ordered, reversed_rows)
        self.assertEqual(
            replay.unordered_key(("x",), [(1,), (2,)]),
            replay.unordered_key(("x",), [(2,), (1,)]),
        )
        self.assertNotEqual(
            replay.unordered_key(("x",), [(1,), (1,)]),
            replay.unordered_key(("x",), [(1,)]),
        )


if __name__ == "__main__":
    unittest.main()
