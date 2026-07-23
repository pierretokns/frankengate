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
ready=0
for _ in {1..50}; do
  if curl --silent --output /dev/null --max-time 1 "http://127.0.0.1:$PORT/direct"; then
    ready=1
    break
  fi
  sleep 0.02
done
if [[ "$ready" != 1 ]]; then
  if ! kill -0 "$fixture_pid" 2>/dev/null; then
    echo "benchmark fixture exited before binding 127.0.0.1:$PORT; check loopback permissions or port availability" >&2
  else
    echo "benchmark fixture did not become ready on 127.0.0.1:$PORT within 1s" >&2
  fi
  exit 1
fi

REQUEST_BODY='{"model":"fixture","tenant":"bench","vk":"vk-bench","messages":[{"role":"user","content":"ping"}]}' \
DIRECT_URL="http://127.0.0.1:$PORT/direct" \
GATEWAY_URL="http://127.0.0.1:$PORT/gateway" \
N="$N" MAX_P95_OVERHEAD_MS="$MAX_P95_OVERHEAD_MS" MAX_P50_OVERHEAD_MS="$MAX_P50_OVERHEAD_MS" \
  "$ROOT/benchmark-gateway-overhead.sh"
