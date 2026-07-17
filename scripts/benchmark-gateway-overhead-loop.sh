#!/usr/bin/env bash
set -euo pipefail

# Periodically run benchmark-gateway-overhead.sh and append timestamped JSONL.
: "${DIRECT_URL:?set DIRECT_URL}"
: "${GATEWAY_URL:?set GATEWAY_URL}"
: "${REQUEST_BODY:?set REQUEST_BODY}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-60}"
OUTPUT="${OUTPUT:-frankengate-overhead.jsonl}"
N="${N:-100}"
MAX_P95_OVERHEAD_MS="${MAX_P95_OVERHEAD_MS:-10}"

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
while :; do
  set +e
  result="$(DIRECT_URL="$DIRECT_URL" GATEWAY_URL="$GATEWAY_URL" REQUEST_BODY="$REQUEST_BODY" \
    N="$N" MAX_P95_OVERHEAD_MS="$MAX_P95_OVERHEAD_MS" \
    "$script_dir/benchmark-gateway-overhead.sh")"
  status=$?
  set -e
  timestamp="$(date -u +%FT%TZ)"
  printf '{"timestamp":"%s","status":%d,"measurement":%s}\n' \
    "$timestamp" "$status" "$result" >>"$OUTPUT"
  sleep "$INTERVAL_SECONDS"
done
