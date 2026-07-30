"""Natural Wisp trajectory adapter for the upstream AgentEvals experiment."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NaturalToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None
    result_observed: bool = False


@dataclass(frozen=True)
class NaturalTrajectory:
    source_sha256: str
    user_text: str
    final_response: str
    tool_calls: tuple[NaturalToolCall, ...]


@dataclass(frozen=True)
class CohortCase:
    case_id: str
    source_path: Path
    trajectory: NaturalTrajectory


def _stable_id(namespace: str, source_sha256: str, width: int) -> str:
    return hashlib.sha256(f"{namespace}\0{source_sha256}".encode("utf-8")).hexdigest()[
        :width
    ]


def _otlp_attribute(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        encoded = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": value}
    else:
        encoded = {"stringValue": str(value)}
    return {"key": key, "value": encoded}


def _message_json(role: str, text: str) -> str:
    return json.dumps(
        [{"role": role, "content": text}],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def build_otlp_export(
    trajectory: NaturalTrajectory,
    *,
    arm: str,
) -> dict[str, Any]:
    """Project a natural trajectory into AgentEvals' OTLP/GenAI input contract."""
    trace_id = _stable_id("trace", trajectory.source_sha256, 32)
    root_id = _stable_id("root", trajectory.source_sha256, 16)
    llm_id = _stable_id("llm", trajectory.source_sha256, 16)
    start = 1_000_000_000
    root_attributes = [
        _otlp_attribute("gen_ai.operation.name", "invoke_agent"),
        _otlp_attribute("gen_ai.agent.name", "frankengate_wisp"),
        _otlp_attribute("frankengate.experiment.arm", arm),
    ]
    llm_attributes = [
        _otlp_attribute("gen_ai.request.model", "recorded-natural-trace"),
        _otlp_attribute(
            "gen_ai.input.messages",
            _message_json("user", trajectory.user_text),
        ),
        _otlp_attribute(
            "gen_ai.output.messages",
            _message_json("assistant", trajectory.final_response),
        ),
    ]
    spans: list[dict[str, Any]] = [
        {
            "traceId": trace_id,
            "spanId": root_id,
            "name": "invoke_agent frankengate_wisp",
            "kind": "SPAN_KIND_INTERNAL",
            "startTimeUnixNano": str(start),
            "endTimeUnixNano": str(start + 10_000_000),
            "attributes": root_attributes,
            "status": {"code": 0},
        },
        {
            "traceId": trace_id,
            "spanId": llm_id,
            "parentSpanId": root_id,
            "name": "chat recorded-natural-trace",
            "kind": "SPAN_KIND_CLIENT",
            "startTimeUnixNano": str(start + 1_000_000),
            "endTimeUnixNano": str(start + 9_000_000),
            "attributes": llm_attributes,
            "status": {"code": 0},
        },
    ]
    for index, call in enumerate(trajectory.tool_calls):
        attributes = [
            _otlp_attribute("gen_ai.tool.name", call.name),
            _otlp_attribute("gen_ai.tool.call.id", call.call_id),
            _otlp_attribute(
                "gen_ai.tool.call.arguments",
                json.dumps(call.arguments, sort_keys=True, separators=(",", ":")),
            ),
        ]
        if call.result_observed:
            attributes.append(
                _otlp_attribute(
                    "gen_ai.tool.call.result",
                    call.result
                    if isinstance(call.result, str)
                    else json.dumps(call.result, sort_keys=True, separators=(",", ":")),
                )
            )
        spans.append(
            {
                "traceId": trace_id,
                "spanId": _stable_id(
                    f"tool-{index}-{call.call_id}", trajectory.source_sha256, 16
                ),
                "parentSpanId": root_id,
                "name": f"execute_tool {call.name}",
                "kind": "SPAN_KIND_INTERNAL",
                "startTimeUnixNano": str(start + (index + 2) * 1_000_000),
                "endTimeUnixNano": str(start + (index + 2) * 1_000_000 + 500_000),
                "attributes": attributes,
                "status": {"code": 0},
            }
        )
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _otlp_attribute("service.name", "frankengate-wisp-projection")
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "frankengate.trace-intelligence.agentevals",
                            "version": "1",
                        },
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def build_eval_set(trajectory: NaturalTrajectory) -> dict[str, Any]:
    """Build the upstream Google ADK EvalSet consumed by AgentEvals."""
    case_id = _stable_id("eval", trajectory.source_sha256, 24)
    tool_uses = [
        {"name": call.name, "args": call.arguments, "id": call.call_id}
        for call in trajectory.tool_calls
    ]
    tool_responses = [
        {
            "name": call.name,
            "response": {"content": call.result},
            "id": call.call_id,
        }
        for call in trajectory.tool_calls
        if call.result_observed
    ]
    return {
        "eval_set_id": f"frankengate-wisp-{case_id}",
        "eval_cases": [
            {
                "eval_id": case_id,
                "conversation": [
                    {
                        "invocation_id": case_id,
                        "user_content": {
                            "role": "user",
                            "parts": [{"text": trajectory.user_text}],
                        },
                        "final_response": {
                            "role": "model",
                            "parts": [{"text": trajectory.final_response}],
                        },
                        "intermediate_data": {
                            "tool_uses": tool_uses,
                            "tool_responses": tool_responses,
                        },
                    }
                ],
            }
        ],
    }


MUTATION_ARMS = (
    "baseline",
    "benign_id_remap",
    "benign_response_wrapper",
    "sequence_reversal",
    "harmful_tool_drop",
    "harmful_argument_corruption",
    "harmful_response_reversal",
)

UPSTREAM_VERSION = "0.9.7"
UPSTREAM_TAG = "v0.9.7"
UPSTREAM_COMMIT = "221febbe05927923242a5edc12e68a2b70fd5ae9"
UPSTREAM_LICENSE = "Apache-2.0"
UPSTREAM_LICENSE_SHA256 = (
    "3b1ee5b1e14fda40515c18ec2f0796d632e65a20b2aca8f017c654bc26ca77bd"
)
UPSTREAM_PYPROJECT_SHA256 = (
    "22bb0564ce3defd3e5f4a20bbc15f3f028c1cdb42363528a6bda7fa1465bfdea"
)
UPSTREAM_LOCK_SHA256 = (
    "d5839865b53e776dbbd5c7ae5ae6c90864fc28f27499f74054e469ac9f77c034"
)


def mutate_trajectory(
    trajectory: NaturalTrajectory,
    arm: str,
) -> NaturalTrajectory:
    """Apply a predeclared deterministic mutation without inferring task outcome."""
    if arm not in MUTATION_ARMS:
        raise ValueError(f"unknown mutation arm: {arm}")
    if arm == "baseline":
        return trajectory
    if arm == "benign_id_remap":
        remapped = tuple(
            replace(
                call,
                call_id=f"remapped-{_stable_id(str(index), call.call_id, 12)}",
            )
            for index, call in enumerate(trajectory.tool_calls)
        )
        return replace(trajectory, tool_calls=remapped)
    if arm == "benign_response_wrapper":
        return replace(
            trajectory,
            final_response=f"Completed result: {trajectory.final_response}",
        )
    if arm == "sequence_reversal":
        return replace(trajectory, tool_calls=tuple(reversed(trajectory.tool_calls)))
    if arm == "harmful_tool_drop":
        return replace(trajectory, tool_calls=trajectory.tool_calls[:-1])
    if arm == "harmful_argument_corruption":
        if not trajectory.tool_calls:
            return trajectory
        corrupted = replace(
            trajectory.tool_calls[0],
            arguments={"frankengate_mutation": "corrupted"},
        )
        return replace(
            trajectory,
            tool_calls=(corrupted, *trajectory.tool_calls[1:]),
        )
    return replace(
        trajectory,
        final_response="The requested task failed and no successful outcome was observed.",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_upstream_checkout(upstream_root: Path) -> None:
    expected_hashes = {
        "LICENSE": UPSTREAM_LICENSE_SHA256,
        "pyproject.toml": UPSTREAM_PYPROJECT_SHA256,
        "uv.lock": UPSTREAM_LOCK_SHA256,
    }
    for relative, expected in expected_hashes.items():
        path = upstream_root / relative
        if not path.is_file() or _sha256_file(path) != expected:
            raise ValueError(f"upstream provenance mismatch: {relative}")
    commit = subprocess.run(
        ["git", "-C", str(upstream_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if commit != UPSTREAM_COMMIT:
        raise ValueError(f"upstream commit mismatch: {commit}")


def _aggregate_deterministic_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        cells.setdefault((row["arm"], row["assertion"]), []).append(row)
    output: list[dict[str, Any]] = []
    for (arm, assertion), group in sorted(cells.items()):
        numeric = [
            float(row["score"]) for row in group if row.get("score") is not None
        ]
        output.append(
            {
                "arm": arm,
                "assertion": assertion,
                "n": len(group),
                "passed": sum(row.get("status") == "PASSED" for row in group),
                "failed": sum(row.get("status") == "FAILED" for row in group),
                "errored": sum(row.get("status") == "ERRORED" for row in group),
                "mean_score": (
                    sum(numeric) / len(numeric) if numeric else None
                ),
            }
        )
    return output


def run_upstream_experiment(
    *,
    trajectories: tuple[NaturalTrajectory, ...],
    upstream_python: Path,
    upstream_root: Path,
    raw_dir: Path,
    arms: tuple[str, ...] = MUTATION_ARMS,
    include_semantic: bool = False,
    judge_model: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
) -> dict[str, Any]:
    """Run the pinned upstream package while retaining only aggregate results."""
    if not trajectories:
        raise ValueError("at least one trajectory is required")
    if not upstream_python.is_file():
        raise ValueError("upstream_python must be an existing interpreter")
    _verify_upstream_checkout(upstream_root)
    for arm in arms:
        if arm not in MUTATION_ARMS:
            raise ValueError(f"unknown mutation arm: {arm}")
    if include_semantic and (
        not judge_model or not judge_base_url or not judge_api_key
    ):
        raise ValueError(
            "semantic execution requires judge_model, judge_base_url, and judge_api_key"
        )

    raw_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, str]] = []
    for index, trajectory in enumerate(trajectories):
        case_id = _stable_id("runtime-case", trajectory.source_sha256, 24)
        eval_path = raw_dir / f"{index:04d}-eval.json"
        eval_path.write_text(
            json.dumps(build_eval_set(trajectory), ensure_ascii=False),
            encoding="utf-8",
        )
        for arm in arms:
            mutated = mutate_trajectory(trajectory, arm)
            trace_path = raw_dir / f"{index:04d}-{arm}.otlp.json"
            trace_path.write_text(
                json.dumps(
                    build_otlp_export(mutated, arm=arm),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            items.append(
                {
                    "case_id": case_id,
                    "arm": arm,
                    "trace_path": str(trace_path),
                    "eval_set_path": str(eval_path),
                }
            )

    spec_path = raw_dir / "driver-spec.json"
    raw_result_path = raw_dir / "driver-result.json"
    spec: dict[str, Any] = {
        "items": items,
        "match_types": ["EXACT", "IN_ORDER", "ANY_ORDER"],
    }
    if include_semantic:
        spec["semantic"] = {
            "arms": [
                arm
                for arm in (
                    "baseline",
                    "benign_response_wrapper",
                    "harmful_response_reversal",
                )
                if arm in arms
            ],
            "judge_model": judge_model,
            "judge_base_url": judge_base_url,
        }
    spec_path.write_text(
        json.dumps(spec),
        encoding="utf-8",
    )
    project_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    prior_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(project_root)
        if not prior_pythonpath
        else os.pathsep.join((str(project_root), prior_pythonpath))
    )
    if include_semantic:
        env["FRANKENGATE_AGENT_EVALS_JUDGE_KEY"] = str(judge_api_key)
    completed = subprocess.run(
        [
            str(upstream_python),
            "-m",
            "agentevals_interop.upstream_driver",
            "--spec",
            str(spec_path),
            "--output",
            str(raw_result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=max(120, len(items) * (95 if include_semantic else 5)),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "upstream AgentEvals driver failed "
            f"(exit={completed.returncode}, stderr_sha256="
            f"{hashlib.sha256(completed.stderr.encode()).hexdigest()})"
        )
    raw_result = json.loads(raw_result_path.read_text(encoding="utf-8"))
    package_version = str(raw_result.get("package_version"))
    if package_version != UPSTREAM_VERSION:
        raise ValueError(f"upstream package mismatch: {package_version}")
    rows = raw_result["rows"]
    semantic_rows = raw_result.get("semantic_rows", [])
    return {
        "schema_version": "frankengate-agentevals-upstream-aggregate-v1",
        "claim_boundary": "stored_trace_assertion_only",
        "changed_system_executed": False,
        "natural_trajectory_count": len(trajectories),
        "mutation_arms": list(arms),
        "upstream": {
            "repository": "https://github.com/agentevals-dev/agentevals",
            "release": UPSTREAM_TAG,
            "commit": UPSTREAM_COMMIT,
            "package": "agentevals-cli",
            "package_version": package_version,
            "python_version": raw_result.get("python_version"),
            "license": UPSTREAM_LICENSE,
            "license_sha256": UPSTREAM_LICENSE_SHA256,
            "pyproject_sha256": UPSTREAM_PYPROJECT_SHA256,
            "lock_sha256": UPSTREAM_LOCK_SHA256,
        },
        "deterministic_assertions": _aggregate_deterministic_rows(rows),
        "semantic_assertions": _aggregate_deterministic_rows(semantic_rows),
        "semantic_evaluator": (
            {
                "metric": "final_response_match_v2",
                "judge_model": judge_model,
                "judge_location": "loopback" if include_semantic else None,
                "threshold": 0.5,
            }
            if include_semantic
            else None
        ),
        "raw_artifacts_committed": False,
        "timeouts": {
            "deterministic_assertion_seconds": 30,
            "semantic_assertion_seconds": 90,
        },
    }


def _message_content(record: dict[str, Any]) -> Any:
    message = record.get("message")
    return message.get("content") if isinstance(message, dict) else None


def extract_wisp_trajectory(path: Path) -> NaturalTrajectory:
    """Extract one bounded single-turn tool trajectory from Claude Code JSONL."""
    source_bytes = path.read_bytes()
    records = [
        json.loads(line)
        for line in source_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]

    user_text = ""
    final_response = ""
    calls: list[NaturalToolCall] = []
    results: dict[str, Any] = {}

    for record in records:
        content = _message_content(record)
        if (
            not user_text
            and record.get("type") == "user"
            and isinstance(content, str)
        ):
            user_text = content

        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    arguments = block.get("input")
                    calls.append(
                        NaturalToolCall(
                            call_id=str(block.get("id", "")),
                            name=str(block.get("name", "")),
                            arguments=arguments if isinstance(arguments, dict) else {},
                        )
                    )
                elif block.get("type") == "tool_result":
                    results[str(block.get("tool_use_id", ""))] = block.get("content")
                elif (
                    record.get("type") == "assistant"
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ):
                    final_response = block["text"]

    paired = tuple(
        NaturalToolCall(
            call_id=call.call_id,
            name=call.name,
            arguments=call.arguments,
            result=results.get(call.call_id),
            result_observed=call.call_id in results,
        )
        for call in calls
    )
    return NaturalTrajectory(
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        user_text=user_text,
        final_response=final_response,
        tool_calls=paired,
    )


def select_wisp_cohort(root: Path, *, max_cases: int) -> tuple[CohortCase, ...]:
    """Select complete, multi-tool natural trajectories without path-based sampling."""
    if max_cases < 1:
        raise ValueError("max_cases must be positive")
    eligible: list[CohortCase] = []
    for path in root.rglob("*.jsonl"):
        try:
            trajectory = extract_wisp_trajectory(path)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (
            not trajectory.user_text.strip()
            or not trajectory.final_response.strip()
            or len(trajectory.tool_calls) < 2
            or not all(call.result_observed for call in trajectory.tool_calls)
        ):
            continue
        eligible.append(
            CohortCase(
                case_id=_stable_id("case", trajectory.source_sha256, 24),
                source_path=path,
                trajectory=trajectory,
            )
        )
    eligible.sort(key=lambda case: (case.trajectory.source_sha256, case.case_id))
    return tuple(eligible[:max_cases])
