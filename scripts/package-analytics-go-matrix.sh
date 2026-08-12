#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

VERSION=${VERSION:-0.1.0}
OUT_DIR=${OUT_DIR:-dist}

targets=(
  "darwin arm64"
  "linux amd64"
  "linux arm64"
)

for target in "${targets[@]}"; do
  read -r target_os target_arch <<<"$target"
  env -u GOOS -u GOARCH TARGET_OS="$target_os" TARGET_ARCH="$target_arch" \
    VERSION="$VERSION" OUT_DIR="$OUT_DIR" ./scripts/package-analytics-go.sh
done

manifest="$OUT_DIR/frankengate-analytics-${VERSION}-SHA256SUMS"
rm -f "$manifest"
for target in "${targets[@]}"; do
  read -r target_os target_arch <<<"$target"
  artifact="frankengate-analytics-${VERSION}-${target_os}-${target_arch}.tar.gz"
  (cd "$OUT_DIR" && shasum -a 256 "$artifact") >>"$manifest"
done

echo "created $manifest"
