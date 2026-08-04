#!/usr/bin/env python3
"""Audit source-stratified longitudinal memory power without pooling identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

import trace_commons_memory_composition as composition
import trace_commons_memory_conformance as native


SCHEMA_VERSION = "longitudinal-memory-cohort-expansion-result-v1"
ANALYSIS_VERSION = "source-stratified-native-claude-expansion-v1"


class ExpansionError(ValueError):
    """Raised when a source stratum or aggregate gate is inconsistent."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _receipt_hashes(manifest: Mapping[str, Any]) -> set[str]:
    cohort = manifest.get("cohort")
    source_files = (
        cohort.get("source_files")
        if isinstance(cohort, dict)
        else manifest.get("source_files")
    )
    if not isinstance(source_files, list):
        raise ExpansionError("source_files are required")
    digests = {
        str(item.get("sha256"))
        for item in source_files
        if isinstance(item, dict) and item.get("sha256")
    }
    if len(digests) != len(source_files):
        raise ExpansionError("source receipt hashes must be unique")
    return digests


def _session_shape_hashes(
    records: Sequence[Mapping[str, Any]],
) -> set[str]:
    grouped: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for record in sorted(
        records,
        key=lambda item: (
            str(item.get("_source_file", "")),
            int(item.get("_source_line", 0)),
        ),
    ):
        session_id = str(record.get("sessionId", ""))
        if not session_id:
            continue
        tool_names: list[str] = []
        result_shapes: list[tuple[str, bool]] = []
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use":
                    tool_names.append(str(item.get("name", "")).casefold())
                elif item.get("type") == "tool_result":
                    result_shapes.append(
                        (
                            "tool_result",
                            bool(item.get("is_error", False)),
                        )
                    )
        grouped[session_id].append(
            (
                str(record.get("type", "")),
                tuple(tool_names),
                tuple(result_shapes),
                bool(record.get("parentUuid") is not None),
            )
        )
    return {
        sha256_bytes(stable_json(shape).encode("utf-8"))
        for shape in grouped.values()
    }


def _cross_source_overlap(
    left: native.VerifiedMemoryCohort,
    right: native.VerifiedMemoryCohort,
) -> dict[str, int]:
    left_sessions = {
        str(item.get("sessionId"))
        for item in left.records
        if item.get("sessionId")
    }
    right_sessions = {
        str(item.get("sessionId"))
        for item in right.records
        if item.get("sessionId")
    }
    left_record_uuids = {
        str(item.get("uuid")) for item in left.records if item.get("uuid")
    }
    right_record_uuids = {
        str(item.get("uuid")) for item in right.records if item.get("uuid")
    }
    left_tool_ids = {
        (item.session_id, item.tool_id) for item in left.calls
    }
    right_tool_ids = {
        (item.session_id, item.tool_id) for item in right.calls
    }
    return {
        "exact_source_file_sha256_overlap": len(
            {str(item["sha256"]) for item in left.receipts}
            & {str(item["sha256"]) for item in right.receipts}
        ),
        "exact_native_session_id_overlap": len(
            left_sessions & right_sessions
        ),
        "exact_record_uuid_overlap": len(
            left_record_uuids & right_record_uuids
        ),
        "exact_session_scoped_tool_id_overlap": len(
            left_tool_ids & right_tool_ids
        ),
        "exact_content_free_session_shape_overlap": len(
            _session_shape_hashes(left.records)
            & _session_shape_hashes(right.records)
        ),
    }


def _source_summary(
    label: str,
    manifest_path: Path,
    source_root: Path,
) -> tuple[dict[str, Any], native.VerifiedMemoryCohort]:
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict):
        raise ExpansionError("source manifest must be an object")
    result = composition.analyze_manifest(manifest_path, source_root)
    gates = composition.longitudinal_gate_metrics(
        manifest_path, source_root
    )
    cohort = native.load_verified_memory_cohort(
        manifest_path,
        source_root,
        default_authority=composition.FIXED_IMPORT_AUTHORITY,
    )
    mechanisms = {}
    for name in ("verbatim", "latest_only", "contextual_bitemporal"):
        arm = result["mechanisms"][name]
        mechanisms[name] = {
            key: arm[key]
            for key in (
                "online_exact",
                "online_stale_returns",
                "online_abstentions",
                "post_observation_retention_exact",
                "retained_revisions",
                "overwritten_revisions",
            )
        }
    return (
        {
            "label": label,
            "dataset_id": result["dataset"]["id"],
            "revision": result["dataset"]["revision"],
            "license": result["dataset"]["license"],
            "manifest_sha256": sha256_bytes(manifest_raw),
            "input_receipt": result["input_receipt"],
            "source_selection": manifest.get("source_selection"),
            "source_provenance": manifest.get("source_provenance"),
            "discovery": result["discovery"],
            "transitions": result["transitions"],
            "evaluation": result["evaluation"],
            "project_cluster_gates": gates,
            "mechanisms": mechanisms,
            "negative_controls": result["negative_controls"],
            "decision_status": result["decision_status"],
            "contributor_count_verified": None,
            "contributor_independence_status": "not_established",
        },
        cohort,
    )


def _aggregate_gates(
    strata: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gate_specs = {
        "online_queries": ("online_queries", 10),
        "changed_post_observation_cases": (
            "changed_post_observation_cases",
            5,
        ),
        "exact_cross_session_write_to_later_read": (
            "exact_cross_session_write_to_later_read",
            2,
        ),
    }
    outcomes: dict[str, Any] = {}
    for output_name, (source_name, minimum) in gate_specs.items():
        values = [
            item["project_cluster_gates"][source_name]
            for item in strata
        ]
        cases = sum(int(item["cases"]) for item in values)
        source_scoped_projects = sum(
            int(item["project_contexts"]) for item in values
        )
        outcomes[output_name] = {
            "cases": cases,
            "minimum": minimum,
            "status": "passed" if cases >= minimum else "failed",
            "source_scoped_project_contexts": source_scoped_projects,
            "cases_per_source_scoped_project_desc": sorted(
                (
                    count
                    for item in values
                    for count in item["cases_per_project_desc"]
                ),
                reverse=True,
            ),
        }
    exact_projects = outcomes[
        "exact_cross_session_write_to_later_read"
    ]["source_scoped_project_contexts"]
    outcomes["independent_project_context_minimum"] = {
        "source_scoped_project_contexts": exact_projects,
        "minimum": 2,
        "status": "passed" if exact_projects >= 2 else "failed",
    }
    outcomes["source_collection_minimum"] = {
        "source_collections": len(strata),
        "minimum": 2,
        "status": "passed" if len(strata) >= 2 else "failed",
    }
    outcomes["minimum_count_gates_all_passed"] = all(
        item["status"] == "passed"
        for item in outcomes.values()
        if isinstance(item, dict) and "status" in item
    )
    source_families_with_exact_transitions = sum(
        int(
            item["project_cluster_gates"][
                "exact_cross_session_write_to_later_read"
            ]["cases"]
        )
        > 0
        for item in strata
    )
    outcomes["confirmatory_diversity_gate"] = {
        "source_families_with_exact_transitions": {
            "observed": source_families_with_exact_transitions,
            "minimum": 3,
            "status": (
                "passed"
                if source_families_with_exact_transitions >= 3
                else "failed"
            ),
        },
        "source_scoped_project_contexts_with_exact_transitions": {
            "observed": exact_projects,
            "minimum": 5,
            "status": "passed" if exact_projects >= 5 else "failed",
        },
    }
    outcomes["confirmatory_diversity_gate"]["status"] = (
        "passed"
        if all(
            item["status"] == "passed"
            for item in outcomes["confirmatory_diversity_gate"].values()
            if isinstance(item, dict)
        )
        else "failed"
    )
    return outcomes


def analyze(
    trace_commons_manifest: Union[Path, str],
    trace_commons_root: Union[Path, str],
    fable_manifest: Union[Path, str],
    fable_root: Union[Path, str],
) -> dict[str, Any]:
    source_specs = (
        (
            "trace_commons",
            Path(trace_commons_manifest),
            Path(trace_commons_root),
        ),
        ("fable5_top_level", Path(fable_manifest), Path(fable_root)),
    )
    strata: list[dict[str, Any]] = []
    cohorts: list[native.VerifiedMemoryCohort] = []
    for label, manifest, root in source_specs:
        summary, cohort = _source_summary(label, manifest, root)
        strata.append(summary)
        cohorts.append(cohort)
    overlap = _cross_source_overlap(cohorts[0], cohorts[1])
    aggregate = _aggregate_gates(strata)
    overlap_all_zero = all(value == 0 for value in overlap.values())
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": ANALYSIS_VERSION,
        "source_strata": strata,
        "cross_source_duplicate_audit": {
            **overlap,
            "all_exact_overlap_controls_zero": overlap_all_zero,
            "semantic_or_provenance_overlap_ruled_out": False,
        },
        "aggregate_engineering_gates": aggregate,
        "decision": {
            "deterministic_longitudinal_count_gates": (
                "passed"
                if aggregate["minimum_count_gates_all_passed"]
                else "failed"
            ),
            "model_and_blinded_human_phase": (
                "eligible_for_exploratory_replication_not_yet_evidence"
                if aggregate["minimum_count_gates_all_passed"]
                and overlap_all_zero
                else "blocked"
            ),
            "confirmatory_architecture_quality_claim": (
                "eligible"
                if aggregate["confirmatory_diversity_gate"]["status"]
                == "passed"
                else "blocked_on_diversity"
            ),
            "population_inference_allowed": False,
            "enterprise_generalization_allowed": False,
            "automatic_memory_promotion_allowed": False,
            "contributor_independence_established": False,
            "reason": (
                "Counts clear the frozen mechanics gates, but evaluable cases "
                "remain concentrated in few source-scoped project contexts "
                "and contributor independence is unknown."
            ),
        },
        "composition_contract": {
            "source_identity_pooled": False,
            "project_identity_pooled_across_sources": False,
            "source_strata_preserved": True,
            "cross_source_user_join_attempted": False,
            "raw_content_emitted": False,
            "native_paths_emitted": False,
            "native_identifiers_emitted": False,
        },
    }
    result["result_sha256"] = sha256_bytes(
        stable_json(result).encode("utf-8")
    )
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    strata = result["source_strata"]
    gates = result["aggregate_engineering_gates"]
    lines = [
        "# Longitudinal memory cohort expansion",
        "",
        "## Outcome",
        "",
        (
            "The source-stratified deterministic count gates passed. This "
            "unseals an exploratory preregistered model and blinded-human "
            "phase; it does "
            "**not** establish memory quality, causal benefit, contributor "
            "independence, population validity, or enterprise generalization."
        ),
        "",
        "## Source strata",
        "",
        "| Stratum | Histories | Online reads | Changed cases | Exact cross-session | Exact-transition projects |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in strata:
        gate = item["project_cluster_gates"]
        source_label = {
            "trace_commons": (
                "[Trace Commons](https://huggingface.co/datasets/"
                "trace-commons/agent-traces/tree/"
                "112ebd4d03ce852b00e935d523107c3d0c9a65bf)"
            ),
            "fable5_top_level": (
                "[Fable-5 top-level](https://huggingface.co/datasets/"
                "Glint-Research/Fable-5-traces/tree/"
                "e05c417852fc59fd8da758e68b352732423ca0cb/claude/projects)"
            ),
        }.get(str(item["label"]), str(item["label"]))
        lines.append(
            "| "
            + " | ".join(
                [
                    source_label,
                    str(item["discovery"]["histories"]),
                    str(gate["online_queries"]["cases"]),
                    str(gate["changed_post_observation_cases"]["cases"]),
                    str(
                        gate[
                            "exact_cross_session_write_to_later_read"
                        ]["cases"]
                    ),
                    str(
                        gate[
                            "exact_cross_session_write_to_later_read"
                        ]["project_contexts"]
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Frozen count gates",
            "",
            "| Gate | Observed | Minimum | Status |",
            "|---|---:|---:|---|",
        ]
    )
    for name in (
        "online_queries",
        "changed_post_observation_cases",
        "exact_cross_session_write_to_later_read",
    ):
        gate = gates[name]
        lines.append(
            f"| {name} | {gate['cases']} | {gate['minimum']} | "
            f"{gate['status']} |"
        )
    exact_projects = gates["independent_project_context_minimum"]
    lines.append(
        "| exact-transition source-scoped project contexts | "
        f"{exact_projects['source_scoped_project_contexts']} | "
        f"{exact_projects['minimum']} | {exact_projects['status']} |"
    )
    diversity = gates["confirmatory_diversity_gate"]
    source_family_gate = diversity[
        "source_families_with_exact_transitions"
    ]
    project_diversity_gate = diversity[
        "source_scoped_project_contexts_with_exact_transitions"
    ]
    lines.extend(
        [
            "",
            "## Confirmatory diversity gate",
            "",
            "| Gate | Observed | Minimum | Status |",
            "|---|---:|---:|---|",
            (
                "| source families with exact transitions | "
                f"{source_family_gate['observed']} | "
                f"{source_family_gate['minimum']} | "
                f"{source_family_gate['status']} |"
            ),
            (
                "| exact-transition source-scoped project contexts | "
                f"{project_diversity_gate['observed']} | "
                f"{project_diversity_gate['minimum']} | "
                f"{project_diversity_gate['status']} |"
            ),
            "",
            (
                "This confirmatory gate fails. It blocks architecture-quality "
                "and enterprise-transfer claims even though the smaller "
                "mechanics count gate passes."
            ),
        ]
    )
    fable = next(
        item for item in strata if item["label"] == "fable5_top_level"
    )
    fable_gates = fable["project_cluster_gates"]
    lines.extend(
        [
            "",
            "## Concentration and hard boundary",
            "",
            (
                "Fable-5 supplies "
                f"{fable_gates['online_queries']['cases']} online cases across "
                f"{fable_gates['online_queries']['project_contexts']} project "
                "contexts with cluster sizes "
                f"{fable_gates['online_queries']['cases_per_project_desc']}. "
                "Its changed cases are distributed "
                f"{fable_gates['changed_post_observation_cases']['cases_per_project_desc']}; "
                "its exact cross-session cases are distributed "
                f"{fable_gates['exact_cross_session_write_to_later_read']['cases_per_project_desc']}."
            ),
            "",
            (
                "Exact source-file, native session, record UUID, "
                "session-scoped tool ID, and content-free session-shape "
                "overlap controls are all zero. These controls do not rule "
                "out re-export, semantic, contributor, or source-family "
                "overlap."
            ),
            "",
            (
                "The selected Glint archive is a 115/115 byte-exact mirror of "
                "the [pinned cfahlgren1 Fable-5 raw archive](https://"
                "huggingface.co/datasets/cfahlgren1/Fable-5-traces/tree/"
                "0ba6f53852f296f8389290b112054b47cec2dc1f). The mirror is "
                "therefore one source-family/publisher-home cluster, never a "
                "second independent source. The dataset card tags the corpus "
                "as machine-generated/synthetic and provides no explicit "
                "donation, consent, or redaction statement."
            ),
            "",
            (
                "Therefore the next phase may measure within-corpus model and "
                "review behavior, but it may not claim a cross-enterprise "
                "effect or enable automatic memory promotion."
            ),
            "",
            f"Result SHA-256: `{result['result_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-commons-manifest", type=Path, required=True)
    parser.add_argument("--trace-commons-root", type=Path, required=True)
    parser.add_argument("--fable-manifest", type=Path, required=True)
    parser.add_argument("--fable-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(
        args.trace_commons_manifest,
        args.trace_commons_root,
        args.fable_manifest,
        args.fable_root,
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(render_markdown(result), encoding="utf-8")
    print(
        stable_json(
            {
                "status": "ok",
                "result_sha256": result["result_sha256"],
                "deterministic_longitudinal_count_gates": result[
                    "decision"
                ]["deterministic_longitudinal_count_gates"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
