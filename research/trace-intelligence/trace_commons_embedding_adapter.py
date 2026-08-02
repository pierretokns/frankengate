#!/usr/bin/env python3
"""Leave-one-project-out lexical/domain-adapter probe on Trace Commons.

This is a small, transparent representation-adaptation baseline.  It learns
token weights from same-workstream versus cross-workstream co-occurrence on
training projects, then evaluates retrieval on a held-out project.  It is not
a neural embedding or an enterprise quality claim; it tests whether supervised
domain weighting can transfer beyond memorized project names.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from trace_commons_feature_ablation import GENERIC_LABELS, cosine, load_sessions, tfidf


SCHEMA_VERSION = "frankengate-trace-commons-domain-adapter-v1"


def docs(sessions: list[dict[str, Any]], mode: str) -> list[Counter[str]]:
    output = []
    for row in sessions:
        document = Counter()
        if mode in {"prompt", "combined"}:
            document.update({f"prompt:{key}": value for key, value in row["prompt"].items()})
        if mode in {"identifier", "combined"}:
            document.update({f"id:{key}": value for key, value in row["identifier"].items()})
        output.append(document)
    return output


def adapter_weights(train_docs: list[Counter[str]], train_labels: list[str]) -> dict[str, float]:
    positive = Counter()
    negative = Counter()
    for left in range(len(train_docs)):
        for right in range(left + 1, len(train_docs)):
            overlap = set(train_docs[left]) & set(train_docs[right])
            target = positive if train_labels[left] == train_labels[right] else negative
            for token in overlap:
                target[token] += 1
    weights = {}
    for token in set(positive) | set(negative):
        # A small additive prior prevents a token seen in one pair from being
        # assigned an unbounded weight.  Clip to keep the adapter auditable.
        ratio = math.log((positive[token] + 1.0) / (negative[token] + 1.0))
        weights[token] = min(2.0, max(-2.0, ratio))
    return weights


def apply_adapter(vector: dict[str, float], weights: dict[str, float]) -> dict[str, float]:
    return {token: value * math.exp(weights.get(token, 0.0)) for token, value in vector.items()}


def evaluate(sessions: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    label_counts = Counter(row["label"] for row in sessions)
    eligible_labels = sorted(label for label, count in label_counts.items() if count >= 2 and label not in GENERIC_LABELS)
    eligible_indices = [index for index, row in enumerate(sessions) if row["label"] in eligible_labels]
    all_docs = docs(sessions, mode)
    base_vectors = tfidf(all_docs)
    baseline_top1 = baseline_mrr = adapted_top1 = adapted_mrr = evaluated = 0
    fold_rows = []
    for heldout in eligible_labels:
        train_indices = [index for index in eligible_indices if sessions[index]["label"] != heldout]
        test_indices = [index for index in eligible_indices if sessions[index]["label"] == heldout]
        if not train_indices or not test_indices:
            continue
        weights = adapter_weights([all_docs[index] for index in train_indices], [sessions[index]["label"] for index in train_indices])
        adapted_vectors = [apply_adapter(vector, weights) for vector in base_vectors]
        fold_baseline_top1 = fold_adapted_top1 = 0
        fold_baseline_mrr = fold_adapted_mrr = 0.0
        for target in test_indices:
            candidates = [index for index in eligible_indices if index != target]
            baseline_ranked = sorted(((cosine(base_vectors[target], base_vectors[index]), index) for index in candidates), reverse=True)
            adapted_ranked = sorted(((cosine(adapted_vectors[target], adapted_vectors[index]), index) for index in candidates), reverse=True)
            target_label = sessions[target]["label"]
            baseline_position = next((rank + 1 for rank, (_, index) in enumerate(baseline_ranked) if sessions[index]["label"] == target_label), None)
            adapted_position = next((rank + 1 for rank, (_, index) in enumerate(adapted_ranked) if sessions[index]["label"] == target_label), None)
            if baseline_position is None or adapted_position is None:
                continue
            evaluated += 1
            fold_baseline_top1 += int(baseline_position == 1)
            fold_adapted_top1 += int(adapted_position == 1)
            fold_baseline_mrr += 1.0 / baseline_position
            fold_adapted_mrr += 1.0 / adapted_position
        baseline_top1 += fold_baseline_top1
        adapted_top1 += fold_adapted_top1
        baseline_mrr += fold_baseline_mrr
        adapted_mrr += fold_adapted_mrr
        fold_rows.append({"heldout_project": heldout, "test_sessions": len(test_indices), "baseline_top1": fold_baseline_top1, "adapter_top1": fold_adapted_top1, "baseline_mrr_sum": fold_baseline_mrr, "adapter_mrr_sum": fold_adapted_mrr, "train_projects": len(eligible_labels) - 1})
    return {"evaluated_sessions": evaluated, "baseline_top1": baseline_top1, "adapter_top1": adapted_top1, "baseline_top1_rate": baseline_top1 / evaluated if evaluated else 0.0, "adapter_top1_rate": adapted_top1 / evaluated if evaluated else 0.0, "baseline_mrr": baseline_mrr / evaluated if evaluated else 0.0, "adapter_mrr": adapted_mrr / evaluated if evaluated else 0.0, "folds": fold_rows}


def run(root: Path, output: Path) -> dict[str, Any]:
    sessions = load_sessions(root.resolve())
    aggregate = {mode: evaluate(sessions, mode) for mode in ("prompt", "identifier", "combined")}
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"session_count": len(sessions), "raw_content_committed": False, "adapter": "same-project versus cross-project token co-occurrence, clipped log-ratio weights"},
        "aggregate": aggregate,
        "claim_boundary": {"leave_one_project_out": True, "domain_adapter_measured": True, "neural_embedding_established": False, "enterprise_quality_established": False, "cross_user_skill_gain_established": False, "reason": "Trace Commons project labels are workstream proxies without stable principal identity, semantic labels, or prospective outcomes."},
    }
    receipt["result_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": {mode: {key: value for key, value in row.items() if key != "folds"} for mode, row in aggregate.items()}, "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
