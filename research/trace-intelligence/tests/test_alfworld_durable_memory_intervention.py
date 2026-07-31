import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("alfworld_durable_memory_intervention", ROOT / "alfworld_durable_memory_intervention.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AlfworldDurableMemoryTests(unittest.TestCase):
    def test_memory_has_stable_provenance_and_no_future_outcomes(self):
        self.assertIn("prior successful", MODULE.MEMORY_TEXT)
        self.assertNotIn("won", MODULE.MEMORY_TEXT.lower())
        self.assertEqual(len(MODULE.sha256_text(MODULE.MEMORY_TEXT)), 64)


if __name__ == "__main__":
    unittest.main()
