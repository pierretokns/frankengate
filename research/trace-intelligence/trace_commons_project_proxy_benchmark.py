#!/usr/bin/env python3
"""Measure session similarity against repeated-project proxies.

The corpus has no principal identity, so this is deliberately a project/workstream
proxy benchmark. Raw prompts are consumed locally and never written to the receipt.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

STOP = {
    "the", "and", "for", "that", "this", "with", "from", "have", "has", "are",
    "was", "were", "you", "your", "can", "not", "but", "what", "how", "please",
    "use", "using", "into", "then", "than", "only", "also", "its", "it's", "a", "an",
    "to", "of", "in", "on", "is", "be", "as", "or", "it", "do", "does", "i", "we",
}


def project_proxy(cwd: str) -> str:
    path = cwd.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", path):
        parts = [p for p in path.split("/") if p][1:]
    elif re.match(r"^/(?:Users|home)/", path):
        parts = [p for p in path.split("/") if p][2:]
    else:
        parts = [p for p in path.split("/") if p]
    # Generic home-directory buckets are not project labels.
    return (parts[0].lower() if parts else "<none>")


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9_./:-]{2,}", text.lower())
    return [w for w in words if w not in STOP and not re.fullmatch(r"[0-9a-f]{8,}", w)]


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def tfidf(documents: list[Counter]) -> list[dict[str, float]]:
    n = len(documents)
    df = Counter(k for doc in documents for k in doc)
    result = []
    for doc in documents:
        row = {}
        for key, count in doc.items():
            row[key] = (1.0 + math.log(count)) * math.log((n + 1) / (df[key] + 1))
        result.append(row)
    return result


def load_sessions(root: Path) -> list[dict]:
    sessions = []
    for path in sorted(root.rglob("*.jsonl")):
        events = Counter()
        prompt_terms = Counter()
        tools = Counter()
        cwds = []
        for line in path.open(encoding="utf-8", errors="ignore"):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events[str(event.get("type", "<missing>"))] += 1
            if isinstance(event.get("cwd"), str):
                cwds.append(event["cwd"])
            if event.get("type") == "user":
                message = event.get("message")
                content = message.get("content") if isinstance(message, dict) else ""
                if isinstance(content, str):
                    prompt_terms.update(tokens(content))
            tool_result = event.get("toolUseResult")
            if isinstance(tool_result, dict):
                tools[str(tool_result.get("type", "<missing>"))] += 1
        labels = Counter(project_proxy(cwd) for cwd in cwds)
        label = labels.most_common(1)[0][0] if labels else "<none>"
        sessions.append({"id": path.stem, "label": label, "events": events, "terms": prompt_terms, "tools": tools})
    return sessions


def vectors(sessions: list[dict], mode: str) -> list[dict[str, float]]:
    docs = []
    for row in sessions:
        doc = Counter()
        if mode in {"structure", "combined"}:
            doc.update({f"event:{k}": v for k, v in row["events"].items()})
            doc.update({f"tool:{k}": v for k, v in row["tools"].items()})
        if mode in {"prompt", "combined"}:
            doc.update({f"term:{k}": v for k, v in row["terms"].items()})
        docs.append(doc)
    return tfidf(docs)


def run(root: Path) -> dict:
    sessions = load_sessions(root)
    label_counts = Counter(row["label"] for row in sessions)
    eligible = [i for i, row in enumerate(sessions) if label_counts[row["label"]] >= 2 and row["label"] not in {"users", "<none>"}]
    arms = {}
    for mode in ("structure", "prompt", "combined"):
        vecs = vectors(sessions, mode)
        top1 = 0
        reciprocal = 0.0
        evaluated = 0
        for i in eligible:
            ranked = sorted(
                ((cosine(vecs[i], vecs[j]), j) for j in range(len(sessions)) if j != i),
                reverse=True,
            )
            if not ranked:
                continue
            evaluated += 1
            first_same = next((rank + 1 for rank, (_, j) in enumerate(ranked) if sessions[j]["label"] == sessions[i]["label"]), None)
            if first_same is not None:
                reciprocal += 1.0 / first_same
                if first_same == 1:
                    top1 += 1
        arms[mode] = {
            "evaluated_sessions": evaluated,
            "same_project_top1": top1,
            "top1_rate": top1 / evaluated if evaluated else 0.0,
            "same_project_mrr": reciprocal / evaluated if evaluated else 0.0,
        }
    return {
        "schema": "trace-commons-project-proxy-benchmark-v1",
        "session_count": len(sessions),
        "eligible_repeated_project_sessions": len(eligible),
        "project_proxy_counts": dict(sorted(label_counts.items())),
        "arms": arms,
        "interpretation": "Project/workstream proxy only; no user identity or cross-user claim is valid.",
        "content_policy": "Prompts are processed locally; no transcript text or token is emitted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
