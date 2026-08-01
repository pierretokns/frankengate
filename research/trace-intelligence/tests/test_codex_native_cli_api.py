from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from codex_native_cli_api import NativeCodexCLIAPI, _extract_json, build_native_prompt


class NativeCodexCLIHarnessTest(unittest.TestCase):
    def test_serializer_is_canonical_and_contains_tool_contract(self) -> None:
        prompt = build_native_prompt(
            messages=[{"role": "user", "content": "hello"}],
            tools=[{"type": "function", "function": {"name": "describe_schema"}}],
            seed=17,
        )
        self.assertIn("MESSAGES (canonical JSON", prompt)
        self.assertIn('"name":"describe_schema"', prompt)
        self.assertIn("REPLAY SEED:\n17", prompt)

    def test_parser_recovers_json_fence_like_output(self) -> None:
        value = _extract_json("prefix\n{\"content\":null,\"tool_calls\":[],\"finish_reason\":\"stop\"}\n")
        self.assertEqual(value["finish_reason"], "stop")

    def test_harness_identity_is_distinct(self) -> None:
        self.assertEqual(NativeCodexCLIAPI.harness_id, "codex-cli-native-json-v1")


if __name__ == "__main__":
    unittest.main()
