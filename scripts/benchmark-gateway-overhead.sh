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
HEADERS_FILE="${HEADERS_FILE:-}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

run() {
  local url="$1" out="$2" status_out="$3" i status
  for ((i=0; i<N; i++)); do
    set +e
    curl --fail --silent --show-error --output /dev/null \
      --connect-timeout 2 --max-time 60 \
      -H 'content-type: application/json' \
      ${HEADERS_FILE:+--config "$HEADERS_FILE"} \
      --data-binary "$REQUEST_BODY" \
      -w '%{time_total}\n' "$url" >>"$out"
    status=$?
    set -e
    printf '%s\n' "$status" >>"$status_out"
  done
}

run "$DIRECT_URL" "$tmp/direct" "$tmp/direct.status"
run "$GATEWAY_URL" "$tmp/gateway" "$tmp/gateway.status"

stats() {
  sort -n "$1" | awk -v n_expected="$N" '
    { v[NR]=$1; sum+=$1 }
    END {
      n=NR; p50=v[int((n+1)*0.50)]; p95=v[int((n+1)*0.95)];
      if (p50=="") p50=v[n]; if (p95=="") p95=v[n];
      printf "{\"n\":%d,\"p50_ms\":%.3f,\"p95_ms\":%.3f,\"mean_ms\":%.3f}\n", n, p50*1000, p95*1000, (sum/n)*1000
    }'
}

direct="$(stats "$tmp/direct")"
gateway="$(stats "$tmp/gateway")"
direct_p95="$(printf '%s' "$direct" | awk -F'\"p95_ms\":' '{split($2,a,","); print a[1]}')"
gateway_p95="$(printf '%s' "$gateway" | awk -F'\"p95_ms\":' '{split($2,a,","); print a[1]}')"
direct_errors="$(awk '$1 != 0 { n++ } END { print n+0 }' "$tmp/direct.status")"
gateway_errors="$(awk '$1 != 0 { n++ } END { print n+0 }' "$tmp/gateway.status")"
awk -v d="$direct_p95" -v g="$gateway_p95" \
  -v direct="$direct" -v gateway="$gateway" \
  -v de="$direct_errors" -v ge="$gateway_errors" -v n="$N" \
  -v max_overhead="$MAX_P95_OVERHEAD_MS" \
  'BEGIN { overhead=g-d; printf "{\"direct\":%s,\"gateway\":%s,\"direct_error_rate\":%.4f,\"gateway_error_rate\":%.4f,\"added_p95_ms\":%.3f,\"max_p95_overhead_ms\":%.3f,\"regression\":%s}\n", direct, gateway, de/n, ge/n, overhead, max_overhead, (overhead > max_overhead ? "true" : "false"); if (overhead > max_overhead) exit 42 }'
