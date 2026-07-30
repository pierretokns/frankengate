#!/usr/bin/env python3
"""Pinned paired-condition analysis for the MATM ALFWorld evaluation shard.

The statistical unit is the (task_id, model) block.  Every admitted block must
contain exactly one no-retrieval row and one row for each of five rerank depths.
Raw trajectories remain outside Git; committed output contains aggregate
statistics and content hashes only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


SCHEMA_VERSION = "matm-paired-pilot-result-v1"
CANONICAL_SCHEMA_VERSION = "canonical-trajectory-v1"
DATASET_ID = "toeunkim/matm-trajectories"
DATASET_REVISION = "d84d6454fc5fcc337e2527533f484b79cf6f0872"
SOURCE_FILE = "alfworld/population_runs.parquet"
SOURCE_SHA256 = "626e2e6351d763739b0e2695a1bc442e1c851c1153c44301017739e3bd1155aa"
SOURCE_SIZE_BYTES = 4_237_969
DATASET_CARD_SHA256 = "0d7fef0a97505a5fe9fb777d48324f50c9992c6e1ff024faf86ea080826e3634"
DECLARED_LICENSE = "Apache-2.0"
ADAPTER = "matm_alfworld_population_v1"
BASELINE = "no_retrieval"
CONDITIONS = (
    BASELINE,
    "rerank_1",
    "rerank_5",
    "rerank_10",
    "rerank_15",
    "rerank_20",
)
EXPECTED_RANK = {
    "no_retrieval": None,
    "rerank_1": 1,
    "rerank_5": 5,
    "rerank_10": 10,
    "rerank_15": 15,
    "rerank_20": 20,
}
PAIR_INVARIANTS = (
    "environment",
    "source_type",
    "model",
    "task_type",
    "task_id",
    "fold",
    "goal",
    "max_steps",
)
KNOWN_MISSING_FIELDS = (
    "retrieved_item_ids",
    "retrieved_item_content",
    "retrieval_scores_and_ranks",
    "memory_snapshot_before",
    "memory_snapshot_after",
    "memory_source_lineage",
    "prompt_after_memory_injection",
    "environment_seed",
    "environment_replay_snapshot",
    "timestamps",
    "authorization_decisions",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def condition_for(row: Mapping[str, Any]) -> str:
    condition = str(row.get("retrieval_strategy"))
    if condition not in CONDITIONS:
        raise ValueError("unknown retrieval condition: %r" % condition)
    expected_rank = EXPECTED_RANK[condition]
    observed_rank = row.get("rank_retrieve")
    if expected_rank is None:
        if observed_rank is not None:
            raise ValueError("baseline unexpectedly has rank_retrieve")
    elif observed_rank is None or int(observed_rank) != expected_rank:
        raise ValueError(
            "%s has rank_retrieve=%r, expected %d"
            % (condition, observed_rank, expected_rank)
        )
    return condition


def parse_trajectory(row: Mapping[str, Any]) -> List[Dict[str, Any]]:
    encoded = row.get("trajectory")
    if isinstance(encoded, str):
        decoded = json.loads(encoded)
    else:
        decoded = encoded
    if not isinstance(decoded, list):
        raise ValueError("trajectory must decode to a list")
    if not all(isinstance(step, dict) for step in decoded):
        raise ValueError("every trajectory step must be an object")
    return decoded


def canonicalize_matm(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Preserve the source row and derive one conservative event per source step.

    MATM puts an action, observation, and reasoning in one step but does not say
    whether the observation is pre-action or post-action.  Splitting a step into
    a fabricated proposal/result span would invent ordering, so the adapter keeps
    an atomic ``environment_interaction_step`` and records the ambiguity.
    """

    source_record = dict(row)
    steps = parse_trajectory(source_record)
    trace_id = sha256_json(source_record)
    events = []
    previous_event_id = None
    for sequence, step in enumerate(steps):
        event_id = "%s:%06d" % (trace_id[:16], sequence)
        events.append(
            {
                "event_id": event_id,
                "sequence": sequence,
                "kind": "environment_interaction_step",
                "observation_status": "observed",
                "source_role": "agent_environment",
                "content": stable_json(step),
                "command": step.get("action"),
                "parent_event_id": previous_event_id,
                "source_step": dict(step),
            }
        )
        previous_event_id = event_id

    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "trace_id": trace_id,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "source_file": SOURCE_FILE,
            "adapter": ADAPTER,
            "model_name": source_record.get("model"),
            "retrieval_condition": condition_for(source_record),
        },
        "task": {
            "task_id": source_record.get("task_id"),
            "task_type": source_record.get("task_type"),
            "goal": source_record.get("goal"),
        },
        "events": events,
        "outcome": {
            "value": bool(source_record.get("success")),
            "score": source_record.get("final_score"),
            "source": "dataset_environment_evaluation",
        },
        "loss_receipt": {
            "source_event_count": len(steps),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": [],
            "known_missing_fields": list(KNOWN_MISSING_FIELDS),
            "ordering_ambiguity": (
                "source does not define whether observation in a trajectory step "
                "precedes or follows that step's action"
            ),
        },
        # This proves round-trip source preservation inside the adapter.  The raw
        # canonical objects are deliberately not written to committed results.
        "source_record": source_record,
    }


def percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        return float("nan")
    index = (len(sorted_values) - 1) * probability
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return float(sorted_values[lower])
    fraction = index - lower
    return float(
        sorted_values[lower] * (1.0 - fraction)
        + sorted_values[upper] * fraction
    )


def bootstrap_pair_ci(
    differences: Sequence[int], replicates: int, seed: int
) -> List[float]:
    rng = random.Random(seed)
    n = len(differences)
    estimates = []
    for _ in range(replicates):
        estimates.append(sum(differences[rng.randrange(n)] for _ in range(n)) / n)
    estimates.sort()
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def bootstrap_model_cluster_ci(
    labeled_differences: Sequence[Tuple[str, int]], replicates: int, seed: int
) -> List[float]:
    by_model = defaultdict(list)
    for model, difference in labeled_differences:
        by_model[model].append(difference)
    models = sorted(by_model)
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        sampled = [models[rng.randrange(len(models))] for _ in models]
        values = [value for model in sampled for value in by_model[model]]
        estimates.append(sum(values) / len(values))
    estimates.sort()
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def exact_two_sided_sign_p(improved: int, worsened: int) -> float:
    discordant = improved + worsened
    if discordant == 0:
        return 1.0
    tail = min(improved, worsened)
    probability = sum(math.comb(discordant, k) for k in range(tail + 1))
    probability /= 2 ** discordant
    return min(1.0, 2.0 * probability)


def grouped_rates(
    rows: Sequence[Mapping[str, Any]], group_field: str
) -> List[Dict[str, Any]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(str(row[group_field]), condition_for(row))].append(row)
    result = []
    for (group, condition), group_rows in sorted(grouped.items()):
        successes = sum(bool(row["success"]) for row in group_rows)
        result.append(
            {
                group_field: group,
                "condition": condition,
                "n": len(group_rows),
                "successes": successes,
                "success_rate": successes / len(group_rows),
                "mean_steps": sum(int(row["num_steps"]) for row in group_rows)
                / len(group_rows),
            }
        )
    return result


def analyze_rows(
    rows: Sequence[Mapping[str, Any]],
    source_sha256: str,
    source_size_bytes: int,
    bootstrap_replicates: int = 10_000,
    bootstrap_seed: int = 20_260_730,
) -> Dict[str, Any]:
    if not rows:
        raise ValueError("dataset is empty")

    parsed = []
    source_record_hashes = []
    null_counts = Counter()
    trajectory_step_mismatches = 0
    for row in rows:
        condition_for(row)
        steps = parse_trajectory(row)
        if len(steps) != int(row["num_steps"]):
            trajectory_step_mismatches += 1
        parsed.append((row, steps))
        source_record_hashes.append(sha256_json(dict(row)))
        for field, value in row.items():
            if value is None:
                null_counts[field] += 1

    pairs = defaultdict(list)
    for row in rows:
        pairs[(str(row["task_id"]), str(row["model"]))].append(row)

    incomplete_pairs = []
    duplicate_condition_rows = 0
    invariant_violations = Counter()
    pair_maps = {}
    for pair_key, pair_rows in sorted(pairs.items()):
        condition_counts = Counter(condition_for(row) for row in pair_rows)
        if set(condition_counts) != set(CONDITIONS) or any(
            count != 1 for count in condition_counts.values()
        ):
            incomplete_pairs.append(
                {
                    "pair_key_sha256": sha256_json(pair_key),
                    "condition_counts": dict(sorted(condition_counts.items())),
                }
            )
        duplicate_condition_rows += sum(
            count - 1 for count in condition_counts.values() if count > 1
        )
        for field in PAIR_INVARIANTS:
            if len({stable_json(row.get(field)) for row in pair_rows}) != 1:
                invariant_violations[field] += 1
        pair_maps[pair_key] = {
            condition_for(row): row for row in pair_rows
        }

    if incomplete_pairs:
        raise ValueError("%d incomplete treatment blocks" % len(incomplete_pairs))

    condition_summaries = []
    for condition in CONDITIONS:
        condition_rows = [row for row in rows if condition_for(row) == condition]
        successes = sum(bool(row["success"]) for row in condition_rows)
        condition_summaries.append(
            {
                "condition": condition,
                "n": len(condition_rows),
                "successes": successes,
                "success_rate": successes / len(condition_rows),
                "mean_steps": sum(int(row["num_steps"]) for row in condition_rows)
                / len(condition_rows),
            }
        )

    outcome_patterns = Counter()
    unique_trajectory_counts = Counter()
    identical_to_baseline = Counter()
    for pair_rows in pair_maps.values():
        outcome_patterns[
            "".join("1" if pair_rows[c]["success"] else "0" for c in CONDITIONS)
        ] += 1
        unique_trajectory_counts[
            len({str(pair_rows[c]["trajectory"]) for c in CONDITIONS})
        ] += 1
        for condition in CONDITIONS[1:]:
            identical_to_baseline[condition] += (
                pair_rows[condition]["trajectory"]
                == pair_rows[BASELINE]["trajectory"]
            )

    paired_effects = []
    for condition_index, condition in enumerate(CONDITIONS[1:], start=1):
        differences = []
        labeled_differences = []
        improved = 0
        worsened = 0
        unchanged_success = 0
        unchanged_failure = 0
        for (_task_id, model), pair_rows in sorted(pair_maps.items()):
            baseline_value = int(bool(pair_rows[BASELINE]["success"]))
            treatment_value = int(bool(pair_rows[condition]["success"]))
            difference = treatment_value - baseline_value
            differences.append(difference)
            labeled_differences.append((model, difference))
            if difference == 1:
                improved += 1
            elif difference == -1:
                worsened += 1
            elif baseline_value:
                unchanged_success += 1
            else:
                unchanged_failure += 1
        seed = bootstrap_seed + condition_index * 1009
        paired_effects.append(
            {
                "condition": condition,
                "baseline": BASELINE,
                "n_pairs": len(differences),
                "success_rate_difference": sum(differences) / len(differences),
                "improved_pairs": improved,
                "worsened_pairs": worsened,
                "unchanged_success_pairs": unchanged_success,
                "unchanged_failure_pairs": unchanged_failure,
                "discordant_pairs": improved + worsened,
                "exact_two_sided_sign_p": exact_two_sided_sign_p(
                    improved, worsened
                ),
                "task_model_pair_bootstrap_95_ci": bootstrap_pair_ci(
                    differences, bootstrap_replicates, seed
                ),
                "model_cluster_bootstrap_95_ci": bootstrap_model_cluster_ci(
                    labeled_differences, bootstrap_replicates, seed + 1
                ),
            }
        )

    pair_outcome_projection = [
        {
            "pair_key_sha256": sha256_json(pair_key),
            "model": pair_key[1],
            "task_type": pair_rows[BASELINE]["task_type"],
            "outcomes": {
                condition: bool(pair_rows[condition]["success"])
                for condition in CONDITIONS
            },
        }
        for pair_key, pair_rows in sorted(pair_maps.items())
    ]
    stable_pairs = sum(count for pattern, count in outcome_patterns.items() if len(set(pattern)) == 1)

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "source_file": SOURCE_FILE,
            "source_sha256": source_sha256,
            "source_size_bytes": source_size_bytes,
            "dataset_card_sha256": DATASET_CARD_SHA256,
            "declared_license": DECLARED_LICENSE,
            "adapter": ADAPTER,
            "raw_data_committed": False,
        },
        "integrity": {
            "row_count": len(rows),
            "column_count": len(rows[0]),
            "columns": list(rows[0].keys()),
            "null_counts": dict(sorted(null_counts.items())),
            "source_record_set_sha256": sha256_json(sorted(source_record_hashes)),
            "trajectory_parse_failures": 0,
            "empty_trajectories": sum(not steps for _, steps in parsed),
            "trajectory_step_count_mismatches": trajectory_step_mismatches,
            "success_final_score_mismatches": sum(
                bool(row["success"]) != (float(row["final_score"]) == 1.0)
                for row in rows
            ),
            "success_done_mismatches": sum(
                bool(row["success"]) != bool(row["done"]) for row in rows
            ),
        },
        "paired_structure": {
            "pair_key": ["task_id", "model"],
            "pair_count": len(pairs),
            "conditions": list(CONDITIONS),
            "rows_per_pair": dict(
                sorted(Counter(len(value) for value in pairs.values()).items())
            ),
            "duplicate_condition_rows": duplicate_condition_rows,
            "incomplete_pairs": len(incomplete_pairs),
            "pair_invariant_violations": dict(sorted(invariant_violations.items())),
            "unique_task_ids": len({str(row["task_id"]) for row in rows}),
            "unique_models": len({str(row["model"]) for row in rows}),
            "tasks_observed_under_multiple_models": sum(
                len({str(row["model"]) for row in rows if row["task_id"] == task_id})
                > 1
                for task_id in {str(row["task_id"]) for row in rows}
            ),
            "pair_outcome_projection_sha256": sha256_json(pair_outcome_projection),
        },
        "outcomes": {
            "by_condition": condition_summaries,
            "by_model_and_condition": grouped_rates(rows, "model"),
            "by_task_type_and_condition": grouped_rates(rows, "task_type"),
            "task_pair_outcome_patterns": dict(sorted(outcome_patterns.items())),
            "pairs_with_same_outcome_in_all_arms": stable_pairs,
            "pairs_with_any_outcome_change": len(pairs) - stable_pairs,
        },
        "paired_effects": paired_effects,
        "trajectory_stability": {
            "unique_trajectory_count_per_pair": dict(
                sorted(unique_trajectory_counts.items())
            ),
            "trajectories_identical_to_baseline_by_condition": dict(
                sorted(identical_to_baseline.items())
            ),
        },
        "statistics": {
            "bootstrap_replicates": bootstrap_replicates,
            "bootstrap_seed": bootstrap_seed,
            "estimand": (
                "within-(task_id, model) intention-to-treat success-rate "
                "difference versus no_retrieval"
            ),
            "multiplicity_note": (
                "five treatment-versus-baseline contrasts are descriptive; no "
                "multiplicity-adjusted confirmatory claim was preregistered"
            ),
        },
        "attribution_assessment": {
            "observed_within_pair_condition_contrast_estimable": True,
            "causal_condition_effect_identified": False,
            "memory_content_effect_estimable": False,
            "reason": (
                "rows identify assigned retrieval depth but omit retrieved item IDs, "
                "content, scores, memory lineage, injected prompt, environment seed, "
                "and replay snapshot; observed differences cannot be assigned to a "
                "specific memory or separated from retrieval/prompt/randomness effects"
            ),
            "additional_design_limits": [
                "each task is observed under exactly one model, so task and model effects are not separately identified",
                "models have only 10 or 11 task blocks each",
                "five correlated treatment contrasts create multiplicity",
                "a deterministic split seed is documented, but an episode execution seed is not",
                "trajectory step observation/action ordering is not defined",
            ],
        },
    }


def load_parquet(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        import pyarrow
        import pyarrow.parquet as parquet
    except ImportError as error:
        raise RuntimeError(
            "pyarrow is required only to read the source Parquet file"
        ) from error
    parquet_file = parquet.ParquetFile(path)
    table = parquet_file.read()
    schema = [
        {"name": field.name, "type": str(field.type)}
        for field in table.schema
    ]
    return table.to_pylist(), {
        "parquet_format_version": parquet_file.metadata.format_version,
        "parquet_created_by": parquet_file.metadata.created_by,
        "parquet_row_groups": parquet_file.metadata.num_row_groups,
        "parquet_schema": schema,
        "pyarrow_version": pyarrow.__version__,
    }


def run(input_path: Path, output_path: Path, replicates: int, seed: int) -> None:
    observed_size = input_path.stat().st_size
    observed_sha256 = sha256_file(input_path)
    if observed_size != SOURCE_SIZE_BYTES:
        raise ValueError(
            "source size mismatch: %d != %d" % (observed_size, SOURCE_SIZE_BYTES)
        )
    if observed_sha256 != SOURCE_SHA256:
        raise ValueError(
            "source SHA-256 mismatch: %s != %s"
            % (observed_sha256, SOURCE_SHA256)
        )
    rows, parquet_metadata = load_parquet(input_path)
    result = analyze_rows(
        rows,
        source_sha256=observed_sha256,
        source_size_bytes=observed_size,
        bootstrap_replicates=replicates,
        bootstrap_seed=seed,
    )
    result["source"].update(parquet_metadata)
    result["statistics"]["analysis_code_sha256"] = sha256_file(Path(__file__))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20_260_730)
    args = parser.parse_args()
    run(
        input_path=args.input,
        output_path=args.output,
        replicates=args.bootstrap_replicates,
        seed=args.bootstrap_seed,
    )


if __name__ == "__main__":
    main()
