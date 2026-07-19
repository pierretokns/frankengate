#!/usr/bin/env bash
set -euo pipefail

# No-live-model overhead smoke benchmark. The fixture returns the same
# response for both paths; /gateway adds governance/OTEL-shaped bookkeeping.
N="${N:-200}"
MAX_P95_OVERHEAD_MS="${MAX_P95_OVERHEAD_MS:-10}"
MAX_P50_OVERHEAD_MS="${MAX_P50_OVERHEAD_MS:-5}"
PORT="${PORT:-18080}"
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
fixture_pid=""
cleanup() { [[ -z "$fixture_pid" ]] || kill "$fixture_pid" 2>/dev/null || true; }
trap cleanup EXIT

python3 "$ROOT/overhead-fixture.py" --port "$PORT" >/dev/null 2>&1 &
fixture_pid=$!
for _ in {1..50}; do
  if curl --silent --output /dev/null --max-time 1 "http://127.0.0.1:$PORT/direct"; then break; fi
  sleep 0.02
done

REQUEST_BODY='{"model":"fixture","tenant":"bench","vk":"vk-bench","messages":[{"role":"user","content":"ping"}]}' \
DIRECT_URL="http://127.0.0.1:$PORT/direct" \
GATEWAY_URL="http://127.0.0.1:$PORT/gateway" \
N="$N" MAX_P95_OVERHEAD_MS="$MAX_P95_OVERHEAD_MS" MAX_P50_OVERHEAD_MS="$MAX_P50_OVERHEAD_MS" \
  "$ROOT/benchmark-gateway-overhead.sh"
