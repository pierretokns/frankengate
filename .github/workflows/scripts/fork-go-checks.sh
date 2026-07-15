#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-test-vet}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

MODULES=()
while IFS= read -r module_file; do
  MODULES+=("${module_file#"$ROOT/"}")
done < <(
  find "$ROOT" -type f -name go.mod \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -print | sed 's#/go\.mod$##' | sort
)

if [ "${#MODULES[@]}" -eq 0 ]; then
  echo "no Go modules discovered" >&2
  exit 1
fi

# Every module still uses the upstream-compatible
# github.com/maximhq/bifrost/... namespace. Running a module in isolation can
# therefore download a published upstream sibling instead of testing the local
# fork. Build an isolated workspace and force every command below through it so
# cross-module imports always resolve to this checkout.
WORKSPACE_DIR="$(mktemp -d)"
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
go list -m all |
  awk '$1 ~ /^github\.com\/maximhq\/bifrost(\/|$)/ && NF > 1 { print }' |
  while IFS= read -r remote_module; do
    echo "unexpected remote Bifrost module: $remote_module" >&2
    exit 1
  done

run_in_modules() {
  local label="$1"
  shift

  for module in "${MODULES[@]}"; do
    if [[ "$label" == "go test compile" && "$module" == "tests/semanticcache" ]]; then
      echo "::group::${label}: ${module}"
      echo "Skipping service-backed semantic-cache TestMain; covered by the dedicated integration job."
      echo "::endgroup::"
      continue
    fi
    echo "::group::${label}: ${module}"
    (
      cd "$ROOT/$module"
      if [[ "$label" == "go vet" && "$module" == "examples/plugins/hello-world-wasm-go" ]]; then
        # This WASM ABI intentionally converts a uint32 linear-memory offset
        # into an unsafe.Pointer. Keep every other vet analyzer enabled and
        # scope the host-only unsafeptr exception to this target-specific module.
        go vet -unsafeptr=false ./...
      else
        "$@"
      fi
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
