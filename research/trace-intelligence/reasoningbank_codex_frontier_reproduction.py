#!/usr/bin/env python3
"""Run upstream ReasoningBank with a Codex-subscription memory judge.

The upstream runner is unchanged; only its LLM client is replaced because the
documented LiteLLM/Azure path is unavailable on this machine. The substitution
is explicit in the output receipt and is not treated as OpenAI/Foundry parity.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


class CodexMemoryClient:
    def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 65536,
        reasoning_effort: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="reasoningbank-codex-") as temp:
            output = Path(temp) / "last_message.txt"
            user = (
                "Follow the system instruction exactly. Return only the requested "
                "answer, with no markdown fence or preamble.\n\n" + prompt
            )
            if system_prompt:
                user = system_prompt + "\n\n" + user
            command = [
                "codex",
                "exec",
                "--json",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--cd",
                temp,
                "--model",
                model.split("/")[-1],
                "--output-last-message",
                str(output),
                "-",
            ]
            if reasoning_effort:
                command[2:2] = ["-c", f"model_reasoning_effort={reasoning_effort}"]
            completed = subprocess.run(
                command,
                input=user,
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            if output.exists():
                return output.read_text(encoding="utf-8", errors="replace").strip()
            for line in completed.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item = event.get("item", {}) or {}
                if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                    return str(item.get("text", "")).strip()
            raise RuntimeError(
                f"Codex memory call failed rc={completed.returncode}: "
                f"{completed.stderr[-500:]}"
            )


def main() -> int:
    from rho import cli
    from rho.selection import llm_client

    llm_client.LiteLLMClient = CodexMemoryClient  # type: ignore[assignment]
    args = [
        "reasoningbank",
        "--dataset",
        "locomo:/private/tmp/rho-upstream.bTsclF/data/locomo10.json",
        "--run-dir",
        "/private/tmp/reasoningbank-locomo-codex-bounded-20260802-r2",
        "--max-train-tasks",
        "2",
        "--max-grading-tasks",
        "2",
        "--memory-n",
        "1",
        "--eval-variant",
        "frozen",
        "--model",
        "gpt-5.6-luna",
        "--reasoning-effort",
        "high",
        "--memory-model",
        "gpt-5.6-luna",
        "--memory-reasoning-effort",
        "high",
        "--embedding-provider",
        "litellm",
        "--embedding-model",
        "local:BAAI/bge-small-en-v1.5",
        "--grade-workers",
        "1",
        "--codex-concurrency",
        "1",
        "--cache",
        "off",
        "--codex-config",
        "/private/tmp/rho-upstream.bTsclF/configs/codex.chatgpt-default.toml",
    ]
    return cli.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
