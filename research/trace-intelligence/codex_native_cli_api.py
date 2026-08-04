#!/usr/bin/env python3
"""Direct Codex CLI chat adapter with a native transcript serializer.

This is intentionally a separate harness from ``codex_openai_proxy.py``:
there is no HTTP server, and messages/tools are serialized as canonical JSON
records inside a direct ``codex exec`` prompt. It returns the same small
OpenAI-shaped response consumed by the factorial runner so the evaluator and
governed database remain identical.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Mapping


OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["content", "tool_calls", "finish_reason"],
    "properties": {
        "content": {"type": ["string", "null"]},
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "name", "arguments"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "arguments": {"type": "string"},
                },
            },
        },
        "finish_reason": {"type": "string", "enum": ["stop", "tool_calls"]},
    },
}


def _extract_json(text: str) -> Mapping[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, Mapping):
        raise ValueError("native Codex output was not an object")
    return value


def build_native_prompt(
    *, messages: list[Mapping[str, Any]], tools: list[Mapping[str, Any]], seed: int
) -> str:
    return (
        "You are the model in a controlled PostgreSQL tool-use experiment. "
        "Do not execute shell commands, read files, browse, or call external "
        "tools. Respond with exactly one JSON object matching the output schema. "
        "Use only the provided function names and argument shapes. Emit a tool "
        "call when the agent should act; emit stop with content only when the "
        "agent should answer. Never invent tool results.\n\n"
        "OUTPUT SCHEMA:\n"
        + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":"))
        + "\n\nTOOLS:\n"
        + json.dumps(tools, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n\nREPLAY SEED:\n"
        + str(seed)
        + "\n\nMESSAGES (canonical JSON, in order):\n"
        + "\n".join(
            json.dumps(message, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            for message in messages
        )
    )


class NativeCodexCLIAPI:
    harness_id = "codex-cli-native-json-v1"

    def __init__(self, *, endpoint: str, request_model_id: str, timeout_seconds: int, max_tokens: int) -> None:
        # endpoint is accepted for interface compatibility but deliberately not
        # used: this harness invokes the authenticated local Codex CLI directly.
        self.endpoint = endpoint
        self.request_model_id = request_model_id
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        seed: int,
        max_tokens: int | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any], float]:
        prompt = build_native_prompt(messages=messages, tools=tools or [], seed=seed)
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="frankengate-codex-native-") as directory:
            root = Path(directory)
            schema = root / "schema.json"
            output = root / "output.json"
            schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
            command = [
                "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check", "-s", "read-only", "-m", self.request_model_id,
                "--output-schema", str(schema), "--output-last-message", str(output),
            ]
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout_seconds or self.timeout_seconds,
                cwd="/private/tmp",
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"native codex exited {completed.returncode}: {completed.stderr[-2_000:]}"
                )
            if not output.exists():
                raise RuntimeError("native codex did not write a final response")
            value = _extract_json(output.read_text(encoding="utf-8"))
        tool_calls = []
        for index, call in enumerate(value.get("tool_calls") or [], start=1):
            arguments = call.get("arguments")
            tool_calls.append(
                {
                    "id": str(call.get("id") or f"native-call-{index}"),
                    "type": "function",
                    "function": {
                        "name": str(call.get("name", "")),
                        "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments or {}, separators=(",", ":")),
                    },
                }
            )
        message: dict[str, Any] = {"role": "assistant", "content": value.get("content")}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return (
            {
                "choices": [{
                    "index": 0,
                    "message": message,
                    "finish_reason": value.get("finish_reason", "tool_calls" if tool_calls else "stop"),
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "system_fingerprint": self.harness_id,
            },
            (time.perf_counter() - started) * 1_000,
        )
