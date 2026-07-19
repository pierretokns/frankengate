#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
MANIFEST="${1:-$ROOT/tests/retrieval/benchmark-manifest.json}"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

jq -e '
  .schema_version == "retrieval-eval-v1" and
  ((["finance_exact_identifier", "finance_semantic_paraphrase", "enterprise_jargon", "hard_negative", "acl_boundary", "deleted_document", "stale_index", "out_of_domain"] - .required_slices) | length == 0) and
  ((["lexical", "dense", "hybrid", "hybrid_reranker", "adapted_candidate"] - .arms) | length == 0) and
  ((["recall_at_1", "recall_at_5", "ndcg_at_10", "mrr", "acl_false_positive_rate", "acl_false_negative_rate", "p50_latency_ms", "p95_latency_ms"] - .metrics) | length == 0) and
  ((["case_id", "tenant_id", "query_hash", "positive_source_ids", "hard_negative_source_ids", "principal_scope", "policy_version", "index_revision", "deleted_source_ids", "expected_authorized_source_ids"] - .record_contract.required) | length == 0) and
  ((["query_text", "document_text", "raw_prompt", "raw_output", "token_ids"] - .record_contract.forbidden) | length == 0) and
  (.promotion_gates.requires_human_mr_approval == true) and
  (.promotion_gates.candidate_may_auto_publish == false)
' "$MANIFEST" >/dev/null

echo "retrieval benchmark manifest valid: $MANIFEST"
