#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --binary PATH --tests PATH [--tag beta-TAG]" >&2
  echo "  PATH to a test report is required so local publication is explicit." >&2
  exit 2
}

BINARY=""
TEST_REPORT=""
TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --binary) BINARY="${2:-}"; shift 2 ;;
    --tests) TEST_REPORT="${2:-}"; shift 2 ;;
    --tag) TAG="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

[[ -n "$BINARY" && -x "$BINARY" && -n "$TEST_REPORT" && -f "$TEST_REPORT" ]] || usage
command -v gh >/dev/null || { echo "gh CLI is required" >&2; exit 1; }
gh auth status >/dev/null

ROOT="$(git rev-parse --show-toplevel)"
SHA="$(git -C "$ROOT" rev-parse HEAD^{commit})"
SHORT_SHA="${SHA:0:12}"
TAG="${TAG:-beta-${SHORT_SHA}}"
[[ "$TAG" == beta-* ]] || { echo "local beta tags must begin with beta-" >&2; exit 1; }

VERSION_OUTPUT="$({ "$BINARY" -version 2>&1 || true; })"
[[ -n "$VERSION_OUTPUT" ]] || { echo "binary did not return version metadata" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/frankengate-beta.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
PACKAGE="frankengate-${TAG}-$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)"
mkdir -p "$WORK/$PACKAGE"
cp "$BINARY" "$WORK/$PACKAGE/frankengate"
cp "$ROOT/LICENSE" "$ROOT/NOTICE" "$WORK/$PACKAGE/"
cp "$TEST_REPORT" "$WORK/$PACKAGE/local-test-report"
git -C "$ROOT" log -n 30 --date=short --pretty=format:'%h %ad %s' > "$WORK/$PACKAGE/CHANGELOG.md"
printf '%s\n' "$VERSION_OUTPUT" > "$WORK/$PACKAGE/version.txt"
cat > "$WORK/$PACKAGE/build-metadata.json" <<EOF
{"source_sha":"$SHA","tag":"$TAG","origin":"local-tested-beta","binary":"$(basename "$BINARY")","platform":"$(uname -s)/$(uname -m)","go_version":"$(go version)","published_at":"$(date -u +%FT%TZ)"}
EOF
(cd "$WORK/$PACKAGE" && sha256sum frankengate > SHA256SUMS)
tar -C "$WORK" -czf "$WORK/$PACKAGE.tar.gz" "$PACKAGE"
(cd "$WORK" && sha256sum "$(basename "$PACKAGE.tar.gz")" > SHA256SUMS)

REPO="$(git -C "$ROOT" remote get-url origin | sed -E 's#^https://github.com/##; s#\.git$##')"
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "release $TAG already exists; refusing to overwrite it" >&2
  exit 1
fi
gh release create "$TAG" "$WORK/$PACKAGE.tar.gz" "$WORK/SHA256SUMS" \
  --repo "$REPO" --target "$SHA" --prerelease \
  --title "FrankenGate local beta ${SHORT_SHA}" \
  --notes "Locally tested beta for commit ${SHA}.\n\nThis is not an official release; the archive includes CHANGELOG.md, local-test-report, and build-metadata.json.\n\nDownload with: gh release download ${TAG} --repo ${REPO}"
echo "published https://github.com/${REPO}/releases/tag/${TAG}"
