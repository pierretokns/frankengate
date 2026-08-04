"""Run the frozen native-tool fixture through Ollama's native chat endpoint.

This adapter returns the same internal response shape as the OpenAI-compatible
runner, allowing a content-free, same-fixture harness comparison. Raw
messages, arguments, and model responses stay in an external audit directory.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import native_tool_protocol_compliance as protocol
from natural_trace_skill_protocol_intervention import ARTIFACTS, BASE_PROMPT, VARIANTS


SCHEMA_VERSION = "frankengate-ollama-native-tool-harness-v1"


class HarnessError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class OllamaNativeChatAPI:
    request_model_id: str

    def __init__(self, *, endpoint: str, model: str) -> None:
        if not endpoint.strip() or not model.strip():
            raise HarnessError("endpoint and model are required")
        self.url = endpoint.rstrip("/") + "/api/chat"
        self.request_model_id = model

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        seed: int,
        max_tokens: int,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], float]:
        # Ollama accepts the OpenAI function schema, but its native response
        # omits call IDs and returns arguments as an object. Normalize both.
        native_messages = deepcopy(messages)
        for message in native_messages:
            if message.get("role") == "tool":
                message.pop("tool_call_id", None)
                message.pop("name", None)
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                if isinstance(function.get("arguments"), str):
                    try:
                        function["arguments"] = json.loads(function["arguments"])
                    except json.JSONDecodeError:
                        pass
        payload = {
            "model": self.request_model_id,
            "messages": native_messages,
            "tools": tools,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "seed": seed,
                "num_predict": max_tokens,
            },
        }
        request = Request(
            self.url,
            data=_canonical(payload),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HarnessError(f"native Ollama HTTP {exc.code}: {detail[:1000]}") from exc
        except (URLError, TimeoutError) as exc:
            raise HarnessError(f"native Ollama request failed: {exc}") from exc
        elapsed_ms = (time.perf_counter() - started) * 1_000
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HarnessError("native Ollama returned invalid JSON") from exc
        message = value.get("message") or {}
        normalized_calls = []
        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            arguments = function.get("arguments") or {}
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
            normalized_calls.append(
                {
                    "id": str(call.get("id") or f"ollama-call-{index}"),
                    "type": "function",
                    "function": {
                        "name": str(function.get("name") or ""),
                        "arguments": arguments,
                    },
                }
            )
        normalized_message = {
            "role": "assistant",
            "content": message.get("content") or "",
        }
        if normalized_calls:
            normalized_message["tool_calls"] = normalized_calls
        normalized = {
            "choices": [
                {
                    "index": 0,
                    "message": normalized_message,
                    "finish_reason": "tool_calls" if normalized_calls else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(value.get("prompt_eval_count") or 0),
                "completion_tokens": int(value.get("eval_count") or 0),
            },
            "system_fingerprint": "ollama-native-api",
        }
        return normalized, elapsed_ms


def _load_fixture(path: Path):
    original_variants = protocol.VARIANT_IDS
    protocol.VARIANT_IDS = VARIANTS
    try:
        value, limits, fixtures = protocol.load_fixture(path)
    finally:
        protocol.VARIANT_IDS = original_variants
    if tuple(item.get("id") for item in value.get("variants", [])) != VARIANTS:
        raise HarnessError("fixture variant order changed")
    return value, limits, fixtures


def run_experiment(
    *, fixture_path: Path, endpoint: str, model: str, raw_audit_dir: Path, output: Path
) -> dict[str, Any]:
    protocol.require_external_raw_path(raw_audit_dir)
    if output.exists():
        raise HarnessError(f"refusing to overwrite {output}")
    value, limits, fixtures = _load_fixture(fixture_path)
    api = OllamaNativeChatAPI(endpoint=endpoint, model=model)
    receipts = []
    original_prompt = protocol.BASE_SYSTEM_PROMPT
    try:
        protocol.VARIANT_IDS = VARIANTS
        for fixture in fixtures:
            fixture_hash = hashlib.sha256(fixture.fixture_id.encode()).hexdigest()[:16]
            for variant in fixture.variant_order:
                protocol.BASE_SYSTEM_PROMPT = BASE_PROMPT + ARTIFACTS[variant]
                raw_path = raw_audit_dir / f"{fixture_hash}-{variant}.jsonl"
                receipts.append(
                    protocol.run_episode(
                        fixture=fixture,
                        variant=variant,
                        limits=limits,
                        api=api,
                        executor=protocol.SyntheticProtocolExecutor(fixture.executor_mode),
                        raw_audit_path=raw_path,
                    )
                )
    finally:
        protocol.BASE_SYSTEM_PROMPT = original_prompt
    aggregate = protocol.aggregate_receipts(
        receipts=receipts,
        fixture_manifest=value,
        fixture_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        request_model_id=model,
    )
    aggregate.update(
        {
            "schema_version": SCHEMA_VERSION,
            "harness": {"id": "ollama-native-api", "endpoint_scope": "loopback-only"},
            "candidate_artifacts": {
                name: {
                    "classification": "baseline" if name == "no_skill" else "placebo" if name == "formatting_placebo" else "trace_mined_candidate",
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
                for name, text in ARTIFACTS.items()
            },
            "claim_boundary": {
                "real_model_tool_loop_executed": True,
                "native_ollama_harness_executed": True,
                "natural_trace_skill_benefit_confirmed": False,
                "enterprise_quality_estimated": False,
                "reason": "Same synthetic content-free fixture as the OpenAI-compatible arm; protocol and latency comparison only.",
                "next_required": "Compare this harness on family-disjoint domain tasks with an independent semantic/security verifier.",
            },
            "raw_data_committed": False,
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        fixture_path=args.fixture,
        endpoint=args.endpoint,
        model=args.model,
        raw_audit_dir=args.raw_audit_dir,
        output=args.output,
    )
    print(json.dumps({"status": "ok", "variants": result["variant_results"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
