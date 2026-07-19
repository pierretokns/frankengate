#!/usr/bin/env bash
set -euo pipefail

# Compare a direct local inference endpoint with the FrankenGate proxy. The
# request body and headers are identical; only the URL changes. This measures
# gateway overhead, not model variance, so point both URLs at the same local
# deterministic/mock provider.
: "${DIRECT_URL:?set DIRECT_URL (for example http://127.0.0.1:8081/v1/chat/completions)}"
: "${GATEWAY_URL:?set GATEWAY_URL (for example http://127.0.0.1:8080/v1/chat/completions)}"
: "${REQUEST_BODY:?set REQUEST_BODY to a JSON request body}"
N="${N:-100}"
MAX_P95_OVERHEAD_MS="${MAX_P95_OVERHEAD_MS:-10}"
MAX_P50_OVERHEAD_MS="${MAX_P50_OVERHEAD_MS:-5}"
MAX_ERROR_RATE="${MAX_ERROR_RATE:-0}"
HEADERS_FILE="${HEADERS_FILE:-}"

awk -v v="$N" 'BEGIN { if (v < 1 || v != int(v)) exit 1 }' || { echo "N must be a positive integer" >&2; exit 2; }
is_decimal() { [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]; }
is_decimal "$MAX_ERROR_RATE" || { echo "MAX_ERROR_RATE must be numeric" >&2; exit 2; }
is_decimal "$MAX_P95_OVERHEAD_MS" || { echo "MAX_P95_OVERHEAD_MS must be numeric" >&2; exit 2; }
is_decimal "$MAX_P50_OVERHEAD_MS" || { echo "MAX_P50_OVERHEAD_MS must be numeric" >&2; exit 2; }
awk -v v="$MAX_ERROR_RATE" 'BEGIN { if (v < 0 || v > 1) exit 1 }' || { echo "MAX_ERROR_RATE must be between 0 and 1" >&2; exit 2; }
awk -v v="$MAX_P95_OVERHEAD_MS" 'BEGIN { if (v < 0) exit 1 }' || { echo "MAX_P95_OVERHEAD_MS must be non-negative" >&2; exit 2; }
awk -v v="$MAX_P50_OVERHEAD_MS" 'BEGIN { if (v < 0) exit 1 }' || { echo "MAX_P50_OVERHEAD_MS must be non-negative" >&2; exit 2; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

run() {
  local url="$1" out="$2" status_out="$3" i status timing
  local -a curl_args=(
    --fail --silent --show-error --output /dev/null
    --connect-timeout 2 --max-time 60
    -H 'content-type: application/json'
    --data-binary "$REQUEST_BODY"
  )
  if [[ -n "$HEADERS_FILE" ]]; then
    curl_args+=(--config "$HEADERS_FILE")
  fi
  : >"$out"
  : >"$status_out"
  for ((i=0; i<N; i++)); do
    timing="$out.$i"
    set +e
    curl "${curl_args[@]}" \
      -w '%{time_total}\n' "$url" >"$timing"
    status=$?
    set -e
    printf '%s\n' "$status" >>"$status_out"
    # Latency percentiles describe successful inference only. Failed requests
    # remain in the error-rate denominator but must not contaminate p50/p95.
    if [[ "$status" -eq 0 ]]; then
      cat "$timing" >>"$out"
    fi
    rm -f "$timing"
  done
}

run "$DIRECT_URL" "$tmp/direct" "$tmp/direct.status"
run "$GATEWAY_URL" "$tmp/gateway" "$tmp/gateway.status"

stats() {
  sort -n "$1" | awk -v n_expected="$N" '
    { v[NR]=$1; sum+=$1 }
    END {
      n=NR; if (n == 0) exit 3;
      p50_idx=int(n*0.50+0.999999); p95_idx=int(n*0.95+0.999999);
      if (p50_idx < 1) p50_idx=1; if (p50_idx > n) p50_idx=n;
      if (p95_idx < 1) p95_idx=1; if (p95_idx > n) p95_idx=n;
      p50=v[p50_idx]; p95=v[p95_idx];
      printf "{\"n\":%d,\"p50_ms\":%.3f,\"p95_ms\":%.3f,\"mean_ms\":%.3f}\n", n, p50*1000, p95*1000, (sum/n)*1000
    }'
}

direct="$(stats "$tmp/direct")" || {
  echo "direct endpoint produced no successful latency samples" >&2
  exit 42
}
gateway="$(stats "$tmp/gateway")" || {
  echo "gateway endpoint produced no successful latency samples" >&2
  exit 42
}
direct_p95="$(printf '%s' "$direct" | awk -F'\"p95_ms\":' '{split($2,a,","); print a[1]}')"
gateway_p95="$(printf '%s' "$gateway" | awk -F'\"p95_ms\":' '{split($2,a,","); print a[1]}')"
direct_p50="$(printf '%s' "$direct" | awk -F'\"p50_ms\":' '{split($2,a,","); print a[1]}')"
gateway_p50="$(printf '%s' "$gateway" | awk -F'\"p50_ms\":' '{split($2,a,","); print a[1]}')"
direct_errors="$(awk '$1 != 0 { n++ } END { print n+0 }' "$tmp/direct.status")"
gateway_errors="$(awk '$1 != 0 { n++ } END { print n+0 }' "$tmp/gateway.status")"
awk -v d="$direct_p95" -v g="$gateway_p95" -v d50="$direct_p50" -v g50="$gateway_p50" \
  -v direct="$direct" -v gateway="$gateway" \
  -v de="$direct_errors" -v ge="$gateway_errors" -v n="$N" \
  -v max_overhead="$MAX_P95_OVERHEAD_MS" \
  -v max_overhead50="$MAX_P50_OVERHEAD_MS" \
  -v max_error_rate="$MAX_ERROR_RATE" \
  'BEGIN { overhead=g-d; overhead50=g50-d50; der=de/n; ger=ge/n; error_regression=(ger > der || ger > max_error_rate); p95_regression=(overhead > max_overhead); p50_regression=(overhead50 > max_overhead50); printf "{\"direct\":%s,\"gateway\":%s,\"direct_error_rate\":%.4f,\"gateway_error_rate\":%.4f,\"added_p50_ms\":%.3f,\"added_p95_ms\":%.3f,\"max_p50_overhead_ms\":%.3f,\"max_p95_overhead_ms\":%.3f,\"max_error_rate\":%.4f,\"regression\":%s,\"latency_regression\":%s,\"error_regression\":%s}\n", direct, gateway, der, ger, overhead50, overhead, max_overhead50, max_overhead, max_error_rate, (p50_regression || p95_regression || error_regression ? "true" : "false"), (p50_regression || p95_regression ? "true" : "false"), (error_regression ? "true" : "false"); if (p50_regression || p95_regression || error_regression) exit 42 }'
