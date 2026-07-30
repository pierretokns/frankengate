#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/frankengate-otel-roundtrip.XXXXXX")"
cleanup() {
  # The Go module cache deliberately makes downloaded module files read-only.
  # Restore owner write permission so the exact mktemp tree can be removed.
  chmod -R u+w "${WORK_ROOT}" 2>/dev/null || true
  rm -rf "${WORK_ROOT}"
}
trap cleanup EXIT

COLLECTOR_VERSION="0.153.0"
COLLECTOR_ARCHIVE_SHA256="3371b4100c56f853e236b8efa4a134516c5ac09183a07e397a2265f4ab61d63f"
COLLECTOR_BINARY_SHA256="e7e443f18b50ee12f03aaa1ca3bbd8269007e089abffca7fa387835b44c62afc"
COLLECTOR_ARCHIVE="otelcol-contrib_${COLLECTOR_VERSION}_darwin_arm64.tar.gz"
COLLECTOR_URL="https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${COLLECTOR_VERSION}/${COLLECTOR_ARCHIVE}"
OUTPUT_PATH="${1:-${SCRIPT_ROOT}/experiments/results/otel-collector-roundtrip-e0-2026-07-30.json}"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  printf '%s\n' \
    "This pinned artifact runner currently supports Darwin arm64 only." >&2
  exit 2
fi

if [[ -n "${FRANKENGATE_OTELCOL_BIN:-}" ]]; then
  COLLECTOR_BIN="${FRANKENGATE_OTELCOL_BIN}"
else
  curl -L --fail --retry 3 \
    -o "${WORK_ROOT}/${COLLECTOR_ARCHIVE}" \
    "${COLLECTOR_URL}"
  ARCHIVE_ACTUAL="$(shasum -a 256 "${WORK_ROOT}/${COLLECTOR_ARCHIVE}" | awk '{print $1}')"
  if [[ "${ARCHIVE_ACTUAL}" != "${COLLECTOR_ARCHIVE_SHA256}" ]]; then
    printf '%s\n' "Collector archive SHA-256 mismatch." >&2
    exit 1
  fi
  mkdir "${WORK_ROOT}/collector"
  tar -xzf "${WORK_ROOT}/${COLLECTOR_ARCHIVE}" \
    -C "${WORK_ROOT}/collector"
  COLLECTOR_BIN="${WORK_ROOT}/collector/otelcol-contrib"
fi

BINARY_ACTUAL="$(shasum -a 256 "${COLLECTOR_BIN}" | awk '{print $1}')"
if [[ "${BINARY_ACTUAL}" != "${COLLECTOR_BINARY_SHA256}" ]]; then
  printf '%s\n' "Collector binary SHA-256 mismatch." >&2
  exit 1
fi

SENDER_BIN="${WORK_ROOT}/otel-roundtrip-sdk"
(
  cd "${SCRIPT_ROOT}/otel-roundtrip-sdk"
  GOWORK=off \
  GOTOOLCHAIN=go1.25.0+auto \
  GOCACHE="${WORK_ROOT}/go-build-cache" \
  GOMODCACHE="${WORK_ROOT}/go-module-cache" \
    go build -trimpath -o "${SENDER_BIN}" .
)

PYTHONPYCACHEPREFIX="${WORK_ROOT}/python-cache" \
python3 "${SCRIPT_ROOT}/otel_collector_roundtrip.py" \
  --fixtures "${SCRIPT_ROOT}/fixtures/governed-v1" \
  --collector "${COLLECTOR_BIN}" \
  --sender "${SENDER_BIN}" \
  --normal-config \
    "${SCRIPT_ROOT}/configs/otel/collector-roundtrip-v0.153.0.yaml" \
  --drop-config \
    "${SCRIPT_ROOT}/configs/otel/collector-drop-v0.153.0.yaml" \
  --output "${OUTPUT_PATH}"
