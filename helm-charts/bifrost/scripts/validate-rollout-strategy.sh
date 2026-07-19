#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$SCRIPT_DIR/.."
command -v helm >/dev/null || { echo "helm is required" >&2; exit 1; }

rendered="$(helm template capacity-safe "$CHART_DIR" \
  --set replicaCount=3 \
  --set autoscaling.enabled=false \
  --set storage.mode=postgres \
  --set postgresql.external.enabled=true \
  --set postgresql.external.host=aurora.example.internal \
  --set strategy.type=RollingUpdate \
  --set strategy.rollingUpdate.maxSurge=0 \
  --set strategy.rollingUpdate.maxUnavailable=1)"

grep -q 'maxSurge: 0' <<<"$rendered" || { echo "capacity-safe maxSurge was not rendered" >&2; exit 1; }
grep -q 'maxUnavailable: 1' <<<"$rendered" || { echo "capacity-safe maxUnavailable was not rendered" >&2; exit 1; }
# The exact-capacity proof must be a fixed three-replica Deployment.  In
# particular, an HPA must not silently replace spec.replicas in this mode:
# that makes the maxSurge=0/maxUnavailable=1 contract impossible to reason
# about on a three-node cluster.
deployment="$(helm template capacity-safe "$CHART_DIR" \
  --show-only templates/deployment.yaml \
  --set replicaCount=3 \
  --set autoscaling.enabled=false \
  --set storage.mode=postgres \
  --set postgresql.external.enabled=true \
  --set postgresql.external.host=aurora.example.internal \
  --set strategy.type=RollingUpdate \
  --set strategy.rollingUpdate.maxSurge=0 \
  --set strategy.rollingUpdate.maxUnavailable=1)"
grep -q '^kind: Deployment$' <<<"$deployment" || { echo "capacity-safe render is not a Deployment" >&2; exit 1; }
[[ "$(grep -c '^kind:' <<<"$deployment")" -eq 1 ]] || { echo "capacity-safe render contains multiple objects" >&2; exit 1; }
grep -q '^  replicas: 3$' <<<"$deployment" || { echo "three fixed replicas were not rendered" >&2; exit 1; }

if grep -q '^kind: HorizontalPodAutoscaler$' <<<"$rendered"; then
  echo "capacity-safe render unexpectedly contains an HPA" >&2
  exit 1
fi
echo "capacity-safe fixed three-replica Deployment rendered (no HPA)"

# Verify the database budget is evaluated against the HPA ceiling, not merely
# the current replica count.  This catches a rollout that is safe at startup
# but exhausts Aurora after an HPA scale-up.
if helm template capacity-budget "$CHART_DIR" \
  --set autoscaling.enabled=true --set autoscaling.minReplicas=1 --set autoscaling.maxReplicas=6 \
  --set storage.mode=postgres --set postgresql.external.enabled=true \
  --set postgresql.external.host=aurora.example.internal \
  --set postgresql.connectionBudget.enabled=true --set postgresql.connectionBudget.maxConnections=100 \
  --set postgresql.connectionBudget.reservedConnections=10 \
  --set storage.configStore.maxOpenConns=10 --set storage.logsStore.maxOpenConns=10 >/dev/null 2>&1; then
  echo "expected HPA connection-budget overflow to be rejected" >&2
  exit 1
fi
echo "capacity budget rejects HPA ceiling that would exhaust PostgreSQL"

if helm template capacity-budget-invalid "$CHART_DIR" \
  --set storage.mode=postgres --set postgresql.external.enabled=true \
  --set postgresql.external.host=aurora.example.internal \
  --set postgresql.connectionBudget.enabled=true --set postgresql.connectionBudget.maxConnections=100 \
  --set postgresql.connectionBudget.reservedConnections=-1 >/dev/null 2>&1; then
  echo "expected negative reserved PostgreSQL connections to be rejected" >&2
  exit 1
fi
echo "capacity budget rejects negative reserved connections"
