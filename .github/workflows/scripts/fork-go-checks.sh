#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-test-vet}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

MODULES=(
  core
  framework
  transports
  plugins/governance
  plugins/logging
  plugins/telemetry
  plugins/mocker
  plugins/jsonparser
)

run_in_modules() {
  local label="$1"
  shift

  for module in "${MODULES[@]}"; do
    if [ ! -f "$ROOT/$module/go.mod" ]; then
      echo "Skipping missing module: $module"
      continue
    fi

    echo "::group::${label}: ${module}"
    (
      cd "$ROOT/$module"
      "$@"
    )
    echo "::endgroup::"
  done
}

run_focused_race_tests() {
  echo "::group::focused race tests: core enterprise primitives"
  (
    cd "$ROOT/core"
    go test -count=1 -race \
      ./admission \
      ./authorityepoch \
      ./evidence \
      ./mcpownership \
      ./privacy \
      ./reservations \
      ./schemas \
      ./vkcrypto
  )
  echo "::endgroup::"

  echo "::group::focused race tests: framework streaming"
  (
    cd "$ROOT/framework"
    go test -count=1 -race ./streaming
  )
  echo "::endgroup::"
}

case "$MODE" in
  test-vet)
    # Compile every package and test binary without executing suites whose
    # explicit service fixtures belong in separate integration jobs.
    run_in_modules "go test compile" go test -run '^$' ./...
    run_focused_race_tests
    run_in_modules "go vet" go vet ./...
    ;;
  vuln)
    run_in_modules "govulncheck" go run golang.org/x/vuln/cmd/govulncheck@v1.1.4 ./...
    ;;
  *)
    echo "unknown mode: $MODE" >&2
    echo "usage: $0 [test-vet|vuln]" >&2
    exit 2
    ;;
esac
