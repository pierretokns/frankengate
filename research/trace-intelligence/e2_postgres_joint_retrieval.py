#!/usr/bin/env python3
"""Joint CodeTraceBench quality and forced-RLS PostgreSQL retrieval run.

The experiment loads the same frozen 145-document E2 cohort and its pinned
1024-dimensional Qwen embeddings into the disposable research table inside one
rollback-only transaction. PostgreSQL performs FTS, trigram, and exact pgvector
ranking as ``trace_research_app`` under forced RLS. Only aggregate metrics and
content hashes may be written to the durable result.

Raw trace text, identifiers, projected metadata, task labels, document IDs, and
vectors remain in process memory or the disposable PostgreSQL transaction. The
connection is rolled back on success and on every error path.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import pathlib
import re
import statistics
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from psycopg2 import connect
from psycopg2.extras import Json, execute_values

import e2_authorized_retrieval_factorial as e2


SCHEMA_VERSION = "frankengate-e2-postgres-joint-retrieval-v1"
ANALYSIS_REVISION = "e2-codetracebench-postgres-joint-v1"
TENANT_ID = "e2-codetracebench"
SUBJECT_ID = "e2-researcher"
AUTHORIZATION_EPOCH = 41
CLASSIFICATION_CEILING = 2
CLASSIFICATION = 1
PURPOSE = "quality-improvement"
POLICY_REVISION = "e2-research-policy-v1"
FTS_TERM_LIMIT = 48
TRIGRAM_QUERY_CHARACTERS = 512
FTS_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,63}")


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def latency_summary(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "samples": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "max_ms": max(values),
    }


def vector_literal(values: Sequence[float]) -> str:
    if len(values) != e2.EXPECTED_EMBEDDING_DIMENSION:
        raise ValueError(
            "unexpected embedding dimension: "
            f"{len(values)} != {e2.EXPECTED_EMBEDDING_DIMENSION}"
        )
    return "[" + ",".join(f"{float(value):.9g}" for value in values) + "]"


def fts_query_text(text: str) -> str:
    """Return a bounded, syntax-safe OR query for PostgreSQL English FTS."""

    terms: list[str] = []
    seen: set[str] = set()
    for match in FTS_WORD_RE.finditer(text):
        term = match.group(0).lower()
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) == FTS_TERM_LIMIT:
            break
    if not terms:
        terms.append("frankengateemptyquery")
    return " | ".join(terms)


def document_key(trace_id: str) -> str:
    return "e2-" + e2.stable_digest(e2.DATASET_REVISION, trace_id)


def ordered_indices(
    rows: Sequence[Sequence[Any]],
    *,
    id_to_index: Mapping[str, int],
    query_index: int,
    document_count: int,
) -> list[int]:
    ranking = [id_to_index[str(row[0])] for row in rows]
    expected = set(range(document_count)) - {query_index}
    if len(ranking) != document_count - 1:
        raise ValueError(
            f"ranking has {len(ranking)} candidates, expected {document_count - 1}"
        )
    if len(set(ranking)) != len(ranking) or set(ranking) != expected:
        raise ValueError("ranking does not contain the exact authorized candidate set")
    return ranking


def set_authority(
    cursor: Any,
    *,
    tenant_id: str,
    subject_id: str,
    authorization_epoch: str,
    classification_ceiling: str,
    purpose: str,
) -> None:
    for key, value in (
        ("app.tenant_id", tenant_id),
        ("app.subject_id", subject_id),
        ("app.authorization_epoch", authorization_epoch),
        ("app.classification_ceiling", classification_ceiling),
        ("app.purpose", purpose),
    ):
        cursor.execute("select set_config(%s, %s, true)", (key, value))


def set_valid_authority(cursor: Any) -> None:
    set_authority(
        cursor,
        tenant_id=TENANT_ID,
        subject_id=SUBJECT_ID,
        authorization_epoch=str(AUTHORIZATION_EPOCH),
        classification_ceiling=str(CLASSIFICATION_CEILING),
        purpose=PURPOSE,
    )


def preflight(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """
        select
          c.relrowsecurity,
          c.relforcerowsecurity,
          a.atttypmod,
          (
            select count(*)
            from trace_research.e2_retrieval_documents
          ),
          (
            select rolsuper or rolbypassrls
            from pg_catalog.pg_roles
            where rolname = 'trace_research_app'
          ),
          (
            select extversion
            from pg_catalog.pg_extension
            where extname = 'vector'
          ),
          (
            select extversion
            from pg_catalog.pg_extension
            where extname = 'pg_trgm'
          )
        from pg_catalog.pg_class c
        join pg_catalog.pg_attribute a
          on a.attrelid = c.oid
         and a.attname = 'embedding'
         and not a.attisdropped
        where c.oid =
          'trace_research.e2_retrieval_documents'::regclass
        """
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("E2 retrieval schema is not installed")
    (
        rls_enabled,
        rls_forced,
        vector_dimension,
        existing_rows,
        unsafe_app_role,
        vector_version,
        trigram_version,
    ) = row
    if not rls_enabled or not rls_forced:
        raise RuntimeError("E2 retrieval table must use forced RLS")
    if int(vector_dimension) != e2.EXPECTED_EMBEDDING_DIMENSION:
        raise RuntimeError("E2 retrieval table is not vector(1024)")
    if int(existing_rows) != 0:
        raise RuntimeError(
            "E2 retrieval table is not empty; refusing to mix candidate cohorts"
        )
    if unsafe_app_role:
        raise RuntimeError("trace_research_app bypasses forced RLS")
    if not vector_version:
        raise RuntimeError("pgvector is required")
    if not trigram_version:
        raise RuntimeError("pg_trgm is required for the joint run")
    cursor.execute("show server_version_num")
    server_version_num = cursor.fetchone()[0]
    cursor.execute(
        """
        select to_regclass(
          'trace_research.e2_retrieval_embedding_hnsw_active_idx'
        ) is not null
        """
    )
    return {
        "database": "local_disposable_postgresql",
        "server_version_num": str(server_version_num),
        "pgvector_version": str(vector_version),
        "pg_trgm_version": str(trigram_version),
        "forced_rls": True,
        "application_role_superuser_or_bypassrls": False,
        "embedding_dimension": int(vector_dimension),
        "hnsw_index_present_but_disabled_for_exact_lane": bool(
            cursor.fetchone()[0]
        ),
        "aurora_emulation": False,
    }


def configure_authority(cursor: Any) -> None:
    cursor.execute(
        """
        insert into trace_research.authority_epochs (
          tenant_id,
          subject_id,
          authorization_epoch,
          classification_ceiling,
          active,
          updated_at
        ) values (%s, %s, %s, %s, true, statement_timestamp())
        on conflict (tenant_id, subject_id) do update set
          authorization_epoch = excluded.authorization_epoch,
          classification_ceiling = excluded.classification_ceiling,
          active = true,
          updated_at = statement_timestamp()
        """,
        (
            TENANT_ID,
            SUBJECT_ID,
            AUTHORIZATION_EPOCH,
            CLASSIFICATION_CEILING,
        ),
    )


def load_documents(
    cursor: Any,
    documents: Sequence[e2.RetrievalDocument],
    document_vectors: Any,
) -> tuple[dict[str, int], float]:
    if len(documents) != 145:
        raise ValueError(f"joint run requires 145 documents, got {len(documents)}")
    if tuple(document_vectors.shape) != (
        len(documents),
        e2.EXPECTED_EMBEDDING_DIMENSION,
    ):
        raise ValueError(f"unexpected document vector shape: {document_vectors.shape}")

    id_to_index: dict[str, int] = {}
    rows: list[tuple[Any, ...]] = []
    for index, (document, embedding) in enumerate(
        zip(documents, document_vectors)
    ):
        key = document_key(document.trace_id)
        if key in id_to_index:
            raise ValueError("document key collision")
        id_to_index[key] = index
        rows.append(
            (
                key,
                TENANT_ID,
                SUBJECT_ID,
                "private",
                None,
                CLASSIFICATION,
                [PURPOSE],
                POLICY_REVISION,
                e2.DATASET_ID,
                e2.DATASET_REVISION,
                key,
                e2.sha256_bytes(document.text.encode("utf-8")),
                "",
                document.text,
                document.text[: e2.MAX_DENSE_CHARACTERS],
                sorted(document.identifiers),
                Json(
                    {
                        "structured_features": sorted(
                            document.structured_features
                        )
                    }
                ),
                vector_literal(embedding),
            )
        )

    started = time.perf_counter_ns()
    execute_values(
        cursor,
        """
        insert into trace_research.e2_retrieval_documents (
          id,
          tenant_id,
          owner_subject_id,
          audience,
          team_id,
          classification,
          allowed_purposes,
          policy_revision,
          source_dataset,
          source_revision,
          source_document_id,
          content_sha256,
          objective_text,
          lexical_text,
          dense_text,
          exact_identifiers,
          structured_metadata,
          embedding
        ) values %s
        """,
        rows,
        template=(
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
            "%s,%s::public.vector(1024))"
        ),
        page_size=16,
    )
    cursor.execute("analyze trace_research.e2_retrieval_documents")
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return id_to_index, elapsed_ms


def storage_receipt(cursor: Any) -> dict[str, int]:
    cursor.execute(
        """
        select
          pg_relation_size(
            'trace_research.e2_retrieval_documents'::regclass
          ),
          pg_indexes_size(
            'trace_research.e2_retrieval_documents'::regclass
          ),
          pg_total_relation_size(
            'trace_research.e2_retrieval_documents'::regclass
          ),
          pg_total_relation_size(
            'trace_research.e2_retrieval_documents'::regclass
          )
          - pg_relation_size(
              'trace_research.e2_retrieval_documents'::regclass
            )
          - pg_indexes_size(
              'trace_research.e2_retrieval_documents'::regclass
            )
        """
    )
    heap, indexes, total, auxiliary = cursor.fetchone()
    return {
        "table_heap_bytes": int(heap),
        "indexes_bytes": int(indexes),
        "auxiliary_bytes": int(auxiliary),
        "total_relation_bytes": int(total),
    }


def query_fts(cursor: Any, query: e2.RetrievalDocument, key: str) -> list[Any]:
    cursor.execute(
        """
        with query as (
          select to_tsquery('english', %s) value
        )
        select d.id, ts_rank_cd(d.content_tsv, query.value) score
        from trace_research.e2_retrieval_documents d
        cross join query
        where d.id <> %s
        order by score desc, d.id
        """,
        (fts_query_text(query.text), key),
    )
    return cursor.fetchall()


def query_trigram(
    cursor: Any,
    query: e2.RetrievalDocument,
    key: str,
) -> list[Any]:
    cursor.execute(
        """
        select d.id, public.similarity(d.lexical_text, %s) score
        from trace_research.e2_retrieval_documents d
        where d.id <> %s
        order by score desc, d.id
        """,
        (query.text[:TRIGRAM_QUERY_CHARACTERS], key),
    )
    return cursor.fetchall()


def query_exact_vector(cursor: Any, query_vector: Sequence[float], key: str) -> list[Any]:
    literal = vector_literal(query_vector)
    cursor.execute(
        """
        select d.id, d.embedding <=> %s::public.vector(1024) distance
        from trace_research.e2_retrieval_documents d
        where d.id <> %s
        order by distance, d.id
        """,
        (literal, key),
    )
    return cursor.fetchall()


def ranked_query(
    run: Any,
    *,
    id_to_index: Mapping[str, int],
    query_index: int,
    document_count: int,
) -> tuple[list[int], float]:
    started = time.perf_counter_ns()
    rows = run()
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return (
        ordered_indices(
            rows,
            id_to_index=id_to_index,
            query_index=query_index,
            document_count=document_count,
        ),
        elapsed_ms,
    )


def exact_vector_plan_receipt(
    cursor: Any,
    query_vector: Sequence[float],
    key: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        explain (format json, costs false)
        select d.id
        from trace_research.e2_retrieval_documents d
        where d.id <> %s
        order by d.embedding <=> %s::public.vector(1024), d.id
        """,
        (key, vector_literal(query_vector)),
    )
    plan = cursor.fetchone()[0][0]["Plan"]
    node_types: set[str] = set()
    index_names: set[str] = set()

    def visit(node: Mapping[str, Any]) -> None:
        if "Node Type" in node:
            node_types.add(str(node["Node Type"]))
        if "Index Name" in node:
            index_names.add(str(node["Index Name"]))
        for child in node.get("Plans", ()):
            visit(child)

    visit(plan)
    ann_index_used = any("hnsw" in name.lower() for name in index_names)
    if ann_index_used or "Seq Scan" not in node_types:
        raise RuntimeError("exact pgvector lane did not use the required exact scan")
    return {
        "node_types": sorted(node_types),
        "ann_index_used": ann_index_used,
        "enable_indexscan": False,
        "enable_bitmapscan": False,
        "enable_indexonlyscan": False,
    }


def quality_and_latency(
    cursor: Any,
    documents: Sequence[e2.RetrievalDocument],
    query_vectors: Any,
    id_to_index: Mapping[str, int],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    task_counts = collections.Counter(
        document.task_identity for document in documents
    )
    eligible_queries = [
        index
        for index, document in enumerate(documents)
        if task_counts[document.task_identity] > 1
    ]
    if len(eligible_queries) != 99:
        raise ValueError(
            f"frozen eligible-query count changed: {len(eligible_queries)}"
        )

    keys = [document_key(document.trace_id) for document in documents]
    cursor.execute("set local enable_indexscan = off")
    cursor.execute("set local enable_bitmapscan = off")
    cursor.execute("set local enable_indexonlyscan = off")

    # One unrecorded warm-up exercises each native operator.
    warm_index = eligible_queries[0]
    query_fts(cursor, documents[warm_index], keys[warm_index])
    query_trigram(cursor, documents[warm_index], keys[warm_index])
    query_exact_vector(cursor, query_vectors[warm_index], keys[warm_index])
    plan_receipt = exact_vector_plan_receipt(
        cursor,
        query_vectors[warm_index],
        keys[warm_index],
    )

    rankings: dict[str, dict[int, list[int]]] = {
        "postgres_fts": {},
        "postgres_trigram": {},
        "postgres_exact_pgvector": {},
        "postgres_hybrid_rrf": {},
    }
    latencies: dict[str, list[float]] = {
        "postgres_fts": [],
        "postgres_trigram": [],
        "postgres_exact_pgvector": [],
        "postgres_hybrid_rrf_end_to_end": [],
        "hybrid_fusion_only": [],
    }

    for query_index in eligible_queries:
        query = documents[query_index]
        key = keys[query_index]
        hybrid_started = time.perf_counter_ns()

        fts_ranking, fts_ms = ranked_query(
            lambda: query_fts(cursor, query, key),
            id_to_index=id_to_index,
            query_index=query_index,
            document_count=len(documents),
        )
        trigram_ranking, trigram_ms = ranked_query(
            lambda: query_trigram(cursor, query, key),
            id_to_index=id_to_index,
            query_index=query_index,
            document_count=len(documents),
        )
        vector_ranking, vector_ms = ranked_query(
            lambda: query_exact_vector(
                cursor,
                query_vectors[query_index],
                key,
            ),
            id_to_index=id_to_index,
            query_index=query_index,
            document_count=len(documents),
        )

        fusion_started = time.perf_counter_ns()
        hybrid_ranking = e2.reciprocal_rank_fusion(
            (fts_ranking, trigram_ranking, vector_ranking),
            rrf_k=e2.RRF_K,
        )
        fusion_ms = (time.perf_counter_ns() - fusion_started) / 1_000_000
        hybrid_ms = (time.perf_counter_ns() - hybrid_started) / 1_000_000

        rankings["postgres_fts"][query_index] = fts_ranking
        rankings["postgres_trigram"][query_index] = trigram_ranking
        rankings["postgres_exact_pgvector"][query_index] = vector_ranking
        rankings["postgres_hybrid_rrf"][query_index] = hybrid_ranking
        latencies["postgres_fts"].append(fts_ms)
        latencies["postgres_trigram"].append(trigram_ms)
        latencies["postgres_exact_pgvector"].append(vector_ms)
        latencies["postgres_hybrid_rrf_end_to_end"].append(hybrid_ms)
        latencies["hybrid_fusion_only"].append(fusion_ms)

    quality = {}
    for name, channel_rankings in rankings.items():
        rows = [
            e2.relevance_metrics(
                documents,
                query_index,
                channel_rankings[query_index],
            )
            for query_index in eligible_queries
        ]
        quality[name] = e2.aggregate_metrics(rows)

    return (
        quality,
        {
            name: latency_summary(values)
            for name, values in latencies.items()
        },
        plan_receipt,
    )


def denial_matrix(
    cursor: Any,
    query: e2.RetrievalDocument,
    query_vector: Sequence[float],
) -> dict[str, dict[str, int]]:
    scenarios = {
        "missing_epoch": {
            "tenant_id": TENANT_ID,
            "subject_id": SUBJECT_ID,
            "authorization_epoch": "",
            "classification_ceiling": str(CLASSIFICATION_CEILING),
            "purpose": PURPOSE,
        },
        "stale_epoch": {
            "tenant_id": TENANT_ID,
            "subject_id": SUBJECT_ID,
            "authorization_epoch": str(AUTHORIZATION_EPOCH - 1),
            "classification_ceiling": str(CLASSIFICATION_CEILING),
            "purpose": PURPOSE,
        },
        "wrong_subject": {
            "tenant_id": TENANT_ID,
            "subject_id": "e2-unauthorized",
            "authorization_epoch": str(AUTHORIZATION_EPOCH),
            "classification_ceiling": str(CLASSIFICATION_CEILING),
            "purpose": PURPOSE,
        },
        "wrong_tenant": {
            "tenant_id": "e2-other-tenant",
            "subject_id": SUBJECT_ID,
            "authorization_epoch": str(AUTHORIZATION_EPOCH),
            "classification_ceiling": str(CLASSIFICATION_CEILING),
            "purpose": PURPOSE,
        },
        "wrong_purpose": {
            "tenant_id": TENANT_ID,
            "subject_id": SUBJECT_ID,
            "authorization_epoch": str(AUTHORIZATION_EPOCH),
            "classification_ceiling": str(CLASSIFICATION_CEILING),
            "purpose": "unapproved-purpose",
        },
    }
    result: dict[str, dict[str, int]] = {}
    for name, authority in scenarios.items():
        set_authority(cursor, **authority)
        cursor.execute(
            """
            with query as (
              select to_tsquery('english', %s) value
            )
            select
              count(*),
              count(*) filter (where d.content_tsv @@ query.value),
              count(*) filter (
                where public.similarity(d.lexical_text, %s) > 0
              ),
              count(*) filter (where d.embedding is not null)
            from trace_research.e2_retrieval_documents d
            cross join query
            """,
            (
                fts_query_text(query.text),
                query.text[:TRIGRAM_QUERY_CHARACTERS],
            ),
        )
        base, fts, trigram, vector = cursor.fetchone()
        result[name] = {
            "base_candidates": int(base),
            "fts_candidates": int(fts),
            "trigram_candidates": int(trigram),
            "vector_candidates": int(vector),
        }
    return result


def lifecycle_oracles(
    cursor: Any,
    documents: Sequence[e2.RetrievalDocument],
) -> dict[str, Any]:
    keys = [document_key(documents[index].trace_id) for index in (0, 1)]
    cursor.execute("reset role")
    cursor.execute(
        """
        update trace_research.e2_retrieval_documents
        set
          visibility_state = 'withdrawn',
          withdrawn_at = statement_timestamp(),
          updated_at = statement_timestamp(),
          lifecycle_receipt = '{"reason":"joint-run-withdrawal-oracle"}'
        where id = %s
        """,
        (keys[0],),
    )
    cursor.execute(
        """
        update trace_research.e2_retrieval_documents
        set
          visibility_state = 'deleted',
          deleted_at = statement_timestamp(),
          updated_at = statement_timestamp(),
          lifecycle_receipt = '{"reason":"joint-run-deletion-oracle"}'
        where id = %s
        """,
        (keys[1],),
    )
    cursor.execute("set local role trace_research_app")
    set_valid_authority(cursor)
    cursor.execute(
        """
        select
          count(*),
          count(*) filter (where id = %s),
          count(*) filter (where id = %s)
        from trace_research.e2_retrieval_documents
        """,
        tuple(keys),
    )
    visible, withdrawn, deleted = cursor.fetchone()
    return {
        "active_candidates_after_oracles": int(visible),
        "expected_active_candidates": len(documents) - 2,
        "withdrawn_candidate_count": int(withdrawn),
        "deleted_candidate_count": int(deleted),
        "passed": (
            int(visible) == len(documents) - 2
            and int(withdrawn) == 0
            and int(deleted) == 0
        ),
    }


def assert_content_free_result(
    result: Mapping[str, Any],
    documents: Sequence[e2.RetrievalDocument],
) -> None:
    serialized = stable_json(result)
    forbidden_keys = (
        '"ranking"',
        '"document_id"',
        '"trace_id"',
        '"task_identity"',
        '"raw_text"',
        '"vector_values"',
        '"exact_identifiers"',
    )
    for forbidden in forbidden_keys:
        if forbidden in serialized:
            raise ValueError(f"durable result contains forbidden field {forbidden}")
    for document in documents:
        for sensitive in (document.trace_id, document.task_identity):
            if len(sensitive) >= 8 and sensitive in serialized:
                raise ValueError("durable result contains a source identity")


def run_joint(args: argparse.Namespace) -> dict[str, Any]:
    documents, source_receipt = e2.load_documents(
        allowlist_path=args.allowlist,
        full_path=args.full,
        archive_root=args.archive_root,
    )
    (query_vectors, document_vectors), dense_contract = e2.dense_embeddings(
        documents,
        args.embedding_model,
        device=args.embedding_device,
    )

    connection = connect(args.dsn)
    rolled_back = False
    post_rollback_rows: int | None = None
    try:
        with connection.cursor() as cursor:
            environment = preflight(cursor)
            # A prior rollback can leave physically allocated, invisible pages.
            # Transaction-local TRUNCATE gives this run a fresh relfilenode for
            # meaningful loaded-state byte measurements; rollback restores the
            # pre-run empty relation and still commits no corpus material.
            cursor.execute(
                "truncate trace_research.e2_retrieval_documents"
            )
            configure_authority(cursor)
            id_to_index, load_ms = load_documents(
                cursor,
                documents,
                document_vectors,
            )
            storage = storage_receipt(cursor)

            cursor.execute("set local role trace_research_app")
            set_valid_authority(cursor)
            cursor.execute(
                "select count(*) from trace_research.e2_retrieval_documents"
            )
            authorized_count = int(cursor.fetchone()[0])
            if authorized_count != len(documents):
                raise RuntimeError(
                    f"authorized candidate count {authorized_count} != {len(documents)}"
                )

            quality, latency, exact_plan = quality_and_latency(
                cursor,
                documents,
                query_vectors,
                id_to_index,
            )
            eligible_index = next(
                index
                for index, document in enumerate(documents)
                if sum(
                    candidate.task_identity == document.task_identity
                    for candidate in documents
                )
                > 1
            )
            denials = denial_matrix(
                cursor,
                documents[eligible_index],
                query_vectors[eligible_index],
            )
            all_denials_zero = all(
                value == 0
                for counts in denials.values()
                for value in counts.values()
            )
            if not all_denials_zero:
                raise RuntimeError("an authority denial exposed retrieval candidates")
            lifecycle = lifecycle_oracles(cursor, documents)
            if not lifecycle["passed"]:
                raise RuntimeError("withdrawal or deletion oracle failed")

        connection.rollback()
        rolled_back = True
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from trace_research.e2_retrieval_documents"
            )
            post_rollback_rows = int(cursor.fetchone()[0])
        connection.rollback()
        if post_rollback_rows != 0:
            raise RuntimeError("rollback left visible E2 retrieval rows")
    finally:
        if not rolled_back:
            connection.rollback()
        connection.close()

    task_counts = collections.Counter(
        document.task_identity for document in documents
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": ANALYSIS_REVISION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.run_date,
        "source": {
            "dataset_id": e2.DATASET_ID,
            "dataset_revision": e2.DATASET_REVISION,
            "dataset_license": e2.manifest_study.DATASET_LICENSE,
            "raw_data_committed": False,
            "projected_text_committed": False,
            "document_ids_committed": False,
            "task_labels_committed": False,
            "embeddings_committed": False,
            **source_receipt,
        },
        "cohort": {
            "documents": len(documents),
            "task_identities": len(task_counts),
            "repeated_task_identities": sum(
                count > 1 for count in task_counts.values()
            ),
            "eligible_queries": sum(
                task_counts[document.task_identity] > 1
                for document in documents
            ),
            "silver_positive_pairs": sum(
                count * (count - 1) // 2
                for count in task_counts.values()
                if count > 1
            ),
            "authorized_candidates_per_query": len(documents) - 1,
        },
        "dense_contract": dense_contract,
        "postgresql": {
            "environment": environment,
            "load": {
                "documents": len(documents),
                "elapsed_ms": load_ms,
                "transaction_committed": False,
                "fresh_transaction_local_relfilenode_for_storage_measurement": True,
            },
            "storage_at_loaded_state": storage,
            "retrieval_contract": {
                "fts": (
                    "English to_tsquery over first 48 unique syntax-safe terms; "
                    "native ts_rank_cd; complete authorized ordering"
                ),
                "trigram": (
                    "native pg_trgm similarity over first 512 query characters; "
                    "complete authorized ordering"
                ),
                "exact_pgvector": (
                    "native cosine distance over distinct Qwen query/document "
                    "vectors with index, bitmap, and index-only scans disabled"
                ),
                "hybrid": (
                    f"fixed equal-channel RRF over FTS, trigram, and exact "
                    f"pgvector; k={e2.RRF_K}"
                ),
                "candidate_scope": (
                    "same 145 loaded documents; self excluded; forced RLS "
                    "applies before every ordering"
                ),
            },
            "quality_against_silver_task_labels": quality,
            "client_observed_sequential_latency": latency,
            "exact_pgvector_plan_receipt": exact_plan,
            "authorized_loaded_candidate_count": authorized_count,
            "denied_pre_ranking_candidate_matrix": denials,
            "all_denied_pre_ranking_candidates_zero": all_denials_zero,
            "lifecycle_oracles": lifecycle,
            "rollback": {
                "required": True,
                "executed": rolled_back,
                "post_rollback_visible_rows": post_rollback_rows,
            },
        },
        "acceptance": {
            "same_candidate_local_postgres_quality_and_rls_gate_passed": (
                len(documents) == 145
                and all_denials_zero
                and lifecycle["passed"]
                and rolled_back
                and post_rollback_rows == 0
            ),
            "human_label_gate_passed": False,
            "real_aurora_gate_passed": False,
            "concurrency_or_scale_gate_passed": False,
            "custom_embedding_authorized": False,
            "database_replacement_authorized": False,
        },
        "claim_limits": [
            "task identity is a publisher-provided silver positive, not blinded human adjudication",
            "the 145-document cohort is a correctness and small-query benchmark, not a scale test",
            "latency is sequential client-observed local PostgreSQL latency without concurrency",
            "the disposable single-node PostgreSQL fixture is not Aurora and does not test failover, replicas, RDS Proxy, or reader lag",
            "FTS and trigram query projections are fixed bounded approximations, not learned query rewriting",
            "all corpus documents share one synthetic private authority; this proves fail-closed mechanics, not enterprise sharing policy quality",
            "withdrawal and deletion are tested as visibility transitions inside the same rollback-only transaction",
            "same benchmark task does not establish that two enterprise users should collaborate",
            "no user skill-gap, productivity, longitudinal memory, or causal improvement claim is supported",
        ],
        "sensitive_material_contract": {
            "raw_text_in_result": False,
            "identifiers_in_result": False,
            "rankings_in_result": False,
            "vectors_in_result": False,
            "source_task_labels_in_result": False,
            "raw_material_locations": [
                "temporary process memory",
                "rollback-only disposable PostgreSQL transaction",
            ],
        },
    }
    assert_content_free_result(result, documents)
    result["result_content_sha256"] = sha256_bytes(
        stable_json(result).encode("utf-8")
    )
    return result


def render_summary(result: Mapping[str, Any]) -> str:
    postgres = result["postgresql"]
    quality = postgres["quality_against_silver_task_labels"]
    rows = []
    for name, metrics in quality.items():
        rows.append(
            "| {name} | {r1:.3f} | {r5:.3f} | {r20:.3f} | {ndcg:.3f} | "
            "{mrr:.3f} |".format(
                name=name,
                r1=metrics["recall_at_1"],
                r5=metrics["recall_at_5"],
                r20=metrics["recall_at_20"],
                ndcg=metrics["ndcg_at_20"],
                mrr=metrics["mrr"],
            )
        )
    latency_rows = []
    for name, metrics in postgres[
        "client_observed_sequential_latency"
    ].items():
        latency_rows.append(
            "| {name} | {p50:.3f} | {p95:.3f} | {p99:.3f} | {maximum:.3f} |".format(
                name=name,
                p50=metrics["p50_ms"],
                p95=metrics["p95_ms"],
                p99=metrics["p99_ms"],
                maximum=metrics["max_ms"],
            )
        )
    limits = "\n".join(f"- {value}" for value in result["claim_limits"])
    return f"""# E2 same-candidate PostgreSQL joint retrieval

**Status:** completed local same-candidate quality + forced-RLS gate
**Dataset documents:** {result['cohort']['documents']}
**Eligible silver-label queries:** {result['cohort']['eligible_queries']}
**Result SHA-256:** `{result['result_content_sha256']}`

The same 145 documents and pinned 1024-dimensional Qwen query/document vectors
were loaded into a rollback-only disposable PostgreSQL transaction. All rankings
ran as the non-owner, non-bypass `trace_research_app` role under forced RLS.

## Native PostgreSQL quality

| Channel | R@1 | R@5 | R@20 | nDCG@20 | MRR |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Sequential local latency

| Operation | p50 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|
{chr(10).join(latency_rows)}

The denied candidate matrix is entirely zero. Withdrawn and soft-deleted rows
both disappeared before ranking. The transaction was rolled back and the
post-rollback visible row count was
{postgres['rollback']['post_rollback_visible_rows']}.

Loaded-state storage was
{postgres['storage_at_loaded_state']['total_relation_bytes']} total bytes,
including {postgres['storage_at_loaded_state']['indexes_bytes']} index bytes.
Raw trace text, source identities, labels, rankings, and vectors are absent from
this result.

## Claim limits

{limits}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--allowlist", required=True, type=pathlib.Path)
    parser.add_argument("--full", required=True, type=pathlib.Path)
    parser.add_argument("--archive-root", required=True, type=pathlib.Path)
    parser.add_argument("--embedding-model", required=True, type=pathlib.Path)
    parser.add_argument(
        "--embedding-device",
        choices=("auto", "cpu", "mps"),
        default="cpu",
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--summary", required=True, type=pathlib.Path)
    parser.add_argument("--run-date", default="2026-07-30")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_joint(args)
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
                "documents": result["cohort"]["documents"],
                "eligible_queries": result["cohort"]["eligible_queries"],
                "denials_zero": result["postgresql"][
                    "all_denied_pre_ranking_candidates_zero"
                ],
                "post_rollback_rows": result["postgresql"]["rollback"][
                    "post_rollback_visible_rows"
                ],
                "result_content_sha256": result["result_content_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
