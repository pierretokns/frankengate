#!/usr/bin/env python3
"""Audit per-request tool narrowing in a pinned MLX/Qwen runtime.

The emitted artifact contains only source/model hashes and synthetic prompt
hashes. It does not contain benchmark, customer, or enterprise content.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


SCHEMA_VERSION = "frankengate-mlx-dynamic-tool-conformance-v1"


class ConformanceError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def tool(name: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Synthetic {name} tool.",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def load_parser(path: Path):
    spec = importlib.util.spec_from_file_location(
        "pinned_qwen3_coder_parser",
        path,
    )
    if spec is None or spec.loader is None:
        raise ConformanceError("could not load parser source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_tool_call


def run_conformance(
    *,
    snapshot: Path,
    server_source: Path,
    parser_source: Path,
) -> dict[str, Any]:
    for required in (
        snapshot / "tokenizer_config.json",
        snapshot / "chat_template.jinja",
        server_source,
        parser_source,
    ):
        if not required.is_file():
            raise ConformanceError(f"missing required input: {required}")

    tokenizer = AutoTokenizer.from_pretrained(
        str(snapshot),
        local_files_only=True,
    )
    execute = tool("execute_sql", {"sql": {"type": "string"}})
    submit = tool("submit_sql", {"attempt_id": {"type": "string"}})
    abstain = tool("abstain", {"reason_code": {"type": "string"}})
    messages = [
        {"role": "system", "content": "Synthetic protocol check."},
        {"role": "user", "content": "Use the synthetic tools."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "synthetic-call-1",
                    "type": "function",
                    "function": {
                        "name": "execute_sql",
                        "arguments": {"sql": "SELECT synthetic_value"},
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "synthetic-call-1",
            "name": "execute_sql",
            "content": (
                '{"attempt_id":"synthetic-attempt-1","status":"ok"}'
            ),
        },
    ]
    render_args = {
        "tokenize": False,
        "add_generation_prompt": True,
        "enable_thinking": False,
    }
    all_prompt = tokenizer.apply_chat_template(
        messages,
        tools=[execute, submit, abstain],
        **render_args,
    )
    terminal_prompt = tokenizer.apply_chat_template(
        messages,
        tools=[submit, abstain],
        **render_args,
    )
    try:
        current_tool_block = terminal_prompt.split(
            "<tools>",
            1,
        )[1].split("</tools>", 1)[0]
    except IndexError as exc:
        raise ConformanceError("rendered prompt has no tools block") from exc

    parse_tool_call = load_parser(parser_source)
    unoffered = parse_tool_call(
        (
            "<function=execute_sql>\n"
            "<parameter=sql>\nSELECT synthetic_value\n</parameter>\n"
            "</function>"
        ),
        [submit, abstain],
    )
    checks = {
        "current_tools_omit_execute_sql": (
            "execute_sql" not in current_tool_block
        ),
        "current_tools_include_submit_sql": (
            "submit_sql" in current_tool_block
        ),
        "current_tools_include_abstain": "abstain" in current_tool_block,
        "historical_execute_sql_call_preserved": (
            "<function=execute_sql>" in terminal_prompt
        ),
        "historical_tool_result_preserved": (
            "synthetic-attempt-1" in terminal_prompt
        ),
        "parser_accepts_unoffered_function_name": (
            unoffered.get("name") == "execute_sql"
        ),
    }
    if not all(checks.values()):
        raise ConformanceError(f"conformance check failed: {checks}")

    return {
        "schema_version": SCHEMA_VERSION,
        "claim_scope": "synthetic_runtime_protocol_conformance_only",
        "benchmark_content_used": False,
        "checks": checks,
        "interpretation": {
            "dynamic_tool_narrowing_supported": True,
            "historical_tool_messages_require_current_schema": False,
            "parser_is_authorization_boundary": False,
            "runner_must_reject_unoffered_tool_names": True,
        },
        "input_receipts": {
            "snapshot_path_disclosed": False,
            "snapshot_directory_name_sha256": sha256_bytes(
                snapshot.name.encode("utf-8")
            ),
            "tokenizer_config_sha256": sha256_file(
                snapshot / "tokenizer_config.json"
            ),
            "chat_template_sha256": sha256_file(
                snapshot / "chat_template.jinja"
            ),
            "mlx_server_source_sha256": sha256_file(server_source),
            "qwen_parser_source_sha256": sha256_file(parser_source),
        },
        "synthetic_render_receipts": {
            "all_tools_prompt_sha256": sha256_bytes(
                all_prompt.encode("utf-8")
            ),
            "terminal_only_prompt_sha256": sha256_bytes(
                terminal_prompt.encode("utf-8")
            ),
            "all_tools_prompt_characters": len(all_prompt),
            "terminal_only_prompt_characters": len(terminal_prompt),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--server-source", required=True, type=Path)
    parser.add_argument("--parser-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        raise ConformanceError(f"refusing to overwrite: {args.output}")
    result = run_conformance(
        snapshot=args.snapshot,
        server_source=args.server_source,
        parser_source=args.parser_source,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(result) + b"\n"
    args.output.write_bytes(encoded)
    print(
        json.dumps(
            {
                "status": "ok",
                "output_sha256": sha256_bytes(encoded),
                "checks": result["checks"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
