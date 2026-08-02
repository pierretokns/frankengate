#!/usr/bin/env python3
"""Probe score-only and identifier-aware abstention on the wiki fixture."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from wiki_agentic_rag_benchmark import WikiIndex, sha256


UNIQUE_ENTITY = re.compile(r"\b(?:atlas|bluebird)-\d{2}\b", re.I)


def evaluate_policy(data: dict[str, Any], sizes: list[int], threshold: float | None = None, entity_gate: bool = False) -> list[dict[str, Any]]:
    all_wikis = sorted({page["wiki_id"] for page in data["pages"]})
    output: list[dict[str, Any]] = []
    for size in sizes:
        selected = set(all_wikis[:size])
        pages = [page for page in data["pages"] if page["wiki_id"] in selected]
        questions = [question for question in data["questions"] if not question["gold_page_ids"] or question["wiki_id"] in selected]
        index = WikiIndex(pages, backend="hybrid", compiled=False)
        gold_rows = 0
        accepted_gold = 0
        correct_accepted = 0
        nil_rows = 0
        nil_false_positive = 0
        for question in questions:
            ranked = index.search(question["question"], k=5)
            top_score = ranked[0]["score"] if ranked else 0.0
            accepted = bool(ranked)
            if threshold is not None:
                accepted = accepted and top_score >= threshold
            if entity_gate:
                accepted = accepted and bool(UNIQUE_ENTITY.search(question["question"]))
            if question["gold_page_ids"]:
                gold_rows += 1
                if accepted:
                    accepted_gold += 1
                    if ranked[0]["page_id"] in set(question["gold_page_ids"]):
                        correct_accepted += 1
            else:
                nil_rows += 1
                nil_false_positive += int(accepted)
        output.append({
            "size": size,
            "threshold": threshold,
            "entity_gate": entity_gate,
            "gold_coverage": accepted_gold / gold_rows if gold_rows else 0.0,
            "accepted_gold_recall_at_1": correct_accepted / accepted_gold if accepted_gold else 0.0,
            "nil_false_positive_rate": nil_false_positive / nil_rows if nil_rows else 0.0,
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    sizes = [1, 5, 10, 25]
    rows: list[dict[str, Any]] = []
    for threshold in (None, 0.65, 0.70, 0.75, 0.80):
        rows.extend(evaluate_policy(data, sizes, threshold=threshold, entity_gate=False))
    rows.extend(evaluate_policy(data, sizes, threshold=None, entity_gate=True))
    result = {
        "schema_version": "frankengate-wiki-abstention-probe-v1",
        "fixture_sha256": sha256(args.fixture),
        "backend": "hybrid raw",
        "rows": rows,
        "claim_boundary": "Synthetic-fixture abstention diagnostic only; no frontier model, human labels, or enterprise NIL labels.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "rows": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
