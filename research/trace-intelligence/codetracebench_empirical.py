#!/usr/bin/env python3
"""Reproducible manifest-level CodeTraceBench E1/E3/E4 study.

Raw trajectories and Parquet inputs stay outside Git.  The committed result contains
aggregates only.  This module deliberately distinguishes label-blind structural
baselines from coarse-stage oracles that consume human annotations.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import pathlib
import random
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


DATASET_ID = "NJU-LINK/CodeTraceBench"
DATASET_REVISION = "aa213b84ffb6690fc37ca15766d6ca174ec36d4d"
DATASET_LICENSE = "MIT"
DATASET_URL = (
    "https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/"
    + DATASET_REVISION
)
PAPER_URL = "https://arxiv.org/abs/2604.11641"
EXPECTED_SHA256 = {
    "full": "0c25108022f518d09505d66cee7a8baeaa2d64708c98e8a66a061819c0b3da6d",
    "verified": "ae5926b496f2f7f4c3f6337c0ad6150311d3650c5f3bd00660556b3e41739505",
}
ANALYSIS_REVISION = "codetracebench-manifest-e1-e3-e4-v1"
DEFAULT_SEED = 20260730
SPLIT_TARGETS = {"train": 0.70, "dev": 0.15, "test": 0.15}
SPLIT_PRIORITY = ("train", "dev", "test")


def _clean(value: Any) -> Any:
    """Convert Arrow/NumPy values to stable Python values."""

    if value is None:
        return None
    if hasattr(value, "tolist"):
        value = value.tolist()
    elif hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    return value


def _items(value: Any) -> list[Any]:
    clean = _clean(value)
    if clean is None:
        return []
    return clean if isinstance(clean, list) else [clean]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_digest(*parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _reference_hash(value: Any) -> str | None:
    clean = _clean(value)
    if clean is None:
        return None
    data = json.dumps(
        clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(data)


@dataclasses.dataclass(frozen=True)
class LabeledStep:
    step_id: int
    labels: tuple[str, ...]
    action_hash: str | None
    observation_hash: str | None


@dataclasses.dataclass(frozen=True)
class TraceRecord:
    traj_id: str
    agent: str
    model: str
    task_name: str
    difficulty: str
    category: str
    solved: bool | None
    step_count: int
    stages: tuple[tuple[int, int, int], ...]
    incorrect_stage_ids: tuple[int, ...]
    incorrect_step_ids: tuple[int, ...]
    unuseful_step_ids: tuple[int, ...]
    labeled_steps: tuple[LabeledStep, ...]
    source_family: str
    repository_family: str
    group_key: str

    @property
    def informative(self) -> bool:
        return bool(self.incorrect_step_ids or self.unuseful_step_ids)


def derive_source_family(source_relpath: Any) -> str:
    path = str(_clean(source_relpath) or "")
    parts = path.split("/")
    if parts and parts[0] == "swe_raw" and len(parts) > 1:
        suffix = parts[1].rsplit("__", 1)[-1]
        return {
            "verified": "swe-bench-verified",
            "pro": "swe-bench-pro",
            "multi": "multi-swe-bench",
            "poly": "swe-polybench",
        }.get(suffix, "swe-unknown")
    if parts and parts[0] in {"openhands", "miniswe", "terminus2"}:
        return "terminal-bench"
    return "unknown-source"


def derive_repository_family(task_name: str, source_family: str) -> str:
    """Return a conservative repository/task family for leakage blocking."""

    task = task_name.removeprefix("instance_")
    if source_family != "terminal-bench" and "__" in task:
        match = re.match(
            r"^(.+?__.+?)-(?:[0-9]+|[0-9a-f]{40})(?:-|$)", task
        )
        if match:
            return match.group(1)
    # TerminalBench has no repository identity in the manifest.  Treat each task
    # as its own indivisible family rather than inventing a repository.
    return "task:" + task_name


def record_from_mapping(row: Mapping[str, Any]) -> TraceRecord:
    traj_id = str(_clean(row.get("traj_id")) or "")
    task_name = str(_clean(row.get("task_name")) or "")
    source_family = derive_source_family(row.get("source_relpath"))
    repository_family = derive_repository_family(task_name, source_family)
    step_count = int(_clean(row.get("step_count")) or 0)
    if not traj_id or not task_name or step_count < 1:
        raise ValueError("trajectory requires traj_id, task_name, and positive step_count")

    stages: list[tuple[int, int, int]] = []
    for stage in _items(row.get("stages")):
        if not isinstance(stage, Mapping):
            continue
        stages.append(
            (
                int(stage["stage_id"]),
                int(stage["start_step_id"]),
                int(stage["end_step_id"]),
            )
        )

    incorrect_ids: set[int] = set()
    unuseful_ids: set[int] = set()
    incorrect_stage_ids: set[int] = set()
    step_details: dict[int, dict[str, Any]] = {}
    for stage in _items(row.get("incorrect_stages")):
        if not isinstance(stage, Mapping):
            continue
        stage_id = int(stage["stage_id"])
        stage_incorrect = {int(value) for value in _items(stage.get("incorrect_step_ids"))}
        stage_unuseful = {int(value) for value in _items(stage.get("unuseful_step_ids"))}
        incorrect_ids.update(stage_incorrect)
        unuseful_ids.update(stage_unuseful)
        if stage_incorrect:
            incorrect_stage_ids.add(stage_id)
        for step in _items(stage.get("steps")):
            if not isinstance(step, Mapping):
                continue
            step_id = int(step["step_id"])
            labels = tuple(sorted(str(label) for label in _items(step.get("labels"))))
            step_details[step_id] = {
                "labels": labels,
                "action_hash": _reference_hash(step.get("action_ref")),
                "observation_hash": _reference_hash(step.get("observation_ref")),
            }

    for step_id in incorrect_ids | unuseful_ids:
        if not 1 <= step_id <= step_count:
            raise ValueError(f"{traj_id}: label step {step_id} outside 1..{step_count}")
        detail = step_details.setdefault(
            step_id,
            {"labels": (), "action_hash": None, "observation_hash": None},
        )
        inferred = set(detail["labels"])
        if step_id in incorrect_ids:
            inferred.add("incorrect")
        if step_id in unuseful_ids:
            inferred.add("unuseful")
        detail["labels"] = tuple(sorted(inferred))

    labeled_steps = tuple(
        LabeledStep(
            step_id=step_id,
            labels=tuple(detail["labels"]),
            action_hash=detail["action_hash"],
            observation_hash=detail["observation_hash"],
        )
        for step_id, detail in sorted(step_details.items())
    )
    solved = _clean(row.get("solved"))
    if solved is not None:
        solved = bool(solved)
    return TraceRecord(
        traj_id=traj_id,
        agent=str(_clean(row.get("agent")) or "unknown"),
        model=str(_clean(row.get("model")) or "unknown"),
        task_name=task_name,
        difficulty=str(_clean(row.get("difficulty")) or "unknown"),
        category=str(_clean(row.get("category")) or "unknown"),
        solved=solved,
        step_count=step_count,
        stages=tuple(sorted(stages, key=lambda item: (item[1], item[2], item[0]))),
        incorrect_stage_ids=tuple(sorted(incorrect_stage_ids)),
        incorrect_step_ids=tuple(sorted(incorrect_ids)),
        unuseful_step_ids=tuple(sorted(unuseful_ids)),
        labeled_steps=labeled_steps,
        source_family=source_family,
        repository_family=repository_family,
        # Repository/task identity is the leakage block even if the source path is
        # missing or the same repository appears in more than one upstream source.
        group_key=repository_family,
    )


def assign_blocked_splits(records: Sequence[TraceRecord]) -> dict[str, str]:
    """Create deterministic 70/15/15 source-stratified, repository-blocked splits."""

    group_sizes: Counter[str] = Counter()
    group_sources: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        group_sizes[record.group_key] += 1
        group_sources[record.group_key][record.source_family] += 1

    by_source: dict[str, dict[str, int]] = defaultdict(dict)
    for group, size in group_sizes.items():
        # Source stratification never wins over repository leakage blocking.
        # Lexical order makes modal ties deterministic.
        primary_source = min(
            group_sources[group],
            key=lambda source: (-group_sources[group][source], source),
        )
        by_source[primary_source][group] = size

    assignments: dict[str, str] = {}
    for source_family, group_sizes in sorted(by_source.items()):
        total = sum(group_sizes.values())
        targets = {name: ratio * total for name, ratio in SPLIT_TARGETS.items()}
        current = {name: 0 for name in SPLIT_TARGETS}
        groups = sorted(
            group_sizes,
            key=lambda group: (-group_sizes[group], _stable_digest(group)),
        )
        for group in groups:
            size = group_sizes[group]

            def objective(split: str) -> tuple[float, int]:
                next_counts = dict(current)
                next_counts[split] += size
                absolute_error = sum(
                    abs(next_counts[name] - targets[name]) for name in targets
                )
                return (absolute_error, SPLIT_PRIORITY.index(split))

            chosen = min(SPLIT_PRIORITY, key=objective)
            assignments[group] = chosen
            current[chosen] += size
    return assignments


def assign_unseen_group(group_key: str) -> str:
    fraction = int(_stable_digest("unseen", group_key)[:16], 16) / 16**16
    if fraction < SPLIT_TARGETS["train"]:
        return "train"
    if fraction < SPLIT_TARGETS["train"] + SPLIT_TARGETS["dev"]:
        return "dev"
    return "test"


def _split_records(
    records: Sequence[TraceRecord], assignments: Mapping[str, str], split: str
) -> list[TraceRecord]:
    return [
        record
        for record in records
        if assignments.get(record.group_key, assign_unseen_group(record.group_key))
        == split
    ]


def _stage_features(record: TraceRecord) -> dict[str, float]:
    spans = [end - start + 1 for _, start, end in record.stages]
    mean_span = statistics.fmean(spans) if spans else float(record.step_count)
    span_cv = (
        statistics.pstdev(spans) / mean_span if len(spans) > 1 and mean_span else 0.0
    )
    max_span_fraction = max(spans, default=record.step_count) / record.step_count
    return {
        "log_steps": math.log1p(record.step_count),
        "log_stages": math.log1p(len(record.stages)),
        "span_cv": span_cv,
        "max_span_fraction": max_span_fraction,
    }


def fit_structural_scaler(records: Sequence[TraceRecord]) -> dict[str, tuple[float, float]]:
    features = [_stage_features(record) for record in records]
    scaler: dict[str, tuple[float, float]] = {}
    for name in ("log_steps", "log_stages", "span_cv", "max_span_fraction"):
        values = [row[name] for row in features]
        mean = statistics.fmean(values)
        std = statistics.pstdev(values) or 1.0
        scaler[name] = (mean, std)
    return scaler


def structural_signal_score(
    record: TraceRecord, scaler: Mapping[str, tuple[float, float]]
) -> float:
    """Fixed, label/outcome-blind equal-weight structural friction score."""

    features = _stage_features(record)
    return sum(
        (features[name] - scaler[name][0]) / scaler[name][1]
        for name in ("log_steps", "log_stages", "span_cv", "max_span_fraction")
    )


def _rank_by_score(
    records: Sequence[TraceRecord], scores: Mapping[str, float]
) -> list[TraceRecord]:
    return sorted(
        records,
        key=lambda record: (-scores[record.traj_id], _stable_digest(record.traj_id)),
    )


def _selection_metrics(
    selected: Sequence[TraceRecord], population: Sequence[TraceRecord]
) -> dict[str, float | int]:
    informative_total = sum(record.informative for record in population)
    informative_selected = sum(record.informative for record in selected)
    precision = informative_selected / len(selected) if selected else 0.0
    recall = informative_selected / informative_total if informative_total else 0.0
    prevalence = informative_total / len(population) if population else 0.0
    return {
        "selected": len(selected),
        "informative_selected": informative_selected,
        "precision": precision,
        "recall": recall,
        "population_prevalence": prevalence,
        "precision_lift": precision - prevalence,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def run_e1(
    train: Sequence[TraceRecord],
    test: Sequence[TraceRecord],
    *,
    seed: int,
    budget_fraction: float = 0.20,
    random_repetitions: int = 500,
) -> dict[str, Any]:
    budget = max(1, math.ceil(len(test) * budget_fraction))
    scaler = fit_structural_scaler(train)
    length_scores = {record.traj_id: float(record.step_count) for record in test}
    stage_scores = {record.traj_id: float(len(record.stages)) for record in test}
    structural_scores = {
        record.traj_id: structural_signal_score(record, scaler) for record in test
    }
    rankings = {
        "trace_length": _rank_by_score(test, length_scores),
        "stage_count": _rank_by_score(test, stage_scores),
        "structural_signal": _rank_by_score(test, structural_scores),
    }
    arms = {
        name: _selection_metrics(ranking[:budget], test)
        for name, ranking in rankings.items()
    }

    random_precisions: list[float] = []
    random_recalls: list[float] = []
    for repetition in range(random_repetitions):
        ranked = sorted(
            test,
            key=lambda record: _stable_digest(seed, repetition, record.traj_id),
        )
        metrics = _selection_metrics(ranked[:budget], test)
        random_precisions.append(float(metrics["precision"]))
        random_recalls.append(float(metrics["recall"]))
    arms["uniform_random"] = {
        "selected": budget,
        "repetitions": random_repetitions,
        "precision_mean": statistics.fmean(random_precisions),
        "precision_interval_95": [
            _quantile(random_precisions, 0.025),
            _quantile(random_precisions, 0.975),
        ],
        "recall_mean": statistics.fmean(random_recalls),
        "recall_interval_95": [
            _quantile(random_recalls, 0.025),
            _quantile(random_recalls, 0.975),
        ],
        "population_prevalence": sum(record.informative for record in test)
        / len(test),
    }

    signal_slots = math.floor(budget * 0.80)
    signal_selected = rankings["structural_signal"][:signal_slots]
    selected_ids = {record.traj_id for record in signal_selected}
    audit_candidates = sorted(
        (record for record in test if record.traj_id not in selected_ids),
        key=lambda record: _stable_digest(seed, "audit", record.traj_id),
    )
    signal_plus_audit = signal_selected + audit_candidates[: budget - signal_slots]
    arms["structural_signal_plus_random_audit"] = _selection_metrics(
        signal_plus_audit, test
    )

    by_source: dict[str, Any] = {}
    selected_ids = {
        record.traj_id for record in rankings["structural_signal"][:budget]
    }
    for source in sorted({record.source_family for record in test}):
        source_rows = [record for record in test if record.source_family == source]
        selected = [record for record in source_rows if record.traj_id in selected_ids]
        by_source[source] = {
            "population": len(source_rows),
            "informative": sum(record.informative for record in source_rows),
            "selected": len(selected),
            "informative_selected": sum(record.informative for record in selected),
        }

    structural_precision = float(arms["structural_signal"]["precision"])
    random_interval = arms["uniform_random"]["precision_interval_95"]
    return {
        "question": "Can label-blind manifest structure enrich human-labeled traces at a fixed review budget?",
        "status": "manifest-level deterministic baseline; not a preregistered Signals replication",
        "label_blind_inputs": [
            "step_count",
            "stage_count",
            "stage span coefficient of variation",
            "largest stage span fraction",
        ],
        "forbidden_from_scores": [
            "solved",
            "incorrect stages or steps",
            "unuseful steps",
            "difficulty",
            "category",
            "agent",
            "model",
        ],
        "gold_informative_definition": "at least one human incorrect or unuseful step label",
        "budget_fraction": budget_fraction,
        "budget": budget,
        "arms": arms,
        "interpretation": {
            "structural_minus_random_mean_precision": structural_precision
            - float(arms["uniform_random"]["precision_mean"]),
            "structural_minus_length_precision": structural_precision
            - float(arms["trace_length"]["precision"]),
            "structural_exceeds_seeded_random_95_interval": structural_precision
            > float(random_interval[1]),
            "conclusion": (
                "ambiguous/negative: structural signal tied trace length and did not "
                "exceed the seeded-random 95% interval"
            ),
        },
        "structural_signal_by_source": by_source,
    }


def _stage_boundaries(record: TraceRecord) -> tuple[list[int], list[int]]:
    starts = [start for _, start, _ in record.stages]
    ends = [end for _, _, end in record.stages]
    return starts, ends


def _rank_steps(record: TraceRecord, method: str, seed: int) -> list[int]:
    steps = list(range(1, record.step_count + 1))
    starts, ends = _stage_boundaries(record)
    if method == "uniform_random":
        return sorted(
            steps, key=lambda step: _stable_digest(seed, record.traj_id, step)
        )
    if method == "forward_chronology":
        return steps
    if method == "reverse_chronology":
        return list(reversed(steps))
    if method == "stage_boundary_recency":
        preferred = list(reversed(ends)) + list(reversed(starts))
    elif method == "longest_stage_end":
        spans = sorted(
            record.stages,
            key=lambda item: (-(item[2] - item[1] + 1), -item[2], item[0]),
        )
        preferred = [end for _, _, end in spans]
    elif method in {"critical_stage_start_oracle", "critical_stage_end_oracle"}:
        stage_map = {stage_id: (start, end) for stage_id, start, end in record.stages}
        boundary_index = 0 if method.endswith("start_oracle") else 1
        preferred = [
            stage_map[stage_id][boundary_index]
            for stage_id in record.incorrect_stage_ids
            if stage_id in stage_map
        ]
    else:
        raise ValueError(f"unknown diagnosis method: {method}")
    seen: set[int] = set()
    ranked: list[int] = []
    for step in preferred + list(reversed(steps)):
        if 1 <= step <= record.step_count and step not in seen:
            seen.add(step)
            ranked.append(step)
    return ranked


def _diagnosis_metrics(
    records: Sequence[TraceRecord], method: str, seed: int
) -> dict[str, float | int]:
    top1 = top3 = 0
    reciprocal_ranks: list[float] = []
    distances: list[int] = []
    precision: list[float] = []
    recall: list[float] = []
    f1: list[float] = []
    for record in records:
        gold = set(record.incorrect_step_ids)
        ranking = _rank_steps(record, method, seed)
        top1 += ranking[0] in gold
        top3 += bool(set(ranking[:3]) & gold)
        rank = next(index for index, step in enumerate(ranking, start=1) if step in gold)
        reciprocal_ranks.append(1.0 / rank)
        distances.append(min(abs(ranking[0] - step) for step in gold))
        predicted = set(ranking[: len(gold)])
        true_positive = len(predicted & gold)
        p = true_positive / len(predicted)
        r = true_positive / len(gold)
        precision.append(p)
        recall.append(r)
        f1.append(2 * p * r / (p + r) if p + r else 0.0)
    count = len(records)
    return {
        "traces": count,
        "top1_accuracy": top1 / count,
        "top3_accuracy": top3 / count,
        "mean_reciprocal_rank": statistics.fmean(reciprocal_ranks),
        "mean_top1_distance": statistics.fmean(distances),
        "macro_precision_at_gold_count": statistics.fmean(precision),
        "macro_recall_at_gold_count": statistics.fmean(recall),
        "macro_f1_at_gold_count": statistics.fmean(f1),
    }


def run_e3(test: Sequence[TraceRecord], *, seed: int) -> dict[str, Any]:
    labeled = [record for record in test if record.incorrect_step_ids]
    blind_methods = [
        "uniform_random",
        "forward_chronology",
        "reverse_chronology",
        "stage_boundary_recency",
        "longest_stage_end",
    ]
    oracle_methods = [
        "critical_stage_start_oracle",
        "critical_stage_end_oracle",
    ]
    methods = {
        method: _diagnosis_metrics(labeled, method, seed)
        for method in blind_methods + oracle_methods
    }

    # Irrelevant-tail control: a terminal junk event should not change a robust
    # localizer.  The manifest lacks event content, so only blind structural methods
    # can be tested here.
    injected: list[TraceRecord] = []
    for record in labeled:
        injected.append(dataclasses.replace(record, step_count=record.step_count + 1))
    irrelevant_tail = {
        method: {
            "original_top1_accuracy": methods[method]["top1_accuracy"],
            "injected_top1_accuracy": _diagnosis_metrics(
                injected, method, seed
            )["top1_accuracy"],
        }
        for method in blind_methods
    }
    return {
        "question": "How well do deterministic manifest-level baselines localize the human incorrect-step set?",
        "target": (
            "human incorrect_step_ids; the paper describes the earliest causal-chain "
            "origin as error-critical, but the released manifest may contain multiple "
            "incorrect steps and chains"
        ),
        "status": (
            "E3 baseline/scaffolding only: no raw action sequence, invariants, modal "
            "evidence, calibrated judge, taxonomy, or abstention was evaluated"
        ),
        "blind_methods": blind_methods,
        "annotation_consuming_upper_bounds": oracle_methods,
        "methods": methods,
        "negative_control_irrelevant_terminal_step": irrelevant_tail,
        "unsupported_negative_controls": [
            "wrong timestamps: manifest has no event timestamps",
            "removed decisive evidence with calibrated abstention: baselines have no evidence model",
            "environment or permission swap: manifest lacks those modalities",
        ],
    }


@dataclasses.dataclass(frozen=True)
class AuditEvent:
    step_id: int
    labels: tuple[str, ...]
    action_hash: str | None
    observation_hash: str | None


def _audit_events(record: TraceRecord) -> list[AuditEvent]:
    return [
        AuditEvent(
            step_id=step.step_id,
            labels=step.labels,
            action_hash=step.action_hash,
            observation_hash=step.observation_hash,
        )
        for step in record.labeled_steps
        if step.step_id in set(record.incorrect_step_ids)
    ]


def evaluate_assertion(
    assertion: str, expected: Sequence[AuditEvent], observed: Sequence[AuditEvent]
) -> bool:
    if assertion == "exact_sequence":
        return list(expected) == list(observed)
    expected_ids = [event.step_id for event in expected]
    observed_ids = [event.step_id for event in observed]
    if assertion == "ordered_required":
        cursor = iter(observed_ids)
        return all(any(candidate == required for candidate in cursor) for required in expected_ids)
    if assertion == "unordered_required":
        return set(expected_ids).issubset(observed_ids)
    if assertion == "combined":
        if not evaluate_assertion("ordered_required", expected, observed):
            return False
        expected_by_id = {event.step_id: event for event in expected}
        counts = Counter(observed_ids)
        if any(counts[step_id] != 1 for step_id in expected_by_id):
            return False
        observed_by_id = {event.step_id: event for event in observed}
        return all(observed_by_id[step_id] == event for step_id, event in expected_by_id.items())
    raise ValueError(f"unknown assertion: {assertion}")


def mutate_audit(
    events: Sequence[AuditEvent],
    mutation: str,
    *,
    irrelevant_step_id: int,
    seed: int = DEFAULT_SEED,
    trajectory_id: str = "",
) -> list[AuditEvent] | None:
    changed = list(events)
    if not changed:
        return None
    candidate_order = sorted(
        range(len(changed)),
        key=lambda index: _stable_digest(
            seed, trajectory_id, mutation, changed[index].step_id
        ),
    )
    if mutation == "remove_required":
        del changed[candidate_order[0]]
        return changed
    if mutation == "duplicate_required":
        index = candidate_order[0]
        changed.insert(index, changed[index])
        return changed
    if mutation == "reorder_required":
        if len(changed) < 2:
            return None
        first, second = sorted(candidate_order[:2])
        changed[first], changed[second] = changed[second], changed[first]
        return changed
    if mutation == "alter_action_reference":
        candidates = [
            index
            for index in candidate_order
            if changed[index].action_hash is not None
        ]
        index = candidates[0] if candidates else None
        if index is None:
            return None
        changed[index] = dataclasses.replace(changed[index], action_hash="mutated")
        return changed
    if mutation == "alter_observation_reference":
        candidates = [
            index
            for index in candidate_order
            if changed[index].observation_hash is not None
        ]
        index = candidates[0] if candidates else None
        if index is None:
            return None
        changed[index] = dataclasses.replace(
            changed[index], observation_hash="mutated"
        )
        return changed
    if mutation == "relabel_required":
        index = candidate_order[0]
        changed[index] = dataclasses.replace(changed[index], labels=("mutated",))
        return changed
    if mutation == "inject_irrelevant":
        changed.append(
            AuditEvent(
                step_id=irrelevant_step_id,
                labels=("irrelevant",),
                action_hash=None,
                observation_hash=None,
            )
        )
        return changed
    raise ValueError(f"unknown mutation: {mutation}")


def run_e4(test: Sequence[TraceRecord], *, seed: int) -> dict[str, Any]:
    assertions = [
        "exact_sequence",
        "ordered_required",
        "unordered_required",
        "combined",
    ]
    harmful = [
        "remove_required",
        "duplicate_required",
        "reorder_required",
        "alter_action_reference",
        "alter_observation_reference",
        "relabel_required",
    ]
    allowed = ["inject_irrelevant"]
    mutations = harmful + allowed
    counts: dict[str, dict[str, int]] = {
        mutation: {"supported": 0, **{assertion: 0 for assertion in assertions}}
        for mutation in mutations
    }
    baseline_failures = Counter()
    for record in test:
        expected = _audit_events(record)
        if not expected:
            continue
        for assertion in assertions:
            if not evaluate_assertion(assertion, expected, expected):
                baseline_failures[assertion] += 1
        for mutation in mutations:
            observed = mutate_audit(
                expected,
                mutation,
                irrelevant_step_id=record.step_count + 1,
                seed=seed,
                trajectory_id=record.traj_id,
            )
            if observed is None:
                continue
            counts[mutation]["supported"] += 1
            for assertion in assertions:
                if not evaluate_assertion(assertion, expected, observed):
                    counts[mutation][assertion] += 1

    matrix: dict[str, Any] = {}
    for mutation in mutations:
        supported = counts[mutation]["supported"]
        matrix[mutation] = {
            "classification": "harmful" if mutation in harmful else "allowed_variation",
            "supported_traces": supported,
            "assertions": {
                assertion: {
                    "failures": counts[mutation][assertion],
                    (
                        "mutant_kill_rate"
                        if mutation in harmful
                        else "false_positive_rate"
                    ): counts[mutation][assertion] / supported
                    if supported
                    else None,
                }
                for assertion in assertions
            },
        }

    aggregate: dict[str, Any] = {}
    for assertion in assertions:
        harmful_supported = sum(counts[mutation]["supported"] for mutation in harmful)
        harmful_kills = sum(counts[mutation][assertion] for mutation in harmful)
        allowed_supported = sum(counts[mutation]["supported"] for mutation in allowed)
        allowed_failures = sum(counts[mutation][assertion] for mutation in allowed)
        aggregate[assertion] = {
            "baseline_failures": baseline_failures[assertion],
            "harmful_mutants": harmful_supported,
            "harmful_mutants_killed": harmful_kills,
            "harmful_mutant_kill_rate": harmful_kills / harmful_supported,
            "allowed_variants": allowed_supported,
            "allowed_variants_rejected": allowed_failures,
            "allowed_variation_false_positive_rate": allowed_failures
            / allowed_supported,
        }
    return {
        "question": "Which retrospective assertions detect seeded changes without rejecting an irrelevant extra event?",
        "status": (
            "annotation-derived retrospective audit mutation test; not a runnable "
            "agent eval and not evidence that a future behavior was corrected"
        ),
        "seed": seed,
        "mutation_target_selection": (
            "one supported target per trace and mutation, selected by SHA-256 of "
            "seed, trajectory ID, mutation, and step ID"
        ),
        "assertion_semantics": {
            "exact_sequence": "all annotated events must be byte-for-byte identical",
            "ordered_required": "required annotated step IDs remain an ordered subsequence",
            "unordered_required": "the required annotated step-ID set remains present",
            "combined": (
                "ordered required IDs, exactly one occurrence, and label/reference "
                "fingerprint equality while allowing unrelated extra events"
            ),
        },
        "mutation_matrix": matrix,
        "aggregate_by_assertion": aggregate,
        "unsupported_assertions": [
            "semantic terminal condition",
            "independently observed external state delta",
            "authorization or policy decision",
            "tool argument or result mutation outside annotated references",
        ],
    }


def _count_by(records: Iterable[TraceRecord], attribute: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(str(getattr(record, attribute)) for record in records).items()
        )
    )


def build_split_audit(
    full: Sequence[TraceRecord],
    verified: Sequence[TraceRecord],
    assignments: Mapping[str, str],
) -> dict[str, Any]:
    full_by_id = {record.traj_id: record for record in full}
    verified_by_id = {record.traj_id: record for record in verified}
    missing_parents = sorted(set(verified_by_id) - set(full_by_id))
    split_for = lambda record: assignments.get(
        record.group_key, assign_unseen_group(record.group_key)
    )
    parent_split_mismatches = sum(
        split_for(record) != split_for(full_by_id[record.traj_id])
        for record in verified
        if record.traj_id in full_by_id
    )
    repository_splits: dict[str, set[str]] = defaultdict(set)
    task_splits: dict[str, set[str]] = defaultdict(set)
    for record in full:
        split = split_for(record)
        repository_splits[record.group_key].add(split)
        task_splits[record.task_name].add(split)
    verified_split_counts = Counter(split_for(record) for record in verified)
    full_split_counts = Counter(split_for(record) for record in full)
    source_table: dict[str, dict[str, int]] = {}
    for source in sorted({record.source_family for record in verified}):
        source_table[source] = dict(
            sorted(
                Counter(
                    split_for(record)
                    for record in verified
                    if record.source_family == source
                ).items()
            )
        )
    return {
        "method": (
            "source-stratified greedy 70/15/15 assignment over verified rows; "
            "repository/task groups remain indivisible across sources, and a "
            "cross-source group is placed in its modal source stratum"
        ),
        "verified_counts": dict(sorted(verified_split_counts.items())),
        "full_counts": dict(sorted(full_split_counts.items())),
        "verified_to_full_parent_overlap": len(set(verified_by_id) & set(full_by_id)),
        "verified_missing_full_parent": len(missing_parents),
        "parent_split_mismatches": parent_split_mismatches,
        "repository_groups_crossing_splits": sum(
            len(splits) > 1 for splits in repository_splits.values()
        ),
        "task_groups_crossing_splits": sum(
            len(splits) > 1 for splits in task_splits.values()
        ),
        "verified_source_by_split": source_table,
        "unknown_source_rows": {
            "verified": sum(
                record.source_family == "unknown-source" for record in verified
            ),
            "full": sum(record.source_family == "unknown-source" for record in full),
        },
    }


def run_study(
    full: Sequence[TraceRecord],
    verified: Sequence[TraceRecord],
    *,
    full_sha256: str,
    verified_sha256: str,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    assignments = assign_blocked_splits(verified)
    train = _split_records(verified, assignments, "train")
    test = _split_records(verified, assignments, "test")
    split_audit = build_split_audit(full, verified, assignments)
    if (
        split_audit["verified_missing_full_parent"]
        or split_audit["parent_split_mismatches"]
        or split_audit["repository_groups_crossing_splits"]
        or split_audit["task_groups_crossing_splits"]
    ):
        raise ValueError("blocked split invariants failed")
    result = {
        "schema_version": "frankengate-trace-empirical-result-v1",
        "analysis_revision": ANALYSIS_REVISION,
        "run_date": "2026-07-30",
        "seed": seed,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "license": DATASET_LICENSE,
            "dataset_url": DATASET_URL,
            "paper_url": PAPER_URL,
            "inputs": {
                "bench_manifest.full.parquet": {
                    "rows": len(full),
                    "sha256": full_sha256,
                },
                "bench_manifest.verified.parquet": {
                    "rows": len(verified),
                    "sha256": verified_sha256,
                },
            },
            "raw_trajectory_artifacts_downloaded": False,
            "raw_data_committed": False,
        },
        "corpus": {
            "verified_trajectories": len(verified),
            "verified_informative": sum(record.informative for record in verified),
            "verified_with_incorrect_steps": sum(
                bool(record.incorrect_step_ids) for record in verified
            ),
            "verified_incorrect_step_labels": sum(
                len(record.incorrect_step_ids) for record in verified
            ),
            "verified_unuseful_step_labels": sum(
                len(record.unuseful_step_ids) for record in verified
            ),
            "agents": _count_by(verified, "agent"),
            "sources": _count_by(verified, "source_family"),
            "difficulty": _count_by(verified, "difficulty"),
        },
        "split_audit": split_audit,
        "e1_signal_selection": run_e1(train, test, seed=seed),
        "e3_decisive_step_diagnosis": run_e3(test, seed=seed),
        "e4_eval_assertion_mutation": run_e4(test, seed=seed),
        "claim_boundary": {
            "supported": [
                "manifest-level label-blind selection performance on a blocked test split",
                "deterministic step-ranking performance against released human incorrect-step labels",
                "seeded mutation sensitivity of annotation-derived retrospective assertions",
            ],
            "not_supported": [
                "full Signals-paper replication",
                "AgentRx/OpenRCA/LLM-judge diagnosis factorial",
                "causal proof that a labeled step caused the terminal outcome",
                "runnable replay eval or independent environment-state verification",
                "enterprise, person-level skill, productivity, or intervention utility",
            ],
        },
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["result_content_sha256"] = _sha256_bytes(canonical)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    e1 = result["e1_signal_selection"]
    e3 = result["e3_decisive_step_diagnosis"]
    e4 = result["e4_eval_assertion_mutation"]
    split = result["split_audit"]
    e1_rows = []
    for name in (
        "uniform_random",
        "trace_length",
        "stage_count",
        "structural_signal",
        "structural_signal_plus_random_audit",
    ):
        arm = e1["arms"][name]
        precision = arm.get("precision", arm.get("precision_mean"))
        recall = arm.get("recall", arm.get("recall_mean"))
        e1_rows.append(f"| `{name}` | {precision:.3f} | {recall:.3f} |")
    e3_rows = []
    for name, metrics in e3["methods"].items():
        kind = "oracle" if name in e3["annotation_consuming_upper_bounds"] else "blind"
        e3_rows.append(
            f"| `{name}` | {kind} | {metrics['top1_accuracy']:.3f} | "
            f"{metrics['top3_accuracy']:.3f} | "
            f"{metrics['mean_reciprocal_rank']:.3f} | "
            f"{metrics['macro_f1_at_gold_count']:.3f} |"
        )
    e4_rows = []
    for name, metrics in e4["aggregate_by_assertion"].items():
        e4_rows.append(
            f"| `{name}` | {metrics['harmful_mutants']} | "
            f"{metrics['harmful_mutant_kill_rate']:.3f} | "
            f"{metrics['allowed_variation_false_positive_rate']:.3f} |"
        )
    source_rows = []
    for source, counts in split["verified_source_by_split"].items():
        source_rows.append(
            f"| `{source}` | {counts.get('train', 0)} | "
            f"{counts.get('dev', 0)} | {counts.get('test', 0)} |"
        )
    return f"""# CodeTraceBench manifest-level E1/E3/E4 study

**Run date:** {result['run_date']}

**Analysis:** `{result['analysis_revision']}`

**Dataset:** [{result['source']['dataset_id']} @
`{result['source']['dataset_revision']}`]({result['source']['dataset_url']}),
{result['source']['license']}

**Paper:** [CodeTracer: Towards Traceable Agent
States]({result['source']['paper_url']})

**Result content hash:** `{result['result_content_sha256']}`

## Abstract

This reproducible study tests three narrow parts of Frankengate's trace-intelligence
program against CodeTraceBench's released manifests.  It uses the 1,000-row verified
set for human labels and the 3,316-row full set solely to verify parent overlap and
split integrity.  Raw trajectory archives were neither downloaded nor committed.

The result is useful but deliberately smaller than the planned E1/E3/E4 factorials:
it measures label-blind structural review selection, deterministic localization
baselines against human incorrect-step labels, and seeded mutation sensitivity of
annotation-derived retrospective assertions.  It does **not** test trace content,
invariants, multimodal evidence, an LLM judge, a resettable environment, or a changed
agent.

## Reproduction

Download exactly these two files from the pinned Hugging Face revision into a
non-repository directory:

```text
bench_manifest.full.parquet
  sha256 {result['source']['inputs']['bench_manifest.full.parquet']['sha256']}
bench_manifest.verified.parquet
  sha256 {result['source']['inputs']['bench_manifest.verified.parquet']['sha256']}
```

Then run:

```bash
python3 research/trace-intelligence/codetracebench_empirical.py \\
  --full /private/tmp/frankengate-codetracebench-aa213b84/bench_manifest.full.parquet \\
  --verified /private/tmp/frankengate-codetracebench-aa213b84/bench_manifest.verified.parquet \\
  --output-json /tmp/codetracebench-result.json \\
  --output-markdown /tmp/codetracebench-result.md
```

The loader fails closed on either file hash.  Output is aggregate-only and deterministic
for the fixed seed `{result['seed']}`.

## Corpus and split integrity

- Verified rows: {result['corpus']['verified_trajectories']}
- Human-labeled informative rows:
  {result['corpus']['verified_informative']}
- Rows with incorrect-step labels:
  {result['corpus']['verified_with_incorrect_steps']}
- Incorrect-step labels: {result['corpus']['verified_incorrect_step_labels']}
- Unuseful-step labels: {result['corpus']['verified_unuseful_step_labels']}
- Verified rows found in full parent: {split['verified_to_full_parent_overlap']}
- Missing parents: {split['verified_missing_full_parent']}
- Parent split mismatches: {split['parent_split_mismatches']}
- Repository groups crossing splits:
  {split['repository_groups_crossing_splits']}
- Task groups crossing splits: {split['task_groups_crossing_splits']}
- Missing source path: {split['unknown_source_rows']['verified']} verified and
  {split['unknown_source_rows']['full']} full rows; these remain explicitly unknown.

The assignment is source-stratified and blocks repository family.  TerminalBench
manifests do not expose repository identity, so each task is the indivisible fallback
group.  The verified set is a subset of full, never an independent test set.

| Source family | Train | Dev | Test |
|---|---:|---:|---:|
{chr(10).join(source_rows)}

## E1: label-blind review selection

The test budget is {e1['budget']} of
{split['verified_counts']['test']} rows ({e1['budget_fraction']:.0%}).  "Informative"
means the authors released at least one incorrect or unuseful step label.  Scores use
only step count and stage-boundary structure.  Outcome, labels, task category, agent,
model, and difficulty are excluded.

| Arm | Precision | Recall |
|---|---:|---:|
{chr(10).join(e1_rows)}

This is a deterministic structural baseline, not a preregistered replication of the
Signals paper.  In particular, the manifest cannot expose rephrasing, semantic loops,
tool failures, disengagement, or stagnation in the raw event stream.  Any improvement
over random only justifies a review-queue heuristic; it is not a diagnosis.

## E3: incorrect-step localization

The gold target is the released `incorrect_step_ids`.  The paper calls the earliest
upstream causal-chain origin error-critical, but a manifest row can contain multiple
incorrect steps or chains.  Results therefore measure overlap with the released set,
not independently established causality.

| Method | Evidence class | Top-1 | Top-3 | MRR | Macro F1@|G| |
|---|---|---:|---:|---:|---:|
{chr(10).join(e3_rows)}

The critical-stage boundary methods consume the annotated incorrect-stage identity
and are explicitly upper bounds, not deployable baselines.  No method here evaluates
the planned invariant × topology/modal-evidence × calibrated-judge factorial.
Irrelevant-tail injection is the only available content-free negative control.
Timestamp, environment, permission, and evidence-removal controls are impossible from
the manifest and remain untested.

## E4: retrospective assertion mutation

Human-labeled steps were converted into four retrospective audit assertions.  One
supported mutation at a time removes, duplicates, reorders, relabels, or changes an
available action/observation reference.  Injecting one unrelated event is the allowed
variation control.

| Assertion | Harmful mutants | Kill rate | Allowed-variation false positive |
|---|---:|---:|---:|
{chr(10).join(e4_rows)}

`exact_sequence` is intentionally brittle.  `combined` retains order, cardinality,
labels, and released reference fingerprints while allowing an unrelated event.  This
validates mutation-harness mechanics only.  Because the assertions are derived from
the same annotations they evaluate, the high kill rate is not evidence of
generalization.  They are audits, not runnable evals; no agent was rerun and no
external state delta was observed.

## What this changes for Frankengate

1. Keep cheap structural signals as label-blind candidate selectors and always retain
   a random audit stratum.  Do not label their output as root cause.
2. Store gold step sets, coarse stages, prediction rankings, alternatives, abstention,
   and evidence IDs separately.  A stage label is useful navigation but cannot be
   counted as a blind step diagnosis.
3. Require every proposed eval to declare whether it is a stored-trace audit or a
   changed-system replay.  Mutation sensitivity and allowed-variation false positives
   are both release gates.
4. Do not use these software-agent labels to infer employee skill, productivity,
   intent, or collaboration fit.  They contain no enterprise authorization,
   intervention, or human-work outcome evidence.

## Limitations and next experiment

CodeTraceBench is filtered: the paper reports removing timeout, truncated,
misconfigured/corrupt, and short correct runs before benchmark curation.  It therefore
cannot estimate natural enterprise failure prevalence.  The released dataset version
also differs from counts reported in the paper; this study treats the pinned files as
the empirical authority and records their hashes.

The next E3/E4 experiment must freeze a license-clean raw-artifact allowlist from the
blocked test groups, parse complete action/observation sequences, and run the full
factorial with invariants, ordered topology/modal evidence, calibrated abstention, and
independent verifier state.  Until then, Frankengate should ship evidence-linked
review and eval proposals, not automatic root-cause or skill claims.
"""


def _load_parquet(path: pathlib.Path) -> list[TraceRecord]:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - exercised by CLI environments
        raise RuntimeError("pandas and a Parquet engine are required") from exc
    frame = pd.read_parquet(path)
    return [record_from_mapping(row) for row in frame.to_dict(orient="records")]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=pathlib.Path, required=True)
    parser.add_argument("--verified", type=pathlib.Path, required=True)
    parser.add_argument("--output-json", type=pathlib.Path, required=True)
    parser.add_argument("--output-markdown", type=pathlib.Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    hashes = {
        "full": _file_sha256(args.full),
        "verified": _file_sha256(args.verified),
    }
    for split, expected in EXPECTED_SHA256.items():
        if hashes[split] != expected:
            raise SystemExit(
                f"{split} input hash mismatch: got {hashes[split]}, expected {expected}"
            )
    full = _load_parquet(args.full)
    verified = _load_parquet(args.verified)
    result = run_study(
        full,
        verified,
        full_sha256=hashes["full"],
        verified_sha256=hashes["verified"],
        seed=args.seed,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output_markdown.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
