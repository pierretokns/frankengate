#!/usr/bin/env python3
"""Frontier adjudication gate for aliases, wrong-system collisions, and NILs.

The cases are public synthetic fixtures with explicit construction-time labels.
They are deliberately not presented as enterprise truth. The receipt retains
only hashes and aggregate agreement/accuracy; prompts and responses stay in a
temporary external directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-nl2sql-stratified-alias-adjudication-v1"
LABELS = ("exact_alias", "semantic_alias", "wrong_system", "nil", "unclear")
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cases"],
    "properties": {
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["case_id", "surface_label", "confidence", "candidate_labels"],
                "properties": {
                    "case_id": {"type": "string"},
                    "surface_label": {"enum": ["exact_alias", "semantic_alias", "nil", "unclear"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "candidate_labels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["db", "identifier", "label"],
                            "properties": {
                                "db": {"type": "string"},
                                "identifier": {"type": "string"},
                                "label": {"enum": list(LABELS)},
                            },
                        },
                    },
                },
            },
        }
    },
}


def _case(case_id: str, category: str, question: str, db: str, target: str | None, candidates: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "expected_surface": category,
        "question": question,
        "scope_db": db,
        "gold_identifier": target,
        "candidates": [{"db": cdb, "identifier": identifier} for cdb, identifier, _ in candidates],
        "expected_candidates": [{"db": cdb, "identifier": identifier, "label": label} for cdb, identifier, label in candidates],
    }


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (question, identifier) in enumerate(
        [
            ("count orders by customer_id", "customer_id"),
            ("join on invoice_number", "invoice_number"),
            ("filter by subscription_status", "subscription_status"),
            ("group by region_code", "region_code"),
            ("find the account_uuid", "account_uuid"),
            ("show the product_sku", "product_sku"),
        ],
        start=1,
    ):
        rows.append(_case(f"exact-{index:02d}", "exact_alias", question, "billing", identifier, [("billing", identifier, "exact_alias")]))
    for index, (question, identifier) in enumerate(
        [
            ("which customer identifier owns this invoice", "customer_id"),
            ("show the invoice reference", "invoice_number"),
            ("what is the subscription state", "subscription_status"),
            ("group customers by geographic region", "region_code"),
            ("find the account unique id", "account_uuid"),
            ("list the catalog stock keeping unit", "product_sku"),
        ],
        start=1,
    ):
        rows.append(_case(f"semantic-{index:02d}", "semantic_alias", question, "billing", identifier, [("billing", identifier, "semantic_alias")]))
    for index, (question, identifier) in enumerate(
        [
            ("count orders by customer_id in billing", "customer_id"),
            ("find invoice_number in billing", "invoice_number"),
            ("filter subscription_status in billing", "subscription_status"),
            ("group by region_code in billing", "region_code"),
            ("find account_uuid in billing", "account_uuid"),
        ],
        start=1,
    ):
        rows.append(_case(f"collision-{index:02d}", "exact_alias", question, "billing", identifier, [("billing", identifier, "exact_alias"), ("support", identifier, "wrong_system")]))
    for index, question in enumerate(
        [
            "what is the churn risk for this account",
            "which cloud region has the lowest latency",
            "summarize the incident severity trend",
            "show the preferred contact channel",
        ],
        start=1,
    ):
        rows.append(_case(f"nil-{index:02d}", "nil", question, "billing", None, [("billing", "customer_id", "nil"), ("support", "region_code", "wrong_system")]))
    rows.extend(
        [
            _case("unclear-01", "unclear", "show the account identifier", "billing", None, [("billing", "account_id", "unclear"), ("billing", "account_uuid", "unclear")]),
            _case("unclear-02", "unclear", "show the region", "billing", None, [("billing", "region_code", "unclear"), ("billing", "region_name", "unclear")]),
        ]
    )
    return rows


def _sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def _prompt(batch: list[dict[str, Any]], role: str) -> str:
    visible = [
        {
            "case_id": row["case_id"],
            "question": row["question"],
            "scope_db": row["scope_db"],
            "candidates": row["candidates"],
        }
        for row in batch
    ]
    return (
        f"You are the {role} adjudicator in a corporate SQL identifier review. "
        "For every case, label the question surface as exact_alias, semantic_alias, nil, or unclear. "
        "Label each candidate exact_alias, semantic_alias, wrong_system, nil, or unclear. "
        "Use nil when the question does not identify any listed identifier; use unclear when multiple "
        "in-scope identifiers remain plausible. Treat database scope as a hard boundary. "
        "Do not invent identifiers. Return exactly the requested JSON schema and include every candidate.\n\n"
        + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":"))
        + "\nDATA:\n"
        + json.dumps(visible, sort_keys=True, separators=(",", ":"))
    )


def _call(prompt: str, model: str, raw_path: Path, role: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-alias-") as directory:
        schema = Path(directory) / "schema.json"
        output = Path(directory) / "output.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "--output-schema", str(schema), "--output-last-message", str(output),
        ]
        process = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=300, check=False, cwd="/private/tmp")
        raw_path.write_text(json.dumps({"role": role, "returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr}), encoding="utf-8")
        if process.returncode != 0 or not output.exists():
            raise RuntimeError(f"frontier adjudication failed for {role}")
        value = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        raise ValueError("frontier adjudication response is not an object with cases")
    return value


def _score(rows: list[dict[str, Any]], observed: dict[str, Any]) -> dict[str, Any]:
    by_id = {item.get("case_id"): item for item in observed.get("cases", [])}
    if set(by_id) != {row["case_id"] for row in rows}:
        raise ValueError("adjudication does not cover every case exactly once")
    surface_correct = 0
    candidate_total = 0
    candidate_correct = 0
    nil_unclear_total = 0
    nil_unclear_abstained = 0
    wrong_system_total = 0
    wrong_system_correct = 0
    confidences: list[float] = []
    for row in rows:
        item = by_id[row["case_id"]]
        if item.get("surface_label") == row["expected_surface"]:
            surface_correct += 1
        confidence = float(item.get("confidence", -1))
        if not 0 <= confidence <= 1:
            raise ValueError("invalid confidence")
        confidences.append(confidence)
        expected = {(candidate["db"], candidate["identifier"]): candidate["label"] for candidate in row["expected_candidates"]}
        observed_candidates = {(candidate.get("db"), candidate.get("identifier")): candidate.get("label") for candidate in item.get("candidate_labels", [])}
        if set(expected) != set(observed_candidates):
            raise ValueError(f"candidate coverage mismatch for {row['case_id']}")
        for key, expected_label in expected.items():
            candidate_total += 1
            observed_label = observed_candidates[key]
            candidate_correct += observed_label == expected_label
            if expected_label == "wrong_system":
                wrong_system_total += 1
                wrong_system_correct += observed_label == expected_label
        if row["expected_surface"] in {"nil", "unclear"}:
            nil_unclear_total += 1
            nil_unclear_abstained += item.get("surface_label") in {"nil", "unclear"}
    return {
        "surface_accuracy": round(surface_correct / len(rows), 6),
        "candidate_accuracy": round(candidate_correct / candidate_total, 6),
        "wrong_system_accuracy": round(wrong_system_correct / wrong_system_total, 6) if wrong_system_total else None,
        "nil_unclear_abstention": round(nil_unclear_abstained / nil_unclear_total, 6) if nil_unclear_total else None,
        "mean_confidence": round(sum(confidences) / len(confidences), 6),
    }


def run(output: Path, raw_dir: Path, *, model: str) -> dict[str, Any]:
    rows = cases()
    raw_dir.mkdir(parents=True, exist_ok=True)
    observations: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    judged_cases: list[dict[str, Any]] = []
    for index, role in enumerate(("independent primary", "independent skeptical"), start=1):
        prompt = _prompt(rows, role)
        raw_path = raw_dir / f"adjudication-{index:02d}.json"
        observed = _call(prompt, model, raw_path, role)
        observations.append({"role": role, "prompt_sha256": _sha(prompt), "raw_sha256": _sha(raw_path.read_bytes())})
        scores.append(_score(rows, observed))
        judged_cases.append(observed)
    first_by_id = {item["case_id"]: item for item in judged_cases[0]["cases"]}
    second_by_id = {item["case_id"]: item for item in judged_cases[1]["cases"]}
    surface_agreement = sum(first_by_id[case_id]["surface_label"] == second_by_id[case_id]["surface_label"] for case_id in first_by_id) / len(first_by_id)
    candidate_agreement_total = 0
    candidate_agreement = 0
    for case_id in first_by_id:
        first_candidates = {(item["db"], item["identifier"]): item["label"] for item in first_by_id[case_id]["candidate_labels"]}
        second_candidates = {(item["db"], item["identifier"]): item["label"] for item in second_by_id[case_id]["candidate_labels"]}
        candidate_agreement_total += len(first_candidates)
        candidate_agreement += sum(first_candidates[key] == second_candidates[key] for key in first_candidates)
    first = observations[0]
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "cases": {"count": len(rows), "categories": {category: sum(row["expected_surface"] == category for row in rows) for category in ("exact_alias", "semantic_alias", "nil", "unclear")}, "ground_truth": "public synthetic construction-time labels; not SME truth"},
        "arms": [{"role": role, "score": score} for role, score in zip(("independent primary", "independent skeptical"), scores)],
        "inter_judge": {
            "prompt_hashes_distinct": observations[0]["prompt_sha256"] != observations[1]["prompt_sha256"],
            "surface_agreement": round(surface_agreement, 6),
            "candidate_agreement": round(candidate_agreement / candidate_agreement_total, 6),
            "raw_receipts": observations,
        },
        "claim_boundary": "Synthetic capability gate only. It measures frontier structured-adjudication accuracy and abstention on constructed aliases, collisions, NILs, and ambiguities; it does not establish corporate semantic truth, SME agreement, downstream retrieval, or artifact utility.",
    }
    receipt["receipt_sha256"] = _sha(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(rows), "scores": scores, "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    args = parser.parse_args()
    run(args.output, args.raw_dir, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
