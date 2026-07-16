#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-test-vet}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "[$(date -u +%FT%TZ)] fork-go-checks starting mode=${MODE} root=${ROOT}"

MODULES=()
while IFS= read -r module_file; do
  MODULES+=("${module_file#"$ROOT/"}")
done < <(
  find "$ROOT" -type f -name go.mod \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/.cache/*' \
    -print | sed 's#/go\.mod$##' | sort
)

if [ "${#MODULES[@]}" -eq 0 ]; then
  echo "no Go modules discovered" >&2
  exit 1
fi

# Release verification must cover everything that can enter the shipped
# binaries, but it should not rebuild example servers and service fixtures that
# have their own CI jobs. Those modules made immutable-tag verification spend
# most of its timeout compiling code that cannot be packaged into FrankenGate.
if [[ "${FORK_RELEASE:-0}" == "1" ]]; then
  RELEASE_MODULES=()
  for module in "${MODULES[@]}"; do
    case "$module" in
      cli|core|framework|plugins/*|transports)
        RELEASE_MODULES+=("$module")
        ;;
    esac
  done
  MODULES=("${RELEASE_MODULES[@]}")
fi

# Every module still uses the upstream-compatible
# github.com/maximhq/bifrost/... namespace. Running a module in isolation can
# therefore download a published upstream sibling instead of testing the local
# fork. Build an isolated workspace and force every command below through it so
# cross-module imports always resolve to this checkout.
WORKSPACE_DIR="$(mktemp -d)"
echo "[$(date -u +%FT%TZ)] creating isolated Go workspace at ${WORKSPACE_DIR}"
UI_DIR="$ROOT/transports/bifrost-http/ui"
UI_PLACEHOLDER="$UI_DIR/ci-placeholder.txt"
UI_DIR_CREATED=0
UI_PLACEHOLDER_CREATED=0
cleanup() {
  rm -rf "$WORKSPACE_DIR"
  if [ "$UI_PLACEHOLDER_CREATED" -eq 1 ]; then
    rm -f "$UI_PLACEHOLDER"
  fi
  if [ "$UI_DIR_CREATED" -eq 1 ]; then
    rmdir "$UI_DIR" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# The HTTP binary embeds `all:ui`, but the generated UI directory is ignored
# and absent in a clean source checkout. Give compile/vet/vuln jobs a
# runner-local visible file; release jobs still build and embed the real UI.
if [ ! -d "$UI_DIR" ]; then
  mkdir -p "$UI_DIR"
  UI_DIR_CREATED=1
fi
if [ -z "$(find "$UI_DIR" -mindepth 1 -maxdepth 1 -not -name '.*' -print -quit)" ]; then
  printf '%s\n' 'CI compile placeholder; release builds embed the generated UI.' > "$UI_PLACEHOLDER"
  UI_PLACEHOLDER_CREATED=1
fi
WORKSPACE_MODULES=()
for module in "${MODULES[@]}"; do
  WORKSPACE_MODULES+=("$ROOT/$module")
done
(
  cd "$WORKSPACE_DIR"
  go work init "${WORKSPACE_MODULES[@]}"
)
export GOWORK="$WORKSPACE_DIR/go.work"

echo "using local fork workspace: $GOWORK"
echo "[$(date -u +%FT%TZ)] validating local module graph"
timeout --foreground --signal=TERM --kill-after=30s "${MODULE_GRAPH_TIMEOUT_SECONDS:-300}s" go list -m all |
  awk '$1 ~ /^github\.com\/maximhq\/bifrost(\/|$)/ && NF > 1 { print }' |
  while IFS= read -r remote_module; do
    echo "unexpected remote Bifrost module: $remote_module" >&2
    exit 1
  done
echo "[$(date -u +%FT%TZ)] local module graph validated"

run_in_modules() {
	local label="$1"
	shift
	# Module-wide compile/vet jobs are memory-heavy. Eight concurrent Go
	# workspaces can starve the runner and present as a silent hang; keep the
	# default conservative while allowing larger runners to opt in.
	local max_parallel="${MODULE_CHECK_MAX_PARALLEL:-2}" failed=0
  local module_timeout="${MODULE_TIMEOUT_SECONDS:-900}"
  local -a pids=()
  run_one() {
    local module="$1"
    shift
    echo "::group::${label}: ${module}"
    if [[ "$label" == "go test compile" && "$module" == "tests/semanticcache" ]]; then
      echo "Skipping service-backed semantic-cache TestMain; covered by the dedicated integration job."
      echo "::endgroup::"
      return 0
    fi
    (
      cd "$ROOT/$module"
      echo "[$(date -u +%FT%TZ)] start ${label}: ${module} (timeout ${module_timeout}s)"
      if [[ "$label" == "go vet" && "$module" == "examples/plugins/hello-world-wasm-go" ]]; then
        timeout --foreground --signal=TERM --kill-after=30s "${module_timeout}s" go vet -unsafeptr=false ./...
      else
        timeout --foreground --signal=TERM --kill-after=30s "${module_timeout}s" "$@"
      fi
      echo "[$(date -u +%FT%TZ)] complete ${label}: ${module}"
    )
    echo "::endgroup::"
  }
  for module in "${MODULES[@]}"; do
    run_one "$module" "$@" &
    pids+=("$!")
    if [ "${#pids[@]}" -ge "$max_parallel" ]; then
      if ! wait "${pids[0]}"; then failed=1; fi
      pids=("${pids[@]:1}")
    fi
  done
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then failed=1; fi
  done
  return "$failed"
}

download_dependencies() {
	local max_parallel="${MODULE_DOWNLOAD_MAX_PARALLEL:-4}" failed=0
  local -a pids=()
  download_one() {
    local module="$1" attempt
    echo "::group::go mod download: ${module}"
    for attempt in 1 2 3; do
      if timeout --foreground --kill-after=30s 180s bash -c 'cd "$1" && go mod download' _ "$ROOT/$module"; then
        echo "::endgroup::"
        return 0
      fi
      if [ "$attempt" -lt 3 ]; then
        sleep $((attempt * 2))
      fi
    done
    echo "dependency download failed after 3 attempts: $module" >&2
    echo "::endgroup::"
    return 1
  }
  for module in "${MODULES[@]}"; do
    download_one "$module" &
    pids+=("$!")
    if [ "${#pids[@]}" -ge "$max_parallel" ]; then
      if ! wait "${pids[0]}"; then failed=1; fi
      pids=("${pids[@]:1}")
    fi
  done
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then failed=1; fi
  done
  return "$failed"
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
    download_dependencies
    # Compile every package and test binary without executing suites whose
    # explicit service fixtures belong in separate integration jobs.
    run_in_modules "go test compile" go test -run '^$' ./...
    run_focused_race_tests
    run_in_modules "go vet" go vet ./...
    ;;
  vuln)
    download_dependencies
    # Compile the scanner once per job. `go run ...@version` recompiles and
    # resolves the tool for every module, which made release tags spend most
    # of their wall time repeating identical scanner setup.
    VULN_BIN="$WORKSPACE_DIR/bin/govulncheck"
    mkdir -p "$(dirname "$VULN_BIN")"
    GOBIN="$(dirname "$VULN_BIN")" go install golang.org/x/vuln/cmd/govulncheck@v1.1.4
    run_in_modules "govulncheck" "$VULN_BIN" ./...
    ;;
  *)
    echo "unknown mode: $MODE" >&2
    echo "usage: $0 [test-vet|vuln]" >&2
    exit 2
    ;;
esac
