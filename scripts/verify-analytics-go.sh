#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

go test ./analytics-go/...
go vet ./analytics-go/...
mkdir -p tmp
(cd analytics-go && go build -trimpath -ldflags='-s -w' -o ../tmp/frankengate-analytics ./cmd/frankengate-analytics)

NAME="frankengate-analytics-clickhouse-test-$$"
APP_PID=""
CH_USER=analytics_test
CH_PASSWORD=analytics_test_password
CID=$(docker run -d --rm --name "$NAME" -e CLICKHOUSE_USER="$CH_USER" -e CLICKHOUSE_PASSWORD="$CH_PASSWORD" -p 0:8123 "${CLICKHOUSE_IMAGE:-clickhouse/clickhouse-server:26.3}")
cleanup() {
  if [[ -n "$APP_PID" ]]; then
    kill "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  fi
  docker rm -f "$CID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

CH_PORT=$(docker port "$CID" 8123/tcp | head -1 | sed -E 's/.*://')
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$CH_PORT/ping" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$CH_PORT/ping" >/dev/null

APP_PORT=${ANALYTICS_TEST_PORT:-18090}
PORT="$APP_PORT" CLICKHOUSE_ADDR="127.0.0.1:$CH_PORT" CLICKHOUSE_USERNAME="$CH_USER" CLICKHOUSE_PASSWORD="$CH_PASSWORD" ANALYTICS_WORKER_TOKEN=test-token \
  ./tmp/frankengate-analytics >tmp/frankengate-analytics-test.log 2>&1 &
APP_PID=$!
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$APP_PORT/readyz" -H 'Authorization: Bearer test-token' >/dev/null 2>&1; then break; fi
  sleep 1
done

BASE="http://127.0.0.1:$APP_PORT"
curl -fsS "$BASE/healthz" | jq -e '.status == "ok"' >/dev/null
curl -fsS -X POST "$BASE/v1/traces" -H 'Authorization: Bearer test-token' -H 'X-Tenant-ID: enterprise-fixture' -H 'Content-Type: application/json' --data-binary @analytics-go/examples/fixtures/enterprise-sanitized-trace.json | jq -e '.admission.eligible == true' >/dev/null
curl -fsS -X POST "$BASE/v1/evaluations" -H 'Authorization: Bearer test-token' -H 'X-Tenant-ID: enterprise-fixture' -H 'Content-Type: application/json' --data-binary @analytics-go/examples/requests/refund-assessment.json | jq -e '.value == 4 and .abstain == false' >/dev/null
curl -fsS "$BASE/v1/reports/evaluations?trace_id=fixture-enterprise-001" -H 'Authorization: Bearer test-token' -H 'X-Tenant-ID: enterprise-fixture' | jq -e '.judgment_count == 1 and .scored_count == 1 and .mean_value == 4' >/dev/null
echo "analytics-go integration verified against ClickHouse"
