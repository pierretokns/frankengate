#!/usr/bin/env python3
"""Compute paired, content-free statistics for the skill intervention receipts.

This is an analysis-only layer over committed aggregate receipts.  It never
opens raw prompts, SQL, model messages, or source traces.  Protocol compliance
and semantic correctness are reported separately because a terminal tool call
is not evidence that the submitted answer was correct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import random
import statistics
from typing import Any, Iterable


ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_INPUTS = (
    "experiments/results/natural-trace-skill-protocol-intervention-2026-07-30.json",
    "experiments/results/natural-trace-skill-protocol-intervention-qwen3-4b-2026-07-31.json",
    "experiments/results/model-harness-transfer-llama-openai-vs-ollama-2026-07-31.json",
    "experiments/results/defog-sql-factorial-fold0-terminal-only-p0-2026-07-30.json",
    "experiments/results/defog-car-fallback-llama-2026-07-31.json",
    "experiments/results/defog-broker-fallback-openai-llama-2026-07-31.json",
    "experiments/results/defog-trace-mined-skill-broker-fold0-llama-2026-07-31.json",
    "experiments/results/defog-trace-mined-skill-heldout-car-2026-08-02.json",
    "experiments/results/defog-trace-mined-skill-heldout-car-schema-injected-2026-08-02.json",
    "experiments/results/defog-trace-mined-skill-heldout-car-repaired-2026-08-02.json",
    "experiments/results/defog-trace-mined-skill-heldout-car-schema-first-2026-08-02.json",
    "experiments/results/defog-trace-mined-skill-family-broker-schema-injected-2026-08-02.json",
)


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _task_key(row: dict[str, Any]) -> str:
    for key in ("fixture_id_sha256", "task_id_sha256"):
        if row.get(key):
            return str(row[key])
    raise ValueError("receipt has no stable task key")


def _rows(value: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(value.get("episode_receipts"), list):
        return [row for row in value["episode_receipts"] if isinstance(row, dict)]
    if isinstance(value.get("task_runs"), list):
        return [row for row in value["task_runs"] if isinstance(row, dict)]
    if isinstance(value.get("task_receipts"), list):
        return [row for row in value["task_receipts"] if isinstance(row, dict)]
    return []


def _endpoint(row: dict[str, Any], metric: str) -> bool:
    if metric == "semantic_correct":
        return bool(row.get("semantic_correct", False))
    if metric == "terminal_match":
        return bool(row.get("expected_terminal_match", False))
    raise ValueError(f"unknown endpoint: {metric}")


def _arm_name(row: dict[str, Any]) -> str:
    return str(row.get("variant") or row.get("arm") or "")


def _paired_rows(value: dict[str, Any], baseline: str, candidate: str) -> list[tuple[bool, bool]]:
    rows = _rows(value)
    base = {_task_key(row): row for row in rows if _arm_name(row) == baseline}
    cand = {_task_key(row): row for row in rows if _arm_name(row) == candidate}
    keys = sorted(set(base) & set(cand))
    if not keys:
        return []
    return [(base[key], cand[key]) for key in keys]


def paired_effect(pairs: Iterable[tuple[bool, bool]]) -> dict[str, Any]:
    values = list(pairs)
    wins = sum(candidate and not baseline for baseline, candidate in values)
    losses = sum(baseline and not candidate for baseline, candidate in values)
    ties = len(values) - wins - losses
    return {
        "tasks": len(values),
        "baseline_successes": sum(baseline for baseline, _ in values),
        "candidate_successes": sum(candidate for _, candidate in values),
        "candidate_wins": wins,
        "candidate_losses": losses,
        "ties": ties,
        "risk_difference": (sum(candidate for _, candidate in values) / len(values)
            - sum(baseline for baseline, _ in values) / len(values)) if values else None,
        "mcnemar_exact_two_sided_p": exact_mcnemar_p(wins, losses),
        "bootstrap_95_percent_ci": bootstrap_risk_difference(values),
    }


def exact_mcnemar_p(wins: int, losses: int) -> float | None:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(0, min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def bootstrap_risk_difference(
    pairs: list[tuple[bool, bool]], *, draws: int = 10_000, seed: int = 20260802
) -> list[float] | None:
    if not pairs:
        return None
    rng = random.Random(seed)
    differences: list[float] = []
    for _ in range(draws):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        differences.append(
            statistics.fmean(float(candidate) - float(baseline) for baseline, candidate in sample)
        )
    differences.sort()
    return [differences[int(0.025 * (len(differences) - 1))], differences[int(0.975 * (len(differences) - 1))]]


def analyze(path: pathlib.Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = _rows(value)
    if not rows:
        return []
    names = {_arm_name(row) for row in rows}
    if "no_skill" not in names:
        return []
    candidate = "trace_mined_terminal_discipline" if "trace_mined_terminal_discipline" in names else None
    semantic_available = any("semantic_correct" in row for row in rows)
    analyses: list[dict[str, Any]] = []
    endpoints = [("terminal_match", "protocol")]
    if semantic_available:
        endpoints.append(("semantic_correct", "semantic"))
    for metric, label in endpoints:
        if candidate:
            pairs = _paired_rows(value, "no_skill", candidate)
            analyses.append({
                "receipt": str(path.relative_to(ROOT)),
                "candidate_class": "trace_mined_candidate",
                "baseline": "no_skill",
                "candidate": candidate,
                "endpoint": label,
                "effect": paired_effect(
                    [(_endpoint(base, metric), _endpoint(cand, metric)) for base, cand in pairs]
                ),
            })
        if "expert_schema_navigation_seed" in names:
            pairs = _paired_rows(value, "no_skill", "expert_schema_navigation_seed")
            analyses.append({
                "receipt": str(path.relative_to(ROOT)),
                "candidate_class": "expert_seed_not_trace_mined",
                "baseline": "no_skill",
                "candidate": "expert_schema_navigation_seed",
                "endpoint": label,
                "effect": paired_effect(
                    [(_endpoint(base, metric), _endpoint(cand, metric)) for base, cand in pairs]
                ),
            })
    return analyses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    parser.add_argument("inputs", nargs="*", type=pathlib.Path)
    args = parser.parse_args()
    paths = args.inputs or [ROOT / path for path in DEFAULT_INPUTS]
    studies: list[dict[str, Any]] = []
    missing: list[str] = []
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        if not resolved.exists():
            missing.append(str(resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved))
            continue
        studies.extend(analyze(resolved))
    result = {
        "schema_version": "frankengate-skill-optimization-meta-analysis-v1",
        "analysis_revision": "paired-receipts-r1",
        "inputs": [str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path) for path in paths],
        "missing_inputs": missing,
        "study_count": len(studies),
        "studies": studies,
        "strata": {
            "trace_mined_candidate": {
                "semantic_studies": sum(s["candidate_class"] == "trace_mined_candidate" and s["endpoint"] == "semantic" for s in studies),
                "protocol_studies": sum(s["candidate_class"] == "trace_mined_candidate" and s["endpoint"] == "protocol" for s in studies),
            },
            "expert_seed_not_trace_mined": {
                "semantic_studies": sum(s["candidate_class"] == "expert_seed_not_trace_mined" and s["endpoint"] == "semantic" for s in studies),
                "protocol_studies": sum(s["candidate_class"] == "expert_seed_not_trace_mined" and s["endpoint"] == "protocol" for s in studies),
            },
        },
        "claim_boundary": {
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Paired receipts are small, heterogeneous, and include protocol-null arms; semantic and protocol endpoints are not pooled.",
            "raw_data_committed": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Skill-optimization paired meta-analysis",
        "",
        f"Analyzed `{len(studies)}` endpoint/study strata from committed aggregate receipts; raw model and trace content was not read.",
        "",
        "| receipt | class | endpoint | tasks | baseline | candidate | risk difference | exact McNemar p | bootstrap 95% CI |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for study in studies:
        e = study["effect"]
        lines.append(
            f"| `{study['receipt']}` | {study['candidate_class']} | {study['endpoint']} | {e['tasks']} | {e['baseline_successes']} | {e['candidate_successes']} | {e['risk_difference'] if e['risk_difference'] is not None else 'n/a'} | {e['mcnemar_exact_two_sided_p']} | {e['bootstrap_95_percent_ci']} |"
        )
    lines += [
        "",
        "The analysis does not pool protocol compliance with semantic correctness and does not authorize skill promotion. The schema-injected car arm has independent security and outcome verification; the family-disjoint broker arm is also independently verified and ties the trace-mined candidate with no-skill at 0/6. The causal claim remains unconfirmed until a larger family-disjoint, held-out replay with sealed outcomes and independent verification.",
    ]
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "study_count": len(studies), "missing_inputs": missing}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
