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
  --set vectorStore.redis.external.host=redis.example.internal \
  --set postgresql.external.existingSecret=aurora-credentials \
  --set vectorStore.redis.external.existingSecret=redis-credentials)"

grep -q 'aurora.example.internal' <<<"$rendered" || { echo "external PostgreSQL host was not rendered" >&2; exit 1; }
grep -q 'redis.example.internal' <<<"$rendered" || { echo "external Redis host was not rendered" >&2; exit 1; }
grep -q 'name: aurora-credentials' <<<"$rendered" || { echo "external PostgreSQL secret reference was not rendered" >&2; exit 1; }
grep -q 'name: redis-credentials' <<<"$rendered" || { echo "external Redis secret reference was not rendered" >&2; exit 1; }
if grep -q 'kind: StatefulSet' <<<"$rendered"; then
  echo "external dependency render unexpectedly includes bundled StatefulSet" >&2
  exit 1
fi

# Assert the application config, not merely a Kubernetes object, points at the
# external endpoints. This catches regressions where values are accepted by
# the schema but silently fall back to chart-managed service names.
config="$(printf '%s\n' "$rendered" | awk '
  /^[[:space:]]*config\.json: \|[[:space:]]*$/ { capture=1; next }
  capture && /^---/ { exit }
  capture { sub(/^[[:space:]]*/, ""); print }
')"
printf '%s\n' "$config" | jq -e '
  .config_store.type == "postgres" and
  .config_store.config.host == "aurora.example.internal" and
  .config_store.config.db_name == "frankengate" and
  .logs_store.type == "postgres" and
  .logs_store.config.host == "aurora.example.internal" and
  .vector_store.config.addr == "redis.example.internal:6379"
' >/dev/null || {
  echo "rendered gateway config does not preserve external PostgreSQL/Redis endpoints" >&2
  exit 1
}
echo "external PostgreSQL and Redis values render without bundled databases"
