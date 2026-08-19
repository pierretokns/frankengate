#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
IMAGE=${IMAGE:-frankengate-analytics-control:verify}
PLATFORM=${PLATFORM:-}
cd "$ROOT"

command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
command -v rg >/dev/null || { echo "rg is required" >&2; exit 1; }

BUILD_ARGS=(build -f analytics-go/Dockerfile -t "$IMAGE")
if [[ -n "$PLATFORM" ]]; then
  BUILD_ARGS+=(--platform "$PLATFORM")
fi
BUILD_ARGS+=(analytics-go)
docker "${BUILD_ARGS[@]}"

docker run --rm "$IMAGE" --check
docker run --rm "$IMAGE" --version | rg -q '^frankengate-analytics '
[[ "$(docker inspect "$IMAGE" --format '{{.Config.User}}')" == "nonroot:nonroot" ]]
echo "analytics image verified: $IMAGE${PLATFORM:+ ($PLATFORM)}"
