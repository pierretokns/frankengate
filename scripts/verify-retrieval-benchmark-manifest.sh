#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
MANIFEST="${1:-$ROOT/tests/retrieval/benchmark-manifest.json}"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

jq -e '
  .schema_version == "retrieval-eval-v1" and
  (.required_slices | length >= 8) and
  (.arms | length == 5) and
  ((.metrics | index("acl_false_positive_rate")) != null) and
  ((.metrics | index("p95_latency_ms")) != null) and
  (.record_contract.required | index("policy_version")) != null and
  (.record_contract.required | index("index_revision")) != null and
  (.record_contract.forbidden | index("query_text")) != null and
  (.record_contract.forbidden | index("raw_output")) != null and
  (.promotion_gates.requires_human_mr_approval == true) and
  (.promotion_gates.candidate_may_auto_publish == false)
' "$MANIFEST" >/dev/null

echo "retrieval benchmark manifest valid: $MANIFEST"
