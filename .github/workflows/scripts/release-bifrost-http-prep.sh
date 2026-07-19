#!/usr/bin/env bash
set -euo pipefail

# Prepare bifrost-http release: update dependencies, build UI, validate, commit/push
# Usage: ./release-bifrost-http-prep.sh <version>

# Get the absolute path of the script directory
# Use readlink if available (Linux), otherwise use cd/pwd (macOS compatible)
if command -v readlink >/dev/null 2>&1 && readlink -f "$0" >/dev/null 2>&1; then
  SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
fi

# Source Go utilities for exponential backoff
source "$SCRIPT_DIR/go-utils.sh"

# Validate input argument
if [ "${1:-}" = "" ]; then
  echo "Usage: $0 <version>" >&2
  exit 1
fi

VERSION="$1"

# Product assembly must resolve the fork's source graph, not a stale published
# module graph.  Standalone GOWORK=off probes belong in separate release-safety
# jobs; allowing them here can silently compile an older core without the
# authority/reservation packages this transport imports.
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
cd "$ROOT_DIR"
# go.work is intentionally gitignored. Clean release checkouts must regenerate
# it from the canonical module list before the assembly graph is inspected.
if [[ ! -f "$ROOT_DIR/go.work" ]]; then
  echo "🔧 go.work not found; initializing the release workspace..."
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/setup-go-workspace.sh"
fi
if [[ ! -f "$ROOT_DIR/go.work" ]]; then
  echo "❌ release assembly could not initialize go.work" >&2
  exit 1
fi
WORKSPACE_MODE="$(go env GOWORK)"
if [[ "$WORKSPACE_MODE" == "off" || -z "$WORKSPACE_MODE" ]]; then
  echo "❌ release assembly resolved GOWORK=$WORKSPACE_MODE; refusing published-module masking" >&2
  exit 1
fi
for required_dir in core/authorityepoch core/reservations; do
  if [[ ! -d "$ROOT_DIR/$required_dir" ]]; then
    echo "❌ release assembly source graph is missing $required_dir" >&2
    exit 1
  fi
done

# Local/diagnostic mode validates the checked-out Go workspace without editing
# transports/go.mod or resolving the fork's private enterprise packages from
# proxy.golang.org. The official release path below intentionally continues to
# normalize published module versions and perform its normal build/push steps.
if [[ "${FRANKENGATE_WORKSPACE_VALIDATE:-0}" == "1" ]]; then
  echo "🔎 Validating the checked-out FrankenGate workspace dependency graph..."
  (cd transports && go build ./...)
  dependencies="$(cd transports && go list -deps ./...)"
  for required_package in \
    "github.com/maximhq/bifrost/core/authorityepoch" \
    "github.com/maximhq/bifrost/core/reservations" \
    "github.com/maximhq/bifrost/plugins/governance"; do
    if ! printf '%s\n' "$dependencies" | grep -Fxq "$required_package"; then
      echo "❌ workspace dependency graph is missing $required_package" >&2
      exit 1
    fi
  done
  echo "✅ Checked-out workspace contains all enterprise governance dependencies"
  exit 0
fi

echo "🚀 Preparing bifrost-http v$VERSION release..."

# Get core and framework versions from version files
CORE_VERSION="v$(tr -d '\n\r' < core/version)"
FRAMEWORK_VERSION="v$(tr -d '\n\r' < framework/version)"

echo "🔍 DEBUG: CORE_VERSION: $CORE_VERSION"
echo "🔍 DEBUG: FRAMEWORK_VERSION: $FRAMEWORK_VERSION"


# Get plugin versions from version files
echo "🔌 Getting plugin versions from version files..."
PLUGIN_NAMES=()
PLUGIN_VERSIONS=()
plugin_version_for() {
  local wanted="$1" i
  for i in "${!PLUGIN_NAMES[@]}"; do
    if [[ "${PLUGIN_NAMES[$i]}" == "$wanted" ]]; then
      printf '%s' "${PLUGIN_VERSIONS[$i]}"
      return 0
    fi
  done
  return 1
}
add_plugin_version() {
  local name="$1" version="$2"
  if plugin_version_for "$name" >/dev/null 2>&1; then
    return 0
  fi
  PLUGIN_NAMES+=("$name")
  PLUGIN_VERSIONS+=("$version")
}

# Get versions for plugins that exist in the plugins/ directory
for plugin_dir in plugins/*/; do
  if [ -d "$plugin_dir" ]; then
    plugin_name=$(basename "$plugin_dir")
    PLUGIN_VERSION="v$(tr -d '\n\r' < "${plugin_dir}version")"
    add_plugin_version "$plugin_name" "$PLUGIN_VERSION"
    echo "   📦 $plugin_name: $PLUGIN_VERSION (from version file)"
  fi
done

# Also check for any plugins already in transport go.mod that might not be in plugins/ directory
cd transports
echo "🔍 Checking for additional plugins in transport go.mod..."
# Parse go.mod plugin lines and add missing ones
while IFS= read -r plugin_line; do
  plugin_name=$(echo "$plugin_line" | awk -F'/' '{print $NF}' | awk '{print $1}')
  current_version=$(echo "$plugin_line" | awk '{print $NF}')

  # Only add if we don't already have this plugin
  if ! plugin_version_for "$plugin_name" >/dev/null 2>&1; then
    echo "   📦 $plugin_name: $current_version (from transport go.mod)"
    add_plugin_version "$plugin_name" "$current_version"
  fi
done < <(grep "github.com/maximhq/bifrost/plugins/" go.mod)
cd ..

echo "🔧 Using versions:"
echo "   Core: $CORE_VERSION"
echo "   Framework: $FRAMEWORK_VERSION"
echo "   Plugins:"
for i in "${!PLUGIN_NAMES[@]}"; do
  echo "     - ${PLUGIN_NAMES[$i]}: ${PLUGIN_VERSIONS[$i]}"
done

# Update transport dependencies to use plugin versions from version files
echo "🔧 Using plugin versions from version files for transport..."

# Track which plugins are actually used by the transport
cd transports

# Normalize the local go.mod directive up front so prior-release artifacts
# (e.g. `go 1.26.2` written by earlier `go get` runs) don't trip GOTOOLCHAIN=local.
go mod edit -go=1.26.5 -toolchain=none

for i in "${!PLUGIN_NAMES[@]}"; do
  plugin_name="${PLUGIN_NAMES[$i]}"
  plugin_version="${PLUGIN_VERSIONS[$i]}"

  # Check if transport depends on this plugin
  if grep -q "github.com/maximhq/bifrost/plugins/$plugin_name" go.mod; then
    echo "  📦 Using $plugin_name plugin $plugin_version"
    # Textual require bump — skips loading the currently-declared version's go.mod
    go mod edit -require="github.com/maximhq/bifrost/plugins/$plugin_name@$plugin_version"
  fi
done

# Also ensure core and framework are up to date

echo "  🔧 Updating core to $CORE_VERSION"
go mod edit -require="github.com/maximhq/bifrost/core@$CORE_VERSION"

echo "  📦 Updating framework to $FRAMEWORK_VERSION"
go mod edit -require="github.com/maximhq/bifrost/framework@$FRAMEWORK_VERSION"

# Re-normalize before tidy in case any edit reintroduced a toolchain line
go mod edit -go=1.26.5 -toolchain=none
go mod tidy

cd ..

# We need to build UI first before we can validate the transport build
echo "🎨 Building UI..."
make build-ui

# Building hello-world plugin
echo "🔨 Building hello-world plugin..."
cd examples/plugins/hello-world
make build
cd ../../..

# Validate transport build
echo "🔨 Validating transport build..."
cd transports
go build ./...
cd ..
echo "✅ Transport build validation successful"

# A source tree can contain enterprise packages without the release binary
# importing them.  Assert the concrete dependency graph before allowing the
# release prep job to continue.  Keep this check on package paths (rather than
# grepping source) so it follows Go's actual build selection.
echo "🔎 Verifying enterprise governance packages are linked..."
DEPENDENCIES="$(cd transports && go list -deps ./... )"
for required_package in \
  "github.com/maximhq/bifrost/core/authorityepoch" \
  "github.com/maximhq/bifrost/core/reservations" \
  "github.com/maximhq/bifrost/plugins/governance"; do
  if ! printf '%s\n' "$DEPENDENCIES" | grep -Fxq "$required_package"; then
    echo "❌ release dependency graph is missing $required_package" >&2
    exit 1
  fi
done
echo "✅ Enterprise governance packages are linked into the transport graph"

# Note: Migration tests run as a separate CI job (test-migrations) before this release job

# Commit and push changes if any
# First, pull latest changes to avoid conflicts
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" = "HEAD" ]; then
  # In detached HEAD state (common in CI), use GITHUB_REF_NAME or default to main
  CURRENT_BRANCH="${GITHUB_REF_NAME:-main}"
fi

echo "Pulling latest changes from origin/$CURRENT_BRANCH..."
if ! git pull origin "$CURRENT_BRANCH"; then
  echo "❌ Error: git pull origin $CURRENT_BRANCH failed"
  exit 1
fi

# Stage any changes made to transports/
git add transports/

# Check if there are staged changes after pulling
if ! git diff --cached --quiet; then
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  echo "🔧 Committing and pushing changes..."
  git commit -m "transports: update dependencies --skip-ci"
  git push -u origin HEAD
else
  echo "ℹ️ No staged changes to commit"
fi

echo "✅ Prep complete for bifrost-http v$VERSION"
echo "success=true" >> "$GITHUB_OUTPUT"
