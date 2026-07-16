#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/.."
command -v helm >/dev/null || { echo "helm is required" >&2; exit 1; }

rendered="$(helm template external-deps "$CHART_DIR" \
  --set storage.mode=postgres \
  --set postgresql.external.enabled=true \
  --set postgresql.external.host=aurora.example.internal \
  --set postgresql.external.database=frankengate \
  --set postgresql.external.user=gateway \
  --set vectorStore.enabled=true \
  --set vectorStore.type=redis \
  --set vectorStore.redis.external.enabled=true \
  --set vectorStore.redis.external.host=redis.example.internal)"

grep -q 'aurora.example.internal' <<<"$rendered" || { echo "external PostgreSQL host was not rendered" >&2; exit 1; }
grep -q 'redis.example.internal' <<<"$rendered" || { echo "external Redis host was not rendered" >&2; exit 1; }
if grep -q 'kind: StatefulSet' <<<"$rendered"; then
  echo "external dependency render unexpectedly includes bundled StatefulSet" >&2
  exit 1
fi
echo "external PostgreSQL and Redis values render without bundled databases"
