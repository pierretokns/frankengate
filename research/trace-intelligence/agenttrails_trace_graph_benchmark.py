#!/usr/bin/env python3
"""Measure AgentTrails-style provenance retrieval on public agent traces.

This is a structural probe, not a semantic task-success benchmark. It turns
each tool call into an action node and each output schema/status into an
artifact node, then compares provenance-graph, call-shape, and tool-family
similarity for predicting the final action of a held-out trajectory. Raw trace
content and identities never enter the receipt.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DATASET = "zhiyaowang/dataclaw-zhiyaowang"
REVISION = "f5157333cbc22489661122a9bc5347b137144900"
ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def tool_family(name: Any) -> str:
    text = str(name or "").lower()
    if any(token in text for token in ("bash", "shell", "terminal", "command", "exec", "run_")):
        return "shell"
    if any(token in text for token in ("read", "cat", "list", "glob", "search", "grep", "find")):
        return "read_search"
    if any(token in text for token in ("edit", "write", "patch", "replace", "file")):
        return "file_mutation"
    if any(token in text for token in ("web", "http", "browser", "fetch")):
        return "external_retrieval"
    if any(token in text for token in ("task", "agent", "delegate", "workflow")):
        return "delegation"
    return "other"


def _schema(value: Any, depth: int = 0) -> Any:
    """Return a bounded shape-only description, never values."""
    if depth > 2:
        return "nested"
    if value is None:
        return "null"
    if isinstance(value, dict):
        return {str(key).lower(): _schema(value[key], depth + 1) for key in sorted(value, key=str)[:32]}
    if isinstance(value, list):
        return ["list", _schema(value[0], depth + 1) if value else "empty"]
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _input_keys(call: dict[str, Any]) -> tuple[str, ...]:
    value = call.get("input")
    return tuple(sorted(str(key).lower() for key in value)) if isinstance(value, dict) else ()


@dataclass(frozen=True)
class Event:
    action_id: str
    family: str
    artifact_id: str
    artifact_schema_id: str
    status: str


@dataclass(frozen=True)
class Episode:
    episode_id: str
    start_time: str
    source_id: str
    project_id: str
    events: tuple[Event, ...]


def _event(call: dict[str, Any]) -> Event:
    tool = str(call.get("tool") or call.get("name") or "").lower()
    family = tool_family(tool)
    status = str(call.get("status") or "unknown").lower()
    output = call.get("output")
    schema = _schema(output)
    action_id = digest({"tool": tool, "input_keys": _input_keys(call)})
    artifact_schema_id = digest(schema)
    artifact_id = digest({"schema": schema, "status": status})
    return Event(action_id, family, artifact_id, artifact_schema_id, status)


def parse_episode(row: dict[str, Any]) -> Episode | None:
    events: list[Event] = []
    for message in row.get("messages", []) if isinstance(row.get("messages"), list) else []:
        if not isinstance(message, dict):
            continue
        uses = message.get("tool_uses") if isinstance(message.get("tool_uses"), list) else []
        for call in uses:
            if isinstance(call, dict):
                events.append(_event(call))
    if len(events) < 4:
        return None
    return Episode(
        episode_id=digest(row.get("session_id")),
        start_time=str(row.get("start_time") or ""),
        source_id=digest(row.get("source")),
        project_id=digest(row.get("project")),
        events=tuple(events),
    )


def request_rows(offset: int, length: int, timeout: int) -> tuple[int, list[dict[str, Any]]]:
    query = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": "train", "offset": offset, "length": length})
    with urllib.request.urlopen(f"{ROWS_ENDPOINT}?{query}", timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    total = int(payload.get("num_rows_total", 0))
    rows = [item.get("row") for item in payload.get("rows", []) if isinstance(item, dict)]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"offset {offset}: malformed rows response")
    return total, rows


def sample_episodes(sample_count: int, timeout: int) -> tuple[int, list[Episode], dict[str, int]]:
    total, _ = request_rows(0, 1, timeout)
    window_count = min(8, max(2, sample_count))
    window_size = (sample_count + window_count - 1) // window_count
    starts = sorted({round(index * (total - window_size) / max(1, window_count - 1)) for index in range(window_count)})
    rows_by_offset: dict[int, dict[str, Any]] = {}
    errors: collections.Counter[str] = collections.Counter()
    for offset in starts:
        try:
            discovered_total, rows = request_rows(offset, window_size, timeout)
            if discovered_total != total:
                errors["row_count_changed"] += 1
            rows_by_offset.update({offset + index: row for index, row in enumerate(rows)})
        except Exception as exc:
            errors[type(exc).__name__] += 1
    episodes = [parse_episode(rows_by_offset[offset]) for offset in sorted(rows_by_offset)]
    return total, [episode for episode in episodes if episode is not None], dict(errors)


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def graph_edges(events: tuple[Event, ...]) -> tuple[str, ...]:
    edges: list[str] = []
    for index, event in enumerate(events):
        edges.append(f"a:{event.action_id}->o:{event.artifact_id}")
        if index + 1 < len(events):
            edges.append(f"o:{event.artifact_id}->a:{events[index + 1].action_id}")
    return tuple(edges)


def similarity(query: tuple[Event, ...], candidate: tuple[Event, ...], mode: str) -> float:
    if mode == "graph":
        return _jaccard(graph_edges(query), graph_edges(candidate))
    if mode == "shape":
        return _jaccard((event.action_id for event in query), (event.action_id for event in candidate))
    if mode == "family":
        return _jaccard((event.family for event in query), (event.family for event in candidate))
    if mode == "graph_shape":
        return 0.5 * similarity(query, candidate, "graph") + 0.5 * similarity(query, candidate, "shape")
    raise ValueError(mode)


def predict(test: Episode, train: list[Episode], mode: str) -> tuple[Event, float] | None:
    query = test.events[:-1]
    ranked = sorted(
        ((similarity(query, candidate.events[:-1], mode), candidate) for candidate in train),
        key=lambda pair: (-pair[0], pair[1].start_time, pair[1].episode_id),
    )
    if not ranked:
        return None
    score, selected = ranked[0]
    return selected.events[-1], score


def run(sample_count: int, timeout: int, output: Path) -> dict[str, Any]:
    total, episodes, sampling_errors = sample_episodes(sample_count, timeout)
    episodes.sort(key=lambda episode: (episode.start_time, episode.episode_id))
    split = max(1, int(len(episodes) * 0.7))
    train = episodes[:split]
    test = episodes[split:]
    arms: dict[str, dict[str, int | float]] = {}
    for mode in ("family", "shape", "graph", "graph_shape"):
        rows: list[tuple[bool, bool, bool, float]] = []
        for episode in test:
            prediction = predict(episode, train, mode)
            if not prediction:
                continue
            predicted, score = prediction
            target = episode.events[-1]
            rows.append((predicted.family == target.family, predicted.action_id == target.action_id, predicted.artifact_schema_id == target.artifact_schema_id, score))
        arms[mode] = {
            "test_cases": len(rows),
            "next_family_accuracy": sum(row[0] for row in rows) / len(rows) if rows else 0.0,
            "next_action_shape_accuracy": sum(row[1] for row in rows) / len(rows) if rows else 0.0,
            "next_artifact_schema_accuracy": sum(row[2] for row in rows) / len(rows) if rows else 0.0,
            "mean_similarity": sum(row[3] for row in rows) / len(rows) if rows else 0.0,
        }
    result = {
        "schema_version": "frankengate-agenttrails-graph-benchmark-v1",
        "source": {"dataset": DATASET, "revision": REVISION, "rows_total": total, "rows_sampled": sample_count, "episodes_eligible": len(episodes), "raw_content_committed": False, "sampling_errors": sampling_errors},
        "protocol": {"split": "chronological 70/30 by start_time", "query": "all but final tool event", "target": "final tool event", "graph": "action -> output-schema/status artifact -> next action", "controls": ["tool-family Jaccard", "action-shape Jaccard", "equal-weight graph+shape"], "identities": "hashed only"},
        "cohort": {"train_episodes": len(train), "test_episodes": len(test), "minimum_tool_events": 4},
        "arms": arms,
        "claim_boundary": {"provenance_structure_measured": True, "semantic_task_success_measured": False, "artifact_utility_measured": False, "cross_user_identity_verified": False, "reason": "The public corpus exposes tool trajectories and output schemas but no independent task outcomes or authorized enterprise identities. The target is structural next-event prediction, so this is an AgentTrails mechanism probe rather than evidence that graph retrieval improves user work."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "eligible": len(episodes), "arms": arms}, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-count", type=int, default=48)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.sample_count, args.timeout, args.output)


if __name__ == "__main__":
    main()
