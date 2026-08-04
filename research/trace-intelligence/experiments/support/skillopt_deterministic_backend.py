"""Deterministic SkillOpt backend used only for lifecycle smoke tests.

This is deliberately not a model-quality substitute.  It exercises SkillOpt's
rollout -> reflect -> aggregate -> update -> gate machinery without requiring
an HTTP model server, so a missing model service cannot be confused with a
failed optimizer experiment.  Quality claims must use the real-model arms.
"""

from __future__ import annotations

import json
from typing import Any


_PATCH = {
    "reasoning": "deterministic lifecycle smoke candidate",
    "edits": [
        {
            "op": "append",
            "target": "",
            "content": (
                "Before selecting an action, inspect the admissible action list "
                "and choose an action that advances the task."
            ),
        }
    ],
}


def _response(stage: str) -> str:
    if stage == "rollout":
        return "<think>deterministic smoke action</think><action>look</action>"
    if stage == "analyst":
        return json.dumps({"patch": _PATCH})
    if stage == "merge":
        return json.dumps(_PATCH)
    return json.dumps(_PATCH)


def install() -> None:
    """Monkey-patch only the disposable OpenAI-compatible SkillOpt backend."""
    from skillopt.model import openai_compatible_backend as backend

    def fake_chat_messages_impl(
        messages: list[dict[str, Any]],
        max_completion_tokens: int,
        retries: int,
        stage: str,
        *,
        role: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        return_message: bool = False,
        deployment: str | None = None,
        timeout: float | None = None,
    ) -> tuple[Any, dict[str, int]]:
        del messages, max_completion_tokens, retries, role, tools, tool_choice
        del deployment, timeout
        content = _response(stage)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if return_message:
            return {"role": "assistant", "content": content}, usage
        return content, usage

    backend._chat_messages_impl = fake_chat_messages_impl


install()
