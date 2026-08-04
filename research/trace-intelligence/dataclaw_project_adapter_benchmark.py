#!/usr/bin/env python3
"""Project-held-out lexical adaptation on a DataClaw export.

Project labels are silver workstream proxies; prompts, tool arguments, and
project names never enter the committed receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "frankengate-dataclaw-project-adapter-v1"
TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.I)
STOP = frozenset("a an and are as at by for from how i in into is it of on or the this to use with you".split())


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tokens(text: str) -> list[str]:
    return [x.lower() for x in TOKEN_RE.findall(text) if x.lower() not in STOP]


def load(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict) or not isinstance(value.get("messages"), list):
                continue
            prompt: list[str] = []
            tools: list[str] = []
            for message in value["messages"]:
                if not isinstance(message, dict):
                    continue
                if message.get("role") == "user" and isinstance(message.get("content"), str):
                    prompt.extend(tokens(message["content"]))
                if message.get("role") == "assistant":
                    for call in message.get("tool_uses", []):
                        if isinstance(call, dict):
                            tools.extend(tokens(str(call.get("tool", "<missing>"))))
            project = str(value.get("project") or "<missing>")
            prompt_counter = Counter("p:" + x for x in prompt)
            tool_counter = Counter("t:" + x for x in tools)
            rows.append({"label": project, "label_hash": digest(project), "prompt": prompt_counter, "tool": tool_counter, "combined": prompt_counter + tool_counter})
    return rows


def vectors(docs: list[Counter[str]], train: list[int]) -> list[dict[str, float]]:
    df = Counter()
    for i in train:
        df.update(set(docs[i]))
    n = max(1, len(train))
    out = []
    for doc in docs:
        total = max(1, sum(doc.values()))
        out.append({k: (v / total) * (math.log((n + 1) / (df.get(k, 0) + 1)) + 1.0) for k, v in doc.items()})
    return out


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    shared = set(a) & set(b)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return sum(a[k] * b[k] for k in shared) / den if den else 0.0


def weights(docs: list[Counter[str]], labels: list[str], train: list[int], pair_cap: int) -> dict[str, float]:
    pos, neg = Counter(), Counter()
    postings: dict[str, list[int]] = defaultdict(list)
    for index in train:
        for token in docs[index]:
            postings[token].append(index)
    for token, members in postings.items():
        for pair_index, (left, right) in enumerate(combinations(members, 2)):
            # Common prompt tokens can create a quadratic pair explosion. The
            # deterministic prefix cap keeps this silver baseline bounded.
            if pair_index >= pair_cap:
                break
            bucket = pos if labels[left] == labels[right] else neg
            bucket[token] += 1
    return {token: max(-2.0, min(2.0, math.log((pos[token] + 1) / (neg[token] + 1)))) for token in set(pos) | set(neg)}


def adapt(vector: dict[str, float], weight: dict[str, float]) -> dict[str, float]:
    return {k: v * math.exp(weight.get(k, 0.0)) for k, v in vector.items()}


def metric(order: list[int], target: int, labels: list[str]) -> dict[str, float]:
    positions = [rank for rank, index in enumerate(order, 1) if labels[index] == labels[target]]
    first = positions[0] if positions else None
    return {"recall_at_1": float(first == 1), "recall_at_5": float(first is not None and first <= 5), "mrr": 1.0 / first if first else 0.0}


def evaluate(rows: list[dict[str, Any]], mode: str, pair_cap: int) -> dict[str, Any]:
    labels = [row["label"] for row in rows]
    eligible = sorted(label for label, count in Counter(labels).items() if count >= 2)
    eligible_indices = [i for i, label in enumerate(labels) if label in eligible]
    docs = [row[mode] for row in rows]
    all_base, all_adapted, folds = [], [], []
    for heldout in eligible:
        train = [i for i in eligible_indices if labels[i] != heldout]
        test = [i for i in eligible_indices if labels[i] == heldout]
        base = vectors(docs, train)
        fold_weights = weights(docs, labels, train, pair_cap)
        adapted = [adapt(x, fold_weights) for x in base]
        fold_base, fold_adapted = [], []
        for target in test:
            candidates = [i for i in eligible_indices if i != target]
            bo = sorted(candidates, key=lambda i: (-cosine(base[target], base[i]), i))
            ao = sorted(candidates, key=lambda i: (-cosine(adapted[target], adapted[i]), i))
            bm, am = metric(bo, target, labels), metric(ao, target, labels)
            fold_base.append(bm); fold_adapted.append(am); all_base.append(bm); all_adapted.append(am)
        folds.append({"held_out_project_hash": digest(heldout), "train_sessions": len(train), "test_sessions": len(test), "training_feature_count": len(fold_weights), "baseline_mrr": sum(x["mrr"] for x in fold_base) / len(fold_base), "adapted_mrr": sum(x["mrr"] for x in fold_adapted) / len(fold_adapted)})
    mean = lambda values, key: round(sum(x[key] for x in values) / len(values), 6) if values else 0.0
    return {"eligible_projects": len(eligible), "eligible_sessions": len(eligible_indices), "folds": len(folds), "baseline_mrr": mean(all_base, "mrr"), "adapted_mrr": mean(all_adapted, "mrr"), "baseline_recall_at_1": mean(all_base, "recall_at_1"), "adapted_recall_at_1": mean(all_adapted, "recall_at_1"), "baseline_recall_at_5": mean(all_base, "recall_at_5"), "adapted_recall_at_5": mean(all_adapted, "recall_at_5"), "folds_detail": folds}


def run(path: Path, output: Path, max_sessions: int | None = None, pair_cap: int = 5000, modes: tuple[str, ...] = ("prompt", "tool", "combined")) -> dict[str, Any]:
    rows = load(path.resolve(strict=True))
    if max_sessions is not None:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(row["label"], []).append(row)
        selected: list[dict[str, Any]] = []
        # Round-robin over projects to avoid making a prefix-only temporal
        # sample look like a project-held-out benchmark.
        while len(selected) < max_sessions and groups:
            for label in sorted(list(groups)):
                bucket = groups[label]
                if bucket:
                    selected.append(bucket.pop(0))
                    if len(selected) >= max_sessions:
                        break
                if not bucket:
                    groups.pop(label, None)
        rows = selected
    aggregate = {mode: evaluate(rows, mode, pair_cap) for mode in modes}
    result = {"schema_version": SCHEMA_VERSION, "source": {"path_sha256": file_digest(path), "session_count": len(rows), "sample_limit": max_sessions, "raw_content_committed": False}, "protocol": {"split": "leave-one-project-out", "representations": "user prompts, tool names, or both; project names excluded", "adapter": "fold-local same-project versus cross-project token log-ratio weights", "pair_cap_per_token": pair_cap, "labels": "DataClaw project labels as silver workstream proxies"}, "aggregate": aggregate, "claim_boundary": {"project_heldout_adaptation_measured": True, "neural_embedding_established": False, "enterprise_semantics_established": False, "artifact_utility_established": False, "promotion_authorized": False, "reason": "Project labels are silver workstream proxies; retrieval similarity does not establish task intent, artifact correctness, or user benefit."}}
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({mode: {k: v for k, v in stats.items() if k != "folds_detail"} for mode, stats in aggregate.items()}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--max-sessions", type=int); parser.add_argument("--pair-cap", type=int, default=5000); parser.add_argument("--mode", choices=("prompt", "tool", "combined"), action="append"); args = parser.parse_args(); run(args.input, args.output, args.max_sessions, args.pair_cap, tuple(args.mode) if args.mode else ("prompt", "tool", "combined"))
