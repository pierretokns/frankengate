from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from defog_trace_mined_native_harness import NativeFactorialAPI


class DefogTraceMinedNativeHarnessTest(unittest.TestCase):
    def test_adapter_keeps_factorial_constructor_contract(self) -> None:
        api = NativeFactorialAPI(
            endpoint="http://127.0.0.1:11434",
            request_model_id="llama3.2:latest",
            timeout_seconds=60,
            max_tokens=256,
        )
        self.assertEqual(api.request_model_id, "llama3.2:latest")
