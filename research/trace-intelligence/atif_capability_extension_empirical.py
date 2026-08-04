#!/usr/bin/env python3
"""Aggregate-only empirical run of the Frankengate ATIF capability profile."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from atif_capability_extension import (
    atif_capability_to_canonical,
    canonical_to_atif_capability,
)
from atif_rl_roundtrip import (
    CAPABILITIES,
    capability_facts,
    load_matm_alfworld,
    load_wisp_tool_rich,
)


RESULT_SCHEMA_VERSION = "atif-capability-extension-empirical-result-v1"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _empty_family() -> dict[str, Any]:
    return {
        "trajectory_count": 0,
        "source_event_count": 0,
        "round_trip_pass_count": 0,
        "round_trip_failure_count": 0,
        "source_fact_count": collections.Counter(),
        "retained_fact_count": collections.Counter(),
        "omitted_field_count": 0,
        "retained_root_field_count": 0,
        "retained_event_field_count": 0,
    }


def _measure(trajectories: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    aggregate = _empty_family()
    for trajectory in trajectories:
        aggregate["trajectory_count"] += 1
        aggregate["source_event_count"] += len(trajectory.get("events", []))
        source_facts = capability_facts(trajectory)
        for capability in CAPABILITIES:
            aggregate["source_fact_count"][capability] += len(source_facts[capability])
        try:
            atif, export_receipt = canonical_to_atif_capability(dict(trajectory))
            restored, import_receipt = atif_capability_to_canonical(atif)
            restored_facts = capability_facts(restored)
            aggregate["round_trip_pass_count"] += 1
            aggregate["omitted_field_count"] += int(export_receipt["omitted_field_count"])
            extension = atif["extra"]["frankengate"]["capability_extension"]
            aggregate["retained_root_field_count"] += len(extension["root_fields"])
            aggregate["retained_event_field_count"] += sum(
                len(item["fields"]) for item in extension["event_records"]
            )
            if import_receipt.get("silently_dropped_event_count") != 0:
                raise AssertionError("profile import reported a silent event drop")
            for capability in CAPABILITIES:
                aggregate["retained_fact_count"][capability] += len(
                    source_facts[capability] & restored_facts[capability]
                )
        except Exception:
            # The aggregate records a failure count, never the trace identity or
            # exception text (which can contain user paths or provider data).
            aggregate["round_trip_failure_count"] += 1

    source_counts = aggregate.pop("source_fact_count")
    retained_counts = aggregate.pop("retained_fact_count")
    capabilities: dict[str, Any] = {}
    for capability in CAPABILITIES:
        source_count = source_counts[capability]
        retained_count = retained_counts[capability]
        capabilities[capability] = {
            "source_fact_count": source_count,
            "retained_fact_count": retained_count,
            "retention": round(retained_count / source_count, 6) if source_count else None,
            "source_status": "observed" if source_count else "not_observed",
        }
    aggregate["capabilities"] = capabilities
    aggregate["overall_retention"] = (
        round(
            sum(item["retained_fact_count"] for item in capabilities.values())
            / sum(item["source_fact_count"] for item in capabilities.values()),
            6,
        )
        if sum(item["source_fact_count"] for item in capabilities.values())
        else None
    )
    return aggregate


def run_experiment(
    *,
    wisp_cache: Path,
    wisp_manifest: Path,
    matm_parquet: Path,
    matm_manifest: Path,
) -> dict[str, Any]:
    wisp, wisp_pin = load_wisp_tool_rich(wisp_cache, wisp_manifest)
    matm, matm_pin = load_matm_alfworld(matm_parquet, matm_manifest)
    families = {
        "wisp_claude_code_tool_rich": {
            "source_pin": wisp_pin,
            "measurement": _measure(wisp),
        },
        "matm_alfworld_rl_environment": {
            "source_pin": matm_pin,
            "measurement": _measure(matm),
        },
    }
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "experiment": {
            "name": "ATIF v1.7 Frankengate capability extension empirical round trip",
            "unit": "profile-retained structural fact observed by the canonical adapter",
            "aggregate_only": True,
            "raw_content_or_trace_identifiers_emitted": False,
            "portable_atif_claim": "none; extension requires a Frankengate-aware reader",
        },
        "profile": {
            "schema_version": "frankengate-atif-capability-extension-v2",
            "hash_algorithm": "sha256",
            "canonicalization": "json-sort-keys-separators-utf8",
            "reference_policy": "governed-reference-required;hash-only-is-not-replayable",
            "preserves": [
                "authorization and authorization epoch facts",
                "environment reset/termination facts and replay references",
                "reward/evaluation attribution",
                "memory reference, revision, scope, epoch, and lineage facts",
                "explicit reset/termination semantics and reader compatibility",
                "event identity, causal edges, branches, retries, and provenance",
            ],
            "omits": [
                "prompt and tool payload content",
                "tool arguments",
            "opaque environment state deltas and memory snapshots",
            "replay or evaluation access without a governed reference",
            ],
        },
        "families": families,
        "claim_limits": [
            "A profile-aware round trip is not a portable ATIF guarantee.",
            "Retention is exact structural fact equality, not task utility or replay equivalence.",
            "MATM does not contain environment seed/replay snapshots, so no format can create that evidence.",
            "Wisp and MATM are not enterprise traces; consented multi-user validation remains open.",
        ],
    }
    result["result_sha256"] = _digest(result)
    return result


def render_summary(result: Mapping[str, Any]) -> str:
    lines = [
        "# Frankengate ATIF capability-extension empirical run",
        "",
        "The extension was run against the pinned Wisp coding sessions and MATM ALFWorld trajectories. It retains structural control facts in a namespaced profile and explicitly omits payload/state content.",
        "",
        "| Family | Trajectories | Round trips | Failures | Overall structural retention | Omitted fields |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, family in result["families"].items():
        measurement = family["measurement"]
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    str(measurement["trajectory_count"]),
                    str(measurement["round_trip_pass_count"]),
                    str(measurement["round_trip_failure_count"]),
                    "not observed" if measurement["overall_retention"] is None else f"{measurement['overall_retention']:.1%}",
                    str(measurement["omitted_field_count"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
        "The extension repairs the schema boundary only for consumers that implement the profile. Generic ATIF readers still see the portable subset and cannot use the extension-only facts.",
            "",
            "No raw prompts, tool arguments, state snapshots, identifiers, or exception text are emitted.",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in result["claim_limits"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wisp-cache", type=Path, required=True)
    parser.add_argument("--wisp-manifest", type=Path, required=True)
    parser.add_argument("--matm-parquet", type=Path, required=True)
    parser.add_argument("--matm-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        wisp_cache=args.wisp_cache,
        wisp_manifest=args.wisp_manifest,
        matm_parquet=args.matm_parquet,
        matm_manifest=args.matm_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.summary.write_text(render_summary(result), encoding="utf-8")
    print(json.dumps({"status": "ok", "result_sha256": result["result_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
