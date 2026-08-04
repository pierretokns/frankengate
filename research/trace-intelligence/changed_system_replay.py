"""Resettable changed-system replay over source-pinned natural trajectories.

The runtime executes opaque, source-derived transitions.  It deliberately does
not execute historical shell commands or claim to reproduce the source host.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentevals_interop.experiment import (
    UPSTREAM_COMMIT,
    UPSTREAM_LICENSE,
    UPSTREAM_LICENSE_SHA256,
    UPSTREAM_LOCK_SHA256,
    UPSTREAM_PYPROJECT_SHA256,
    UPSTREAM_TAG,
    UPSTREAM_VERSION,
    CohortCase,
    NaturalToolCall,
    NaturalTrajectory,
    _verify_upstream_checkout,
    build_eval_set,
    build_otlp_export,
)


@dataclass(frozen=True)
class ReplayTask:
    source_sha256: str
    user_text: str
    expected_final_response: str
    expected_calls: tuple[NaturalToolCall, ...]

    @classmethod
    def from_natural_trajectory(cls, trajectory: NaturalTrajectory) -> "ReplayTask":
        return cls(
            source_sha256=trajectory.source_sha256,
            user_text=trajectory.user_text,
            expected_final_response=trajectory.final_response,
            expected_calls=trajectory.tool_calls,
        )


@dataclass(frozen=True)
class ReplayState:
    completed_transition_count: int
    expected_transition_count: int


@dataclass(frozen=True)
class ReplayOutcome:
    completed: bool
    reason: str


@dataclass(frozen=True)
class ReplayExecution:
    implementation: str
    state_before: ReplayState
    state_after: ReplayState
    trajectory: NaturalTrajectory
    outcome: ReplayOutcome


class OriginalReplaySystem:
    """Reference implementation of the resettable transition replay."""

    implementation = "original"

    def __init__(self) -> None:
        self.reset_count = 0
        self._completed = 0

    def _reset(self) -> None:
        self._completed = 0
        self.reset_count += 1

    def _program(self, task: ReplayTask) -> tuple[NaturalToolCall, ...]:
        return task.expected_calls

    def execute(self, task: ReplayTask) -> ReplayExecution:
        self._reset()
        before = ReplayState(
            completed_transition_count=self._completed,
            expected_transition_count=len(task.expected_calls),
        )
        actual_calls = self._program(task)
        for expected, actual in zip(task.expected_calls, actual_calls):
            if expected.name == actual.name and expected.arguments == actual.arguments:
                self._completed += 1
        completed = self._completed == len(task.expected_calls)
        after = ReplayState(
            completed_transition_count=self._completed,
            expected_transition_count=len(task.expected_calls),
        )
        trajectory = NaturalTrajectory(
            source_sha256=task.source_sha256,
            user_text=task.user_text,
            final_response=(
                task.expected_final_response
                if completed
                else "Replay system did not apply every required transition."
            ),
            tool_calls=actual_calls,
        )
        return ReplayExecution(
            implementation=self.implementation,
            state_before=before,
            state_after=after,
            trajectory=trajectory,
            outcome=ReplayOutcome(
                completed=completed,
                reason=(
                    "all_source_transitions_applied"
                    if completed
                    else "required_source_transition_missing"
                ),
            ),
        )


class BenignAuditSystem(OriginalReplaySystem):
    implementation = "benign_audit"

    def _program(self, task: ReplayTask) -> tuple[NaturalToolCall, ...]:
        audit = NaturalToolCall(
            call_id=f"audit-{task.source_sha256[:16]}",
            name="FrankengateAudit",
            arguments={"source_transition_count": len(task.expected_calls)},
            result={"recorded": True},
            result_observed=True,
        )
        return (*task.expected_calls, audit)


class HarmfulDropSystem(OriginalReplaySystem):
    implementation = "harmful_drop"

    def _program(self, task: ReplayTask) -> tuple[NaturalToolCall, ...]:
        return task.expected_calls[:-1]


SYSTEM_IMPLEMENTATIONS = (
    OriginalReplaySystem,
    BenignAuditSystem,
    HarmfulDropSystem,
)
GOOGLE_ADK_VERSION = "2.1.0"
GOOGLE_ADK_TAG_COMMIT = "6d15e19f057ee4035960ba5984499cb1eaf943ca"


def _stable_json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trajectory_evidence(trajectory: NaturalTrajectory) -> dict[str, Any]:
    calls = [
        {
            "name": call.name,
            "arguments": call.arguments,
            "result": call.result,
            "result_observed": call.result_observed,
        }
        for call in trajectory.tool_calls
    ]
    return {
        "tool_call_count": len(calls),
        "tool_path_sha256": _stable_json_hash(
            [{"name": call["name"], "arguments": call["arguments"]} for call in calls]
        ),
        "observed_result_count": sum(call["result_observed"] for call in calls),
        "tool_result_evidence_sha256": _stable_json_hash(
            [
                {
                    "name": call["name"],
                    "result": call["result"],
                    "observed": call["result_observed"],
                }
                for call in calls
            ]
        ),
        "final_response_sha256": hashlib.sha256(
            trajectory.final_response.encode("utf-8")
        ).hexdigest(),
    }


def build_input_manifest(
    *,
    cohort: tuple[CohortCase, ...],
    cache_root: Path,
    dataset_manifest_path: Path,
) -> dict[str, Any]:
    """Freeze the selected source files and verify their HF cache revision."""
    dataset = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    revision = str(dataset["dataset_revision"])
    selected: list[dict[str, Any]] = []
    resolved_cache = cache_root.resolve()
    for case in cohort:
        source = case.source_path.resolve()
        try:
            relative = source.relative_to(resolved_cache)
        except ValueError as error:
            raise ValueError("source path is outside the pinned cache") from error
        actual_source_sha = _sha256_file(source)
        if actual_source_sha != case.trajectory.source_sha256:
            raise ValueError("source content hash mismatch")
        metadata = (
            resolved_cache
            / ".cache"
            / "huggingface"
            / "download"
            / Path(f"{relative}.metadata")
        )
        if not metadata.is_file():
            raise ValueError("Hugging Face revision metadata is missing")
        cached_revision = metadata.read_text(encoding="utf-8").splitlines()[0]
        if cached_revision != revision:
            raise ValueError(
                "Hugging Face revision mismatch: "
                f"expected {revision}, observed {cached_revision}"
            )
        selected.append(
            {
                "case_id": case.case_id,
                "source_sha256": actual_source_sha,
                "hf_cache_revision_verified": True,
                "tool_call_count": len(case.trajectory.tool_calls),
                "paired_tool_result_count": sum(
                    call.result_observed for call in case.trajectory.tool_calls
                ),
                "task_prompt_sha256": hashlib.sha256(
                    case.trajectory.user_text.encode("utf-8")
                ).hexdigest(),
                "expected_final_response_sha256": hashlib.sha256(
                    case.trajectory.final_response.encode("utf-8")
                ).hexdigest(),
                "expected_tool_path_sha256": _trajectory_evidence(
                    case.trajectory
                )["tool_path_sha256"],
                "expected_tool_result_evidence_sha256": _trajectory_evidence(
                    case.trajectory
                )["tool_result_evidence_sha256"],
            }
        )
    return {
        "schema_version": "frankengate-changed-system-replay-input-manifest-v1",
        "dataset_id": dataset["dataset_id"],
        "dataset_revision": revision,
        "license": dataset["license"],
        "dataset_manifest_sha256": _sha256_file(dataset_manifest_path),
        "selection": (
            f"first {len(cohort)} by source-content hash among complete "
            "single-turn histories with at least two paired tool calls and a "
            "final response"
        ),
        "selected_inputs": selected,
        "raw_content_committed": False,
    }


def _aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["arm"]), str(row["assertion"]))
        cells.setdefault(key, []).append(row)
    aggregate: list[dict[str, Any]] = []
    for (implementation, assertion), group in sorted(cells.items()):
        scores = [
            float(row["score"]) for row in group if row.get("score") is not None
        ]
        aggregate.append(
            {
                "implementation": implementation,
                "assertion": assertion,
                "n": len(group),
                "passed": sum(row.get("status") == "PASSED" for row in group),
                "failed": sum(row.get("status") == "FAILED" for row in group),
                "errored": sum(row.get("status") == "ERRORED" for row in group),
                "mean_score": sum(scores) / len(scores) if scores else None,
            }
        )
    return aggregate


def _prospective_metrics(
    assertion_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {
        (row["implementation"], row["assertion"]): row
        for row in assertion_results
    }
    output: list[dict[str, Any]] = []
    for assertion in ("EXACT", "IN_ORDER", "ANY_ORDER"):
        baseline = by_key[("original", assertion)]
        benign = by_key[("benign_audit", assertion)]
        harmful = by_key[("harmful_drop", assertion)]
        output.append(
            {
                "assertion": assertion,
                "original_false_positive_rate": baseline["failed"] / baseline["n"],
                "benign_false_positive_rate": benign["failed"] / benign["n"],
                "harmful_regression_recall": harmful["failed"] / harmful["n"],
                "errored_runs": (
                    baseline["errored"] + benign["errored"] + harmful["errored"]
                ),
            }
        )
    return output


def _attest_upstream_runtime(
    upstream_python: Path,
    upstream_root: Path,
) -> dict[str, Any]:
    probe = subprocess.run(
        [
            str(upstream_python),
            "-c",
            (
                "import agentevals,json;"
                "from importlib.metadata import version;"
                "print(json.dumps({'agentevals_file':agentevals.__file__,"
                "'agentevals_version':version('agentevals-cli'),"
                "'google_adk_version':version('google-adk')}))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    observed = json.loads(probe.stdout)
    module_path = Path(observed["agentevals_file"]).resolve()
    expected_source = (upstream_root / "src" / "agentevals").resolve()
    try:
        module_path.relative_to(expected_source)
    except ValueError as error:
        raise ValueError(
            "AgentEvals runtime was not loaded from the pinned checkout"
        ) from error
    if observed["agentevals_version"] != UPSTREAM_VERSION:
        raise ValueError("AgentEvals runtime package version mismatch")
    if observed["google_adk_version"] != GOOGLE_ADK_VERSION:
        raise ValueError("Google ADK runtime package version mismatch")
    return {
        "agentevals_loaded_from_pinned_checkout": True,
        "agentevals_version": observed["agentevals_version"],
        "google_adk_version": observed["google_adk_version"],
    }


def run_changed_system_experiment(
    *,
    tasks: tuple[ReplayTask, ...],
    upstream_python: Path,
    upstream_root: Path,
    raw_dir: Path,
) -> dict[str, Any]:
    """Execute three resettable systems, then evaluate their emitted trajectories."""
    if not tasks:
        raise ValueError("at least one replay task is required")
    if not upstream_python.is_file():
        raise ValueError("upstream_python must be an existing interpreter")
    _verify_upstream_checkout(upstream_root)
    runtime_attestation = _attest_upstream_runtime(upstream_python, upstream_root)
    raw_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, str]] = []
    cases: list[dict[str, Any]] = []
    outcome_counts = {
        implementation.implementation: {"n": 0, "completed": 0, "incomplete": 0}
        for implementation in SYSTEM_IMPLEMENTATIONS
    }
    for index, task in enumerate(tasks):
        expected = NaturalTrajectory(
            source_sha256=task.source_sha256,
            user_text=task.user_text,
            final_response=task.expected_final_response,
            tool_calls=task.expected_calls,
        )
        eval_path = raw_dir / f"{index:04d}-expected-eval.json"
        eval_path.write_text(
            json.dumps(build_eval_set(expected), ensure_ascii=False),
            encoding="utf-8",
        )
        case_evidence: dict[str, Any] = {
            "case_id": hashlib.sha256(
                f"case\0{task.source_sha256}".encode("utf-8")
            ).hexdigest()[:24],
            "source_sha256": task.source_sha256,
            "task_prompt_sha256": hashlib.sha256(
                task.user_text.encode("utf-8")
            ).hexdigest(),
            "expected": _trajectory_evidence(expected),
            "executions": {},
        }
        for implementation_type in SYSTEM_IMPLEMENTATIONS:
            system = implementation_type()
            execution = system.execute(task)
            repeated = system.execute(task)
            if execution != repeated or system.reset_count != 2:
                raise RuntimeError(
                    f"non-resettable implementation: {system.implementation}"
                )
            counts = outcome_counts[system.implementation]
            counts["n"] += 1
            counts["completed" if execution.outcome.completed else "incomplete"] += 1
            actual_evidence = _trajectory_evidence(execution.trajectory)
            case_evidence["executions"][system.implementation] = {
                **actual_evidence,
                "state_before_completed": execution.state_before.completed_transition_count,
                "state_after_completed": execution.state_after.completed_transition_count,
                "expected_transition_count": execution.state_after.expected_transition_count,
                "outcome_completed": execution.outcome.completed,
                "outcome_reason": execution.outcome.reason,
                "repeat_reset_verified": True,
            }
            trace_path = (
                raw_dir / f"{index:04d}-{system.implementation}-actual.otlp.json"
            )
            trace_path.write_text(
                json.dumps(
                    build_otlp_export(
                        execution.trajectory,
                        arm=system.implementation,
                    ),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            items.append(
                {
                    "case_id": case_evidence["case_id"],
                    "arm": system.implementation,
                    "trace_path": str(trace_path),
                    "eval_set_path": str(eval_path),
                }
            )
        cases.append(case_evidence)

    spec = {
        "items": items,
        "match_types": ["EXACT", "IN_ORDER", "ANY_ORDER"],
    }
    spec_path = raw_dir / "driver-spec.json"
    result_path = raw_dir / "driver-result.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    project_root = Path(__file__).resolve().parent
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (str(project_root), env.get("PYTHONPATH"))
        if value
    )
    completed = subprocess.run(
        [
            str(upstream_python),
            "-m",
            "agentevals_interop.upstream_driver",
            "--spec",
            str(spec_path),
            "--output",
            str(result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=max(120, len(items) * 5),
    )
    if completed.returncode != 0:
        stderr_sha = hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest()
        raise RuntimeError(
            "upstream AgentEvals driver failed "
            f"(exit={completed.returncode}, stderr_sha256={stderr_sha})"
        )
    upstream_result = json.loads(result_path.read_text(encoding="utf-8"))
    if str(upstream_result.get("package_version")) != UPSTREAM_VERSION:
        raise ValueError(
            f"upstream package mismatch: {upstream_result.get('package_version')}"
        )
    assertion_results = _aggregate_rows(upstream_result["rows"])
    return {
        "schema_version": "frankengate-changed-system-replay-aggregate-v1",
        "claim_boundary": "resettable_opaque_transition_replay",
        "changed_system_executed": True,
        "source_environment_executed": False,
        "natural_trajectory_count": len(tasks),
        "system_implementations": [
            {
                "name": "original",
                "change": "execute every source-derived transition",
                "expected_outcome": "completed",
            },
            {
                "name": "benign_audit",
                "change": "execute every source transition plus one audit-only tool call",
                "expected_outcome": "completed",
            },
            {
                "name": "harmful_drop",
                "change": "omit the final required source-derived transition",
                "expected_outcome": "incomplete",
            },
        ],
        "implementation_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "upstream": {
            "repository": "https://github.com/agentevals-dev/agentevals",
            "release": UPSTREAM_TAG,
            "commit": UPSTREAM_COMMIT,
            "package": "agentevals-cli",
            "package_version": str(upstream_result.get("package_version")),
            "python_version": upstream_result.get("python_version"),
            "license": UPSTREAM_LICENSE,
            "license_sha256": UPSTREAM_LICENSE_SHA256,
            "pyproject_sha256": UPSTREAM_PYPROJECT_SHA256,
            "lock_sha256": UPSTREAM_LOCK_SHA256,
            "trajectory_matcher_dependency": {
                "package": "google-adk",
                "version": GOOGLE_ADK_VERSION,
                "source_tag_commit": GOOGLE_ADK_TAG_COMMIT,
            },
            "runtime_attestation": runtime_attestation,
        },
        "assertion_results": assertion_results,
        "prospective_metrics": _prospective_metrics(assertion_results),
        "outcomes": outcome_counts,
        "cases": cases,
        "raw_artifacts_committed": False,
        "raw_artifact_policy": (
            "content-bearing eval sets, actual OTLP, per-case upstream scores, "
            "prompts, responses, tool arguments, and tool results remain external"
        ),
    }
