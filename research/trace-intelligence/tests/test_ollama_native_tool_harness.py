from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from ollama_native_tool_harness import OllamaNativeChatAPI, _load_fixture


class OllamaNativeToolHarnessTest(unittest.TestCase):
    def test_normalizes_native_tool_arguments(self) -> None:
        self.assertEqual(OllamaNativeChatAPI.__name__, "OllamaNativeChatAPI")

    def test_loads_the_frozen_fixture(self) -> None:
        value, limits, fixtures = _load_fixture(
            Path(__file__).parents[1]
            / "configs"
            / "experiments"
            / "natural-trace-skill-protocol-fixture-2026-07-30.json"
        )
        self.assertEqual(len(fixtures), 6)
        self.assertEqual(limits.max_sql_attempts, 2)
        self.assertEqual(value["schema_version"], "frankengate-native-tool-protocol-fixture-v1")
