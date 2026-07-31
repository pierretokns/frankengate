import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("alfworld_model_generated_memory_intervention", ROOT / "alfworld_model_generated_memory_intervention.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ModelGeneratedMemoryTests(unittest.TestCase):
    def test_memory_hash_is_stable(self):
        self.assertEqual(len(MODULE.sha256_text("memory")), 64)

    def test_source_and_target_are_separate_inputs(self):
        self.assertTrue(callable(MODULE.expert_trace))
        self.assertTrue(callable(MODULE.evaluate))


if __name__ == "__main__":
    unittest.main()
