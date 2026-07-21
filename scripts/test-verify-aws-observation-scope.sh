#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_scope="$(mktemp)"
trap 'rm -f "$tmp_scope"' EXIT

jq 'del(.client_matrix)' "$ROOT/provenance/aws-observation-scope.json" >"$tmp_scope"
if SCOPE_PATH="$tmp_scope" "$ROOT/scripts/verify-aws-observation-scope.sh" > /tmp/aws-scope-verifier.out 2>&1; then
  echo "regression failed: verifier accepted a missing client_matrix" >&2
  exit 1
fi
grep -F "client_matrix must contain exactly six lane entries" /tmp/aws-scope-verifier.out >/dev/null || {
  echo "regression failed: missing client_matrix diagnostic" >&2
  cat /tmp/aws-scope-verifier.out >&2
  exit 1
}
rm -f /tmp/aws-scope-verifier.out
echo "missing client_matrix regression passed"
