#!/usr/bin/env python3
"""Synthesize independent skill/artifact replay receipts without pooling labels.

The inputs intentionally remain separate datasets and protocols.  This script
only extracts their aggregate outcomes, hashes the source receipts, and emits
an adoption-oriented comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-skill-replay-evidence-synthesis-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(skilllearn: Path, bird: Path, changed: Path, alfworld: Path, output: Path) -> dict[str, Any]:
    sources = {"skilllearn_changed_data": load(skilllearn), "bird_family_disjoint": load(bird), "changed_system_subplan": load(changed), "alfworld_skillopt": load(alfworld)}
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_receipts": {name: {"path": str(path), "sha256": digest(payload), "schema_version": payload.get("schema_version", payload.get("schema"))} for name, path, payload in (("skilllearn_changed_data", skilllearn, sources["skilllearn_changed_data"]), ("bird_family_disjoint", bird, sources["bird_family_disjoint"]), ("changed_system_subplan", changed, sources["changed_system_subplan"]), ("alfworld_skillopt", alfworld, sources["alfworld_skillopt"]))},
        "comparisons": {
            "skilllearn_changed_data": {
                "dataset": "one public changed-data task, two stochastic runs",
                "null_recall": sources["skilllearn_changed_data"]["aggregate_q1"]["none"]["recall"],
                "reviewed_recall": sources["skilllearn_changed_data"]["aggregate_q1"]["human_authored"]["recall"],
                "composite_recall": sources["skilllearn_changed_data"]["aggregate_q1"]["composite-human-plus-b1"]["recall"],
                "reviewed_precision": sources["skilllearn_changed_data"]["aggregate_q1"]["human_authored"]["precision"],
                "composite_precision": sources["skilllearn_changed_data"]["aggregate_q1"]["composite-human-plus-b1"]["precision"],
                "claim": "Reviewed human guidance was stable on this mutation; generated composition added no demonstrated value.",
            },
            "bird_family_disjoint": {
                "dataset": "40 family-disjoint BIRD tasks, two replays",
                "no_skill_exact": sources["bird_family_disjoint"]["arms"]["no_skill"]["exact"],
                "placebo_exact": sources["bird_family_disjoint"]["arms"]["formatting_placebo"]["exact"],
                "composable_exact": sources["bird_family_disjoint"]["arms"]["composable_subplan_library"]["exact"],
                "unique_tasks": sources["bird_family_disjoint"].get("unique_task_count"),
                "stable_library_wins": sources["bird_family_disjoint"].get("stable_comparisons", {}).get("no_skill", {}).get("stable_library_wins"),
                "stable_library_losses": sources["bird_family_disjoint"].get("stable_comparisons", {}).get("no_skill", {}).get("stable_library_losses"),
                "claim": "Validated subplans show one stable win and no stable losses, but the aggregate is underpowered and low-headroom.",
            },
            "changed_system_subplan": {
                "dataset": "five deterministic changed-system fixtures",
                "name_only_unsafe_accepts": sources["changed_system_subplan"]["aggregate"]["name_only_subplan"]["unsafe_accept"],
                "semantic_id_unsafe_accepts": sources["changed_system_subplan"]["aggregate"]["semantic_subplan"]["unsafe_accept"],
                "name_only_correct": sources["changed_system_subplan"]["aggregate"]["name_only_subplan"]["semantic_correct"],
                "semantic_id_correct": sources["changed_system_subplan"]["aggregate"]["semantic_subplan"]["semantic_correct"],
                "claim": "Typed semantic admission prevents the two unsafe name-only accepts in this controlled replay.",
            },
            "alfworld_skillopt": {
                "dataset": "two unseen ALFWorld tasks, Codex/Luna",
                "no_skill_wins": sources["alfworld_skillopt"]["summary"]["no_skill"]["wins"],
                "candidate_wins": sources["alfworld_skillopt"]["summary"]["skillopt_candidate"]["wins"],
                "placebo_wins": sources["alfworld_skillopt"]["summary"]["formatting_placebo"]["wins"],
                "claim": "The real SkillOpt candidate did not improve this bounded task outcome; this is a negative replication, not a disproof of SkillOpt generally.",
            },
        },
        "adoption": {
            "promote_now": ["typed semantic-ID admission", "reviewed human guidance as a candidate arm", "validated subplans behind replay and scope gates"],
            "do_not_promote_now": ["generic trace-mined prose", "automatic skill composition", "name-only artifact reuse", "raw-log-derived skill or embedding updates"],
            "next_causal_gate": "A powered, task-disjoint changed-system cohort with no-skill, placebo, reviewed, mined, generated, and composed arms plus independent outcomes.",
        },
        "claim_boundary": {
            "datasets_pooled": False,
            "causal_enterprise_skill_benefit": False,
            "automatic_promotion_authorized": False,
            "reason": "These are separate proxy protocols; synthesis is a decision map, not a pooled effect estimate.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"comparisons": result["comparisons"], "adoption": result["adoption"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skilllearn", type=Path, required=True)
    parser.add_argument("--bird", type=Path, required=True)
    parser.add_argument("--changed", type=Path, required=True)
    parser.add_argument("--alfworld", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.skilllearn, args.bird, args.changed, args.alfworld, args.output)
