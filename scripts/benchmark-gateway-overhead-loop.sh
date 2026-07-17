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
MAX_ERROR_RATE="${MAX_ERROR_RATE:-0}"
HEADERS_FILE="${HEADERS_FILE:-}"

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
while :; do
  set +e
  result="$(DIRECT_URL="$DIRECT_URL" GATEWAY_URL="$GATEWAY_URL" REQUEST_BODY="$REQUEST_BODY" \
    N="$N" MAX_P95_OVERHEAD_MS="$MAX_P95_OVERHEAD_MS" \
    MAX_ERROR_RATE="$MAX_ERROR_RATE" HEADERS_FILE="$HEADERS_FILE" \
    "$script_dir/benchmark-gateway-overhead.sh")"
  status=$?
  set -e
  timestamp="$(date -u +%FT%TZ)"
  if [[ "$status" -eq 0 && "$result" == \{*\} ]]; then
    measurement="$result"
  else
    # Keep the JSONL stream valid when a run fails (for example, no successful
    # samples or an overhead/error-rate regression). Consumers can alert on
    # status without having to special-case malformed lines.
    measurement="{\"error\":\"benchmark_failed\",\"exit_status\":$status}"
  fi
  printf '{"timestamp":"%s","status":%d,"measurement":%s}\n' \
    "$timestamp" "$status" "$measurement" >>"$OUTPUT"
  sleep "$INTERVAL_SECONDS"
done
