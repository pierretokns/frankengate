import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "crmarena_trace_replay.py"
SPEC = importlib.util.spec_from_file_location("crmarena_trace_replay", MODULE_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(replay)


class CRMARenaTraceReplayTest(unittest.TestCase):
    def test_extracts_shell_quoted_sql_with_inner_identifiers(self):
        command = 'python3 query.py "SELECT Id FROM \\"Case\\" WHERE Status = \'Closed\'"'
        self.assertEqual(
            'SELECT Id FROM "Case" WHERE Status = \'Closed\'',
            replay.extract_sql(command),
        )

    def test_ignores_schema_and_non_query_commands(self):
        self.assertIsNone(replay.extract_sql("cat schema.md"))
        self.assertIsNone(replay.extract_sql("python3 query.py \'UPDATE Case SET Status=\\\'Closed\\\'\'"))


if __name__ == "__main__":
    unittest.main()
