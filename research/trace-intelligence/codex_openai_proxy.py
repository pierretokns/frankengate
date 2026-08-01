#!/usr/bin/env python3
"""Small OpenAI-compatible chat proxy backed by the authenticated Codex CLI.

This is research glue for public Defog experiments. Each request is translated
to a stateless Codex prompt and the model is constrained to return a structured
assistant message or function calls. It does not expose a production endpoint
and should only bind to loopback.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
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


def _message_text(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    return json.dumps(content, sort_keys=True, ensure_ascii=False)


def build_prompt(payload: Mapping[str, Any]) -> str:
    messages = payload.get("messages") or []
    tools = payload.get("tools") or []
    transcript: list[str] = []
    for message in messages:
        role = str(message.get("role", "unknown"))
        transcript.append(f"[{role}] {_message_text(message)}")
        if message.get("tool_calls"):
            transcript.append(
                "[assistant_tool_calls] "
                + json.dumps(message["tool_calls"], sort_keys=True, ensure_ascii=False)
            )
        if role == "tool":
            transcript.append(f"[tool_name] {message.get('name', '')}")
    return (
        "You are an OpenAI-compatible model inside a controlled SQL-agent "
        "experiment. Do not execute shell commands, read files, browse, or "
        "call external tools. Based only on the conversation and tool schemas, "
        "return one JSON object matching the required output schema. If the "
        "agent should call a function, set finish_reason='tool_calls', content "
        "null, and emit one or more calls with arguments as JSON-encoded strings. Use "
        "only the exact function names and argument shapes provided. If the "
        "agent should answer without a call, set finish_reason='stop', provide "
        "content, and use an empty tool_calls array. Never invent tool results "
        "or claim a query executed unless the transcript shows it.\n\n"
        "TOOL SCHEMAS:\n"
        + json.dumps(tools, sort_keys=True, ensure_ascii=False)
        + "\n\nCONVERSATION:\n"
        + "\n".join(transcript)
    )


def _extract_json(value: str) -> Mapping[str, Any]:
    value = value.strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(value[start:end + 1])
    if not isinstance(parsed, Mapping):
        raise ValueError("Codex output was not an object")
    return parsed


def call_codex(payload: Mapping[str, Any], *, model: str, timeout: int) -> Mapping[str, Any]:
    prompt = build_prompt(payload)
    with tempfile.TemporaryDirectory(prefix="frankengate-codex-proxy-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        output_path = root / "output.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "--output-schema", str(schema_path), "--output-last-message", str(output_path),
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd="/private/tmp",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"codex exited {completed.returncode}: {completed.stderr[-2000:]}")
        if not output_path.exists():
            raise RuntimeError("codex did not write a final response")
        return _extract_json(output_path.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    model = "gpt-5.6-luna"
    timeout = 180

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = call_codex(payload, model=self.model, timeout=self.timeout)
            content = result.get("content")
            tool_calls = []
            for call in result.get("tool_calls") or []:
                tool_calls.append({
                    "id": str(call.get("id") or f"codex-call-{len(tool_calls) + 1}"),
                    "type": "function",
                    "function": {
                        "name": str(call.get("name", "")),
                        "arguments": (
                            str(call.get("arguments"))
                            if isinstance(call.get("arguments"), str)
                            else json.dumps(call.get("arguments") or {}, separators=(",", ":"))
                        ),
                    },
                })
            message = {"role": "assistant", "content": content}
            if tool_calls:
                message["tool_calls"] = tool_calls
            body = {
                "id": f"codex-proxy-{time.time_ns()}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.model,
                "choices": [{"index": 0, "message": message, "finish_reason": result.get("finish_reason", "tool_calls" if tool_calls else "stop")}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "system_fingerprint": "codex-cli-research-proxy",
            }
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except Exception as exc:  # research endpoint reports failure explicitly
            encoded = json.dumps({"error": {"message": str(exc), "type": "proxy_error"}}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    Handler.model = args.model
    Handler.timeout = args.timeout
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"status": "listening", "host": args.host, "port": args.port, "model": args.model}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
