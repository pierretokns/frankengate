#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 ARCHIVE EXPECTED_SHA" >&2; exit 2; }
[[ $# -eq 2 ]] || usage
ARCHIVE="$1"
EXPECTED_SHA="$2"
[[ -f "$ARCHIVE" ]] || { echo "archive not found: $ARCHIVE" >&2; exit 1; }
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{7,64}$ ]] || { echo "expected SHA must be hexadecimal" >&2; exit 1; }
command -v tar >/dev/null || { echo "tar is required" >&2; exit 1; }
command -v sha256sum >/dev/null || { echo "sha256sum is required" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/frankengate-verify.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
LIST="$WORK/list"
tar -tzf "$ARCHIVE" > "$LIST"
if grep -E '(^|/)\.\.?(/|$)|(^|/)\.\./' "$LIST" >/dev/null; then
	 echo "archive contains unsafe path" >&2
	 exit 1
fi
tar -xzf "$ARCHIVE" -C "$WORK"
PACKAGE_DIR="$(find "$WORK" -mindepth 1 -maxdepth 1 -type d -print -quit)"
[[ -n "$PACKAGE_DIR" ]] || { echo "archive has no package directory" >&2; exit 1; }
for required in frankengate LICENSE NOTICE local-test-report version.txt build-metadata.json CHANGELOG.md; do
	[[ -f "$PACKAGE_DIR/$required" ]] || { echo "missing $required" >&2; exit 1; }
done
grep -q '"source_sha":"'"$EXPECTED_SHA"'"' "$PACKAGE_DIR/build-metadata.json" || {
	 echo "build metadata source_sha does not match expected commit" >&2
	 exit 1
}
(cd "$PACKAGE_DIR" && sha256sum -c SHA256SUMS >/dev/null)
echo "verified beta archive for $EXPECTED_SHA"
