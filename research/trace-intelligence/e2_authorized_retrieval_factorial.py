#!/usr/bin/env python3
"""Frozen E2 same-work retrieval factorial over raw CodeTraceBench traces.

This experiment answers a deliberately bounded question: can trace-derived exact,
lexical, structured, and general-dense views recover another attempt at the same
public benchmark task?  The public task identity supplies *silver* positives.  It
does not supply human task-family labels, enterprise authorization labels, or
evidence that two employees should collaborate.

Raw archives, projected text, token dictionaries, and embeddings remain outside
Git.  The durable result contains aggregate metrics and content hashes only.
PostgreSQL/RLS behavior is reported from the existing independent runtime proof;
this script does not claim that its offline ranking ran inside PostgreSQL.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import math
import pathlib
import random
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pyarrow.parquet as pq

import codetracebench_empirical as manifest_study
from codetracebench_raw_factorial import ParsedTrajectory, parse_archive


SCHEMA_VERSION = "frankengate-e2-authorized-retrieval-factorial-v1"
ANALYSIS_REVISION = "e2-raw-codetracebench-retrieval-v1"
DATASET_ID = manifest_study.DATASET_ID
DATASET_REVISION = manifest_study.DATASET_REVISION
DEFAULT_SEED = manifest_study.DEFAULT_SEED
RRF_K = 60
MAX_VIEW_CHARACTERS = 24_000
MAX_DENSE_CHARACTERS = 8_000
EMBEDDING_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
EMBEDDING_MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
EXPECTED_EMBEDDING_DIMENSION = 1024
EMBEDDING_QUERY_INSTRUCTION = (
    "Given an agent trajectory, retrieve other trajectories attempting the same task"
)
EMBEDDING_QUERY_TEMPLATE = "Instruct: {instruction}\nQuery: {trajectory}"

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./:+@#-]{1,127}")
IDENTIFIER_RE = re.compile(
    r"""(?x)
    (?:
      [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+ |
      [A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+ |
      (?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+ |
      --?[A-Za-z][A-Za-z0-9_-]+ |
      [A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_.-]+ |
      [A-Za-z_][A-Za-z0-9_]{2,} |
      [A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+ |
      [A-Za-z]+Error |
      [A-Z]{2,}[0-9_-]* |
      [0-9a-f]{7,40}
    )
    """
)
ERROR_CLASS_PATTERNS = {
    "assertion": re.compile(r"(?i)\bassert(?:ion)?(?:error|failed)?\b"),
    "build": re.compile(r"(?i)\b(?:build|compile|linker)\b.*\b(?:fail|error)\b"),
    "dependency": re.compile(
        r"(?i)\b(?:dependency|package|module|version|resolution)\b.*\b(?:fail|error|missing|conflict)\b"
    ),
    "not_found": re.compile(r"(?i)\b(?:not found|no such file|missing)\b"),
    "permission": re.compile(r"(?i)\b(?:permission denied|forbidden|unauthorized)\b"),
    "syntax": re.compile(r"(?i)\b(?:syntaxerror|syntax error|parse error)\b"),
    "test": re.compile(r"(?i)\b(?:test|tests|pytest)\b.*\b(?:fail|error)\b"),
    "timeout": re.compile(r"(?i)\b(?:timeout|timed out|deadline exceeded)\b"),
}


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_digest(*parts: object) -> str:
    return sha256_bytes("\x1f".join(str(part) for part in parts).encode())


def normalize_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1
    )


def extract_identifiers(text: str) -> frozenset[str]:
    return frozenset(
        value.lower()
        for value in IDENTIFIER_RE.findall(text)
        if len(value) > 2
    )


def bounded_text(parts: Iterable[str], limit: int = MAX_VIEW_CHARACTERS) -> str:
    output: list[str] = []
    length = 0
    for part in parts:
        normalized = re.sub(r"\s+", " ", part).strip()
        if not normalized:
            continue
        remaining = limit - length
        if remaining <= 0:
            break
        output.append(normalized[:remaining])
        length += min(len(normalized), remaining)
    return "\n".join(output)


@dataclasses.dataclass(frozen=True)
class RetrievalDocument:
    trace_id: str
    task_identity: str
    repository_family: str
    source_family: str
    category: str
    tags: tuple[str, ...]
    agent: str
    model: str
    text: str
    tokens: tuple[str, ...]
    identifiers: frozenset[str]
    structured_features: frozenset[str]


def structured_features(
    parsed: ParsedTrajectory,
    *,
    category: str,
    tags: Sequence[str],
) -> frozenset[str]:
    features: set[str] = set()
    tool_counts = collections.Counter(step.tool_family for step in parsed.steps)
    for family, count in tool_counts.items():
        features.add(f"tool:{family}")
        features.add(f"tool_count:{family}:{min(count, 8)}")
    for step in parsed.steps:
        for name in normalize_tokens(step.tool_name):
            features.add(f"tool_name:{name}")
        material = step.action + "\n" + (step.observation or "")
        for error_class, pattern in ERROR_CLASS_PATTERNS.items():
            if pattern.search(material):
                features.add(f"error:{error_class}")
        for identifier in extract_identifiers(material):
            suffix = pathlib.PurePosixPath(identifier).suffix.lower()
            if suffix:
                features.add(f"extension:{suffix}")
    # Category and tags are publisher-provided task metadata, not retrieval gold.
    # They are included only in the structured arm and disclosed in the result.
    if category:
        features.add("category:" + category.lower())
    features.update("tag:" + tag.lower() for tag in tags if tag)
    return frozenset(features)


def build_document(
    parsed: ParsedTrajectory,
    row: Mapping[str, Any],
) -> RetrievalDocument:
    text = bounded_text(
        part
        for step in parsed.steps
        for part in (step.action, step.observation or "")
    )
    tags = tuple(sorted(str(value) for value in (row.get("tags") or [])))
    category = str(row.get("category") or "")
    source_family = manifest_study.derive_source_family(row.get("source_relpath"))
    repository_family = manifest_study.derive_repository_family(
        str(row["task_name"]), source_family
    )
    return RetrievalDocument(
        trace_id=parsed.traj_id,
        task_identity=str(row["task_name"]),
        repository_family=repository_family,
        source_family=source_family,
        category=category,
        tags=tags,
        agent=str(row.get("agent") or ""),
        model=str(row.get("model") or ""),
        text=text,
        tokens=normalize_tokens(text),
        identifiers=extract_identifiers(text),
        structured_features=structured_features(
            parsed,
            category=category,
            tags=tags,
        ),
    )


def load_documents(
    *,
    allowlist_path: pathlib.Path,
    full_path: pathlib.Path,
    archive_root: pathlib.Path,
) -> tuple[list[RetrievalDocument], dict[str, Any]]:
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    if allowlist.get("dataset_revision") != DATASET_REVISION:
        raise ValueError("allowlist dataset revision mismatch")
    full_rows = {
        str(row["traj_id"]): row
        for row in pq.read_table(full_path).to_pylist()
    }
    documents: list[RetrievalDocument] = []
    alignment = collections.Counter()
    parser_variants = collections.Counter()
    relevant_member_count = 0
    relevant_uncompressed_bytes = 0
    for item in allowlist["files"]:
        trace_id = str(item["traj_id"])
        row = full_rows.get(trace_id)
        if row is None:
            raise ValueError(f"{trace_id}: missing full manifest row")
        archive_path = archive_root / str(item["artifact_path"])
        parsed = parse_archive(
            archive_path,
            traj_id=trace_id,
            agent=str(item["agent"]),
            manifest_step_count=int(row["step_count"]),
            expected_sha256=str(item["sha256"]),
        )
        documents.append(build_document(parsed, row))
        alignment[parsed.alignment_status] += 1
        parser_variants[parsed.parser_variant] += 1
        relevant_member_count += parsed.relevant_member_count
        relevant_uncompressed_bytes += parsed.relevant_uncompressed_bytes
    return documents, {
        "archives": len(documents),
        "compressed_bytes": int(allowlist["compressed_bytes"]),
        "alignment": dict(sorted(alignment.items())),
        "parser_variants": dict(sorted(parser_variants.items())),
        "relevant_member_count": relevant_member_count,
        "relevant_uncompressed_bytes": relevant_uncompressed_bytes,
        "allowlist_sha256": sha256_file(allowlist_path),
        "allowlist_identity_digest": allowlist["file_identity_digest"],
        "full_manifest_sha256": sha256_file(full_path),
    }


class BM25:
    def __init__(self, documents: Sequence[RetrievalDocument]) -> None:
        self.document_count = len(documents)
        self.lengths = [len(document.tokens) for document in documents]
        self.average_length = statistics.fmean(self.lengths) if self.lengths else 0.0
        self.term_frequencies = [
            collections.Counter(document.tokens) for document in documents
        ]
        document_frequency: collections.Counter[str] = collections.Counter()
        for frequencies in self.term_frequencies:
            document_frequency.update(frequencies.keys())
        self.idf = {
            term: math.log(
                1.0
                + (self.document_count - count + 0.5) / (count + 0.5)
            )
            for term, count in document_frequency.items()
        }

    def score(
        self,
        query_tokens: Sequence[str],
        document_index: int,
        *,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> float:
        frequencies = self.term_frequencies[document_index]
        length = self.lengths[document_index]
        denominator_scale = (
            1.0 - b + b * length / self.average_length
            if self.average_length
            else 1.0
        )
        score = 0.0
        for term in set(query_tokens):
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            score += self.idf.get(term, 0.0) * (
                frequency * (k1 + 1.0)
                / (frequency + k1 * denominator_scale)
            )
        return score


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def exact_score(query: RetrievalDocument, candidate: RetrievalDocument) -> float:
    overlap = query.identifiers & candidate.identifiers
    return float(len(overlap))


def rank_channel(
    documents: Sequence[RetrievalDocument],
    query_index: int,
    scores: Sequence[float],
) -> list[int]:
    return sorted(
        (index for index in range(len(documents)) if index != query_index),
        key=lambda index: (
            -scores[index],
            stable_digest(documents[query_index].trace_id, documents[index].trace_id),
        ),
    )


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]],
    *,
    rrf_k: int = RRF_K,
) -> list[int]:
    scores: collections.Counter[int] = collections.Counter()
    for ranking in rankings:
        for rank, index in enumerate(ranking, start=1):
            scores[index] += 1.0 / (rrf_k + rank)
    return sorted(
        scores,
        key=lambda index: (-scores[index], index),
    )


def dense_embeddings(
    documents: Sequence[RetrievalDocument],
    model_path: pathlib.Path,
    *,
    device: str,
) -> tuple[tuple[Any, Any], dict[str, Any]]:
    if model_path.name != EMBEDDING_MODEL_REVISION:
        raise ValueError(
            "embedding model path must end in pinned revision "
            + EMBEDDING_MODEL_REVISION
        )
    from sentence_transformers import SentenceTransformer

    requested_device = device
    if device == "auto":
        import torch

        device = "mps" if torch.backends.mps.is_available() else "cpu"

    model = SentenceTransformer(
        str(model_path),
        device=device,
        local_files_only=True,
    )
    model.max_seq_length = min(model.max_seq_length, 512)
    document_texts = [
        document.text[:MAX_DENSE_CHARACTERS]
        for document in documents
    ]
    query_texts = [
        EMBEDDING_QUERY_TEMPLATE.format(
            instruction=EMBEDDING_QUERY_INSTRUCTION,
            trajectory=document.text[:MAX_DENSE_CHARACTERS],
        )
        for document in documents
    ]
    document_vectors = model.encode(
        document_texts,
        batch_size=8,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    query_vectors = model.encode(
        query_texts,
        batch_size=8,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    expected_shape = (len(documents), EXPECTED_EMBEDDING_DIMENSION)
    if document_vectors.shape != expected_shape:
        raise ValueError(
            f"unexpected document embedding shape: {document_vectors.shape}"
        )
    if query_vectors.shape != expected_shape:
        raise ValueError(
            f"unexpected query embedding shape: {query_vectors.shape}"
        )
    contract_files = (
        "config.json",
        "config_sentence_transformers.json",
        "modules.json",
        "tokenizer_config.json",
    )
    return (query_vectors, document_vectors), {
        "model_id": EMBEDDING_MODEL_ID,
        "revision": EMBEDDING_MODEL_REVISION,
        "dimension": EXPECTED_EMBEDDING_DIMENSION,
        "distance": "cosine_on_l2_normalized_vectors",
        "requested_device": requested_device,
        "resolved_device": device,
        "max_sequence_length": model.max_seq_length,
        "query_instruction": EMBEDDING_QUERY_INSTRUCTION,
        "query_template": EMBEDDING_QUERY_TEMPLATE,
        "document_prompt": None,
        "separate_query_and_document_embeddings": True,
        "contract_file_sha256": {
            name: sha256_file(model_path / name)
            for name in contract_files
        },
        "weights_emitted": False,
        "vectors_emitted": False,
    }


def hard_negative(
    query: RetrievalDocument,
    candidate: RetrievalDocument,
) -> bool:
    if query.task_identity == candidate.task_identity:
        return False
    same_repository = (
        not query.repository_family.startswith("task:")
        and query.repository_family == candidate.repository_family
    )
    same_category_with_tag = (
        bool(query.category)
        and query.category == candidate.category
        and bool(set(query.tags) & set(candidate.tags))
    )
    same_structure = jaccard(
        query.structured_features, candidate.structured_features
    ) >= 0.50
    return same_repository or same_category_with_tag or same_structure


def relevance_metrics(
    documents: Sequence[RetrievalDocument],
    query_index: int,
    ranking: Sequence[int],
) -> dict[str, float]:
    query = documents[query_index]
    relevant = {
        index
        for index, document in enumerate(documents)
        if index != query_index and document.task_identity == query.task_identity
    }
    if not relevant:
        raise ValueError("query has no silver-positive candidate")
    relevant_ranks = [
        rank
        for rank, index in enumerate(ranking, start=1)
        if index in relevant
    ]
    first_relevant = min(relevant_ranks)

    def recall_at(k: int) -> float:
        return len(relevant & set(ranking[:k])) / len(relevant)

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in relevant_ranks
        if rank <= 20
    )
    ideal = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, min(20, len(relevant)) + 1)
    )
    hard_ranks = [
        rank
        for rank, index in enumerate(ranking, start=1)
        if hard_negative(query, documents[index])
    ]
    exact_positive = any(
        query.identifiers & documents[index].identifiers
        for index in relevant
    )
    return {
        "recall_at_1": recall_at(1),
        "recall_at_5": recall_at(5),
        "recall_at_20": recall_at(20),
        "ndcg_at_20": dcg / ideal if ideal else 0.0,
        "mrr": 1.0 / first_relevant,
        "hard_negative_top1": float(
            bool(ranking) and hard_negative(query, documents[ranking[0]])
        ),
        "hard_negative_above_first_positive": float(
            bool(hard_ranks) and min(hard_ranks) < first_relevant
        ),
        "exact_id_slice": float(exact_positive),
        "exact_id_recall_at_20": recall_at(20) if exact_positive else math.nan,
    }


def mean_metric(rows: Sequence[Mapping[str, float]], name: str) -> float:
    values = [float(row[name]) for row in rows if not math.isnan(float(row[name]))]
    return statistics.fmean(values) if values else math.nan


def aggregate_metrics(rows: Sequence[Mapping[str, float]]) -> dict[str, float | int]:
    names = (
        "recall_at_1",
        "recall_at_5",
        "recall_at_20",
        "ndcg_at_20",
        "mrr",
        "hard_negative_top1",
        "hard_negative_above_first_positive",
        "exact_id_recall_at_20",
    )
    return {
        "queries": len(rows),
        "exact_id_slice_queries": sum(row["exact_id_slice"] == 1.0 for row in rows),
        **{name: mean_metric(rows, name) for name in names},
    }


def bootstrap_delta(
    rows: Sequence[Mapping[str, float]],
    baseline: Sequence[Mapping[str, float]],
    name: str,
    *,
    seed: int,
    repetitions: int = 2_000,
) -> list[float]:
    paired = [
        (float(row[name]), float(base[name]))
        for row, base in zip(rows, baseline)
        if not math.isnan(float(row[name]))
        and not math.isnan(float(base[name]))
    ]
    if not paired:
        return [math.nan, math.nan]
    generator = random.Random(seed)
    deltas = []
    for _ in range(repetitions):
        sample = [generator.choice(paired) for _ in paired]
        deltas.append(statistics.fmean(left - right for left, right in sample))
    deltas.sort()
    return [deltas[int(0.025 * repetitions)], deltas[int(0.975 * repetitions)]]


def build_rankings(
    documents: Sequence[RetrievalDocument],
    dense_vectors: tuple[Any, Any] | None,
) -> tuple[dict[str, dict[int, list[int]]], dict[int, dict[str, list[int]]]]:
    bm25 = BM25(documents)
    channels: dict[int, dict[str, list[int]]] = {}
    for query_index, query in enumerate(documents):
        exact_scores = [
            exact_score(query, candidate) for candidate in documents
        ]
        lexical_scores = [
            bm25.score(query.tokens, index)
            for index in range(len(documents))
        ]
        structured_scores = [
            jaccard(query.structured_features, candidate.structured_features)
            for candidate in documents
        ]
        query_channels = {
            "exact": rank_channel(
                documents, query_index, exact_scores
            ),
            "lexical": rank_channel(
                documents, query_index, lexical_scores
            ),
            "structured": rank_channel(
                documents, query_index, structured_scores
            ),
        }
        if dense_vectors is not None:
            query_vectors, document_vectors = dense_vectors
            dense_scores = document_vectors @ query_vectors[query_index]
            query_channels["dense"] = rank_channel(
                documents, query_index, dense_scores.tolist()
            )
        channels[query_index] = query_channels

    arms: dict[str, dict[int, list[int]]] = {}
    for structured in (False, True):
        for lexical in (False, True):
            for dense in (False, True):
                if dense and dense_vectors is None:
                    continue
                arm_name = (
                    f"S{int(structured)}L{int(lexical)}D{int(dense)}"
                )
                rankings = {}
                for query_index, query_channels in channels.items():
                    active = [query_channels["exact"]]
                    if structured:
                        active.append(query_channels["structured"])
                    if lexical:
                        active.append(query_channels["lexical"])
                    if dense:
                        active.append(query_channels["dense"])
                    rankings[query_index] = reciprocal_rank_fusion(active)
                arms[arm_name] = rankings
    return arms, channels


def runtime_authorization_evidence(result_path: pathlib.Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    matrix = result.get("denied_pre_ranking_candidate_matrix") or {}
    counts_by_scenario = matrix.get("counts", matrix)
    all_zero = all(
        value == 0
        for counts in counts_by_scenario.values()
        if isinstance(counts, Mapping)
        for value in counts.values()
    )
    return {
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
        "schema_version": result.get("schema_version"),
        "denied_scenarios": len(counts_by_scenario),
        "all_denied_pre_ranking_candidates_zero": all_zero,
        "same_corpus_as_quality_factorial": False,
        "joint_quality_and_rls_run": False,
        "claim": (
            "independent local PostgreSQL forced-RLS composition proof; "
            "not evidence that the offline E2 ranks were produced by PostgreSQL"
        ),
    }


def run_factorial(
    documents: Sequence[RetrievalDocument],
    *,
    dense_vectors: tuple[Any, Any] | None,
    dense_contract: Mapping[str, Any] | None,
    source_receipt: Mapping[str, Any],
    authorization_result_path: pathlib.Path,
    seed: int,
    run_date: str,
) -> dict[str, Any]:
    task_counts = collections.Counter(
        document.task_identity for document in documents
    )
    eligible_queries = [
        index
        for index, document in enumerate(documents)
        if task_counts[document.task_identity] > 1
    ]
    arms, _ = build_rankings(documents, dense_vectors)
    arm_rows: dict[str, list[dict[str, float]]] = {}
    for arm_name, rankings in arms.items():
        arm_rows[arm_name] = [
            relevance_metrics(
                documents,
                query_index,
                rankings[query_index],
            )
            for query_index in eligible_queries
        ]
    exact_rows = arm_rows["S0L0D0"]
    arm_results = {}
    for arm_name, rows in arm_rows.items():
        metrics = aggregate_metrics(rows)
        metrics["recall_at_20_delta_vs_exact"] = (
            float(metrics["recall_at_20"])
            - float(aggregate_metrics(exact_rows)["recall_at_20"])
        )
        metrics["recall_at_20_delta_95ci"] = bootstrap_delta(
            rows,
            exact_rows,
            "recall_at_20",
            seed=int(stable_digest(seed, arm_name)[:16], 16),
        )
        metrics["exact_id_recall_at_20_delta_vs_exact"] = (
            float(metrics["exact_id_recall_at_20"])
            - float(
                aggregate_metrics(exact_rows)["exact_id_recall_at_20"]
            )
        )
        arm_results[arm_name] = metrics

    hard_negative_pairs = sum(
        hard_negative(query, candidate)
        for query in documents
        for candidate in documents
        if query.trace_id < candidate.trace_id
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": ANALYSIS_REVISION,
        "run_date": run_date,
        "seed": seed,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "dataset_license": manifest_study.DATASET_LICENSE,
            "raw_data_committed": False,
            "projected_text_committed": False,
            "embeddings_committed": False,
            **source_receipt,
        },
        "cohort": {
            "documents": len(documents),
            "task_identities": len(task_counts),
            "repeated_task_identities": sum(
                count > 1 for count in task_counts.values()
            ),
            "eligible_queries": len(eligible_queries),
            "silver_positive_pairs": sum(
                count * (count - 1) // 2
                for count in task_counts.values()
                if count > 1
            ),
            "metadata_derived_hard_negative_pairs": hard_negative_pairs,
            "sources": dict(
                sorted(collections.Counter(
                    document.source_family for document in documents
                ).items())
            ),
        },
        "label_contract": {
            "positive": (
                "same public benchmark task_name across distinct trajectories"
            ),
            "positive_authority": "publisher identity; silver, not human adjudication",
            "hard_negative": (
                "different task with same repository, category+tag overlap, "
                "or >=0.50 trace-structure Jaccard"
            ),
            "hard_negative_authority": (
                "metadata-derived candidate only; not human adjudication"
            ),
            "gold_fields_forbidden_from_features": [
                "task_name",
                "task_slug",
                "solved",
                "incorrect_stages",
                "incorrect_step_ids",
                "unuseful_step_ids",
            ],
        },
        "views": {
            "exact": "trace-derived identifier overlap",
            "lexical": "dependency-free BM25 over bounded raw action/observation text",
            "structured": (
                "tool family/name, error class, file extension, publisher category/tags"
            ),
            "dense": (
                "one normalized general embedding of bounded action/observation text"
                if dense_vectors is not None
                else "not run"
            ),
            "fusion": f"fixed equal-channel reciprocal-rank fusion k={RRF_K}",
            "raw_prompt_or_objective_projection": False,
        },
        "dense_contract": dense_contract,
        "factorial": {
            "factors": {
                "structured": [False, True],
                "lexical": [False, True],
                "dense": [False, True] if dense_vectors is not None else [False],
                "exact_identifier_channel_always_on": True,
            },
            "arms": arm_results,
        },
        "runtime_authorization_evidence": runtime_authorization_evidence(
            authorization_result_path
        ),
        "acceptance": {
            "all_eight_core_arms_ran": len(arm_results) == 8,
            "exact_identifier_no_regression": all(
                (
                    math.isnan(
                        float(metrics["exact_id_recall_at_20_delta_vs_exact"])
                    )
                    or float(
                        metrics["exact_id_recall_at_20_delta_vs_exact"]
                    )
                    >= 0.0
                )
                for metrics in arm_results.values()
            ),
            "custom_embedding_authorized": False,
            "aurora_replacement_authorized": False,
            "human_label_gate_passed": False,
            "joint_quality_rls_gate_passed": False,
        },
        "claim_limits": [
            "task identity is a silver positive, not a blinded human task-family label",
            "hard negatives are metadata-derived candidates, not adjudicated negatives",
            "publisher category and tags are available only to structured-on arms",
            "the raw user objective/prompt is not consistently projected across agents",
            "offline BM25 is not PostgreSQL FTS or pg_trgm",
            "offline dense ranking is not pgvector execution",
            "the independent RLS proof used a different public corpus and deterministic vectors",
            "no deletion, selective-RLS latency, concurrency, or real-Aurora test ran jointly with quality",
            "same benchmark work does not imply cross-user collaboration value",
            "no person-level skill, productivity, enterprise transfer, or causal utility claim is supported",
        ],
        "next_gates": [
            "blind and independently adjudicate task-family positives and hard negatives",
            "project provider-neutral objective/environment/failure/recovery views",
            "load the same candidates and 1024-dimensional vectors into forced-RLS PostgreSQL",
            "run deletion, stale/missing epoch, purpose, classification, and selective-scope oracles per arm",
            "measure PostgreSQL FTS, pg_trgm, exact pgvector, p50/p95/p99, bytes, rebuild time, and cost",
            "test a reranker only after freezing the best dense and non-dense candidate generators",
            "test domain adaptation only on a named hard slice and require +5 absolute Recall@20",
        ],
    }
    result["result_content_sha256"] = sha256_bytes(
        stable_json(result).encode("utf-8")
    )
    return result


def render_summary(result: Mapping[str, Any]) -> str:
    cohort = result["cohort"]
    rows = []
    for arm_name, metrics in sorted(
        result["factorial"]["arms"].items()
    ):
        rows.append(
            "| {arm} | {r1:.3f} | {r5:.3f} | {r20:.3f} | {ndcg:.3f} | "
            "{mrr:.3f} | {hard:.3f} | {exact:.3f} |".format(
                arm=arm_name,
                r1=metrics["recall_at_1"],
                r5=metrics["recall_at_5"],
                r20=metrics["recall_at_20"],
                ndcg=metrics["ndcg_at_20"],
                mrr=metrics["mrr"],
                hard=metrics["hard_negative_above_first_positive"],
                exact=metrics["exact_id_recall_at_20"],
            )
        )
    best = max(
        result["factorial"]["arms"].items(),
        key=lambda item: (
            item[1]["recall_at_20"],
            item[1]["ndcg_at_20"],
            item[1]["mrr"],
        ),
    )
    limits = "\n".join(
        f"- {value}" for value in result["claim_limits"]
    )
    gates = "\n".join(
        f"- {value}" for value in result["next_gates"]
    )
    dense = result.get("dense_contract")
    dense_line = (
        f"`{dense['model_id']}` at `{dense['revision']}`"
        if dense
        else "not run"
    )
    return f"""# E2 raw CodeTraceBench retrieval factorial

**Run date:** {result['run_date']}
**Status:** completed silver-label offline quality pilot; human-label and joint
PostgreSQL/RLS gates remain open
**Dataset:** `{result['source']['dataset_id']}` at
`{result['source']['dataset_revision']}`
**Dense model:** {dense_line}
**Result SHA-256:** `{result['result_content_sha256']}`

## Cohort

The frozen raw allowlist contains {cohort['documents']} hash-verified archives,
{cohort['task_identities']} task identities, {cohort['repeated_task_identities']}
repeated-task groups, {cohort['eligible_queries']} leave-one-trace-out queries,
{cohort['silver_positive_pairs']} silver positive pairs, and
{cohort['metadata_derived_hard_negative_pairs']} metadata-derived hard-negative
candidate pairs. Raw trace text and embeddings were not committed.

## Factorial result

Every arm retains the exact-identifier channel. `S`, `L`, and `D` switch structured,
lexical, and dense channels. Channels use fixed equal-weight reciprocal-rank fusion.

| Arm | R@1 | R@5 | R@20 | nDCG@20 | MRR | hard negative above positive | exact-ID R@20 |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The strongest arm by the preregistered lexicographic summary was
`{best[0]}` with Recall@20 {best[1]['recall_at_20']:.3f}. This is not a
production winner: the labels are not human-adjudicated and the quality ranking did
not execute inside PostgreSQL.

## Authorization boundary

The result references the existing forced-RLS PostgreSQL benchmark only as an
independent composition proof. Its denied pre-ranking candidate matrix remained all
zero, but it used a different corpus and deterministic eight-dimensional vectors.
Therefore neither joint quality-plus-RLS nor deletion correctness has passed.

## Claim limits

{limits}

## Required next gates

{gates}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", required=True, type=pathlib.Path)
    parser.add_argument("--full", required=True, type=pathlib.Path)
    parser.add_argument("--archive-root", required=True, type=pathlib.Path)
    parser.add_argument("--authorization-result", required=True, type=pathlib.Path)
    parser.add_argument("--embedding-model", type=pathlib.Path)
    parser.add_argument(
        "--embedding-device",
        choices=("auto", "cpu", "mps"),
        default="cpu",
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--summary", required=True, type=pathlib.Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--run-date", default="2026-07-30")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    documents, source_receipt = load_documents(
        allowlist_path=args.allowlist,
        full_path=args.full,
        archive_root=args.archive_root,
    )
    vectors = None
    dense_contract = None
    if args.embedding_model is not None:
        vectors, dense_contract = dense_embeddings(
            documents,
            args.embedding_model,
            device=args.embedding_device,
        )
    result = run_factorial(
        documents,
        dense_vectors=vectors,
        dense_contract=dense_contract,
        source_receipt=source_receipt,
        authorization_result_path=args.authorization_result,
        seed=args.seed,
        run_date=args.run_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(render_summary(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "arms": len(result["factorial"]["arms"]),
                "eligible_queries": result["cohort"]["eligible_queries"],
                "result_content_sha256": result["result_content_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
