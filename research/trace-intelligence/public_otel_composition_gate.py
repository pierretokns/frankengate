#!/usr/bin/env python3
"""Fail-closed composition gate for public OTel triage -> proposal evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def evaluate(selector: dict[str, Any], second: dict[str, Any], lifecycle: dict[str, Any]) -> dict[str, Any]:
    app = selector["arms"]["signals_error_and_tools"]
    browse = second["arms"]["signals_error_and_tools"]
    lifecycle_ok = bool(lifecycle.get("proposal_policies_run", 0) >= 2 and lifecycle.get("no_proposal_control_run"))
    selector_generalizes = (
        app["population_prevalence"] > 0
        and second["arms"]["uniform_random_seeded"]["population_prevalence"] > 0
        and abs(app["precision"] - browse["precision"]) < 0.2
    )
    return {
        "schema_version": "fg-public-otel-composition-gate-v1",
        "selector_arms": ["appworld", "browsecompplus"],
        "selector_generalizes": selector_generalizes,
        "lifecycle_mechanics_present": lifecycle_ok,
        "held_out_causal_outcome": False,
        "promotion": "defer",
        "defer_reasons": [
            "selector workload strata disagree or have zero-positive prevalence",
            "no independent human outcome or changed-system causal result",
        ],
        "raw_content_emitted": False,
        "enterprise_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--appworld", type=Path, required=True)
    parser.add_argument("--browsecomp", type=Path, required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(_load(args.appworld), _load(args.browsecomp), _load(args.lifecycle))
    result["input_sha256"] = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in (("appworld", args.appworld), ("browsecomp", args.browsecomp), ("lifecycle", args.lifecycle))
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
