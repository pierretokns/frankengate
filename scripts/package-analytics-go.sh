#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

VERSION=${VERSION:-0.1.0}
TARGET_OS=${TARGET_OS:-${GOOS:-$(env -u GOOS -u GOARCH go env GOOS)}}
TARGET_ARCH=${TARGET_ARCH:-${GOARCH:-$(env -u GOOS -u GOARCH go env GOARCH)}}
OUT_DIR=${OUT_DIR:-dist}
NAME="frankengate-analytics-${VERSION}-${TARGET_OS}-${TARGET_ARCH}"
STAGE="$OUT_DIR/$NAME"

HOST_OS=$(env -u GOOS -u GOARCH go env GOOS)
HOST_ARCH=$(env -u GOOS -u GOARCH go env GOARCH)

rm -rf "$STAGE"
mkdir -p "$STAGE"
(cd analytics-go && GOOS="$HOST_OS" GOARCH="$HOST_ARCH" go test ./...)
(cd analytics-go && CGO_ENABLED=0 GOOS="$TARGET_OS" GOARCH="$TARGET_ARCH" go build \
  -trimpath -ldflags="-s -w -X main.buildVersion=beta-trace-eval/${VERSION}" \
  -o "$ROOT/$STAGE/frankengate-analytics" ./cmd/frankengate-analytics)

cp analytics-go/README.md "$STAGE/README.md"
cp analytics-go/examples/rubrics/support-refund.json "$STAGE/support-refund-rubric.json"
cp analytics-go/examples/fixtures/enterprise-sanitized-trace.json "$STAGE/enterprise-sanitized-trace.json"
cp analytics-go/examples/requests/refund-assessment.json "$STAGE/refund-assessment.json"
tar -C "$OUT_DIR" -czf "$OUT_DIR/$NAME.tar.gz" "$NAME"
(cd "$OUT_DIR" && shasum -a 256 "$NAME.tar.gz" > "$NAME.tar.gz.sha256")
if [[ "$TARGET_OS" == "$HOST_OS" && "$TARGET_ARCH" == "$HOST_ARCH" ]]; then
  "$STAGE/frankengate-analytics" --version
else
  file "$STAGE/frankengate-analytics"
fi
echo "created $OUT_DIR/$NAME.tar.gz"
echo "checksum $OUT_DIR/$NAME.tar.gz.sha256"
