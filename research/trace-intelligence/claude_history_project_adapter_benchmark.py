#!/usr/bin/env python3
"""Project-held-out lexical adaptation on a real Claude history export.

Project directories are silver workstream labels.  The receipt contains only
aggregate retrieval metrics and project-label hashes; no transcript, term,
path, or identifier text is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dataclaw_project_adapter_benchmark import adapt, digest, metric, vectors, weights


SCHEMA_VERSION = "frankengate-claude-history-project-adapter-v1"
TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.I)
STOP = frozenset("a an and are as at by for from how i in into is it of on or the this to use with you".split())


def text_parts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(text_parts(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for key in ("text", "content", "input", "output"):
            if key in value:
                out.extend(text_parts(value[key]))
        return out
    return []


def tokens(text: str, prefix: str) -> Counter[str]:
    return Counter(prefix + token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOP)


def manifest(root: Path) -> tuple[int, int, str]:
    rows: list[tuple[str, int]] = []
    total = 0
    for path in sorted(root.rglob("*.jsonl")):
        size = path.stat().st_size
        total += size
        rows.append((str(path.relative_to(root)), size))
    return len(rows), total, hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.jsonl")):
        user_parts: list[str] = []
        all_parts: list[str] = []
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = record.get("message") if isinstance(record, dict) else None
                    if not isinstance(message, dict):
                        continue
                    parts = [part for part in text_parts(message.get("content")) if part.strip()]
                    if not parts:
                        continue
                    text = "\n".join(parts)
                    all_parts.append(text)
                    if message.get("role") == "user":
                        user_parts.append(text)
        except OSError:
            continue
        if not all_parts:
            continue
        project = path.parent.name
        rows.append(
            {
                "label": project,
                "label_hash": digest(project),
                "prompt": tokens("\n".join(user_parts), "p:"),
                "all": tokens("\n".join(all_parts), "m:"),
            }
        )
    return rows


def fast_cosine(left: dict[str, float], right: dict[str, float], left_norm: float, right_norm: float) -> float:
    if not left_norm or not right_norm:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items()) / (left_norm * right_norm)


def fast_evaluate(rows: list[dict[str, Any]], mode: str, pair_cap: int) -> dict[str, Any]:
    labels = [row["label"] for row in rows]
    eligible = sorted(label for label, count in Counter(labels).items() if count >= 2)
    eligible_indices = [index for index, label in enumerate(labels) if label in eligible]
    docs = [row[mode] for row in rows]
    all_base: list[dict[str, float]] = []
    all_adapted: list[dict[str, float]] = []
    folds: list[dict[str, Any]] = []
    for heldout in eligible:
        train = [index for index in eligible_indices if labels[index] != heldout]
        test = [index for index in eligible_indices if labels[index] == heldout]
        base = vectors(docs, train)
        fold_weights = weights(docs, labels, train, pair_cap)
        adapted = [adapt(vector, fold_weights) for vector in base]
        base_norms = [sum(value * value for value in vector.values()) ** 0.5 for vector in base]
        adapted_norms = [sum(value * value for value in vector.values()) ** 0.5 for vector in adapted]
        fold_base: list[dict[str, float]] = []
        fold_adapted: list[dict[str, float]] = []
        for target in test:
            candidates = [index for index in eligible_indices if index != target]
            base_order = sorted(candidates, key=lambda index: (-fast_cosine(base[target], base[index], base_norms[target], base_norms[index]), index))
            adapted_order = sorted(candidates, key=lambda index: (-fast_cosine(adapted[target], adapted[index], adapted_norms[target], adapted_norms[index]), index))
            base_metric = metric(base_order, target, labels)
            adapted_metric = metric(adapted_order, target, labels)
            fold_base.append(base_metric)
            fold_adapted.append(adapted_metric)
            all_base.append(base_metric)
            all_adapted.append(adapted_metric)
        folds.append(
            {
                "held_out_project_hash": digest(heldout),
                "train_sessions": len(train),
                "test_sessions": len(test),
                "training_feature_count": len(fold_weights),
                "baseline_mrr": sum(item["mrr"] for item in fold_base) / len(fold_base),
                "adapted_mrr": sum(item["mrr"] for item in fold_adapted) / len(fold_adapted),
            }
        )
    mean = lambda values, key: round(sum(item[key] for item in values) / len(values), 6) if values else 0.0
    return {
        "eligible_projects": len(eligible),
        "eligible_sessions": len(eligible_indices),
        "folds": len(folds),
        "baseline_mrr": mean(all_base, "mrr"),
        "adapted_mrr": mean(all_adapted, "mrr"),
        "baseline_recall_at_1": mean(all_base, "recall_at_1"),
        "adapted_recall_at_1": mean(all_adapted, "recall_at_1"),
        "baseline_recall_at_5": mean(all_base, "recall_at_5"),
        "adapted_recall_at_5": mean(all_adapted, "recall_at_5"),
        "folds_detail": folds,
    }


def run(root: Path, output: Path, pair_cap: int = 500) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = manifest(root)
    rows = load(root)
    eligible_projects = sum(1 for count in Counter(row["label"] for row in rows).values() if count >= 2)
    aggregate = {mode: fast_evaluate(rows, mode, pair_cap) for mode in ("prompt", "all")}
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": file_count,
            "byte_count": byte_count,
            "manifest_sha256": manifest_hash,
            "session_count": len(rows),
            "raw_content_committed": False,
        },
        "protocol": {
            "split": "leave-one-project-out",
            "representations": "user-message tokens versus all textual message tokens; project names excluded",
            "adapter": "fold-local same-project versus cross-project token log-ratio weights",
            "pair_cap_per_token": pair_cap,
            "labels": "project directory labels as silver workstream proxies",
        },
        "eligible_project_count": eligible_projects,
        "aggregate": aggregate,
        "claim_boundary": {
            "project_heldout_adaptation_measured": True,
            "neural_embedding_established": False,
            "enterprise_semantics_established": False,
            "artifact_utility_established": False,
            "promotion_authorized": False,
            "reason": "Project labels are silver workstream proxies; retrieval similarity does not establish task intent, artifact correctness, or user benefit.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({mode: {k: v for k, v in stats.items() if k != "folds_detail"} for mode, stats in aggregate.items()}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pair-cap", type=int, default=500)
    args = parser.parse_args()
    run(args.input, args.output, args.pair_cap)
