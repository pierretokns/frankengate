#!/usr/bin/env python3
"""Loss-aware CodeTraceBench raw-trajectory E3/E4 factorial.

The program has two offline phases:

* ``allowlist`` freezes the existing repository/task-blocked test split against a
  pinned Hugging Face inventory.
* ``run`` verifies every downloaded archive, streams it through format-specific
  parsers, emits loss receipts, and evaluates deterministic diagnosis/assertion arms.

Raw archives remain outside Git.  Aggregate output contains no action, observation,
prompt, command, path from a local machine, or credential material.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import pathlib
import re
import statistics
import subprocess
import tarfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import codetracebench_empirical as manifest_study


DATASET_ID = manifest_study.DATASET_ID
DATASET_REVISION = manifest_study.DATASET_REVISION
DATASET_LICENSE = manifest_study.DATASET_LICENSE
DATASET_URL = manifest_study.DATASET_URL
CODETRACER_REVISION = "2d302191dd07e7c0c2da6f7a5e9451c7cbb62d34"
CODETRACER_URL = (
    "https://github.com/NJU-LINK/CodeTracer/tree/" + CODETRACER_REVISION
)
ISSUE_URL = "https://github.com/pierretokns/frankengate/issues/104"
BEAD_ID = "bif-kyy.17.13.4.2.1"
ANALYSIS_REVISION = "codetracebench-raw-e3-e4-factorial-v1"
ALLOWLIST_VERSION = "codetracebench-raw-blocked-test-allowlist-v1"
RESULT_VERSION = "frankengate-trace-empirical-result-v1"
DEFAULT_SEED = manifest_study.DEFAULT_SEED
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_RELEVANT_ARCHIVE_BYTES = 512 * 1024 * 1024

STRONG_ERROR_RE = re.compile(
    r"(?i)(?:"
    r"<returncode>\s*[1-9]\d*|"
    r"(?:exit|return)\s*code\s*[:=]?\s*[1-9]\d*|"
    r"traceback \(most recent call last\)|"
    r"assertionerror|syntaxerror|command not found|permission denied|"
    r"no such file or directory|tests? failed|failed:\s*[1-9]\d*|"
    r"\berror:\s+\S"
    r")"
)
RISKY_REASONING_RE = re.compile(
    r"(?i)\b(?:assum(?:e|ing)|guess|workaround|mock|hardcode|skip|disable|"
    r"for now|instead|cannot|can't|probably|maybe)\b"
)
EDIT_RE = re.compile(
    r"(?i)(?:apply_patch|str_replace|write_file|create_file|edit_file|"
    r"\bsed\s+-i\b|\bcat\s*>|\becho\b.*>|\bpatch\b|\bgit\s+apply\b)"
)
TEST_RE = re.compile(
    r"(?i)(?:pytest|go test|cargo test|npm test|pnpm test|yarn test|"
    r"make test|ctest|unittest|test_output)"
)
INSPECT_RE = re.compile(
    r"(?i)(?:\brg\b|\bgrep\b|\bfind\b|\bls\b|\bcat\b|\bhead\b|\btail\b|"
    r"read_file|view_file|search|str_replace_editor.*view)"
)
SETUP_RE = re.compile(
    r"(?i)(?:pip install|uv add|apt(?:-get)? install|npm install|pnpm install|"
    r"chmod|mkdir|git clone|docker)"
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_digest(*parts: object) -> str:
    return _sha256_bytes("\x1f".join(str(part) for part in parts).encode("utf-8"))


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def _json_bytes(data: bytes) -> Any:
    return json.loads(data.decode("utf-8", errors="replace"))


def _safe_text(data: bytes | None) -> str:
    return data.decode("utf-8", errors="replace") if data is not None else ""


def _tool_family(action: str, tool_name: str = "") -> str:
    material = tool_name + "\n" + action
    if TEST_RE.search(material):
        return "test"
    if EDIT_RE.search(material):
        return "edit"
    if INSPECT_RE.search(material):
        return "inspect"
    if SETUP_RE.search(material):
        return "setup"
    if re.search(r"(?i)\b(?:finish|submit|done)\b", tool_name):
        return "finish"
    return "other"


def _explicit_error(observation: str | None) -> bool:
    return bool(observation and STRONG_ERROR_RE.search(observation))


@dataclasses.dataclass(frozen=True)
class RawStep:
    native_step_id: int
    manifest_step_id: int | None
    action: str
    observation: str | None
    tool_name: str
    tool_family: str
    timestamp: str | float | int | None
    action_hash: str
    observation_hash: str | None
    source_action_hash: str
    source_observation_hash: str | None


@dataclasses.dataclass(frozen=True)
class VerifierEvidence:
    available: bool
    independent: bool
    outcome: bool | None
    source_kind: str


@dataclasses.dataclass(frozen=True)
class ParsedTrajectory:
    traj_id: str
    agent: str
    steps: tuple[RawStep, ...]
    manifest_step_count: int
    native_step_count: int
    mapped_step_count: int
    alignment_status: str
    parser_variant: str
    action_coverage: float
    observation_coverage: float
    timestamp_coverage: float
    relevant_member_count: int
    relevant_uncompressed_bytes: int
    archive_sha256: str
    verifier: VerifierEvidence
    losses: tuple[str, ...]


def build_allowlist(
    verified_path: pathlib.Path,
    full_path: pathlib.Path,
    inventory_paths: Sequence[pathlib.Path],
) -> dict[str, Any]:
    import pandas as pd

    verified_frame = pd.read_parquet(verified_path)
    full_frame = pd.read_parquet(full_path)
    records = [
        manifest_study.record_from_mapping(row)
        for row in verified_frame.to_dict(orient="records")
    ]
    assignments = manifest_study.assign_blocked_splits(records)
    test_records = {
        record.traj_id: record
        for record in records
        if assignments[record.group_key] == "test"
    }
    inventory: dict[str, Any] = {}
    for path in inventory_paths:
        for item in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(item, dict) and item.get("type") == "file":
                inventory[item["path"]] = item

    files: list[dict[str, Any]] = []
    missing_artifact_rows: list[str] = []
    missing_inventory: list[str] = []
    verified_by_id = {
        str(row["traj_id"]): row for row in verified_frame.to_dict(orient="records")
    }
    for traj_id, record in sorted(test_records.items()):
        row = verified_by_id[traj_id]
        artifact_path = row.get("artifact_path")
        if artifact_path is None or (
            isinstance(artifact_path, float) and math.isnan(artifact_path)
        ):
            missing_artifact_rows.append(traj_id)
            continue
        artifact_path = str(artifact_path)
        item = inventory.get(artifact_path)
        if item is None:
            missing_inventory.append(artifact_path)
            continue
        lfs = item.get("lfs") or {}
        sha256 = lfs.get("oid")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError(f"{artifact_path}: inventory has no immutable LFS hash")
        files.append(
            {
                "traj_id": traj_id,
                "agent": record.agent,
                "source_family": record.source_family,
                "artifact_path": artifact_path,
                "bytes": int(item["size"]),
                "sha256": sha256,
            }
        )
    if missing_inventory:
        raise ValueError(f"{len(missing_inventory)} artifacts absent from inventory")

    file_identity_digest = _canonical_hash(
        [
            [item["artifact_path"], item["bytes"], item["sha256"]]
            for item in files
        ]
    )
    return {
        "schema_version": ALLOWLIST_VERSION,
        "issue": ISSUE_URL,
        "bead": BEAD_ID,
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "license": DATASET_LICENSE,
        "dataset_url": DATASET_URL,
        "split_derivation": {
            "analysis_revision": manifest_study.ANALYSIS_REVISION,
            "seed": manifest_study.DEFAULT_SEED,
            "verified_rows": len(verified_frame),
            "full_rows": len(full_frame),
            "blocked_test_rows": len(test_records),
            "repository_or_task_blocked": True,
            "verified_sha256": _sha256_file(verified_path),
            "full_sha256": _sha256_file(full_path),
        },
        "files": files,
        "file_count": len(files),
        "compressed_bytes": sum(item["bytes"] for item in files),
        "missing_artifact_row_count": len(missing_artifact_rows),
        "missing_artifact_traj_ids": missing_artifact_rows,
        "file_identity_digest": file_identity_digest,
        "raw_data_committed": False,
    }


def _wanted_member(name: str) -> bool:
    base = pathlib.PurePosixPath(name).name
    return (
        base.endswith(".traj.json")
        or base.endswith(".traj")
        or base.startswith("tensorblock")
        and base.endswith(".json")
        or "/events/" in name
        and base.endswith(".json")
        or "/event_cache/" in name
        and base.endswith(".json")
        or re.search(r"/agent-logs/episode-\d+/(?:response\.txt|prompt\.txt|debug\.json)$", name)
        is not None
        or base in {
            "results.json",
            "report.json",
            "test_output.txt",
            "gpt5_output.json",
        }
        or base.endswith("_result.json")
    )


def read_relevant_archive(path: pathlib.Path) -> tuple[dict[str, bytes], int, int]:
    """Stream selected members from a zstd tar without extracting paths."""

    process = subprocess.Popen(
        ["zstd", "-d", "-c", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None:
        raise RuntimeError("zstd stdout unavailable")
    members: dict[str, bytes] = {}
    relevant_bytes = 0
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                name = member.name
                pure = pathlib.PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise ValueError(f"unsafe tar member: {name}")
                if not member.isfile() or not _wanted_member(name):
                    continue
                if member.size > MAX_MEMBER_BYTES:
                    raise ValueError(f"relevant tar member too large: {name}")
                relevant_bytes += member.size
                if relevant_bytes > MAX_RELEVANT_ARCHIVE_BYTES:
                    raise ValueError(f"relevant archive content too large: {path.name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"could not read tar member: {name}")
                members[name] = extracted.read()
    finally:
        process.stdout.close()
    stderr = process.stderr.read() if process.stderr else b""
    return_code = process.wait()
    if return_code:
        raise ValueError(
            f"zstd failed for {path.name}: {stderr.decode(errors='replace')[:200]}"
        )
    return members, len(members), relevant_bytes


def _make_step(
    native_step_id: int,
    manifest_step_id: int | None,
    action: str,
    observation: str | None,
    *,
    tool_name: str = "",
    timestamp: str | float | int | None = None,
    source_action: str | bytes | None = None,
    source_observation: str | bytes | None = None,
) -> RawStep:
    action = action or ""
    action_bytes = action.encode("utf-8", errors="replace")
    observation_bytes = (
        observation.encode("utf-8", errors="replace")
        if observation is not None
        else None
    )
    source_action_bytes = (
        source_action.encode("utf-8", errors="replace")
        if isinstance(source_action, str)
        else source_action
    ) or action_bytes
    source_observation_bytes = (
        source_observation.encode("utf-8", errors="replace")
        if isinstance(source_observation, str)
        else source_observation
    )
    if source_observation_bytes is None:
        source_observation_bytes = observation_bytes
    return RawStep(
        native_step_id=native_step_id,
        manifest_step_id=manifest_step_id,
        action=action,
        observation=observation,
        tool_name=tool_name,
        tool_family=_tool_family(action, tool_name),
        timestamp=timestamp,
        action_hash=_sha256_bytes(action_bytes),
        observation_hash=(
            _sha256_bytes(observation_bytes)
            if observation_bytes is not None
            else None
        ),
        source_action_hash=_sha256_bytes(source_action_bytes),
        source_observation_hash=(
            _sha256_bytes(source_observation_bytes)
            if source_observation_bytes is not None
            else None
        ),
    )


def _bash_content(content: str) -> str:
    match = re.search(r"```bash\s*\n(.*?)\n?```", content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()


def _parse_miniswe(members: Mapping[str, bytes]) -> tuple[list[RawStep], str, list[str]]:
    candidates = sorted(
        (name for name in members if name.endswith(".traj.json")),
        key=lambda name: (-len(members[name]), name),
    )
    for name in candidates:
        try:
            value = _json_bytes(members[name])
        except (ValueError, TypeError):
            continue
        messages = value.get("messages") if isinstance(value, dict) else None
        if not isinstance(messages, list):
            continue
        action_indices = [
            index
            for index, message in enumerate(messages)
            if isinstance(message, dict)
            and message.get("role") == "assistant"
            and isinstance(message.get("content"), str)
            and "```bash" in message["content"]
        ]
        steps: list[RawStep] = []
        for index in action_indices:
            message = messages[index]
            observation_message = next(
                (
                    later
                    for later in messages[index + 1 :]
                    if isinstance(later, dict)
                    and later.get("role") == "user"
                    and isinstance(later.get("content"), str)
                    and "<returncode>" in later["content"]
                ),
                None,
            )
            observation = (
                str(observation_message["content"])
                if observation_message is not None
                else None
            )
            steps.append(
                _make_step(
                    len(steps) + 1,
                    len(steps) + 1,
                    _bash_content(str(message.get("content") or "")),
                    observation,
                    timestamp=message.get("timestamp"),
                    source_action=json.dumps(message, sort_keys=True),
                    source_observation=(
                        json.dumps(observation_message, sort_keys=True)
                        if observation_message is not None
                        else None
                    ),
                )
            )
        losses = [
            f"{len(messages) - 2 * len(steps)} non-action/context messages are not normalized as steps",
            "commands are reconstructed from fenced bash; no proposal/authorization event exists",
        ]
        return steps, "miniswe_traj_json_bash_v1", losses
    return [], "miniswe_unparsed", ["no parseable messages trajectory found"]


def _parse_sweagent(members: Mapping[str, bytes]) -> tuple[list[RawStep], str, list[str]]:
    candidates = sorted(
        (
            name
            for name in members
            if name.endswith(".traj") and not name.endswith(".traj.json")
        ),
        key=lambda name: (-len(members[name]), name),
    )
    for name in candidates:
        try:
            value = _json_bytes(members[name])
        except (ValueError, TypeError):
            continue
        trajectory = value.get("trajectory") if isinstance(value, dict) else None
        if not isinstance(trajectory, list):
            continue
        steps = []
        for item in trajectory:
            if not isinstance(item, dict):
                continue
            steps.append(
                _make_step(
                    len(steps) + 1,
                    len(steps) + 1,
                    str(item.get("action") or ""),
                    (
                        str(item.get("observation"))
                        if item.get("observation") is not None
                        else None
                    ),
                    timestamp=None,
                    source_action=json.dumps(item, sort_keys=True),
                    source_observation=(
                        str(item.get("observation"))
                        if item.get("observation") is not None
                        else None
                    ),
                )
            )
        return steps, "sweagent_trajectory_v1", [
            "execution_time is a duration, not an event timestamp",
            "tool proposals and authorization decisions are not distinct events",
        ]
    return [], "sweagent_unparsed", ["no parseable .traj trajectory found"]


def _extract_terminus_action(response: str) -> tuple[str, str]:
    try:
        value = json.loads(response)
        if isinstance(value, dict):
            commands = value.get("commands")
            if isinstance(commands, list) and commands:
                parts = []
                for command in commands:
                    if isinstance(command, dict):
                        parts.append(str(command.get("keystrokes") or ""))
                    elif isinstance(command, str):
                        parts.append(command)
                return "\n".join(part for part in parts if part), "terminal"
            analysis = str(value.get("analysis") or value.get("state_analysis") or "")
            plan = str(value.get("plan") or value.get("explanation") or "")
            return "\n".join(part for part in (analysis, plan) if part), "reasoning"
    except json.JSONDecodeError:
        pass
    return response.strip(), "terminal"


def _terminus_observation(prompt: str) -> str:
    marker = "New Terminal Output:"
    return prompt.split(marker, 1)[1].strip() if marker in prompt else prompt.strip()


def _parse_terminus(
    members: Mapping[str, bytes], manifest_step_count: int
) -> tuple[list[RawStep], str, list[str]]:
    responses: dict[int, tuple[str, bytes]] = {}
    prompts: dict[int, tuple[str, bytes]] = {}
    debug: dict[int, Mapping[str, Any]] = {}
    for name, data in members.items():
        match = re.search(r"/agent-logs/episode-(\d+)/(response\.txt|prompt\.txt|debug\.json)$", name)
        if not match:
            continue
        episode = int(match.group(1))
        kind = match.group(2)
        if kind == "response.txt":
            responses[episode] = (_safe_text(data), data)
        elif kind == "prompt.txt":
            prompts[episode] = (_safe_text(data), data)
        else:
            try:
                value = _json_bytes(data)
                if isinstance(value, dict):
                    debug[episode] = value
            except (ValueError, TypeError):
                pass
    episode_numbers = sorted(set(responses) | set(prompts))
    steps = []
    if not episode_numbers:
        return [], "terminus2_unparsed", ["no episode logs found"]
    # Match the published CodeTracer adapter: logical step N pairs response N-1
    # with prompt N.  Prompt-only records are retained rather than silently
    # discarded.  Some released manifests stop before one or more native tail
    # episodes; retain those tails but leave them outside the manifest map.
    for step_id in range(1, max(episode_numbers) + 2):
        response_pair = responses.get(step_id - 1)
        prompt_pair = prompts.get(step_id)
        if response_pair is None and prompt_pair is None:
            continue
        response, response_bytes = response_pair or ("", b"")
        action, tool_name = _extract_terminus_action(response)
        observation = _terminus_observation(prompt_pair[0]) if prompt_pair else None
        metadata = debug.get(step_id - 1, {})
        timestamp = metadata.get("start_time") or metadata.get("api_call_start_time")
        steps.append(
            _make_step(
                step_id,
                step_id if step_id <= manifest_step_count else None,
                action,
                observation,
                tool_name=tool_name,
                timestamp=timestamp,
                source_action=response_bytes,
                source_observation=prompt_pair[1] if prompt_pair else None,
            )
        )
    native_tail = max(0, len(steps) - manifest_step_count)
    return steps, "terminus2_episode_pair_v2", [
        "final response may have no following prompt/observation",
        "terminal keystrokes are reconstructed commands without authorization events",
        f"{native_tail} native tail steps remain outside the manifest step map",
    ]


def _openhands_command(event: Mapping[str, Any]) -> tuple[str, str]:
    if event.get("action") == "run_ipython":
        args = event.get("args") or {}
        return (
            str(args.get("code") or "") if isinstance(args, dict) else "",
            "run_ipython",
        )
    metadata = event.get("tool_call_metadata") or {}
    if isinstance(metadata, dict):
        args = metadata.get("args") or {}
        if isinstance(args, dict) and args.get("command"):
            return str(args["command"]), str(event.get("action") or "run")
        response = metadata.get("model_response") or {}
        if isinstance(response, dict):
            for choice in response.get("choices") or []:
                message = choice.get("message") if isinstance(choice, dict) else None
                for tool_call in (
                    message.get("tool_calls") if isinstance(message, dict) else []
                ) or []:
                    function = (
                        tool_call.get("function")
                        if isinstance(tool_call, dict)
                        else None
                    )
                    if not isinstance(function, dict):
                        continue
                    try:
                        arguments = json.loads(str(function.get("arguments") or "{}"))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(arguments, dict) and arguments.get("command"):
                        return str(arguments["command"]), str(
                            function.get("name") or "run"
                        )
    message = event.get("message")
    if isinstance(message, str) and message.startswith("Running command:"):
        return message.removeprefix("Running command:").strip(), "run"
    return "", str(event.get("action") or "run")


def _parse_openhands_events(
    members: Mapping[str, bytes],
) -> tuple[list[RawStep], str, list[str]] | None:
    events = []
    for name, data in members.items():
        if "/events/" not in name and "/event_cache/" not in name:
            continue
        try:
            value = _json_bytes(data)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            events.append(value)
        elif isinstance(value, list):
            events.extend(item for item in value if isinstance(item, dict))
    if not events:
        return None
    events.sort(
        key=lambda event: (
            int(event["id"]) if isinstance(event.get("id"), int) else 10**9
        )
    )
    actions: dict[int, Mapping[str, Any]] = {}
    observations: dict[int, Mapping[str, Any]] = {}
    for event in events:
        event_id = event.get("id")
        if not isinstance(event_id, int) or event_id == 0:
            continue
        command, _ = _openhands_command(event)
        if event.get("action") in {"run", "run_ipython"} and command:
            actions[event_id] = event
        cause = event.get("cause")
        if isinstance(cause, int) and "observation" in event:
            observations.setdefault(cause, event)
    steps = []
    for event_id in sorted(actions):
        action_event = actions[event_id]
        observation_event = observations.get(event_id)
        command, tool_name = _openhands_command(action_event)
        observation = None
        if observation_event is not None:
            observation = str(
                observation_event.get("content")
                or observation_event.get("observation")
                or ""
            )
        steps.append(
            _make_step(
                len(steps) + 1,
                len(steps) + 1,
                command,
                observation,
                tool_name=tool_name,
                timestamp=action_event.get("timestamp"),
                source_action=json.dumps(action_event, sort_keys=True),
                source_observation=(
                    json.dumps(observation_event, sort_keys=True)
                    if observation_event is not None
                    else None
                ),
            )
        )
    return steps, "openhands_event_cause_v1", [
        f"{len(events) - len(actions) - len(observations)} context events remain outside the action/observation projection",
        "parallel and non-command tool actions are not represented as diagnosis steps",
    ]


def _response_message(record: Mapping[str, Any]) -> Mapping[str, Any]:
    response = record.get("response") or {}
    choices = response.get("choices") if isinstance(response, dict) else None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            return message
    return {}


def _tensor_action(message: Mapping[str, Any]) -> tuple[str, str]:
    calls = message.get("tool_calls") or []
    rendered = []
    names = []
    for call in calls if isinstance(calls, list) else []:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "")
        names.append(name)
        rendered.append(name + "(" + str(function.get("arguments") or "") + ")")
    content = message.get("content")
    if content:
        rendered.append(str(content))
    return "\n".join(rendered), "+".join(names)


def _parse_openhands_tensorblocks(
    members: Mapping[str, bytes], manifest_step_count: int
) -> tuple[list[RawStep], str, list[str]]:
    records = []
    for name, data in members.items():
        if not pathlib.PurePosixPath(name).name.startswith("tensorblock"):
            continue
        try:
            value = _json_bytes(data)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            records.append((name, value, data))
    records.sort(key=lambda item: (float(item[1].get("timestamp") or 0), item[0]))
    native: list[RawStep] = []
    tool_names: list[str] = []
    for index, (_, record, source_data) in enumerate(records):
        message = _response_message(record)
        action, tool_name = _tensor_action(message)
        next_messages = (
            records[index + 1][1].get("messages")
            if index + 1 < len(records)
            else []
        )
        observations = []
        if isinstance(next_messages, list):
            for incoming in reversed(next_messages):
                if not isinstance(incoming, dict) or incoming.get("role") != "tool":
                    if observations:
                        break
                    continue
                observations.append(json.dumps(incoming.get("content"), sort_keys=True))
        observations.reverse()
        tool_names.append(tool_name)
        native.append(
            _make_step(
                index + 1,
                None,
                action,
                "\n".join(observations) if observations else None,
                tool_name=tool_name,
                timestamp=record.get("timestamp"),
                source_action=source_data,
                source_observation="\n".join(observations) if observations else None,
            )
        )

    mapping_variant = "unmapped"
    mapped_indices: list[int] = []
    candidates: list[tuple[str, list[int]]] = [
        ("all_calls", list(range(len(native)))),
    ]
    if len(native) >= 2:
        first_is_planning = "task_tracker" in tool_names[0].lower()
        last_is_finish = "finish" in tool_names[-1].lower()
        if first_is_planning and last_is_finish:
            candidates.append(
                ("drop_initial_planning_and_terminal_finish", list(range(1, len(native) - 1)))
            )
    candidates.extend(
        [
            (
                "exclude_terminal_finish",
                [
                    index
                    for index, name in enumerate(tool_names)
                    if "finish" not in name.lower()
                ],
            ),
            (
                "tool_calls_only",
                [index for index, name in enumerate(tool_names) if name],
            ),
        ]
    )
    for name, indices in candidates:
        if len(indices) == manifest_step_count:
            mapping_variant = name
            mapped_indices = indices
            break
    mapped_position = {
        native_index: manifest_id
        for manifest_id, native_index in enumerate(mapped_indices, start=1)
    }
    steps = [
        dataclasses.replace(step, manifest_step_id=mapped_position.get(index))
        for index, step in enumerate(native)
    ]
    return steps, "openhands_tensorblock_v1:" + mapping_variant, [
        f"{len(native) - len(mapped_indices)} native calls remain outside the manifest step map",
        "tool observations are reconstructed from the next LLM request",
        "the published CodeTracer source has no tensorblock parser at the reviewed revision",
    ]


def _extract_verifier(
    members: Mapping[str, bytes], agent: str
) -> VerifierEvidence:
    for name, data in sorted(members.items()):
        base = pathlib.PurePosixPath(name).name
        try:
            value = _json_bytes(data) if base.endswith(".json") else None
        except (ValueError, TypeError):
            value = None
        if base.endswith("_result.json") and isinstance(value, dict):
            outcome = value.get("resolved")
            return VerifierEvidence(
                True,
                True,
                bool(outcome) if outcome is not None else None,
                "swe_external_result",
            )
        if base == "report.json" and isinstance(value, dict):
            rows = [item for item in value.values() if isinstance(item, dict)]
            outcomes = [item.get("resolved") for item in rows if "resolved" in item]
            return VerifierEvidence(
                True,
                True,
                bool(all(outcomes)) if outcomes else None,
                "openhands_external_report",
            )
        if base == "gpt5_output.json" and isinstance(value, dict):
            tests = value.get("tests")
            statuses = [
                str(item.get("status") or "").lower()
                for item in tests
                if isinstance(item, dict)
            ] if isinstance(tests, list) else []
            passing = {"pass", "passed", "success", "ok"}
            outcome = all(status in passing for status in statuses) if statuses else None
            return VerifierEvidence(
                True, True, outcome, "miniswe_external_test_report"
            )
        if base == "results.json" and isinstance(value, dict):
            outcome = value.get("is_resolved")
            return VerifierEvidence(
                True,
                True,
                bool(outcome) if outcome is not None else None,
                "terminus_external_result",
            )
    return VerifierEvidence(False, False, None, "none")


def parse_archive(
    archive_path: pathlib.Path,
    *,
    traj_id: str,
    agent: str,
    manifest_step_count: int,
    expected_sha256: str,
) -> ParsedTrajectory:
    actual_sha256 = _sha256_file(archive_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(f"{archive_path.name}: immutable hash mismatch")
    members, member_count, relevant_bytes = read_relevant_archive(archive_path)
    if agent == "mini-SWE-agent":
        steps, parser_variant, losses = _parse_miniswe(members)
    elif agent == "SWE-agent":
        steps, parser_variant, losses = _parse_sweagent(members)
    elif agent == "Terminus2":
        steps, parser_variant, losses = _parse_terminus(
            members, manifest_step_count
        )
    elif agent == "OpenHands":
        event_result = _parse_openhands_events(members)
        if event_result is not None:
            steps, parser_variant, losses = event_result
        else:
            steps, parser_variant, losses = _parse_openhands_tensorblocks(
                members, manifest_step_count
            )
    else:
        steps, parser_variant, losses = [], "unknown", ["unsupported agent format"]

    mapped = [step for step in steps if step.manifest_step_id is not None]
    mapped_ids = sorted(step.manifest_step_id for step in mapped)
    expected_ids = list(range(1, manifest_step_count + 1))
    alignment_status = (
        "exact" if mapped_ids == expected_ids else "count_or_identity_mismatch"
    )
    if alignment_status != "exact":
        losses.append(
            f"manifest step map mismatch: mapped={len(mapped)}, manifest={manifest_step_count}"
        )
    if not steps:
        losses.append("no normalized action/observation steps")
    losses.extend(
        [
            "authorization, purpose, classification, and authorization epoch are absent",
            "no independent step-level causal verifier exists",
        ]
    )
    return ParsedTrajectory(
        traj_id=traj_id,
        agent=agent,
        steps=tuple(steps),
        manifest_step_count=manifest_step_count,
        native_step_count=len(steps),
        mapped_step_count=len(mapped),
        alignment_status=alignment_status,
        parser_variant=parser_variant,
        action_coverage=(
            sum(bool(step.action) for step in mapped) / len(mapped) if mapped else 0.0
        ),
        observation_coverage=(
            sum(step.observation is not None for step in mapped) / len(mapped)
            if mapped
            else 0.0
        ),
        timestamp_coverage=(
            sum(step.timestamp is not None for step in mapped) / len(mapped)
            if mapped
            else 0.0
        ),
        relevant_member_count=member_count,
        relevant_uncompressed_bytes=relevant_bytes,
        archive_sha256=actual_sha256,
        verifier=_extract_verifier(members, agent),
        losses=tuple(losses),
    )


def _mapped_steps(trajectory: ParsedTrajectory) -> list[RawStep]:
    return sorted(
        (step for step in trajectory.steps if step.manifest_step_id is not None),
        key=lambda step: int(step.manifest_step_id or 0),
    )


def _factor_scores(steps: Sequence[RawStep]) -> dict[str, list[float]]:
    invariants = [0.0] * len(steps)
    topology = [0.0] * len(steps)
    judge = [0.0] * len(steps)
    for index, step in enumerate(steps):
        if _explicit_error(step.observation):
            invariants[index] += 2.0
        if step.observation is None:
            invariants[index] += 0.25
        previous = steps[max(0, index - 3) : index]
        if any(older.action_hash == step.action_hash for older in previous):
            topology[index] += 1.0
        if step.observation_hash and any(
            older.observation_hash == step.observation_hash for older in previous
        ):
            topology[index] += 0.75
        if step.tool_family in {"edit", "setup"}:
            for later in steps[index + 1 : index + 4]:
                if later.tool_family == "test" and _explicit_error(later.observation):
                    topology[index] += 2.0
                    break
        if step.tool_family == "inspect" and any(
            older.tool_family == "inspect" and older.action_hash == step.action_hash
            for older in previous
        ):
            topology[index] += 0.5
        material = step.action + "\n" + (step.observation or "")
        judge[index] += min(2.0, len(STRONG_ERROR_RE.findall(material)) * 0.75)
        judge[index] += min(1.5, len(RISKY_REASONING_RE.findall(step.action)) * 0.5)
    return {
        "invariants": invariants,
        "topology_modal": topology,
        "deterministic_judge": judge,
    }


def _normalize(values: Sequence[float]) -> list[float]:
    maximum = max(values, default=0.0)
    return [value / maximum for value in values] if maximum else [0.0] * len(values)


def _factorial_ranking(
    steps: Sequence[RawStep],
    *,
    invariants: bool,
    topology: bool,
    judge: bool,
) -> list[int]:
    factors = _factor_scores(steps)
    total = [0.0] * len(steps)
    for enabled, name in (
        (invariants, "invariants"),
        (topology, "topology_modal"),
        (judge, "deterministic_judge"),
    ):
        if enabled:
            for index, value in enumerate(_normalize(factors[name])):
                total[index] += value
    return [
        int(steps[index].manifest_step_id or 0)
        for index in sorted(
            range(len(steps)),
            key=lambda index: (
                -total[index],
                -int(steps[index].manifest_step_id or 0),
            ),
        )
    ]


def _diagnosis_metrics(
    trajectories: Sequence[tuple[ParsedTrajectory, set[int]]],
    factor_state: tuple[bool, bool, bool],
) -> dict[str, float | int]:
    top1 = top3 = 0
    reciprocal = []
    f1_scores = []
    for trajectory, gold in trajectories:
        ranking = _factorial_ranking(
            _mapped_steps(trajectory),
            invariants=factor_state[0],
            topology=factor_state[1],
            judge=factor_state[2],
        )
        top1 += ranking[0] in gold
        top3 += bool(set(ranking[:3]) & gold)
        first_rank = next(
            index for index, step_id in enumerate(ranking, start=1) if step_id in gold
        )
        reciprocal.append(1.0 / first_rank)
        predicted = set(ranking[: len(gold)])
        overlap = len(predicted & gold)
        precision = overlap / len(predicted)
        recall = overlap / len(gold)
        f1_scores.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    count = len(trajectories)
    return {
        "traces": count,
        "top1_accuracy": top1 / count if count else 0.0,
        "top3_accuracy": top3 / count if count else 0.0,
        "mean_reciprocal_rank": statistics.fmean(reciprocal) if reciprocal else 0.0,
        "macro_f1_at_gold_count": statistics.fmean(f1_scores) if f1_scores else 0.0,
    }


def _clone_with_steps(
    trajectory: ParsedTrajectory, steps: Sequence[RawStep]
) -> ParsedTrajectory:
    return dataclasses.replace(trajectory, steps=tuple(steps))


def _negative_controls(
    trajectories: Sequence[tuple[ParsedTrajectory, set[int]]],
) -> dict[str, Any]:
    combined = (True, True, True)
    original = _diagnosis_metrics(trajectories, combined)

    evidence_removed = []
    benign_tail = []
    irrelevant_error_tail = []
    timestamp_shuffled = []
    top1_changes = Counter()
    for trajectory, gold in trajectories:
        steps = _mapped_steps(trajectory)
        original_rank = _factorial_ranking(
            steps, invariants=True, topology=True, judge=True
        )

        removed_steps = [
            dataclasses.replace(
                step,
                observation=None,
                observation_hash=None,
                source_observation_hash=None,
            )
            if step.manifest_step_id in gold
            else step
            for step in steps
        ]
        removed_trajectory = _clone_with_steps(trajectory, removed_steps)
        evidence_removed.append((removed_trajectory, gold))

        benign = _make_step(
            len(steps) + 1,
            trajectory.manifest_step_count + 1,
            "true",
            "completed successfully",
            tool_name="benign_control",
        )
        benign_trajectory = _clone_with_steps(trajectory, [*steps, benign])
        benign_rank = _factorial_ranking(
            [*steps, benign], invariants=True, topology=True, judge=True
        )
        top1_changes["benign_tail"] += benign_rank[0] != original_rank[0]
        # The extra event is not in the manifest gold universe, so evaluate only
        # ranking stability rather than recomputing diagnosis metrics.
        benign_tail.append((benign_trajectory, gold))

        noisy = _make_step(
            len(steps) + 1,
            trajectory.manifest_step_count + 1,
            "echo unrelated diagnostic",
            "ERROR: synthetic unrelated log",
            tool_name="irrelevant_control",
        )
        noisy_rank = _factorial_ranking(
            [*steps, noisy], invariants=True, topology=True, judge=True
        )
        top1_changes["irrelevant_error_tail"] += noisy_rank[0] != original_rank[0]
        irrelevant_error_tail.append(
            (_clone_with_steps(trajectory, [*steps, noisy]), gold)
        )

        shuffled_timestamps = [
            dataclasses.replace(step, timestamp=steps[-index - 1].timestamp)
            for index, step in enumerate(steps)
        ]
        shuffled_rank = _factorial_ranking(
            shuffled_timestamps, invariants=True, topology=True, judge=True
        )
        top1_changes["timestamp_shuffle"] += shuffled_rank[0] != original_rank[0]
        timestamp_shuffled.append(
            (_clone_with_steps(trajectory, shuffled_timestamps), gold)
        )

    count = len(trajectories)
    return {
        "combined_original": original,
        "gold_observation_evidence_removed": _diagnosis_metrics(
            evidence_removed, combined
        ),
        "top1_prediction_change_rate": {
            key: value / count if count else 0.0
            for key, value in sorted(top1_changes.items())
        },
        "timestamp_control_interpretation": (
            "timestamps are preserved where available but excluded from the "
            "deterministic scorer; zero change is expected"
        ),
        "unsupported": [
            "environment swap: no common resettable environment snapshot is present",
            "permission/policy swap: source has no authorization decisions",
        ],
    }


@dataclasses.dataclass(frozen=True)
class AuditState:
    steps: tuple[RawStep, ...]
    verifier_outcome: bool | None


def _ordered_subsequence(expected: Sequence[str], observed: Sequence[str]) -> bool:
    cursor = iter(observed)
    return all(any(candidate == wanted for candidate in cursor) for wanted in expected)


def _assertion_passes(
    assertion: str,
    expected: AuditState,
    observed: AuditState,
    gold: set[int],
) -> bool:
    expected_steps = list(expected.steps)
    observed_steps = list(observed.steps)
    if assertion == "exact_sequence":
        return expected == observed
    expected_gold = [
        step for step in expected_steps if step.manifest_step_id in gold
    ]
    observed_hashes = [step.action_hash for step in observed_steps]
    required_hashes = [step.action_hash for step in expected_gold]
    if assertion == "ordered_gold_action":
        return _ordered_subsequence(required_hashes, observed_hashes)
    if assertion == "invariant_non_regression":
        expected_errors = sum(_explicit_error(step.observation) for step in expected_steps)
        observed_errors = sum(_explicit_error(step.observation) for step in observed_steps)
        return observed_errors <= expected_errors
    if assertion == "combined_raw_and_verifier":
        if not _ordered_subsequence(required_hashes, observed_hashes):
            return False
        counts = Counter(observed_hashes)
        if any(counts[value] != 1 for value in required_hashes):
            return False
        observed_by_action = {step.action_hash: step for step in observed_steps}
        for step in expected_gold:
            candidate = observed_by_action.get(step.action_hash)
            if candidate is None or candidate.observation_hash != step.observation_hash:
                return False
        if expected.verifier_outcome is not None:
            return observed.verifier_outcome == expected.verifier_outcome
        return True
    raise ValueError(f"unknown assertion: {assertion}")


def _mutate_state(
    state: AuditState,
    gold: set[int],
    mutation: str,
    *,
    seed: int,
    traj_id: str,
) -> AuditState | None:
    steps = list(state.steps)
    gold_indices = [
        index for index, step in enumerate(steps) if step.manifest_step_id in gold
    ]
    gold_indices.sort(
        key=lambda index: _stable_digest(seed, traj_id, mutation, steps[index].manifest_step_id)
    )
    if mutation == "remove_gold":
        del steps[gold_indices[0]]
    elif mutation == "duplicate_gold":
        index = gold_indices[0]
        steps.insert(index, steps[index])
    elif mutation == "reorder_gold":
        if len(gold_indices) < 2:
            return None
        first, second = sorted(gold_indices[:2])
        steps[first], steps[second] = steps[second], steps[first]
    elif mutation == "alter_gold_action":
        index = gold_indices[0]
        steps[index] = dataclasses.replace(
            steps[index],
            action=steps[index].action + "\n# mutated",
            action_hash="mutated",
        )
    elif mutation == "alter_gold_observation":
        candidates = [
            index for index in gold_indices if steps[index].observation is not None
        ]
        if not candidates:
            return None
        index = candidates[0]
        steps[index] = dataclasses.replace(
            steps[index],
            observation=(steps[index].observation or "") + "\nmutated",
            observation_hash="mutated",
        )
    elif mutation == "inject_benign_tail":
        steps.append(
            _make_step(
                len(steps) + 1,
                max(int(step.manifest_step_id or 0) for step in steps) + 1,
                "true",
                "completed successfully",
                tool_name="benign_control",
            )
        )
    elif mutation == "shift_timestamps":
        steps = [
            dataclasses.replace(step, timestamp=f"shifted-{index}")
            for index, step in enumerate(steps)
        ]
    elif mutation == "flip_verifier":
        if state.verifier_outcome is None:
            return None
        return AuditState(tuple(steps), not state.verifier_outcome)
    else:
        raise ValueError(f"unknown mutation: {mutation}")
    return AuditState(tuple(steps), state.verifier_outcome)


def _run_e4(
    trajectories: Sequence[tuple[ParsedTrajectory, set[int]]], seed: int
) -> dict[str, Any]:
    assertions = [
        "exact_sequence",
        "ordered_gold_action",
        "invariant_non_regression",
        "combined_raw_and_verifier",
    ]
    harmful = [
        "remove_gold",
        "duplicate_gold",
        "reorder_gold",
        "alter_gold_action",
        "alter_gold_observation",
        "flip_verifier",
    ]
    allowed = ["inject_benign_tail", "shift_timestamps"]
    matrix: dict[str, dict[str, Any]] = {}
    for mutation in harmful + allowed:
        supported = 0
        failures = Counter()
        for trajectory, gold in trajectories:
            state = AuditState(
                tuple(_mapped_steps(trajectory)), trajectory.verifier.outcome
            )
            mutated = _mutate_state(
                state, gold, mutation, seed=seed, traj_id=trajectory.traj_id
            )
            if mutated is None:
                continue
            supported += 1
            for assertion in assertions:
                failures[assertion] += not _assertion_passes(
                    assertion, state, mutated, gold
                )
        rate_name = (
            "mutant_kill_rate" if mutation in harmful else "false_positive_rate"
        )
        matrix[mutation] = {
            "classification": "harmful" if mutation in harmful else "allowed",
            "supported_traces": supported,
            "assertions": {
                assertion: {
                    "failures": failures[assertion],
                    rate_name: failures[assertion] / supported if supported else None,
                }
                for assertion in assertions
            },
        }
    aggregate = {}
    for assertion in assertions:
        harmful_supported = sum(matrix[name]["supported_traces"] for name in harmful)
        harmful_killed = sum(
            matrix[name]["assertions"][assertion]["failures"] for name in harmful
        )
        allowed_supported = sum(matrix[name]["supported_traces"] for name in allowed)
        allowed_failed = sum(
            matrix[name]["assertions"][assertion]["failures"] for name in allowed
        )
        aggregate[assertion] = {
            "harmful_mutants": harmful_supported,
            "harmful_mutants_killed": harmful_killed,
            "harmful_mutant_kill_rate": (
                harmful_killed / harmful_supported if harmful_supported else 0.0
            ),
            "allowed_variants": allowed_supported,
            "allowed_variants_rejected": allowed_failed,
            "allowed_variation_false_positive_rate": (
                allowed_failed / allowed_supported if allowed_supported else 0.0
            ),
        }
    return {
        "status": (
            "stored-trace audit mutation test; no changed agent or resettable "
            "environment was executed"
        ),
        "seed": seed,
        "matrix": matrix,
        "aggregate_by_assertion": aggregate,
    }


def _factorial_name(state: tuple[bool, bool, bool]) -> str:
    return f"I{int(state[0])}T{int(state[1])}J{int(state[2])}"


def _aggregate_receipts(parsed: Sequence[ParsedTrajectory]) -> dict[str, Any]:
    by_agent = {}
    for agent in sorted({trajectory.agent for trajectory in parsed}):
        rows = [trajectory for trajectory in parsed if trajectory.agent == agent]
        by_agent[agent] = {
            "archives": len(rows),
            "exact_alignment": sum(
                row.alignment_status == "exact" for row in rows
            ),
            "mean_action_coverage": statistics.fmean(
                row.action_coverage for row in rows
            ),
            "mean_observation_coverage": statistics.fmean(
                row.observation_coverage for row in rows
            ),
            "mean_timestamp_coverage": statistics.fmean(
                row.timestamp_coverage for row in rows
            ),
            "parser_variants": dict(
                sorted(Counter(row.parser_variant for row in rows).items())
            ),
        }
    return {
        "archives_parsed": len(parsed),
        "exact_alignment": sum(
            trajectory.alignment_status == "exact" for trajectory in parsed
        ),
        "alignment_mismatch": sum(
            trajectory.alignment_status != "exact" for trajectory in parsed
        ),
        "native_steps": sum(trajectory.native_step_count for trajectory in parsed),
        "mapped_steps": sum(trajectory.mapped_step_count for trajectory in parsed),
        "manifest_steps": sum(
            trajectory.manifest_step_count for trajectory in parsed
        ),
        "relevant_members": sum(
            trajectory.relevant_member_count for trajectory in parsed
        ),
        "relevant_uncompressed_bytes": sum(
            trajectory.relevant_uncompressed_bytes for trajectory in parsed
        ),
        "by_agent": by_agent,
        "loss_types": dict(
            sorted(
                Counter(
                    loss
                    for trajectory in parsed
                    for loss in trajectory.losses
                ).items()
            )
        ),
    }


def run_study(
    verified_path: pathlib.Path,
    full_path: pathlib.Path,
    allowlist_path: pathlib.Path,
    archive_root: pathlib.Path,
    *,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    import pandas as pd

    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    if allowlist.get("schema_version") != ALLOWLIST_VERSION:
        raise ValueError("unsupported allowlist version")
    if allowlist.get("dataset_revision") != DATASET_REVISION:
        raise ValueError("allowlist dataset revision mismatch")
    if allowlist["split_derivation"]["verified_sha256"] != _sha256_file(
        verified_path
    ):
        raise ValueError("verified manifest hash mismatch")
    if allowlist["split_derivation"]["full_sha256"] != _sha256_file(full_path):
        raise ValueError("full manifest hash mismatch")

    verified_frame = pd.read_parquet(verified_path)
    row_by_id = {
        str(row["traj_id"]): row for row in verified_frame.to_dict(orient="records")
    }
    manifest_records = {
        record.traj_id: record
        for record in (
            manifest_study.record_from_mapping(row)
            for row in verified_frame.to_dict(orient="records")
        )
    }
    parsed = []
    for item in allowlist["files"]:
        row = row_by_id[item["traj_id"]]
        archive_path = archive_root / item["artifact_path"]
        if not archive_path.exists():
            raise ValueError(f"missing allowlisted archive: {item['artifact_path']}")
        parsed.append(
            parse_archive(
                archive_path,
                traj_id=item["traj_id"],
                agent=item["agent"],
                manifest_step_count=int(row["step_count"]),
                expected_sha256=item["sha256"],
            )
        )

    eligible = []
    exclusion = Counter()
    for trajectory in parsed:
        gold = set(manifest_records[trajectory.traj_id].incorrect_step_ids)
        if trajectory.alignment_status != "exact":
            exclusion["alignment_mismatch"] += 1
        elif not gold:
            exclusion["no_incorrect_step_gold"] += 1
        else:
            eligible.append((trajectory, gold))

    factorial = {}
    for invariant in (False, True):
        for topology in (False, True):
            for judge in (False, True):
                state = (invariant, topology, judge)
                factorial[_factorial_name(state)] = _diagnosis_metrics(
                    eligible, state
                )

    verifier_rows = [
        trajectory
        for trajectory in parsed
        if trajectory.verifier.available
    ]
    verifier_with_outcome = [
        trajectory
        for trajectory in verifier_rows
        if trajectory.verifier.outcome is not None
        and manifest_records[trajectory.traj_id].solved is not None
    ]
    verifier_agreement = sum(
        trajectory.verifier.outcome
        == manifest_records[trajectory.traj_id].solved
        for trajectory in verifier_with_outcome
    )
    result = {
        "schema_version": RESULT_VERSION,
        "analysis_revision": ANALYSIS_REVISION,
        "run_date": "2026-07-30",
        "issue": ISSUE_URL,
        "bead": BEAD_ID,
        "seed": seed,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "license": DATASET_LICENSE,
            "dataset_url": DATASET_URL,
            "codetracer_revision": CODETRACER_REVISION,
            "codetracer_url": CODETRACER_URL,
            "codetracer_release_status": "untagged; no repository tags at review time",
            "codetracer_lfs_checkout_status": (
                "code reviewed with LFS smudge disabled because the public repository "
                "reported an exhausted LFS budget"
            ),
            "allowlist_sha256": _sha256_file(allowlist_path),
            "allowlist_identity_digest": allowlist["file_identity_digest"],
            "archive_count": allowlist["file_count"],
            "compressed_bytes": allowlist["compressed_bytes"],
            "missing_artifact_rows": allowlist["missing_artifact_row_count"],
            "all_archive_hashes_verified": True,
            "raw_data_committed": False,
        },
        "loss_receipt_aggregate": _aggregate_receipts(parsed),
        "e3_factorial": {
            "status": (
                "deterministic label-blind factor baselines on exact-aligned raw "
                "trajectories; the lexical judge emits rankings, not probabilities"
            ),
            "factors": {
                "I": "explicit error/missing-observation invariants",
                "T": "repetition and edit/setup-to-failing-test topology/modal evidence",
                "J": "deterministic error/risky-reasoning lexical judge",
            },
            "eligible_traces": len(eligible),
            "exclusions": dict(sorted(exclusion.items())),
            "arms": factorial,
            "calibration": {
                "status": "not applicable",
                "reason": (
                    "the deterministic judge produces no probability; Brier score "
                    "and ECE would fabricate calibration"
                ),
            },
            "negative_controls": _negative_controls(eligible),
        },
        "e4_assertion_mutation": _run_e4(eligible, seed),
        "independent_verifier": {
            "available": len(verifier_rows),
            "with_binary_outcome_and_manifest_comparator": len(
                verifier_with_outcome
            ),
            "agreement_with_manifest_solved": (
                verifier_agreement / len(verifier_with_outcome)
                if verifier_with_outcome
                else None
            ),
            "step_level_causal_verifier_available": 0,
            "interpretation": (
                "external reports can corroborate terminal outcome but cannot prove "
                "which earlier action caused it"
            ),
        },
        "cost": {
            "model_api_calls": 0,
            "model_tokens": 0,
            "model_cost_usd": 0.0,
            "compressed_input_bytes": allowlist["compressed_bytes"],
            "relevant_uncompressed_bytes": sum(
                trajectory.relevant_uncompressed_bytes for trajectory in parsed
            ),
        },
        "claim_boundary": {
            "supported": [
                "raw action/observation parser coverage and explicit loss",
                "deterministic factorial localization against released step labels",
                "stored-trace assertion mutation sensitivity",
                "terminal verifier availability and agreement",
            ],
            "not_supported": [
                "causal root cause",
                "calibrated LLM-judge performance",
                "changed-system replay or intervention benefit",
                "authorization correctness",
                "enterprise-human skill, productivity, intent, or collaboration",
            ],
        },
    }
    canonical = json.dumps(
        result, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    result["result_content_sha256"] = _sha256_bytes(canonical)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    receipt = result["loss_receipt_aggregate"]
    e3 = result["e3_factorial"]
    e4 = result["e4_assertion_mutation"]
    arm_rows = []
    for name, metrics in sorted(e3["arms"].items()):
        arm_rows.append(
            f"| `{name}` | {metrics['top1_accuracy']:.3f} | "
            f"{metrics['top3_accuracy']:.3f} | "
            f"{metrics['mean_reciprocal_rank']:.3f} | "
            f"{metrics['macro_f1_at_gold_count']:.3f} |"
        )
    parser_rows = []
    for agent, metrics in receipt["by_agent"].items():
        parser_rows.append(
            f"| {agent} | {metrics['archives']} | {metrics['exact_alignment']} | "
            f"{metrics['mean_action_coverage']:.3f} | "
            f"{metrics['mean_observation_coverage']:.3f} | "
            f"{metrics['mean_timestamp_coverage']:.3f} |"
        )
    assertion_rows = []
    for name, metrics in e4["aggregate_by_assertion"].items():
        assertion_rows.append(
            f"| `{name}` | {metrics['harmful_mutants']} | "
            f"{metrics['harmful_mutant_kill_rate']:.3f} | "
            f"{metrics['allowed_variation_false_positive_rate']:.3f} |"
        )
    best_arm, best_metrics = max(
        e3["arms"].items(), key=lambda item: item[1]["top1_accuracy"]
    )
    baseline = e3["arms"]["I0T0J0"]
    controls = e3["negative_controls"]
    return f"""# CodeTraceBench raw-trajectory E3/E4 factorial

**Issue:** [#104]({result['issue']})

**Bead:** `{result['bead']}`

**Dataset:** [{result['source']['dataset_id']} @
`{result['source']['dataset_revision']}`]({result['source']['dataset_url']}),
{result['source']['license']}

**CodeTracer source:** [untagged `{result['source']['codetracer_revision']}`](
{result['source']['codetracer_url']})

**Result hash:** `{result['result_content_sha256']}`

## Abstract

This study acquired every available artifact in the previously frozen,
repository/task-blocked CodeTraceBench test split: {result['source']['archive_count']}
archives totaling {result['source']['compressed_bytes'] / 2**20:.2f} MiB.  Three
blocked-test rows had no artifact path.  Every archive was verified against its
immutable Hugging Face LFS SHA-256 and streamed without committing raw content.

The result is negative/partial.  Of {receipt['archives_parsed']} parsed archives,
{receipt['exact_alignment']} exactly preserved the published manifest step identity.
Only {e3['eligible_traces']} exact-aligned traces also had incorrect-step gold labels
and could enter E3/E4.  The best deterministic arm, `{best_arm}`, reached
{best_metrics['top1_accuracy']:.3f} top-1 versus
{baseline['top1_accuracy']:.3f} for reverse-chronology tie-breaking.  This does not
establish causal diagnosis, and no arm is a calibrated LLM judge.

## Reproduction and admission

The committed allowlist contains only public artifact IDs, byte sizes, and immutable
hashes—not trace content.  Its identity digest is
`{result['source']['allowlist_identity_digest']}`.  Raw archives remain under
`/private/tmp` or another non-repository directory.

The dataset repository is MIT.  CodeTracer has no published tag at the reviewed
revision.  Its ordinary checkout failed because GitHub reported an exhausted LFS
budget, so source code was reviewed with LFS smudging disabled.  The Hugging Face
artifacts remained independently available.

## Loss receipts

| Agent | Archives | Exact alignment | Action coverage | Observation coverage | Timestamp coverage |
|---|---:|---:|---:|---:|---:|
{chr(10).join(parser_rows)}

Across the corpus, the adapters observed {receipt['native_steps']} native steps,
mapped {receipt['mapped_steps']} steps against {receipt['manifest_steps']} manifest
steps, and read {receipt['relevant_members']} relevant members.  Mismatches are
quarantined from localization instead of truncated or padded.

The common irreducible losses are authorization/purpose/classification/epoch,
independent step-level causal state, and portable proposal/result events.  OpenHands
tensorblock observations require reconstruction from the following LLM request;
Terminus2 may omit the final observation; SWE-agent lacks absolute timestamps.

## E3 factorial

The eight arms cross:

- `I`: explicit error and missing-observation invariants;
- `T`: repetition plus edit/setup-to-failing-test topology/modal evidence; and
- `J`: a deterministic error/risky-reasoning lexical judge.

No factor reads `solved`, incorrect-stage identity, incorrect-step IDs, difficulty,
agent, model, or category.  Human incorrect-step IDs are used only after ranking.

| Arm | Top-1 | Top-3 | MRR | Macro F1@|G| |
|---|---:|---:|---:|---:|
{chr(10).join(arm_rows)}

The deterministic judge emits no probabilities.  Reporting Brier score or ECE would
fabricate calibration, so calibration is explicitly not applicable.  The study used
zero model calls, zero tokens, and $0 model cost.

### Negative controls

- Gold-step observation removal changed combined top-1 from
  {controls['combined_original']['top1_accuracy']:.3f} to
  {controls['gold_observation_evidence_removed']['top1_accuracy']:.3f}.
- Benign-tail top-1 change rate:
  {controls['top1_prediction_change_rate'].get('benign_tail', 0):.3f}.
- Irrelevant-error-tail top-1 change rate:
  {controls['top1_prediction_change_rate'].get('irrelevant_error_tail', 0):.3f}.
- Timestamp shuffle top-1 change rate:
  {controls['top1_prediction_change_rate'].get('timestamp_shuffle', 0):.3f};
  timestamps are deliberately excluded from scoring.
- Environment and authorization swaps are unsupported by the source and were not
  simulated.

## E4 stored-trace assertion mutations

| Assertion | Harmful mutants | Kill rate | Allowed-variation false positive |
|---|---:|---:|---:|
{chr(10).join(assertion_rows)}

These are stored-trace audits.  No changed agent ran in a resettable environment.
High mutation kill rate is mechanical sensitivity, not evidence of future behavior.
Exact sequence checks are expected to be brittle to benign additions and timestamp
changes.

## Independent verifier boundary

An external terminal verifier was present for
{result['independent_verifier']['available']} archives.  A binary verifier outcome and
manifest comparator were both available for
{result['independent_verifier']['with_binary_outcome_and_manifest_comparator']};
their agreement was
{result['independent_verifier']['agreement_with_manifest_solved']}.
There were zero independent step-level causal verifiers.  Terminal pass/fail can
corroborate an outcome but cannot identify the action that caused it.

## Frankengate decision

This run supports loss-aware ingestion, evidence-linked review, and retrospective eval
proposal mechanics.  It does not clear the L3 product gate for automatic cause
language: the deterministic arms must beat simple baselines on an independently
adjudicated holdout, emit calibrated abstention, and survive irrelevant-error
injection.  Frankengate must continue to call these findings hypotheses or audits.

Nothing in this coding-agent corpus supports claims about an employee's skill,
productivity, intent, or ideal collaborator.
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    allow = subparsers.add_parser("allowlist")
    allow.add_argument("--verified", type=pathlib.Path, required=True)
    allow.add_argument("--full", type=pathlib.Path, required=True)
    allow.add_argument(
        "--inventory", type=pathlib.Path, action="append", required=True
    )
    allow.add_argument("--output", type=pathlib.Path, required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--verified", type=pathlib.Path, required=True)
    run.add_argument("--full", type=pathlib.Path, required=True)
    run.add_argument("--allowlist", type=pathlib.Path, required=True)
    run.add_argument("--archive-root", type=pathlib.Path, required=True)
    run.add_argument("--output-json", type=pathlib.Path, required=True)
    run.add_argument("--output-markdown", type=pathlib.Path, required=True)
    run.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    if args.command == "allowlist":
        value = build_allowlist(
            args.verified, args.full, args.inventory
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0

    result = run_study(
        args.verified,
        args.full,
        args.allowlist,
        args.archive_root,
        seed=args.seed,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_markdown.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
