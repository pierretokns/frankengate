import unittest

from codex_openai_proxy import _extract_json, build_prompt


class CodexOpenAIProxyTest(unittest.TestCase):
    def test_prompt_preserves_tool_schema_and_transcript(self):
        prompt = build_prompt({
            "messages": [{"role": "user", "content": "List tables"}],
            "tools": [{"type": "function", "function": {"name": "describe_schema"}}],
        })
        self.assertIn("describe_schema", prompt)
        self.assertIn("List tables", prompt)

    def test_extract_json_handles_fenced_or_plain_output(self):
        self.assertEqual(_extract_json('{"content":"ok"}')['content'], "ok")
        self.assertEqual(_extract_json('```json\n{"content":"ok"}\n```')['content'], "ok")


if __name__ == "__main__":
    unittest.main()
