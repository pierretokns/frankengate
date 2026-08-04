#!/usr/bin/env python3
"""Benchmark exact, lexical, dense, and frontier retrieval on a real NL2SQL cohort.

The raw cohort is produced by ``nl2sql_real_alias_cohort.py`` and remains
outside Git.  The receipt stores only hashes, candidate positions, and
aggregate metrics.  Frontier ranking is deliberately a late-stage arm: it
sees the question, database scope, and candidate schema objects, but never the
gold SQL, target labels, or source row IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib import request

from nl2sql_real_alias_cohort import exact_surface, lexical_score, normalize, question_tokens


SCHEMA_VERSION = "frankengate-nl2sql-real-alias-benchmark-v1"
DEFAULT_MODEL = "gpt-5.6-luna"
EMBED_MODEL = "nomic-embed-text:latest"
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "scores"],
    "properties": {
        "decision": {"enum": ["retrieve", "abstain"]},
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "relevance"],
                "properties": {
                    "index": {"type": "integer", "minimum": 0},
                    "relevance": {"type": "integer", "minimum": 0, "maximum": 3},
                },
            },
        },
    },
}


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_key(candidate: Mapping[str, str]) -> tuple[str, str, str]:
    return (str(candidate["db"]), str(candidate["table"]), str(candidate["identifier"]))


def candidate_fingerprint(candidate: Mapping[str, str]) -> str:
    return stable_hash(candidate_key(candidate))[:16]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(a * a for a in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def post_embed(endpoint: str, texts: Sequence[str]) -> list[list[float]]:
    payload = json.dumps({"model": EMBED_MODEL, "input": list(texts), "truncate": True}).encode()
    req = request.Request(endpoint.rstrip("/") + "/api/embed", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=240) as response:
        value = json.loads(response.read().decode())
    vectors = value.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("embedding response count mismatch")
    return [[float(item) for item in vector] for vector in vectors]


def _summary(case: Mapping[str, Any], candidates: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    return {
        "question": str(case["question"])[:700],
        "scope_db": str(case["scope_db"]),
        "candidates": [
            {"index": index, "db": candidate["db"], "table": candidate["table"], "identifier": candidate["identifier"]}
            for index, candidate in enumerate(candidates)
        ],
    }


def _prompt(case: Mapping[str, Any], candidates: Sequence[Mapping[str, str]]) -> str:
    return (
        "You are a blinded schema-object retrieval judge. Rank the candidate "
        "objects that best answer the natural-language SQL question under the "
        "stated database scope. Use relevance 3 for an object directly needed, "
        "2 for a strongly related object, 1 for weakly related, and 0 for an "
        "unrelated or wrong-system distractor. Treat the scope database as a "
        "hard boundary. If none of the candidates is a plausible answer, choose "
        "abstain; otherwise choose retrieve. You are not shown gold SQL or "
        "target labels. Include every candidate index exactly once and return "
        "only the requested JSON schema.\n\n"
        + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":"))
        + "\nDATA:\n"
        + json.dumps(_summary(case, candidates), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    )


def _call_frontier(prompt: str, model: str, timeout_seconds: int, raw_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-nl2sql-reranker-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "--output-schema", str(schema), "--output-last-message", str(output),
        ]
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout_seconds, cwd="/private/tmp", check=False)
        raw_record = {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
        if completed.returncode != 0 or not output.exists():
            raw_path.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")
            raise RuntimeError(f"frontier call failed: {completed.stderr[-1000:]}")
        value = json.loads(output.read_text(encoding="utf-8"))
        raw_record["structured_output"] = value
        raw_path.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")
    if not isinstance(value, dict) or not isinstance(value.get("scores"), list):
        raise ValueError("frontier response missing scores")
    return value


def _order_from_scores(scores: Sequence[Mapping[str, Any]], count: int) -> tuple[list[int], str]:
    by_index = {int(item["index"]): int(item["relevance"]) for item in scores}
    if set(by_index) != set(range(count)) or len(scores) != count:
        raise ValueError("frontier response must score every candidate exactly once")
    return sorted(range(count), key=lambda index: (by_index[index], -index), reverse=True), "ok"


def _target_set(case: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    return {(str(item["db"]), str(item["table"]), str(item["identifier"])) for item in case.get("target_objects", [])}


def _case_metrics(case: Mapping[str, Any], order: Sequence[int]) -> dict[str, float | int | None]:
    candidates = case["candidates"]
    targets = _target_set(case)
    if not targets:
        return {"mrr": None, "recall_at_1": None, "recall_at_5": None, "wrong_system_before_target": None}
    positions = [position for position, index in enumerate(order, start=1) if candidate_key(candidates[index]) in targets]
    first = min(positions) if positions else None
    target_norms = {normalize(item["identifier"]) for item in case["target_objects"]}
    wrong_before = 0.0
    if first is not None:
        wrong_before = float(any(
            candidates[index]["db"] != case["scope_db"]
            and normalize(candidates[index]["identifier"]) in target_norms
            for index in order[: first - 1]
        ))
    return {
        "mrr": 1.0 / first if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "wrong_system_before_target": wrong_before,
    }


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    targeted = [row for row in rows if row["mrr"] is not None]
    nil = [row for row in rows if row["mrr"] is None]
    def mean(key: str, values: Sequence[Mapping[str, Any]]) -> float | None:
        usable = [float(row[key]) for row in values if row.get(key) is not None]
        return round(sum(usable) / len(usable), 6) if usable else None
    return {
        "targeted_cases": len(targeted),
        "nil_cases": len(nil),
        "targeted_mrr": mean("mrr", targeted),
        "targeted_recall_at_1": mean("recall_at_1", targeted),
        "targeted_recall_at_5": mean("recall_at_5", targeted),
        "targeted_wrong_system_before_target": mean("wrong_system_before_target", targeted),
    }


def _select_cases(cases: Sequence[Mapping[str, Any]], per_group: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        groups[(str(case["scope_db"]), str(case["category"]))].append(dict(case))
    selected: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda case: case["case_id"])
        selected.extend(group[:per_group])
    return selected


def run(raw_path: Path, output: Path, raw_dir: Path, *, endpoint: str, model: str, per_group: int, timeout_seconds: int) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    cases = _select_cases(raw["cases"], per_group)
    if not cases:
        raise ValueError("cohort has no cases")
    raw_dir.mkdir(parents=True, exist_ok=True)
    aggregate_per_arm: dict[str, list[dict[str, Any]]] = {"exact_scope": [], "lexical_scope": [], "dense_scope": [], "frontier_scope": []}
    per_case: list[dict[str, Any]] = []
    texts: list[str] = []
    text_keys: list[tuple[str, int | None]] = []
    for case_index, case in enumerate(cases):
        texts.append(f"database {case['scope_db']} question {case['question']}")
        text_keys.append(("query", case_index))
        for candidate_index, candidate in enumerate(case["candidates"]):
            texts.append(f"database {candidate['db']} table {candidate['table']} identifier {candidate['identifier']}")
            text_keys.append(("candidate", case_index * 1000 + candidate_index))
    vectors = post_embed(endpoint, texts)
    query_vectors = {case_index: vectors[position] for position, (_, case_index) in enumerate(text_keys) if _ == "query"}
    candidate_vectors: dict[tuple[int, int], list[float]] = {}
    for position, (kind, key) in enumerate(text_keys):
        if kind == "candidate":
            candidate_vectors[(key // 1000, key % 1000)] = vectors[position]
    frontier_calls: list[dict[str, Any]] = []
    failures = 0
    for case_index, case in enumerate(cases):
        candidates = case["candidates"]
        exact_order = sorted(range(len(candidates)), key=lambda index: (not exact_surface(case["question"], candidates[index]["identifier"]), candidates[index]["db"] != case["scope_db"], index))
        lexical_order = sorted(range(len(candidates)), key=lambda index: (-lexical_score(case["question"], candidates[index]), candidates[index]["db"] != case["scope_db"], index))
        dense_order = sorted(range(len(candidates)), key=lambda index: (-cosine(query_vectors[case_index], candidate_vectors[(case_index, index)]), candidates[index]["db"] != case["scope_db"], index))
        orders = {"exact_scope": exact_order, "lexical_scope": lexical_order, "dense_scope": dense_order}
        prompt = _prompt(case, candidates)
        raw_response_path = raw_dir / f"case-{case_index:03d}.json"
        try:
            response = _call_frontier(prompt, model, timeout_seconds, raw_response_path)
            frontier_order, status = _order_from_scores(response["scores"], len(candidates))
            decision = response.get("decision")
            if decision not in {"retrieve", "abstain"}:
                raise ValueError("invalid frontier decision")
            orders["frontier_scope"] = frontier_order
            frontier_calls.append({"case": case_index, "status": status, "decision": decision, "prompt_sha256": stable_hash(prompt), "raw_sha256": file_sha256(raw_response_path)})
        except Exception as exc:
            failures += 1
            frontier_calls.append({"case": case_index, "status": "error", "error": type(exc).__name__, "prompt_sha256": stable_hash(prompt), "raw_sha256": file_sha256(raw_response_path) if raw_response_path.exists() else None})
            continue
        metrics = {arm: _case_metrics(case, order) for arm, order in orders.items()}
        for arm, values in metrics.items():
            aggregate_per_arm[arm].append(values)
        per_case.append({
            "case_id": case["case_id"],
            "category": case["category"],
            "candidate_fingerprints": [candidate_fingerprint(candidate) for candidate in candidates],
            "target_fingerprints": [candidate_fingerprint(candidate) for candidate in case.get("target_objects", [])],
            "orders": {arm: list(order) for arm, order in orders.items()},
            "metrics": metrics,
            "frontier_decision": response["decision"],
            "frontier_decision_correct": bool(response["decision"] == ("retrieve" if case.get("target_objects") else "abstain")),
        })
    if failures:
        raise RuntimeError(f"frontier failures: {failures}/{len(cases)}")
    decision_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in per_case:
        decision_counts[str(row["category"])][str(row["frontier_decision"])] += 1
    nil_categories = {"scope_swapped_nil"}
    nil_rows = [row for row in per_case if row["category"] in nil_categories]
    nil_abstention = sum(row["frontier_decision"] == "abstain" for row in nil_rows) / len(nil_rows) if nil_rows else None
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"raw_sha256": file_sha256(raw_path), "selected_cases": len(cases), "categories": {category: sum(case["category"] == category for case in cases) for category in sorted({case["category"] for case in cases})}, "raw_content_committed": False},
        "protocol": {"model": model, "embedding_model": EMBED_MODEL, "endpoint": endpoint, "candidate_generation": "frozen by real alias cohort manifest", "frontier_sees_gold_targets": False, "frontier_sees_source_row_ids": False, "raw_model_outputs_external": True, "per_group": per_group},
        "aggregate": {arm: _aggregate(values) for arm, values in aggregate_per_arm.items()},
        "frontier_decisions": {
            "by_category": {category: dict(sorted(values.items())) for category, values in sorted(decision_counts.items())},
            "scope_swapped_nil_abstention": round(nil_abstention, 6) if nil_abstention is not None else None,
        },
        "frontier_decision": {
            "accuracy": round(sum(int(row["frontier_decision_correct"]) for row in per_case) / len(per_case), 6) if per_case else 0.0,
            "targeted_retrieve_rate": round(sum(int(row["frontier_decision"] == "retrieve") for row in per_case if row["category"] != "scope_swapped_nil") / max(1, sum(row["category"] != "scope_swapped_nil" for row in per_case)), 6),
            "nil_abstention_rate": round(sum(int(row["frontier_decision"] == "abstain") for row in per_case if row["category"] == "scope_swapped_nil") / max(1, sum(row["category"] == "scope_swapped_nil" for row in per_case)), 6),
        },
        "per_case": per_case,
        "frontier_calls": {"requested": len(cases), "completed": len(per_case), "failures": failures, "receipts": frontier_calls},
        "claim_boundary": "Gold-SQL target retrieval and constructed scope-swapped NIL benchmark on public NL2SQL data. It does not establish semantic-alias truth, human agreement, changed-agent utility, or enterprise production performance.",
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "aggregate": result["aggregate"], "result_sha256": result["result_sha256"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--per-group", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    run(args.raw, args.output, args.raw_dir, endpoint=args.endpoint, model=args.model, per_group=args.per_group, timeout_seconds=args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
