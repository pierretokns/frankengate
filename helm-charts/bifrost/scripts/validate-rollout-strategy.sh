#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/.."
command -v helm >/dev/null || { echo "helm is required" >&2; exit 1; }

rendered="$(helm template capacity-safe "$CHART_DIR" \
  --set replicaCount=3 \
  --set storage.mode=postgres \
  --set postgresql.external.enabled=true \
  --set postgresql.external.host=aurora.example.internal \
  --set strategy.type=RollingUpdate \
  --set strategy.rollingUpdate.maxSurge=0 \
  --set strategy.rollingUpdate.maxUnavailable=1)"

grep -q 'maxSurge: 0' <<<"$rendered" || { echo "capacity-safe maxSurge was not rendered" >&2; exit 1; }
grep -q 'maxUnavailable: 1' <<<"$rendered" || { echo "capacity-safe maxUnavailable was not rendered" >&2; exit 1; }
grep -q 'replicas: 3' <<<"$rendered" || { echo "three replicas were not rendered" >&2; exit 1; }
echo "capacity-safe three-replica rollout strategy rendered"
