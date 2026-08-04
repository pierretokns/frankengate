import importlib.util
import pathlib
import sqlite3
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "bird_sql_skill_factorial_verify.py"
SPEC = importlib.util.spec_from_file_location("bird_sql_skill_factorial_verify", MODULE_PATH)
verify = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verify)


class BirdSQLSkillFactorialVerifyTest(unittest.TestCase):
    def test_duplicate_evaluator_preserves_bounded_row_limit(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE items (value INTEGER)")
            connection.executemany("INSERT INTO items(value) VALUES (?)", ((i,) for i in range(10_001)))
            with self.assertRaises(verify.ReplayLimit):
                verify.execute(connection, "SELECT value FROM items")
        finally:
            connection.close()

    def test_candidate_sql_strips_one_terminal_semicolon(self):
        self.assertEqual("SELECT 1", verify.candidate_sql("SELECT 1;"))
        self.assertIsNone(verify.candidate_sql("SELECT 1; SELECT 2"))


if __name__ == "__main__":
    unittest.main()
