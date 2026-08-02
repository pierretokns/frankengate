#!/usr/bin/env python3
"""Ablate prompt, structure, and durable-identifier features on Trace Commons.

Trace Commons has no stable principal labels.  The repeated project/workspace
component of ``cwd`` is therefore used only as a clearly labeled workstream
proxy.  Raw transcript content is consumed locally and never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-trace-commons-feature-ablation-v1"
GENERIC_LABELS = frozenset({"<none>", "users", "documents", "desktop", "code"})
STOP = frozenset(
    "a an and are as at by for from how in into is of on or per please return the to what which with this that have has was were you your can not but use using then than only also its it's we i do does be it"
    .split()
)
TOKEN_RE = re.compile(r"[a-z][a-z0-9_./:-]{2,}")
PATH_RE = re.compile(r"(?:[A-Za-z]:[/\\]|/)[^\s\"']+")


def project_proxy(cwd: str) -> str:
    path = cwd.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", path):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[1].lower() in {"users", "home"}:
            parts = parts[3:]
        else:
            parts = parts[1:]
    elif re.match(r"^/(?:Users|home)/", path):
        parts = [p for p in path.split("/") if p][2:]
    else:
        parts = [p for p in path.split("/") if p]
    return parts[0].lower() if parts else "<none>"


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP and not re.fullmatch(r"[0-9a-f]{8,}", t)]


def tfidf(documents: list[Counter[str]]) -> list[dict[str, float]]:
    n = len(documents)
    df = Counter(token for document in documents for token in document)
    vectors = []
    for document in documents:
        vector = {}
        for token, count in document.items():
            vector[token] = (1.0 + math.log(count)) * math.log((n + 1) / (df[token] + 1))
        vectors.append(vector)
    return vectors


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    denominator = math.sqrt(sum(v * v for v in left.values())) * math.sqrt(sum(v * v for v in right.values()))
    return sum(v * right.get(k, 0.0) for k, v in left.items()) / denominator if denominator else 0.0


def _content_text(value: Any, *, include_content: bool = False) -> list[str]:
    if isinstance(value, str):
        return [value] if include_content else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_content_text(item, include_content=include_content))
        return result
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            if key in {"filePath", "file", "filenames", "query", "command", "prompt", "path", "oldString", "newString"}:
                result.extend(_content_text(item, include_content=True))
            elif key in {"content", "stdout", "stderr", "originalFile", "structuredPatch"} and include_content:
                result.extend(_content_text(item, include_content=True))
            elif isinstance(item, (dict, list)):
                result.extend(_content_text(item, include_content=include_content))
        return result
    return []


def load_sessions(root: Path) -> list[dict[str, Any]]:
    sessions = []
    for path in sorted(root.rglob("*.jsonl")):
        events = Counter()
        prompt_terms = Counter()
        identifier_terms = Counter()
        labels = Counter()
        for line in path.open(encoding="utf-8", errors="ignore"):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events[str(event.get("type", "<missing>"))] += 1
            cwd = event.get("cwd")
            if isinstance(cwd, str):
                labels[project_proxy(cwd)] += 1
            if event.get("type") == "user":
                message = event.get("message")
                content = message.get("content") if isinstance(message, dict) else ""
                for term in _content_text(content, include_content=True):
                    prompt_terms.update(tokens(term))
            tool_result = event.get("toolUseResult")
            if isinstance(tool_result, dict):
                for text in _content_text(tool_result):
                    identifier_terms.update(tokens(text))
        label = labels.most_common(1)[0][0] if labels else "<none>"
        sessions.append({"id": path.stem, "label": label, "events": events, "prompt": prompt_terms, "identifier": identifier_terms})
    return sessions


def evaluate(sessions: list[dict[str, Any]], mode: str, *, mask_labels: bool) -> dict[str, Any]:
    labels = {row["label"] for row in sessions}
    documents = []
    for row in sessions:
        document = Counter()
        if mode in {"structure", "combined", "identifier"}:
            document.update({f"event:{key}": value for key, value in row["events"].items()})
        if mode in {"prompt", "combined"}:
            document.update({f"prompt:{key}": value for key, value in row["prompt"].items()})
        if mode in {"identifier", "combined"}:
            document.update({f"id:{key}": value for key, value in row["identifier"].items()})
        if mask_labels and row["label"] not in {"<none>", "users"}:
            document = Counter({key: value for key, value in document.items() if row["label"] not in key})
        documents.append(document)
    vectors = tfidf(documents)
    eligible = [i for i, row in enumerate(sessions) if labels and sum(other["label"] == row["label"] for other in sessions) >= 2 and row["label"] not in GENERIC_LABELS]
    top1 = 0
    reciprocal = 0.0
    evaluated = 0
    for index in eligible:
        ranked = sorted(((cosine(vectors[index], vectors[j]), j) for j in range(len(sessions)) if j != index), reverse=True)
        first_same = next((rank + 1 for rank, (_, candidate) in enumerate(ranked) if sessions[candidate]["label"] == sessions[index]["label"]), None)
        if first_same is None:
            continue
        evaluated += 1
        top1 += int(first_same == 1)
        reciprocal += 1.0 / first_same
    return {"evaluated_sessions": evaluated, "same_project_top1": top1, "top1_rate": top1 / evaluated if evaluated else 0.0, "same_project_mrr": reciprocal / evaluated if evaluated else 0.0}


def run(root: Path, output: Path) -> dict[str, Any]:
    sessions = load_sessions(root.resolve())
    label_counts = Counter(row["label"] for row in sessions)
    manifest_rows = []
    for path in sorted(root.resolve().rglob("*.jsonl")):
        manifest_rows.append({"path": str(path.relative_to(root.resolve())), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest_digest = hashlib.sha256(json.dumps(manifest_rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    arms = {}
    for mode in ("structure", "prompt", "identifier", "combined"):
        for mask in (False, True):
            arms[f"{mode}{'_masked' if mask else ''}"] = evaluate(sessions, mode, mask_labels=mask)
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"session_count": len(sessions), "session_file_count": len(manifest_rows), "manifest_sha256": manifest_digest, "raw_content_committed": False},
        "cohort": {"eligible_repeated_project_sessions": sum(count for label, count in label_counts.items() if count >= 2 and label not in GENERIC_LABELS), "project_proxy_counts": dict(sorted(label_counts.items()))},
        "arms": arms,
        "claim_boundary": {"workstream_proxy_measured": True, "cross_user_identity_established": False, "skill_gap_established": False, "enterprise_outcome_established": False, "reason": "Trace Commons has project/workspace proxies but no stable principal identity, semantic task labels, or prospective outcomes."},
    }
    receipt["result_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": arms, "result_sha256": receipt["result_sha256"]}, sort_keys=True))
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
