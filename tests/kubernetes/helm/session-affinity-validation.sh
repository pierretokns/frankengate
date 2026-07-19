#!/usr/bin/env bash
set -euo pipefail

# Session affinity is an optional Service routing optimization, not a
# correctness requirement: all request/session state must remain in the
# configured stores so HPA can move clients between replicas safely.
chart=${1:-helm-charts/bifrost}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

helm template affinity-default "$chart" >/dev/null

cat >"$tmp/invalid.yaml" <<'EOF'
service:
  sessionAffinity: None
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 60
EOF
if helm template affinity-invalid "$chart" -f "$tmp/invalid.yaml" >"$tmp/out" 2>"$tmp/err"; then
  echo "expected sessionAffinityConfig with None to fail" >&2
  exit 1
fi
grep -q 'sessionAffinityConfig requires service.sessionAffinity=ClientIP' "$tmp/err"

cat >"$tmp/valid.yaml" <<'EOF'
service:
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 600
EOF
helm template affinity-valid "$chart" -f "$tmp/valid.yaml" >/dev/null

echo "session affinity validation passed"
