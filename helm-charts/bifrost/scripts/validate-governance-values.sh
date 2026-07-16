#!/usr/bin/env bash
set -euo pipefail

# Cluster-independent proof that the fork chart accepts and renders the
# governance virtual-key shape. This complements validate.sh, whose final
# kubectl dry-run requires a live cluster.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }
command -v helm >/dev/null || { echo "helm is required" >&2; exit 1; }

schema="$ROOT/values.schema.json"
for path in \
  '.properties.bifrost.properties.governance.properties.virtualKeys' \
  '.properties.bifrost.properties.governance.properties."virtual-keys"'; do
  jq -e "$path != null" "$schema" >/dev/null || {
    echo "missing Helm schema path: $path" >&2
    exit 1
  }
done

rendered="$(helm template governance-values "$ROOT" \
  -f "$ROOT/values-examples/providers-and-virtual-keys.yaml")"
config="$(printf '%s\n' "$rendered" | awk '
  /^[[:space:]]*config\.json: \|[[:space:]]*$/ { capture=1; next }
  capture && /^---/ { exit }
  capture { sub(/^[[:space:]]*/, ""); print }
')"
printf '%s\n' "$config" | jq -e '.governance.virtual_keys | type == "array"' >/dev/null || {
  echo "rendered config is missing governance.virtual_keys" >&2
  exit 1
}

echo "governance virtual-key Helm schema and render validation passed"
