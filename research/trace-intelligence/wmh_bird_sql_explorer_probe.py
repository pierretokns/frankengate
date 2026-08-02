#!/usr/bin/env python3
"""Test a separate frontier explorer on exposed, replayable SQL tables.

The explorer sees only the natural-language question and the exposed table
names.  Gold SQL, replay results, and equivalence labels remain evaluator-only.
This is the first bridge from the public tool-explorer probe to validated SQL
artifact candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from wmh_bird_exposure_counterfactual import (
    Trace,
    execute,
    lexical_score,
    load_traces,
    rank_metrics,
)
from wmh_bird_equivalence_aware_retrieval import equivalent_candidates


SCHEMA_VERSION = "frankengate-wmh-bird-sql-explorer-probe-v1"
MODEL = "gpt-5.6-luna"
MAX_SHORTLIST = 8
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["selected_indices"],
    "properties": {
        "selected_indices": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0},
            "minItems": 1,
            "maxItems": MAX_SHORTLIST,
        }
    },
}


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_cases(traces: list[Trace], db_root: Path, limit: int) -> list[tuple[Trace, frozenset[str]]]:
    by_db: dict[str, list[Trace]] = defaultdict(list)
    for trace in traces:
        db_path = db_root / trace.db_name / f"{trace.db_name}.sqlite"
        status, _ = execute(db_path, trace.sql)
        if status == "ok" and trace.used_tables & trace.exposed_tables:
            by_db[trace.db_name].append(trace)
    selected: list[tuple[Trace, frozenset[str]]] = []
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda item: item.trace_hash)
        chosen = ordered[0]
        equivalent: set[str] = set()
        # Prefer a query with an independently replay-confirmed acceptable
        # alternative when the public cohort contains one; otherwise retain
        # the first deterministic trace. This keeps the probe informative
        # without changing the evaluator's labels.
        for candidate in ordered:
            replay_equivalent, _, _ = equivalent_candidates(candidate, db_root)
            if replay_equivalent:
                chosen = candidate
                equivalent = set(replay_equivalent)
                break
        if not equivalent:
            equivalent, _, _ = equivalent_candidates(chosen, db_root)
        selected.append((chosen, frozenset(equivalent)))
        if len(selected) >= limit:
            break
    return selected


def lexical_order(trace: Trace) -> list[str]:
    return sorted(trace.exposed_tables, key=lambda table: (-lexical_score(trace.prompt, table), table))


def metric_row(order: list[str], targets: frozenset[str], compatible: frozenset[str], pool_size: int) -> dict[str, Any]:
    strict = rank_metrics(order, targets)
    compatible_metrics = rank_metrics(order, compatible)
    selected = set(order)
    invalid = selected - compatible
    return {
        "pool_size": pool_size,
        "selected_count": len(order),
        "strict_mrr": strict["mrr"],
        "strict_recall_at_1": strict["recall_at_1"],
        "strict_recall_at_5": strict["recall_at_5"],
        "strict_recall_at_10": strict["recall_at_10"],
        "compatible_mrr": compatible_metrics["mrr"],
        "compatible_recall_at_1": compatible_metrics["recall_at_1"],
        "compatible_recall_at_5": compatible_metrics["recall_at_5"],
        "compatible_recall_at_10": compatible_metrics["recall_at_10"],
        "compatible_selected_rate": len(selected & compatible) / max(1, len(selected)),
        "invalid_selected_count": len(invalid),
        "target_count": len(targets),
        "compatible_count": len(compatible),
    }


def prompt_for(trace: Trace, candidates: list[str], run_label: str) -> str:
    items = [{"index": index, "table": table} for index, table in enumerate(candidates)]
    return (
        "You are a conservative SQL table explorer. Select the smallest ordered "
        f"shortlist of at most {MAX_SHORTLIST} exposed table names that should be "
        "inspected for the user's question. Use only the question and table names. "
        "Do not invent tables, write SQL, or claim that a table is correct or safe. "
        "Return JSON matching the schema and no prose. The evaluator will check "
        "replay separately.\n"
        + json.dumps(OUTPUT_SCHEMA, separators=(",", ":"))
        + "\nRUN_LABEL="
        + run_label
        + "\nQUESTION="
        + trace.prompt
        + "\nEXPOSED_TABLES="
        + json.dumps(items, separators=(",", ":"))
    )


def call_frontier(prompt: str, model: str, raw_path: Path, *, attempts: int = 3) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-sql-explorer-") as directory:
        output_path = Path(directory) / "output.json"
        # The nested harness must be able to update its own local state DB;
        # the prompt itself remains read-only and raw outputs stay external.
        command = ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check", "--sandbox", "workspace-write", "--cd", "/private/tmp", "--model", model, "--output-last-message", str(output_path), "-"]
        raw: dict[str, Any] = {"prompt_sha256": stable_hash(prompt), "attempts": []}
        completed = None
        for attempt in range(1, attempts + 1):
            completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=300, cwd="/private/tmp", check=False)
            raw["attempts"].append({"attempt": attempt, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
            if completed.returncode == 0 and output_path.exists():
                break
            if attempt < attempts:
                time.sleep(2 * attempt)
        if completed is None or completed.returncode != 0 or not output_path.exists():
            raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            raise RuntimeError("frontier SQL explorer call failed")
        response = output_path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            value = json.loads(response)
        except json.JSONDecodeError:
            start, end = response.find("{"), response.rfind("}")
            value = json.loads(response[start : end + 1]) if start >= 0 and end > start else None
        raw["structured_output"] = value
        raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    if not isinstance(value, dict):
        raise ValueError("SQL explorer response is not an object")
    indices = value.get("selected_indices")
    if not isinstance(indices, list) or not indices or len(indices) > MAX_SHORTLIST or len(indices) != len(set(indices)):
        raise ValueError("SQL explorer returned invalid selected_indices")
    return value


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(row[key]) for row in rows) / len(rows), 6) if rows else 0.0


def run(traces_path: Path, manifest: Path, db_root: Path, output: Path, raw_dir: Path, *, limit: int = 8, model: str = MODEL, run_label: str = "", reuse_raw: bool = False) -> dict[str, Any]:
    selected = select_cases(load_traces(traces_path, manifest), db_root, limit)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    failures = 0
    for index, (trace, equivalents) in enumerate(selected):
        candidates = sorted(trace.exposed_tables)
        targets = frozenset(trace.used_tables & trace.exposed_tables)
        lexical = lexical_order(trace)[:MAX_SHORTLIST]
        raw_path = raw_dir / f"case-{index:03d}.json"
        try:
            value = json.loads(raw_path.read_text(encoding="utf-8")).get("structured_output") if reuse_raw else call_frontier(prompt_for(trace, candidates, run_label), model, raw_path)
            indices = [int(item) for item in value["selected_indices"]]
            if any(item < 0 or item >= len(candidates) for item in indices):
                raise ValueError("selected index outside exposed table pool")
            explorer_order = [candidates[item] for item in indices]
            compatible = targets | equivalents
            rows.append({
                "case_index": index,
                "db_name": trace.db_name,
                "trace_hash": trace.trace_hash,
                "prompt_chars": len(prompt_for(trace, candidates, run_label)),
                "candidate_count": len(candidates),
                "target_tables": sorted(targets),
                "replay_equivalent_tables": sorted(equivalents),
                "lexical": metric_row(lexical, targets, compatible, len(candidates)),
                "explorer": metric_row(explorer_order, targets, compatible, len(candidates)),
            })
        except Exception as exc:
            failures += 1
            rows.append({"case_index": index, "db_name": trace.db_name, "trace_hash": trace.trace_hash, "candidate_count": len(candidates), "error": type(exc).__name__, "error_message": str(exc)})
    completed = [row for row in rows if "explorer" in row]
    arms = {}
    for arm in ("lexical", "explorer"):
        values = [row[arm] for row in completed]
        arms[arm] = {
            "records": len(values),
            "strict_mrr": mean(values, "strict_mrr"),
            "strict_recall_at_1": mean(values, "strict_recall_at_1"),
            "strict_recall_at_5": mean(values, "strict_recall_at_5"),
            "strict_recall_at_10": mean(values, "strict_recall_at_10"),
            "compatible_mrr": mean(values, "compatible_mrr"),
            "compatible_recall_at_1": mean(values, "compatible_recall_at_1"),
            "compatible_recall_at_5": mean(values, "compatible_recall_at_5"),
            "compatible_recall_at_10": mean(values, "compatible_recall_at_10"),
            "compatible_selected_rate": mean(values, "compatible_selected_rate"),
            "invalid_selected_count": mean(values, "invalid_selected_count"),
            "selected_count": mean(values, "selected_count"),
        }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces_path), "manifest_sha256": file_hash(manifest), "raw_content_committed": False, "sqlite_root": "external-pinned-bird-minidev"},
        "dataset": {"selected_cases": len(selected), "database_families": sorted({row["db_name"] for row in rows}), "selection": "first replayable successful trace by database name", "candidate_pool": "all tables exposed in that trace", "target": "recorded SQL table references; compatibility adds result-preserving substitutions"},
        "protocol": {"model": model, "run_label": run_label, "max_shortlist": MAX_SHORTLIST, "explorer_sees_sql": False, "explorer_sees_replay_outcomes": False, "explorer_sees_gold_targets": False, "tool_endpoints_invoked": False, "raw_model_outputs_external": True},
        "arms": arms,
        "rows": rows,
        "failures": failures,
        "claim_boundary": {"separate_sql_explorer_measured": failures < len(selected), "replay_compatibility_measured": True, "semantic_alias_quality_established": False, "validated_artifact_utility_established": False, "enterprise_skill_transfer_measured": False, "reason": "The evaluator uses independent SQLite replay on a public BIRD proxy. Result-preserving substitutions are query-local compatibility labels, not enterprise intent or authorization truth."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": arms, "failures": failures}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--run-label", default="")
    parser.add_argument("--reuse-raw", action="store_true")
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, args.raw_dir, limit=args.limit, model=args.model, run_label=args.run_label, reuse_raw=args.reuse_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
