#!/usr/bin/env python3
"""Reduce frontier alias adjudication to a content-free aggregate receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "frankengate-nl2sql-alias-adjudication-receipt-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cases_path: Path, adjudication_path: Path, *, model: str) -> dict[str, Any]:
    cases_payload = json.loads(cases_path.read_text(encoding="utf-8"))
    adjudications = json.loads(adjudication_path.read_text(encoding="utf-8"))
    cases = cases_payload.get("cases", [])
    if not isinstance(cases, list) or not isinstance(adjudications, list):
        raise ValueError("cases and adjudication must be arrays")
    case_ids = [case.get("case_id") for case in cases]
    result_ids = [item.get("case_id") for item in adjudications]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("duplicate case IDs in input")
    if set(case_ids) != set(result_ids) or len(result_ids) != len(case_ids):
        raise ValueError("adjudication must cover every case exactly once")
    by_case = {case["case_id"]: case for case in cases}
    surface_labels = Counter()
    candidate_labels = Counter()
    confidences: list[float] = []
    scope_correct: list[float] = []
    wrong_system_candidates: list[float] = []
    unknown_cases = 0
    for item in adjudications:
        case = by_case[item["case_id"]]
        label = str(item.get("surface_label", "unclear"))
        surface_labels[label] += 1
        confidence = float(item.get("confidence", 0.0))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence outside [0,1]: {item['case_id']}")
        confidences.append(confidence)
        if label in {"nil", "unclear"}:
            unknown_cases += 1
        candidates = item.get("candidate_labels", [])
        expected_candidates = {tuple(candidate) for candidate in case.get("candidate_same_surface", [])}
        observed_candidates = {(candidate.get("db"), candidate.get("identifier")) for candidate in candidates}
        if observed_candidates != expected_candidates:
            raise ValueError(f"candidate coverage mismatch: {item['case_id']}")
        target = (case["scope_db"], case["gold_identifier"])
        target_label = None
        wrong_count = 0
        for candidate in candidates:
            candidate_label = str(candidate.get("label", "unclear"))
            candidate_labels[candidate_label] += 1
            key = (candidate.get("db"), candidate.get("identifier"))
            if key == target:
                target_label = candidate_label
            elif candidate_label == "wrong_system":
                wrong_count += 1
        scope_correct.append(float(target_label in {"exact_alias", "semantic_alias"}))
        other_count = max(0, len(candidates) - 1)
        wrong_system_candidates.append(wrong_count / other_count if other_count else 0.0)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "source": {
            "cases_sha256": sha256(cases_path),
            "adjudication_sha256": sha256(adjudication_path),
            "cases": len(cases),
            "raw_content_committed": False,
        },
        "surface_label_counts": dict(sorted(surface_labels.items())),
        "candidate_label_counts": dict(sorted(candidate_labels.items())),
        "mean_confidence": round(sum(confidences) / len(confidences), 6) if confidences else 0.0,
        "scope_candidate_correct_rate": round(sum(scope_correct) / len(scope_correct), 6) if scope_correct else 0.0,
        "other_scope_wrong_system_rate": round(sum(wrong_system_candidates) / len(wrong_system_candidates), 6) if wrong_system_candidates else 0.0,
        "unknown_or_unclear_cases": unknown_cases,
        "claim_boundary": "Single frontier-model adjudication of a small, generic public collision sample; not independent human truth, semantic alias quality, or changed-agent utility. Use only to calibrate the next stratified SME and held-out replay gate.",
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.cases, args.adjudication, model=args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "cases": result["source"]["cases"], "scope_correct": result["scope_candidate_correct_rate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
