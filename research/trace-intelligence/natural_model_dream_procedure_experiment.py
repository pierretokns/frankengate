#!/usr/bin/env python3
"""Generate content-minimized natural-trace procedures with Codex.

Only structural summaries of temporary public traces enter the model prompt.
The model response is retained outside the checkout; the committed receipt
contains hashes, controlled-vocabulary counts, and an independent structural
quality verdict.  This is a generator-quality experiment, not a semantic
utility or skill-benefit claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from real_user_analysis_arms import read_session, tool_family


MODEL = "gpt-5.6-luna"
ALLOWED_FAMILIES = sorted({"shell", "file_mutation", "file_read", "external_retrieval", "tool_discovery", "task_coordination", "delegation", "skill_invocation", "human_interaction", "structured_output", "other"})
SCHEMA_VERSION = "frankengate-natural-model-dream-procedure-v1"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_json(text: str) -> dict[str, Any] | None:
    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.I | re.S)
    candidates.extend(fenced)
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def call_model(prompt: str, workdir: Path, backend: str, model: str) -> tuple[str, bool]:
    if backend == "ollama":
        try:
            process = subprocess.run(
                ["ollama", "run", model],
                input=prompt,
                text=True,
                capture_output=True,
                timeout=240,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return "", False
        response = process.stdout.strip()
        return response, process.returncode == 0 and bool(response)
    with tempfile.TemporaryDirectory(prefix="frankengate-dream-", dir="/private/tmp") as tmp:
        output = Path(tmp) / "last_message.txt"
        command = [
            "codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "--cd", str(workdir), "--model", model,
            "--output-last-message", str(output), "-",
        ]
        try:
            process = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=180, check=False)
        except (OSError, subprocess.SubprocessError):
            return "", False
        response = output.read_text(encoding="utf-8", errors="replace").strip() if output.exists() else ""
        return response, process.returncode == 0 and bool(response)


def structural_summary(path: Path, corpus_root: Path) -> tuple[str, dict[str, Any]]:
    session = read_session(path, corpus_root)
    relative = path.relative_to(corpus_root).as_posix()
    evidence_id = "ev-" + sha256_text(relative)[:16]
    families = Counter(call.family for call in session.call_order)
    motifs = Counter((item.error_family, item.recovery_family, item.tier) for item in session.recoveries)
    summary = {
        "evidence_id": evidence_id,
        "records": session.valid_records,
        "malformed_records": session.invalid_records,
        "tool_calls": len(session.calls),
        "tool_results": len(session.results),
        "explicit_errors": session.explicit_errors,
        "recovery_candidates": len(session.recoveries),
        "branch_points": session.branch_points,
        "dangling_parents": session.dangling_parents,
        "tool_families": dict(sorted(families.items())),
        "recovery_motifs": [
            {"error_family": e, "recovery_family": r, "tier": t, "count": n}
            for (e, r, t), n in sorted(motifs.items())
        ],
    }
    return evidence_id, summary


def validate_candidate(candidate: dict[str, Any] | None, evidence: dict[str, Any]) -> dict[str, Any]:
    known = {evidence["evidence_id"]}
    if candidate is None:
        return {"valid_json": False, "evidence_grounded": False, "controlled_steps": False, "quality_passed": False}
    citations = candidate.get("evidence_ids")
    steps = candidate.get("steps")
    families = set(evidence["tool_families"])
    controlled = isinstance(steps, list) and bool(steps) and len(steps) <= 8 and all(
        isinstance(step, dict) and step.get("tool_family") in ALLOWED_FAMILIES
        and step.get("tool_family") in families
        for step in steps
    )
    grounded = isinstance(citations, list) and bool(citations) and set(citations) <= known
    shaped = isinstance(candidate.get("procedure_title"), str) and isinstance(candidate.get("preconditions"), list) and isinstance(candidate.get("stop_conditions"), list)
    return {
        "valid_json": True,
        "evidence_grounded": grounded,
        "controlled_steps": controlled,
        "required_fields": shaped,
        "quality_passed": bool(grounded and controlled and shaped),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--max-projects", type=int, default=3)
    parser.add_argument("--workdir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--backend", choices=("ollama", "codex"), default="ollama")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.corpus_root.rglob("*.jsonl"))[: max(1, args.max_projects)]
    rows: list[dict[str, Any]] = []
    for path in paths:
        evidence_id, evidence = structural_summary(path, args.corpus_root)
        prompt = (
            "You are a governed procedure generator. The following is a content-free structural summary "
            "of one agent trace. Produce ONLY a JSON object with fields procedure_title (string), "
            "preconditions (array of short strings), steps (array of objects with tool_family and action), "
            "stop_conditions (array of short strings), and evidence_ids (array). Use only observed tool "
            "families and cite the supplied evidence_id. Never invent paths, identifiers, user content, "
            "commands, outcomes, or credentials. This is a proposal, not an instruction to execute.\n\n"
            + json.dumps(evidence, sort_keys=True)
        )
        response, completed = call_model(prompt, args.workdir, args.backend, args.model)
        candidate = extract_json(response)
        checks = validate_candidate(candidate, evidence)
        rows.append({
            "evidence_id": evidence_id,
            "evidence_summary": evidence,
            "model": args.model,
            "codex_completed": completed,
            "model_response_sha256": sha256_text(response),
            "candidate_sha256": sha256_text(json.dumps(candidate, sort_keys=True)) if candidate is not None else None,
            "candidate_length": len(response),
            "checks": checks,
        })
    result = {
        "schema_version": SCHEMA_VERSION,
        "study": "model_generated_natural_trace_procedure_structural_quality",
        "model": args.model,
        "projects_attempted": len(rows),
        "projects_with_valid_candidate": sum(row["checks"]["valid_json"] for row in rows),
        "projects_quality_passed": sum(row["checks"]["quality_passed"] for row in rows),
        "rows": rows,
        "claim_boundary": {
            "model_generated_procedure_executed": True,
            "structural_quality_measured": True,
            "semantic_procedure_quality_confirmed": False,
            "causal_skill_or_memory_utility_confirmed": False,
            "enterprise_transfer_confirmed": False,
            "reason": "Only content-free structural summaries were supplied; no task outcome, human label, or changed-system execution was available.",
        },
        "content_policy": {"raw_trace_content_emitted": False, "model_response_emitted": False, "paths_emitted": False},
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"projects_attempted": len(rows), "projects_quality_passed": result["projects_quality_passed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
