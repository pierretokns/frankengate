#!/usr/bin/env python3
"""Bounded ComRAG-style centroid-memory benchmark on public trace sessions.

This is a retrieval/memory-mechanics experiment, not an answer-quality claim.
It fetches a bounded chronological sample through the Hugging Face rows API,
keeps prompts/tool-shape sets locally only for the run, and emits aggregates
plus a content hash.  A repeated normalized tool shape or project match is a
proxy for recurrence, not semantic task equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


DATASET = "zhiyaowang/dataclaw-zhiyaowang"
REVISION = "f5157333cbc22489661122a9bc5347b137144900"
ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clean(text: str) -> str:
    text = re.sub(r"<[^>]{1,160}>", " ", text or "")
    text = re.sub(r"/private/tmp/[^\s]+", " ", text)
    return " ".join(text.split())


def normalized_call(call: dict[str, Any]) -> str:
    tool = str(call.get("tool") or call.get("name") or "").lower()
    inputs = call.get("input")
    keys = sorted(str(key).lower() for key in inputs) if isinstance(inputs, dict) else []
    return sha256_json({"tool": tool, "input_keys": keys})[:16]


@dataclass(frozen=True)
class Session:
    prompt: str
    project: str
    shapes: frozenset[str]
    has_error: bool
    start_time: str
    raw_digest: str


def extract_session(row: dict[str, Any]) -> Session | None:
    messages = row.get("messages") if isinstance(row.get("messages"), list) else []
    prompts: list[str] = []
    shapes: set[str] = set()
    has_error = False
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").lower() == "user" and isinstance(message.get("content"), str):
            if len(prompts) < 3:
                prompts.append(clean(message["content"])[:1400])
        uses = message.get("tool_uses") if isinstance(message.get("tool_uses"), list) else []
        for call in uses:
            if not isinstance(call, dict):
                continue
            shapes.add(normalized_call(call))
            status = str(call.get("status") or "").lower()
            output = call.get("output")
            if isinstance(output, dict):
                status = status or str(output.get("status") or "").lower()
                raw = output.get("raw")
                if isinstance(raw, dict) and raw.get("stderr"):
                    has_error = True
            if status in {"error", "failed", "failure", "interrupted"}:
                has_error = True
    prompt = "\n".join(part for part in prompts if part)
    if not prompt:
        return None
    return Session(
        prompt=prompt,
        project=str(row.get("project") or "<unknown>"),
        shapes=frozenset(shapes),
        has_error=has_error,
        start_time=str(row.get("start_time") or ""),
        raw_digest=sha256_json({"session_id": row.get("session_id"), "start_time": row.get("start_time")}),
    )


def fetch_rows(offset: int, length: int, timeout: int) -> tuple[int, list[dict[str, Any]], str]:
    params = urllib.parse.urlencode({
        "dataset": DATASET,
        "config": "default",
        "split": "train",
        "offset": offset,
        "length": length,
    })
    url = f"{ROWS_ENDPOINT}?{params}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = [item.get("row") for item in payload.get("rows", []) if isinstance(item, dict) and isinstance(item.get("row"), dict)]
    return int(payload.get("num_rows_total", 0)), rows, sha256_json(payload)


@dataclass
class Cluster:
    centroid: np.ndarray
    members: list[int] = field(default_factory=list)
    representative: int = -1
    representative_quality: int = -1


class CentroidStore:
    """Online threshold clustering with bounded representative memory."""

    def __init__(self, *, threshold: float, max_clusters: int):
        self.threshold = threshold
        self.max_clusters = max_clusters
        self.clusters: list[Cluster] = []

    @staticmethod
    def similarity(left: np.ndarray, right: np.ndarray) -> float:
        left_norm = np.linalg.norm(left)
        right_norm = np.linalg.norm(right)
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return float(np.dot(left, right) / (left_norm * right_norm))

    def _merge_closest(self) -> None:
        if len(self.clusters) < 2:
            return
        best: tuple[float, int, int] | None = None
        for left in range(len(self.clusters)):
            for right in range(left + 1, len(self.clusters)):
                score = self.similarity(self.clusters[left].centroid, self.clusters[right].centroid)
                candidate = (score, left, right)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        _, left, right = best
        first, second = self.clusters[left], self.clusters[right]
        members = first.members + second.members
        if first.representative_quality >= second.representative_quality:
            representative, quality = first.representative, first.representative_quality
        else:
            representative, quality = second.representative, second.representative_quality
        merged = Cluster(
            centroid=np.mean([first.centroid, second.centroid], axis=0),
            members=members,
            representative=representative,
            representative_quality=quality,
        )
        self.clusters = [cluster for index, cluster in enumerate(self.clusters) if index not in {left, right}]
        self.clusters.append(merged)

    def add(self, vector: np.ndarray, item_index: int, quality: int) -> None:
        if not self.clusters:
            self.clusters.append(Cluster(vector.copy(), [item_index], item_index, quality))
            return
        similarities = [self.similarity(vector, cluster.centroid) for cluster in self.clusters]
        index = int(np.argmax(similarities))
        if similarities[index] < self.threshold:
            if len(self.clusters) >= self.max_clusters:
                self._merge_closest()
                similarities = [self.similarity(vector, cluster.centroid) for cluster in self.clusters]
                index = int(np.argmax(similarities))
            else:
                self.clusters.append(Cluster(vector.copy(), [item_index], item_index, quality))
                return
        cluster = self.clusters[index]
        cluster.members.append(item_index)
        cluster.centroid = np.mean([cluster.centroid, vector], axis=0)
        if quality > cluster.representative_quality:
            cluster.representative = item_index
            cluster.representative_quality = quality

    def retrieve(self, vector: np.ndarray) -> int | None:
        if not self.clusters:
            return None
        index = int(np.argmax([self.similarity(vector, cluster.centroid) for cluster in self.clusters]))
        return self.clusters[index].representative


def hit(candidate: int | None, target: Session, sessions: Sequence[Session]) -> tuple[bool, bool]:
    if candidate is None:
        return False, False
    selected = sessions[candidate]
    return bool(target.shapes and selected.shapes & target.shapes), selected.project == target.project


def run(sessions: Sequence[Session], *, train_fraction: float, threshold: float, max_clusters: int) -> dict[str, Any]:
    split = max(1, min(len(sessions) - 1, int(len(sessions) * train_fraction)))
    train, test = list(sessions[:split]), list(sessions[split:])
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=50_000)
    vectors = vectorizer.fit_transform([session.prompt for session in sessions]).toarray().astype(np.float32)
    full_history: list[int] = []
    store = CentroidStore(threshold=threshold, max_clusters=max_clusters)
    high_store = CentroidStore(threshold=threshold, max_clusters=max_clusters)
    low_store = CentroidStore(threshold=threshold, max_clusters=max_clusters)
    rows: list[dict[str, Any]] = []
    for index, target in enumerate(test, start=split):
        query_vector = vectors[index]
        static_candidate = None
        if full_history:
            static_candidate = max(full_history, key=lambda item: CentroidStore.similarity(query_vector, vectors[item]))
        centroid_candidate = store.retrieve(query_vector)
        quality_candidate = high_store.retrieve(query_vector)
        if quality_candidate is None:
            quality_candidate = low_store.retrieve(query_vector)
        static_shape, static_project = hit(static_candidate, target, sessions)
        centroid_shape, centroid_project = hit(centroid_candidate, target, sessions)
        quality_shape, quality_project = hit(quality_candidate, target, sessions)
        rows.append({
            "position": index,
            "has_shape_overlap_in_history": bool(target.shapes and any(target.shapes & sessions[item].shapes for item in full_history)),
            "static_shape_hit": static_shape,
            "static_project_hit": static_project,
            "centroid_shape_hit": centroid_shape,
            "centroid_project_hit": centroid_project,
            "quality_routed_shape_hit": quality_shape,
            "quality_routed_project_hit": quality_project,
            "cluster_count_before_update": len(store.clusters),
        })
        quality = 0 if target.has_error else 1
        full_history.append(index)
        store.add(query_vector, index, quality)
        (low_store if target.has_error else high_store).add(query_vector, index, quality)
    def mean(key: str) -> float:
        return sum(1 for row in rows if row[key]) / len(rows) if rows else 0.0
    return {
        "train_sessions": len(train),
        "test_sessions": len(test),
        "threshold": threshold,
        "max_clusters": max_clusters,
        "mean_cluster_count_before_update": sum(row["cluster_count_before_update"] for row in rows) / len(rows) if rows else 0.0,
        "final_all_cluster_count": len(store.clusters),
        "final_high_cluster_count": len(high_store.clusters),
        "final_low_cluster_count": len(low_store.clusters),
        "history_shape_overlap_rate": mean("has_shape_overlap_in_history"),
        "static_shape_hit_rate": mean("static_shape_hit"),
        "centroid_shape_hit_rate": mean("centroid_shape_hit"),
        "quality_routed_shape_hit_rate": mean("quality_routed_shape_hit"),
        "static_project_hit_rate": mean("static_project_hit"),
        "centroid_project_hit_rate": mean("centroid_project_hit"),
        "quality_routed_project_hit_rate": mean("quality_routed_project_hit"),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--length", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--max-clusters", type=int, default=12)
    parser.add_argument("--output", type=argparse.FileType("w"), required=True)
    args = parser.parse_args()
    total, raw_rows, payload_digest = fetch_rows(args.offset, args.length, args.timeout)
    sessions = [session for row in raw_rows if (session := extract_session(row)) is not None]
    sessions.sort(key=lambda session: (session.start_time, session.raw_digest))
    result = {
        "schema_version": "frankengate-comrag-centroid-trace-benchmark-v1",
        "dataset": {"name": DATASET, "revision": REVISION, "total_rows": total, "offset": args.offset, "requested_rows": args.length, "parseable_sessions": len(sessions), "payload_sha256": payload_digest},
        "mechanism": {"threshold": args.threshold, "max_clusters": args.max_clusters, "quality_proxy": "sessions with explicit tool errors are low quality; all others high", "embedding": "TF-IDF word+bigram vectors", "order": "source start_time, then content digest"},
        "claim_boundary": "Recurrence and project matches are proxies; this tests centroid compression and quality routing, not answer correctness, artifact portability, authorization, or user benefit.",
        "result": run(sessions, train_fraction=args.train_fraction, threshold=args.threshold, max_clusters=args.max_clusters),
        "next_gate": "Repeat on timestamp-ordered consented traces with validated outcomes, stale/conflict mutations, and dense embeddings; compare static, centroid, and hybrid stores under a fixed memory/cost budget.",
    }
    args.output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"parseable_sessions": len(sessions), "result": {key: value for key, value in result["result"].items() if key != "rows"}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
