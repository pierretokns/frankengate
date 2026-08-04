"""Run the governed Defog trace-mined pilot through Ollama's native harness.

The SQL evaluator, authority contract, task selection, and three intervention
arms are shared with ``defog_trace_mined_skill_pilot``. Only the model adapter
changes, so a terminal/protocol difference can be attributed to the harness
boundary rather than to a new task or candidate.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import defog_sql_factorial as factorial
from defog_trace_mined_skill_pilot import run_pilot
from ollama_native_tool_harness import OllamaNativeChatAPI


class NativeFactorialAPI(OllamaNativeChatAPI):
    def __init__(
        self,
        *,
        endpoint: str,
        request_model_id: str,
        timeout_seconds: int,
        max_tokens: int,
    ) -> None:
        super().__init__(endpoint=endpoint, model=request_model_id)
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--authority-manifest", type=Path, required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    original_api = factorial.ChatAPI
    factorial.ChatAPI = NativeFactorialAPI
    try:
        result = run_pilot(
            source_root=args.source_root.resolve(strict=True),
            cohort_manifest=args.cohort_manifest.resolve(strict=True),
            dataset_manifest=args.dataset_manifest.resolve(strict=True),
            authority_manifest=args.authority_manifest.resolve(strict=True),
            task_ids=args.task_id,
            dsn=args.dsn,
            endpoint=args.endpoint,
            model=args.model,
            raw_audit_dir=args.raw_audit_dir,
            output=args.output,
        )
    finally:
        factorial.ChatAPI = original_api
    result["harness"] = {
        "id": "ollama-native-api",
        "endpoint_scope": "loopback-only",
        "adapter_reused": "ollama_native_tool_harness.OllamaNativeChatAPI",
    }
    # The shared pilot has already written a content-free result. Rewrite it
    # only to bind the harness identity; raw SQL and model records stay out.
    args.output.write_text(__import__("json").dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(__import__("json").dumps({"status": "ok", "arms": result["arms"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
