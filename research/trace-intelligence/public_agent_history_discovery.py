#!/usr/bin/env python3
"""Build a content-free, source-pinned public agent-history discovery receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "public-agent-history-discovery-result-v1"


class DiscoveryError(ValueError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def load_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DiscoveryError(f"{path}: object required")
    return value, hashlib.sha256(raw).hexdigest()


def build_result(config_dir: Path) -> dict[str, Any]:
    discovery, discovery_sha = load_json(
        config_dir / "public-agent-history-discovery.json"
    )
    if discovery.get("schema_version") != (
        "public-agent-history-discovery-manifest-v1"
    ):
        raise DiscoveryError("unexpected discovery manifest schema")

    sources: dict[str, Any] = {}
    for filename in discovery["source_manifests"]:
        manifest, sha = load_json(config_dir / filename)
        source_id = manifest.get("dataset_id")
        if not source_id or source_id in sources:
            raise DiscoveryError(f"{filename}: unique dataset_id required")
        sources[source_id] = {
            "manifest": filename,
            "manifest_sha256": sha,
            "revision": manifest.get("dataset_revision"),
            "license": manifest.get("license"),
            "admission": manifest.get("admission"),
            "known_scope": (
                manifest.get("known_scope")
                or manifest.get("observed_scope_at_pinned_revision")
                or {}
            ),
        }

    github = discovery["github"]
    if github["codex_top_repositories_with_auth_adjacent"] > (
        github["codex_top_repositories_inspected"]
    ):
        raise DiscoveryError("auth-adjacent count exceeds inspected repos")

    output = {
        "schema_version": SCHEMA_VERSION,
        "audit_date": discovery["audit_date"],
        "input_receipts": {
            "discovery_manifest_sha256": discovery_sha,
            "source_manifest_count": len(sources),
        },
        "discovery_scale": {
            "hugging_face_agent_trace_dataset_hits": discovery[
                "hugging_face"
            ]["dataset_hits"],
            "github_claude_indexed_matches": github[
                "claude_indexed_matches"
            ],
            "github_codex_indexed_matches": github[
                "codex_indexed_matches"
            ],
            "top_repo_native_claude_files": github[
                "claude_native_jsonl_files"
            ],
            "top_repo_native_claude_bytes": github[
                "claude_native_jsonl_bytes"
            ],
            "top_repo_native_codex_files": github[
                "codex_native_jsonl_files"
            ],
            "top_repo_native_codex_bytes": github[
                "codex_native_jsonl_bytes"
            ],
        },
        "classification": {
            "near_complete_home_state": [
                "github/jkim0731/2p-hcr-autocoreg/.claude"
            ],
            "partial_home": ["Glint-Research/Fable-5-traces"],
            "portable_session_bundle": [
                "github/jimmc414/cctrace/phase0-investigation"
            ],
            "native_codex_archives": [
                "github/wjmlong/Codex_Sessions",
                "github/byesngmin/KGA-codex-sessions",
            ],
            "real_research_trace_strata": [
                "clem/ml-intern-sessions",
                "evalstate/model-toolcall-research",
            ],
            "paired_trace_and_memory_strata": [
                "github/seokhawn01/wineLab-research/.claude",
                "trace-commons/agent-traces-memory-pairing",
            ],
            "research_memory_target_strata": [
                "github/biaslab/RAL2026-CPG-ActInf/.claude/memory",
            ],
            "controlled_scientific_trace_strata": [
                "FrontisAI/NatureBench-traces",
                "AgentNativeResearchLab/discoverphysics-opus4.8-max-ara",
            ],
            "card_only_no_payload": ["zenlm/zen-agentic-dataset"],
        },
        "security_observation": {
            "codex_repositories_inspected": github[
                "codex_top_repositories_inspected"
            ],
            "codex_repositories_with_auth_adjacent": github[
                "codex_top_repositories_with_auth_adjacent"
            ],
            "required_control": (
                "strict path allowlists before content scanning; deny auth, "
                "credentials, caches, shell config, and opaque account state"
            ),
        },
        "sources": sources,
        "claim_boundary": (
            "discovery establishes corpus availability and import-shape "
            "coverage, not independent users, task correctness, employee "
            "skill, or enterprise intervention benefit"
        ),
        "raw_content_committed": discovery["raw_content_committed"],
        "candidate_values_emitted": discovery[
            "candidate_values_emitted"
        ],
    }
    output["result_sha256"] = hashlib.sha256(
        stable_json(output).encode("utf-8")
    ).hexdigest()
    return output


def render_markdown(result: dict[str, Any]) -> str:
    scale = result["discovery_scale"]
    security = result["security_observation"]
    return "\n".join(
        [
            "# Public agent-history expanded discovery",
            "",
            f"**Audit date:** {result['audit_date']}",
            "",
            "## Result",
            "",
            f"- Hugging Face agent-trace dataset hits: "
            f"{scale['hugging_face_agent_trace_dataset_hits']}",
            f"- GitHub indexed native Claude/Codex matches: "
            f"{scale['github_claude_indexed_matches']} / "
            f"{scale['github_codex_indexed_matches']}",
            f"- Native files in inspected top repositories: "
            f"{scale['top_repo_native_claude_files']} Claude "
            f"({scale['top_repo_native_claude_bytes']} bytes) and "
            f"{scale['top_repo_native_codex_files']} Codex "
            f"({scale['top_repo_native_codex_bytes']} bytes)",
            f"- Near-complete public Claude home-state trees: "
            f"{len(result['classification']['near_complete_home_state'])}",
            f"- Real researcher-trace and paired trace/memory strata: "
            f"{len(result['classification']['real_research_trace_strata'])} / "
            f"{len(result['classification']['paired_trace_and_memory_strata'])}",
            f"- Codex repositories with adjacent auth state: "
            f"{security['codex_repositories_with_auth_adjacent']}/"
            f"{security['codex_repositories_inspected']}",
            "",
            "## Decision",
            "",
            "Public corpus availability is sufficient. Build strict native, "
            "portable-bundle, partial-home, and transformed-export adapters. "
            "Do not recursively ingest a harness home; trace, versioned "
            "context/policy, and unsafe/excluded state are separate lanes.",
            "",
            f"Claim boundary: {result['claim_boundary']}.",
            "",
            f"Result SHA-256: `{result['result_sha256']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(__file__).parent / "configs",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    result = build_result(args.config_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
