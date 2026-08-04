#!/usr/bin/env python3
"""Run an exposure-aware retrieval proxy over the public LRAT samples.

The browsed-document set is treated as silver relevance evidence only.  The
receipt contains hashes and aggregates; query, snippets, and document IDs stay
external.  This is a candidate-coverage experiment, not a correctness or
enterprise-artifact result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


SCHEMA_VERSION = "frankengate-lrat-trajectory-retrieval-proxy-v1"
DOC_RE = re.compile(r"DocID\s*[:=]\s*([A-Za-z0-9_.:-]+)", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
STOP = frozenset("a an and are as at by for from how in into is of on or per please return the to what which with".split())


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOP}


def doc_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None and parsed != value:
            return doc_ids(parsed)
        return DOC_RE.findall(value)
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int))]
    if isinstance(value, dict):
        output: list[str] = []
        for key, item in value.items():
            if str(key).lower() in {"docid", "docids", "document_id", "document_ids"}:
                if isinstance(item, (str, int)):
                    output.append(str(item))
                else:
                    output.extend(doc_ids(item))
            else:
                output.extend(doc_ids(item))
        return output
    return []


def extract_trajectories(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("result"), list):
            continue
        exposed: list[str] = []
        browsed: set[str] = set()
        snippets: dict[str, str] = defaultdict(str)
        for step in value["result"]:
            if not isinstance(step, dict) or step.get("type") != "tool_call":
                continue
            tool = str(step.get("tool_name", ""))
            arguments = step.get("arguments")
            output = step.get("output", "")
            if tool == "search":
                found = doc_ids(output)
                for identifier in found:
                    if identifier not in exposed:
                        exposed.append(identifier)
                    snippets[identifier] += " " + str(output)
            elif tool in {"visit", "get_document"}:
                browsed.update(doc_ids(arguments))
                browsed.update(doc_ids(output))
        positive = browsed & set(exposed)
        if exposed and positive:
            rows.append({
                "path_hash": file_hash(path),
                "query": str(value.get("query", "")),
                "exposed": exposed,
                "positive": positive,
                "snippets": dict(snippets),
            })
    return rows


def rank_lexical(query: str, exposed: list[str], snippets: dict[str, str]) -> list[str]:
    query_tokens = tokens(query)
    return sorted(
        exposed,
        key=lambda identifier: (-len(query_tokens & tokens(snippets.get(identifier, ""))), exposed.index(identifier)),
    )


def metrics(order: list[str], positive: set[str]) -> dict[str, float]:
    positions = [index + 1 for index, identifier in enumerate(order) if identifier in positive]
    first = positions[0] if positions else None
    return {
        "mrr": 1.0 / first if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "recall_at_10": float(first is not None and first <= 10),
        "positive_pool_recall": float(bool(positions)),
    }


def aggregate(rows: list[dict[str, float]]) -> dict[str, float]:
    return {key: round(sum(row[key] for row in rows) / len(rows), 6) for key in rows[0]} if rows else {}


def run(root: Path, model_path: Path, output: Path) -> dict[str, Any]:
    trajectories = extract_trajectories(root)
    model = SentenceTransformer(str(model_path), local_files_only=True)
    arms: dict[str, list[dict[str, float]]] = {"search_order": [], "lexical": [], "dense": []}
    counts = {"trajectories_with_exposure_and_browse_positive": len(trajectories), "exposed_documents": 0, "positive_documents": 0}
    for row in trajectories:
        exposed = row["exposed"]
        positive = set(row["positive"])
        counts["exposed_documents"] += len(exposed)
        counts["positive_documents"] += len(positive)
        lexical = rank_lexical(row["query"], exposed, row["snippets"])
        texts = [row["snippets"].get(identifier, identifier) for identifier in exposed]
        vectors = model.encode([row["query"], *texts], normalize_embeddings=True, show_progress_bar=False)
        dense_scores = np.asarray(vectors[1:]) @ np.asarray(vectors[0])
        dense = [identifier for _, identifier in sorted(zip(dense_scores.tolist(), exposed), key=lambda pair: (-pair[0], exposed.index(pair[1])))]
        arms["search_order"].append(metrics(exposed, positive))
        arms["lexical"].append(metrics(lexical, positive))
        arms["dense"].append(metrics(dense, positive))
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"root_uri": "external://lrat-repro/trajectory", "file_count": len(trajectories), "raw_content_committed": False},
        "protocol": {"positive_definition": "browsed document intersected with search-exposed document", "candidate_pool": "within-trajectory exposed documents", "dense_model": model_path.name, "positive_labels_are_silver": True},
        "cohort": counts,
        "arms": {arm: aggregate(values) for arm, values in arms.items()},
        "claim_boundary": {"exposure_candidate_retrieval_measured": True, "document_correctness_established": False, "enterprise_artifact_utility_established": False, "trajectory_distilled_training_performed": False, "reason": "Browsing is a weak relevance signal; the samples have no independent correctness, principal, authority, or changed-system outcome labels."},
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohort": counts, "arms": result["arms"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.model_path, args.output)
