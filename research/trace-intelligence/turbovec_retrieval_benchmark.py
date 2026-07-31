#!/usr/bin/env python3
"""Benchmark TurboVec against the pinned CodeTraceBench dense cohort.

This is deliberately an adapter-level experiment.  The public task identity is
only a silver retrieval label; no cross-user or enterprise utility claim is
made.  Raw trajectories and vectors remain outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import time
from typing import Any

import numpy as np

import e2_authorized_retrieval_factorial as e2


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_order(query: np.ndarray, documents: np.ndarray, query_index: int) -> np.ndarray:
    scores = documents @ query
    order = np.argsort(-scores, kind="stable")
    return order[order != query_index]


def positive_ids(documents: list[Any], query_index: int) -> set[int]:
    identity = documents[query_index].task_identity
    return {
        index + 1
        for index, document in enumerate(documents)
        if index != query_index and document.task_identity == identity
    }


def recall_at(retrieved: np.ndarray, relevant: set[int], k: int) -> float:
    if not relevant:
        return float("nan")
    return len(set(int(value) for value in retrieved[:k]) & relevant) / len(relevant)


def run(*, allowlist: pathlib.Path, manifest: pathlib.Path, archive_root: pathlib.Path,
        model_path: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    documents, source = e2.load_documents(
        allowlist_path=allowlist,
        full_path=manifest,
        archive_root=archive_root,
    )
    (query_vectors, document_vectors), embedding = e2.dense_embeddings(
        documents, model_path, device="auto"
    )
    dimensions = int(document_vectors.shape[1])
    query_count = len(documents)
    eligible = [
        index for index in range(query_count)
        if positive_ids(documents, index)
    ]
    from turbovec import IdMapIndex

    arms: dict[str, Any] = {}
    for bit_width in (2, 4):
        index = IdMapIndex(dim=dimensions, bit_width=bit_width)
        ids = np.arange(1, query_count + 1, dtype=np.uint64)
        started = time.perf_counter()
        index.add_with_ids(document_vectors.astype(np.float32, copy=False), ids)
        ingest_ms = (time.perf_counter() - started) * 1000
        exact_recalls: list[float] = []
        turbo_recalls: list[float] = []
        exact_top1 = 0
        turbo_top1 = 0
        query_ms: list[float] = []
        for query_index in eligible:
            relevant = positive_ids(documents, query_index)
            exact = exact_order(query_vectors[query_index], document_vectors, query_index)
            exact_ids = exact + 1
            exact_recalls.append(recall_at(exact_ids, relevant, 20))
            exact_top1 += int(int(exact_ids[0]) in relevant)
            started = time.perf_counter()
            _, returned = index.search(
                query_vectors[query_index].reshape(1, -1).astype(np.float32, copy=False),
                20,
            )
            query_ms.append((time.perf_counter() - started) * 1000)
            returned_ids = np.asarray(
                [value for value in np.asarray(returned[0], dtype=np.uint64)
                 if int(value) != query_index + 1],
                dtype=np.uint64,
            )
            turbo_recalls.append(recall_at(returned_ids, relevant, 20))
            turbo_top1 += int(returned_ids.size > 0 and int(returned_ids[0]) in relevant)

        # Filter correctness is compared with exact float ranking inside the
        # same allowlist, independent of task labels.  Use a deterministic
        # per-query allowlist that always contains the query and at least one
        # candidate, but excludes roughly half the corpus.
        filter_recalls: list[float] = []
        filter_query_ms: list[float] = []
        filter_allowed_counts: list[int] = []
        for query_index in range(query_count):
            allowed_mask = np.array(
                [((index * 17 + query_index * 31) % 100) < 47 for index in range(query_count)],
                dtype=bool,
            )
            # Retrieval metrics exclude the query document itself, matching
            # the existing E2 quality factorial.
            allowed_mask[query_index] = False
            allowed = np.flatnonzero(allowed_mask)
            allowed_ids = (allowed + 1).astype(np.uint64)
            exact_allowed = exact_order(query_vectors[query_index], document_vectors, query_index)
            exact_allowed = np.array(
                [index for index in exact_allowed if allowed_mask[index]], dtype=np.int64
            )
            started = time.perf_counter()
            _, returned = index.search(
                query_vectors[query_index].reshape(1, -1).astype(np.float32, copy=False),
                20,
                allowlist=allowed_ids,
            )
            filter_query_ms.append((time.perf_counter() - started) * 1000)
            returned_ids = np.asarray(returned[0], dtype=np.uint64)
            filter_allowed_counts.append(int(len(allowed_ids)))
            expected_ids = (exact_allowed[: len(returned_ids)] + 1).astype(np.uint64)
            # Recall against the exact allowed top-k, not task labels.
            filter_recalls.append(
                len(set(int(x) for x in returned_ids) & set(int(x) for x in expected_ids))
                / max(1, len(expected_ids))
            )
            if any(int(x) not in set(int(y) for y in allowed_ids) for x in returned_ids):
                raise AssertionError("TurboVec returned an ID outside the allowlist")

        persistence_dir = output.parent / ".turbovec-runtime"
        persistence_dir.mkdir(parents=True, exist_ok=True)
        path = persistence_dir / f"codetrace-{bit_width}bit.tvim"
        index.write(str(path))
        loaded = IdMapIndex.load(str(path))
        deleted_id = np.uint64(query_count)
        loaded.remove(deleted_id)
        _, post_delete = loaded.search(query_vectors[0].reshape(1, -1).astype(np.float32), 20)
        if int(deleted_id) in set(int(x) for x in np.asarray(post_delete[0], dtype=np.uint64)):
            raise AssertionError("deleted TurboVec ID was returned")
        arms[f"{bit_width}bit"] = {
            "dimensions": dimensions,
            "documents": query_count,
            "eligible_task_queries": len(eligible),
            "ingest_ms": round(ingest_ms, 3),
            "query_mean_ms": round(float(np.mean(query_ms)), 6),
            "query_p95_ms": round(float(np.percentile(query_ms, 95)), 6),
            "filter_query_mean_ms": round(float(np.mean(filter_query_ms)), 6),
            "filter_query_p95_ms": round(float(np.percentile(filter_query_ms, 95)), 6),
            "mean_allowed_count": round(float(np.mean(filter_allowed_counts)), 3),
            "exact_float_recall_at_20": round(float(np.mean(exact_recalls)), 8),
            "turbovec_recall_at_20": round(float(np.mean(turbo_recalls)), 8),
            "turbovec_recall_delta_vs_exact": round(float(np.mean(turbo_recalls) - np.mean(exact_recalls)), 8),
            "exact_float_top1": round(exact_top1 / len(eligible), 8),
            "turbovec_top1": round(turbo_top1 / len(eligible), 8),
            "filtered_exact_topk_overlap": round(float(np.mean(filter_recalls)), 8),
            "persistent_index_bytes": path.stat().st_size,
            "deletion_roundtrip_passed": True,
        }
        path.unlink(missing_ok=True)

    result = {
        "schema_version": "frankengate-turbovec-codetracebench-v1",
        "source": {
            "dataset_id": e2.DATASET_ID,
            "dataset_revision": e2.DATASET_REVISION,
            "raw_data_committed": False,
            "projected_text_committed": False,
            "embeddings_committed": False,
            **source,
        },
        "embedding": embedding,
        "turbovec": {
            "package": "turbovec",
            "version": "0.8.0",
            "algorithm": "TurboQuant",
            "filtered_search": "IdMapIndex allowlist inside SIMD search",
        },
        "arms": arms,
        "claim_boundary": {
            "silver_task_identity_only": True,
            "authorization_evaluated": False,
            "enterprise_cross_user_utility_confirmed": False,
            "downstream_skill_uplift_confirmed": False,
            "automatic_backend_promotion_authorized": False,
            "reason": "This is a same-corpus dense-index and filtered-kernel benchmark; it does not establish RLS authority, enterprise utility, or skill uplift.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "arms": arms}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", type=pathlib.Path, required=True)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--archive-root", type=pathlib.Path, required=True)
    parser.add_argument("--model-path", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    run(
        allowlist=args.allowlist,
        manifest=args.manifest,
        archive_root=args.archive_root,
        model_path=args.model_path,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
