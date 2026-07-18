#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --binary PATH --tests PATH [--tag beta-TAG] [--prepare-only DIR]" >&2
  echo "  PATH to a test report is required so local publication is explicit." >&2
  echo "  --prepare-only packages and verifies locally without GitHub auth." >&2
  exit 2
}

BINARY=""
TEST_REPORT=""
TAG=""
PREPARE_ONLY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --binary) BINARY="${2:-}"; shift 2 ;;
    --tests) TEST_REPORT="${2:-}"; shift 2 ;;
    --tag) TAG="${2:-}"; shift 2 ;;
    --prepare-only) PREPARE_ONLY="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

[[ -n "$BINARY" && -x "$BINARY" && -n "$TEST_REPORT" && -f "$TEST_REPORT" ]] || usage

# A beta must carry evidence of a successful verification run. Merely having
# a file at --tests is not sufficient: an earlier workflow accidentally
# packaged reports containing a failed package or panic. Keep this check
# intentionally format-light so Go, shell, and composite local reports work,
# while rejecting the unambiguous failure markers emitted by those runners.
[[ -s "$TEST_REPORT" ]] || { echo "test report is empty" >&2; exit 1; }
if rg -n -i '(^|[[:space:]])(FAIL|panic:|fatal error:|exit status [1-9])([[:space:]]|$)' "$TEST_REPORT" >/dev/null 2>&1; then
	echo "test report contains failure markers; refusing to package beta" >&2
	exit 1
fi
if ! rg -n -i '(^|[[:space:]])(ok|pass(ed)?)([[:space:]]|$)' "$TEST_REPORT" >/dev/null 2>&1; then
	echo "test report has no successful test marker; refusing to package beta" >&2
	exit 1
fi
if [[ -z "$PREPARE_ONLY" ]]; then
  command -v gh >/dev/null || { echo "gh CLI is required" >&2; exit 1; }
  gh auth status >/dev/null
fi

ROOT="$(git rev-parse --show-toplevel)"
SHA="$(git -C "$ROOT" rev-parse HEAD^{commit})"
SHORT_SHA="${SHA:0:12}"
TAG="${TAG:-beta-${SHORT_SHA}}"
[[ "$TAG" == beta-* ]] || { echo "local beta tags must begin with beta-" >&2; exit 1; }

VERSION_OUTPUT="$({ "$BINARY" -version 2>&1 || true; })"
[[ -n "$VERSION_OUTPUT" ]] || { echo "binary did not return version metadata" >&2; exit 1; }
# A normal beta must identify a real release version. Development binaries are
# still useful for local experiments, but require an explicit beta-dev tag so
# they cannot be mistaken for a consumable release artifact.
if printf '%s\n' "$VERSION_OUTPUT" | rg -q 'FrankenGate v0\.0\.0-dev' && [[ "$TAG" != beta-dev-* ]]; then
	echo "development binary requires an explicit beta-dev-* tag" >&2
	exit 1
fi

# Cross-built binaries are common on developer workstations. Allow the caller
# to describe the artifact platform explicitly instead of silently labeling a
# Linux binary as Darwin (or vice versa). Defaults preserve host behavior.
BETA_PLATFORM="${BETA_PLATFORM:-$(uname -s | tr '[:upper:]' '[:lower:]')}"
BETA_ARCH="${BETA_ARCH:-$(uname -m)}"
[[ "$BETA_PLATFORM" =~ ^[a-z0-9._-]+$ && "$BETA_ARCH" =~ ^[a-z0-9._-]+$ ]] || {
	echo "BETA_PLATFORM and BETA_ARCH must contain only lowercase safe identifier characters" >&2
	exit 1
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/frankengate-beta.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
# Platform-specific tags already carry their platform suffix. Avoid repeating
# it in the archive/package name while preserving the suffix for generic tags.
platform_suffix="-${BETA_PLATFORM}-${BETA_ARCH}"
if [[ "$TAG" == *"$platform_suffix" ]]; then
	PACKAGE="frankengate-${TAG}"
else
	PACKAGE="frankengate-${TAG}-${BETA_PLATFORM}-${BETA_ARCH}"
fi
mkdir -p "$WORK/$PACKAGE"
cp "$BINARY" "$WORK/$PACKAGE/frankengate"
cp "$ROOT/LICENSE" "$ROOT/NOTICE" "$WORK/$PACKAGE/"
cp "$TEST_REPORT" "$WORK/$PACKAGE/local-test-report"
git -C "$ROOT" log -n 30 --date=short --pretty=format:'%h %ad %s' > "$WORK/$PACKAGE/CHANGELOG.md"
printf '%s\n' "$VERSION_OUTPUT" > "$WORK/$PACKAGE/version.txt"
cat > "$WORK/$PACKAGE/build-metadata.json" <<EOF
{"source_sha":"$SHA","tag":"$TAG","origin":"local-tested-beta","binary":"$(basename "$BINARY")","platform":"$BETA_PLATFORM/$BETA_ARCH","go_version":"$(go version)","published_at":"$(date -u +%FT%TZ)"}
EOF
(cd "$WORK/$PACKAGE" && sha256sum frankengate > SHA256SUMS)
tar -C "$WORK" -czf "$WORK/$PACKAGE.tar.gz" "$PACKAGE"
(cd "$WORK" && sha256sum "$(basename "$PACKAGE.tar.gz")" > SHA256SUMS)
"$ROOT/scripts/verify-beta-local.sh" "$WORK/$PACKAGE.tar.gz" "$SHA"

if [[ -n "$PREPARE_ONLY" ]]; then
  mkdir -p "$PREPARE_ONLY"
  cp "$WORK/$PACKAGE.tar.gz" "$WORK/SHA256SUMS" "$PREPARE_ONLY/"
  # A prepare directory may intentionally retain older betas for comparison.
  # Publish an explicit pointer so consumers never have to choose an archive
  # by glob order or modification time.
  printf '%s\n' "$(basename "$WORK/$PACKAGE.tar.gz")" > "$PREPARE_ONLY/LATEST"
  echo "prepared $(cd "$PREPARE_ONLY" && pwd)/$(basename "$WORK/$PACKAGE.tar.gz")"
  exit 0
fi

REPO="$(git -C "$ROOT" remote get-url origin | sed -E 's#^https://github.com/##; s#\.git$##')"
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "release $TAG already exists; refusing to overwrite it" >&2
  exit 1
fi
NOTES="Locally tested beta for commit ${SHA}.\n\nThis is not an official release; the archive includes CHANGELOG.md, local-test-report, and build-metadata.json.\n\nDownload with: gh release download ${TAG} --repo ${REPO}"
# Create draft-first and upload independently. A single gh release create call
# can leave a partially uploaded release when one asset request times out.
gh release create "$TAG" --repo "$REPO" --target "$SHA" --prerelease --draft \
	--title "FrankenGate local beta ${SHORT_SHA}" --notes "$NOTES" >/dev/null
for asset in "$WORK/$PACKAGE.tar.gz" "$WORK/SHA256SUMS"; do
	 uploaded=false
	 for attempt in 1 2 3; do
		if gh release upload "$TAG" "$asset" --repo "$REPO" --clobber >/dev/null; then
			uploaded=true
			break
		fi
		sleep $((attempt * 2))
	 done
	 if [[ "$uploaded" != true ]]; then
		echo "failed to upload beta asset $(basename "$asset"); draft release left for inspection" >&2
		exit 1
	 fi
done
# Do not publish until both expected assets are visible on the draft release.
ASSET_COUNT="$(gh release view "$TAG" --repo "$REPO" --json assets --jq '.assets | map(select(.name == "'"$(basename "$WORK/$PACKAGE.tar.gz")"'" or .name == "SHA256SUMS")) | length')"
[[ "$ASSET_COUNT" == 2 ]] || { echo "beta release asset verification failed (found $ASSET_COUNT/2)" >&2; exit 1; }
gh release edit "$TAG" --repo "$REPO" --tag "$TAG" --draft=false >/dev/null
for attempt in 1 2 3 4 5; do
	RELEASE_STATE="$(gh release view "$TAG" --repo "$REPO" --json isDraft,tagName --jq '[.isDraft, .tagName] | @tsv' 2>/dev/null || true)"
	DRAFT_STATE="${RELEASE_STATE%%$'\t'*}"
	RELEASE_TAG="${RELEASE_STATE#*$'\t'}"
	if [[ "$DRAFT_STATE" == false && "$RELEASE_TAG" == "$TAG" ]]; then
		FINAL_URL="$(gh release view "$TAG" --repo "$REPO" --json url --jq '.url')"
		echo "published $FINAL_URL"
		exit 0
	fi
	sleep "$attempt"
done
echo "release $TAG did not become published after asset verification" >&2
exit 1
