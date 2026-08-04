import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "trace2skill_governed_launcher.py"
SANDBOX_PATH = pathlib.Path(__file__).parents[1] / "governed_tool_sandbox.py"

sandbox_spec = importlib.util.spec_from_file_location(
    "governed_tool_sandbox", SANDBOX_PATH
)
sandbox_module = importlib.util.module_from_spec(sandbox_spec)
assert sandbox_spec.loader is not None
sys.modules[sandbox_spec.name] = sandbox_module
sandbox_spec.loader.exec_module(sandbox_module)

SPEC = importlib.util.spec_from_file_location(
    "trace2skill_governed_launcher", MODULE_PATH
)
launcher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


class Trace2SkillGovernedLauncherTest(unittest.TestCase):
    def test_option_value_supports_both_cli_forms(self):
        self.assertEqual(
            "/skills", launcher.option_value(["--skills_dir", "/skills"], "--skills_dir")
        )
        self.assertEqual(
            "/skills", launcher.option_value(["--skills_dir=/skills"], "--skills_dir")
        )
        self.assertIsNone(launcher.option_value([], "--skills_dir"))

    def test_source_verifier_fails_closed_on_hash_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "spreadsheet_agent" / "tools").mkdir(parents=True)
            (root / "data" / "spreadsheetbench_verified" / "spreadsheetbench_verified_400").mkdir(
                parents=True
            )
            (root / "run_spreadsheetbench.py").write_text("", encoding="utf-8")
            (root / "evaluate_with_official.py").write_text("", encoding="utf-8")
            (root / "spreadsheet_agent" / "tools" / "bash.py").write_text(
                "", encoding="utf-8"
            )
            dataset = root / launcher.DATASET_RELATIVE_PATH
            dataset.write_text(json.dumps([{"id": 1}] * 400), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                launcher.verify_source(root)

    def test_manifest_pin_matches_available_snapshot_when_present(self):
        root = pathlib.Path("/private/tmp/trace2skill-3d0b52a-research")
        if not root.exists():
            self.skipTest("external pinned Trace2Skill snapshot is unavailable")
        receipt = launcher.verify_source(root)
        self.assertEqual(400, receipt["dataset_rows"])
        self.assertEqual(launcher.PINNED_REVISION, receipt["revision"])


if __name__ == "__main__":
    unittest.main()
