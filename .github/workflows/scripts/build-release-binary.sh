#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:?VERSION is required}"
ROOT="$(git rev-parse --show-toplevel)"

# The UI is built once by the release workflow. This script deliberately does
# not invoke `make build`, whose build-ui prerequisite would rebuild Next.js on
# every native platform runner.
make -C "$ROOT" setup-workspace >/dev/null
mkdir -p "$ROOT/tmp"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
esac

cd "$ROOT/transports/bifrost-http"
BUILD_TAGS=()
if [[ "$OS" != "linux" ]]; then
  BUILD_TAGS=( -tags sqlite_static )
fi
CGO_ENABLED=1 GOOS="$OS" GOARCH="$ARCH" go build \
  -ldflags="-w -s -X main.Version=v${VERSION}" \
  -a -trimpath "${BUILD_TAGS[@]}" \
  -o "$ROOT/tmp/bifrost-http" .
"$ROOT/tmp/bifrost-http" -version
