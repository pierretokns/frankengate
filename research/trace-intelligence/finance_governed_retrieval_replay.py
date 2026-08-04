#!/usr/bin/env python3
"""Run the FinanceBench embedding through a disposable forced-RLS pgvector lab.

The source corpus and vectors remain outside Git.  The data transaction is
rolled back, and the disposable table is dropped after the receipt is written.
The result measures governed candidate visibility plus relevance/latency; it is
not an Aurora availability or production-scale claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import statistics
import time
from collections.abc import Sequence
from typing import Any

from psycopg2 import connect
from psycopg2.extras import Json, execute_values

import finance_mteb_retrieval_benchmark as benchmark


SCHEMA_VERSION = "frankengate-finance-governed-retrieval-v1"
ANALYSIS_REVISION = "financebench-r1-forced-rls-pgvector-v1"
TENANT = "financebench-tenant"
SUBJECT = "financebench-alice"
AUTHORIZATION_EPOCH = 41
CLASSIFICATION_CEILING = 2
PURPOSE = "quality-improvement"
POLICY_REVISION = "financebench-policy-v1"
SOURCE_DATASET = benchmark.DATASET_ID
DOC_MAX_CHARACTERS = 2500
QUERY_MAX_CHARACTERS = 2000
TABLE = "trace_research.finance_retrieval_documents"
MIGRATION = pathlib.Path(__file__).resolve().parent / "sql/012_finance_retrieval_768.sql"


def vector_literal(values: Sequence[float]) -> str:
    if len(values) != 768:
        raise ValueError(f"expected 768 dimensions, got {len(values)}")
    return "[" + ",".join(f"{float(value):.9g}" for value in values) + "]"


def set_setting(cursor: Any, key: str, value: str | None) -> None:
    cursor.execute("select set_config(%s, %s, true)", (key, value or ""))


def set_authority(cursor: Any, *, tenant: str | None, subject: str | None, epoch: str | None, ceiling: str | None, purpose: str | None) -> None:
    for key, value in (
        ("app.tenant_id", tenant),
        ("app.subject_id", subject),
        ("app.authorization_epoch", epoch),
        ("app.classification_ceiling", ceiling),
        ("app.purpose", purpose),
    ):
        set_setting(cursor, key, value)


def percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def latency_summary(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "samples": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "max_ms": max(values),
    }


def retrieve(cursor: Any, vector: Sequence[float], limit: int = 20) -> tuple[list[str], float]:
    started = time.perf_counter()
    cursor.execute(
        f"""
        select source_document_id
        from {TABLE}
        order by embedding <=> %s::public.vector, source_document_id
        limit %s
        """,
        (vector_literal(vector), limit),
    )
    rows = [str(row[0]) for row in cursor.fetchall()]
    return rows, (time.perf_counter() - started) * 1_000


def quality_metrics(ranked: dict[str, list[str]], relevant: dict[str, set[str]]) -> dict[str, float | int]:
    reciprocal: list[float] = []
    recalls = {k: [] for k in (1, 5, 10, 20)}
    for query_id, positives in relevant.items():
        values = ranked[query_id]
        positions = [position for position, value in enumerate(values, 1) if value in positives]
        reciprocal.append(1 / positions[0] if positions else 0.0)
        for k in recalls:
            recalls[k].append(float(bool(set(values[:k]) & positives)))
    result: dict[str, float | int] = {
        "queries": len(relevant),
        "mrr": statistics.fmean(reciprocal),
    }
    result.update({f"recall@{k}": statistics.fmean(values) for k, values in recalls.items()})
    return result


def load_inputs(corpus_path: pathlib.Path, queries_path: pathlib.Path, qrels_path: pathlib.Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, set[str]]]:
    corpus = benchmark.read_arrow(corpus_path)
    queries = benchmark.read_arrow(queries_path)
    qrels = benchmark.read_arrow(qrels_path)
    relevant: dict[str, set[str]] = {}
    for row in qrels:
        if float(row.get("score", 0)) > 0:
            relevant.setdefault(str(row["query-id"]), set()).add(str(row["corpus-id"]))
    return corpus, queries, relevant


def setup_database(dsn: str) -> dict[str, Any]:
    connection = connect(dsn)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"drop table if exists {TABLE} cascade")
            cursor.execute("drop function if exists trace_research.finance_authority_valid(text, text) cascade")
            cursor.execute("drop table if exists trace_research.finance_authority_epochs cascade")
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
            cursor.execute(
                """
                select
                  c.relrowsecurity,
                  c.relforcerowsecurity,
                  format_type(a.atttypid, a.atttypmod),
                  (select rolsuper or rolbypassrls from pg_roles where rolname = 'trace_research_app'),
                  (select extversion from pg_extension where extname = 'vector'),
                  (select exists (select 1 from pg_indexes where indexname = 'finance_retrieval_embedding_hnsw_active_idx'))
                from pg_class c
                join pg_attribute a on a.attrelid = c.oid and a.attname = 'embedding' and not a.attisdropped
                where c.oid = %s::regclass
                """,
                (TABLE,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("finance retrieval table was not created")
            rls, forced, vector_type, unsafe_role, vector_version, hnsw = row
            cursor.execute("show server_version")
            server_version = str(cursor.fetchone()[0])
            if not rls or not forced or vector_type != "vector(768)" or unsafe_role or not vector_version:
                raise RuntimeError("governed pgvector preflight failed")
            return {
                "database": "local_disposable_postgresql_pgvector",
                "server_version": server_version,
                "pgvector_version": str(vector_version),
                "forced_rls": bool(forced),
                "application_role_superuser_or_bypassrls": bool(unsafe_role),
                "embedding_type": vector_type,
                "hnsw_index_present": bool(hnsw),
                "aurora_emulation": False,
            }
    finally:
        connection.close()


def run(*, dsn: str, corpus_path: pathlib.Path, queries_path: pathlib.Path, qrels_path: pathlib.Path, model_id: str) -> dict[str, Any]:
    corpus, queries, relevant = load_inputs(corpus_path, queries_path, qrels_path)
    corpus_by_id = {str(row["_id"]): row for row in corpus}
    query_by_id = {str(row["_id"]): row for row in queries}
    query_ids = [query_id for query_id in query_by_id if query_id in relevant]
    document_ids = list(corpus_by_id)
    documents = [str(corpus_by_id[doc_id].get("title", "")) + "\n" + str(corpus_by_id[doc_id]["text"]) for doc_id in document_ids]
    query_texts = [str(query_by_id[query_id]["text"]) for query_id in query_ids]
    projected_documents = [value[:DOC_MAX_CHARACTERS] for value in documents]
    projected_queries = [value[:QUERY_MAX_CHARACTERS] for value in query_texts]
    query_vectors, document_vectors, model_receipt = benchmark._embed(model_id, projected_queries, projected_documents)
    source_revision = benchmark.DATASET_REVISION
    setup = setup_database(dsn)

    connection = connect(dsn)
    connection.autocommit = False
    ranked: dict[str, list[str]] = {}
    latencies: list[float] = []
    denied: dict[str, int] = {}
    deleted_source_document_id = str(next(iter(relevant[query_ids[0]])))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into trace_research.finance_authority_epochs (tenant_id, subject_id, authorization_epoch, classification_ceiling, active) values (%s, %s, %s, %s, true)",
                (TENANT, SUBJECT, AUTHORIZATION_EPOCH, CLASSIFICATION_CEILING),
            )
            records = []
            for doc_id, embedding, text in zip(document_ids, document_vectors, projected_documents):
                content_hash = hashlib.sha256((str(corpus_by_id[doc_id].get("title", "")) + "\n" + str(corpus_by_id[doc_id]["text"])).encode()).hexdigest()
                records.append(
                    (
                        f"finance-{doc_id}", TENANT, SUBJECT, "private", 1,
                        [PURPOSE], POLICY_REVISION, SOURCE_DATASET, source_revision,
                        doc_id, content_hash, text, text, Json({"source": "financebench", "document_id": doc_id}),
                        vector_literal(embedding), Json({"lifecycle": "active"}),
                    )
                )
            execute_values(
                cursor,
                f"insert into {TABLE} (id, tenant_id, owner_subject_id, audience, classification, allowed_purposes, policy_revision, source_dataset, source_revision, source_document_id, content_sha256, lexical_text, dense_text, structured_metadata, embedding, lifecycle_receipt) values %s",
                records,
                template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::public.vector,%s)",
                page_size=100,
            )
            cursor.execute(f"analyze {TABLE}")
            cursor.execute(f"select count(*) from {TABLE}")
            inserted = int(cursor.fetchone()[0])

            cursor.execute("set role trace_research_app")
            set_authority(cursor, tenant=TENANT, subject=SUBJECT, epoch=str(AUTHORIZATION_EPOCH), ceiling=str(CLASSIFICATION_CEILING), purpose=PURPOSE)
            cursor.execute(f"select count(*) from {TABLE}")
            authorized_count = int(cursor.fetchone()[0])
            for query_id, vector in zip(query_ids, query_vectors):
                values, elapsed = retrieve(cursor, vector)
                ranked[query_id] = values
                latencies.append(elapsed)

            denial_cases = {
                "wrong_tenant": ("other-tenant", SUBJECT, str(AUTHORIZATION_EPOCH), str(CLASSIFICATION_CEILING), PURPOSE),
                "wrong_subject": (TENANT, "financebench-bob", str(AUTHORIZATION_EPOCH), str(CLASSIFICATION_CEILING), PURPOSE),
                "stale_epoch": (TENANT, SUBJECT, "40", str(CLASSIFICATION_CEILING), PURPOSE),
                "wrong_purpose": (TENANT, SUBJECT, str(AUTHORIZATION_EPOCH), str(CLASSIFICATION_CEILING), "incident-response"),
                "insufficient_clearance": (TENANT, SUBJECT, str(AUTHORIZATION_EPOCH), "0", PURPOSE),
                "missing_epoch": (TENANT, SUBJECT, None, str(CLASSIFICATION_CEILING), PURPOSE),
            }
            for name, values in denial_cases.items():
                set_authority(cursor, tenant=values[0], subject=values[1], epoch=values[2], ceiling=values[3], purpose=values[4])
                cursor.execute(f"select count(*) from {TABLE}")
                denied[name] = int(cursor.fetchone()[0])

            cursor.execute("reset role")
            cursor.execute(
                f"update {TABLE} set visibility_state = 'deleted', deleted_at = statement_timestamp(), lifecycle_receipt = %s where source_document_id = %s",
                (Json({"reason": "deletion-oracle"}), deleted_source_document_id),
            )
            cursor.execute("set role trace_research_app")
            set_authority(cursor, tenant=TENANT, subject=SUBJECT, epoch=str(AUTHORIZATION_EPOCH), ceiling=str(CLASSIFICATION_CEILING), purpose=PURPOSE)
            cursor.execute(f"select count(*) from {TABLE}")
            post_delete_count = int(cursor.fetchone()[0])
            deleted_visible = any(deleted_source_document_id in values for values in ranked.values())
            cursor.execute(f"select count(*) from {TABLE} where source_document_id = %s", (deleted_source_document_id,))
            deleted_query_visible = int(cursor.fetchone()[0])
    finally:
        connection.rollback()
        connection.close()

    cleanup = connect(dsn)
    cleanup.autocommit = True
    try:
        with cleanup.cursor() as cursor:
            cursor.execute(f"select count(*) from {TABLE}")
            rows_after_rollback = int(cursor.fetchone()[0])
            cursor.execute(f"drop table if exists {TABLE} cascade")
            cursor.execute("drop table if exists trace_research.finance_authority_epochs cascade")
            cursor.execute("select to_regclass(%s)", (TABLE,))
            table_after_cleanup = cursor.fetchone()[0]
    finally:
        cleanup.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": ANALYSIS_REVISION,
        "dataset": {
            "id": SOURCE_DATASET,
            "revision": source_revision,
            "corpus_rows": len(corpus),
            "query_rows": len(queries),
            "evaluated_queries": len(query_ids),
            "multi_positive_queries": sum(len(values) > 1 for values in relevant.values()),
            "corpus_sha256": benchmark.file_sha256(corpus_path),
            "queries_sha256": benchmark.file_sha256(queries_path),
            "qrels_sha256": benchmark.file_sha256(qrels_path),
            "projection": {
                "document_max_characters": DOC_MAX_CHARACTERS,
                "query_max_characters": QUERY_MAX_CHARACTERS,
                "documents_truncated": sum(len(value) > DOC_MAX_CHARACTERS for value in documents),
                "queries_truncated": sum(len(value) > QUERY_MAX_CHARACTERS for value in query_texts),
            },
        },
        "model": {"model_id": model_id, "embedding_dimension": 768, **model_receipt},
        "database": setup,
        "inserted_rows": inserted,
        "authorized_candidate_count": authorized_count,
        "quality": {**quality_metrics(ranked, relevant), "query_latency_ms": latency_summary(latencies)},
        "authorization_oracles": {
            "denied_candidate_counts": denied,
            "all_denials_zero": all(value == 0 for value in denied.values()),
        },
        "deletion_oracle": {
            "deleted_source_document_id": deleted_source_document_id,
            "post_delete_authorized_count": post_delete_count,
            "deleted_row_visible_after_update": deleted_query_visible != 0,
            "deleted_id_present_in_pre_delete_rankings": deleted_visible,
            "deletion_filtered_before_ranking": deleted_query_visible == 0,
        },
        "cleanup": {
            "rows_after_transaction_rollback": rows_after_rollback,
            "table_after_cleanup": table_after_cleanup,
            "raw_data_committed": False,
        },
        "claim_boundary": {
            "governed_rls_exercised": True,
            "deletion_exercised": True,
            "aurora_scale_or_failover_evaluated": False,
            "production_promotion_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--corpus", type=pathlib.Path, required=True)
    parser.add_argument("--queries", type=pathlib.Path, required=True)
    parser.add_argument("--qrels", type=pathlib.Path, required=True)
    parser.add_argument("--model", default="BalyasnyAI/multilingual-e5-base")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = run(
        dsn=args.dsn,
        corpus_path=args.corpus,
        queries_path=args.queries,
        qrels_path=args.qrels,
        model_id=args.model,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    q = result["quality"]
    lines = [
        "# FinanceBench governed pgvector replay",
        "",
        f"The revision-pinned FinanceBench corpus was loaded into a disposable forced-RLS PostgreSQL/pgvector table using the 768-dimensional finance-specialized embedding.",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| Recall@20 | {q['recall@20']:.4f} |",
        f"| MRR | {q['mrr']:.4f} |",
        f"| authorized candidates | {result['authorized_candidate_count']} |",
        f"| latency p50 (ms) | {q['query_latency_ms']['p50_ms']:.3f} |",
        f"| latency p95 (ms) | {q['query_latency_ms']['p95_ms']:.3f} |",
        "",
        f"All denial scenarios zero: `{result['authorization_oracles']['all_denials_zero']}`.",
        f"Deletion filtered before ranking: `{result['deletion_oracle']['deletion_filtered_before_ranking']}`.",
        f"Rows after rollback: `{result['cleanup']['rows_after_transaction_rollback']}`; table cleanup: `{result['cleanup']['table_after_cleanup'] is None}`.",
        "",
        "This proves a local governed RLS/deletion path, not Aurora availability, failover, or production promotion.",
    ]
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "quality": q, "authorization": result["authorization_oracles"], "deletion": result["deletion_oracle"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
