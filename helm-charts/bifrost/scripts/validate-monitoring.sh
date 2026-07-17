#!/usr/bin/env bash
# Validate the optional Prometheus Operator resources without a cluster.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/.."
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

helm template monitoring-test "$CHART_DIR" --set image.tag=validation \
  --set monitoring.serviceMonitor.enabled=true \
  --set monitoring.prometheusRule.enabled=true \
  --set 'monitoring.prometheusRule.rules[0].alert=FrankenGateValidationAlert' >"$tmp"

grep -q '^kind: ServiceMonitor$' "$tmp"
grep -q '^kind: PrometheusRule$' "$tmp"
grep -q 'path: /metrics' "$tmp"
grep -q 'alert: FrankenGateValidationAlert' "$tmp"

if helm template monitoring-disabled "$CHART_DIR" --set image.tag=validation | \
  grep -qE '^kind: (ServiceMonitor|PrometheusRule)$'; then
  echo "monitoring resources rendered while disabled" >&2
  exit 1
fi

echo "Prometheus Operator ServiceMonitor and PrometheusRule validation passed"
