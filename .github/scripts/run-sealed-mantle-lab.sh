#!/usr/bin/env bash
set -Eeuo pipefail

root="$(git rev-parse --show-toplevel)"
lab="$root/tests/conformance/lab"
artifacts="$root/.artifacts/sealed-mantle"
build="$RUNNER_TEMP/sealed-mantle-build"
run_id="${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
registry="localhost:5000"
placeholder="registry.invalid/cleanup@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
bridge_prefix="fg$(printf '%s' "$run_id" | sha256sum | cut -c1-12)"
export LAB_RUN_ID="$run_id" BIFROST_IMAGE="$placeholder" CODEX_RUNNER_IMAGE="$placeholder" CLAUDE_RUNNER_IMAGE="$placeholder" EGRESS_SENTINEL_IMAGE="$placeholder"
export LAB_CLIENT_BRIDGE="${bridge_prefix}c" LAB_CONTROL_BRIDGE="${bridge_prefix}o" LAB_DATA_BRIDGE="${bridge_prefix}d"
if test -e "$artifacts"; then echo "refusing stale artifact directory: $artifacts" >&2; exit 1; fi
mkdir -p "$artifacts" "$build"
printf '{"schema":"sealed-mantle-ci-diagnostics/v1","run_id":"%s","artifact_status":"collecting"}\n' "$run_id" >"$artifacts/diagnostics.json"

cleanup() {
  local status=$? bounds=0 total=0 count=0 file size
  trap - EXIT
  docker compose --project-name "fg-lab-$run_id" --file "$lab/compose.yaml" --profile clients down --volumes --remove-orphans --timeout 10 || true
  docker rm --force sealed-lab-registry >/dev/null 2>&1 || true
  for file in "$artifacts"/*; do
    test -f "$file" || continue
    case "$(basename "$file")" in diagnostics.json|runtime-lock.json|lifecycle.json|failure-diagnostics.json) ;; *) rm -f "$file"; bounds=1; continue ;; esac
    size="$(stat -c %s "$file")"; count=$((count+1)); total=$((total+size))
    if (( size > 4194304 )); then rm -f "$file"; bounds=1; fi
  done
  if (( count > 4 || total > 8388608 )); then bounds=1; fi
  for _ in 1 2 3 4; do
    printf '{"schema":"sealed-mantle-ci-diagnostics/v1","run_id":"%s","artifact_status":"%s","file_count":%d,"observed_bytes":%d}\n' "$run_id" "$([[ $bounds == 0 ]] && echo bounded || echo rejected-oversize)" "$count" "$total" >"$artifacts/diagnostics.json"
    count=0; total=0
    for file in "$artifacts"/*; do test -f "$file" || continue; count=$((count+1)); total=$((total+$(stat -c %s "$file"))); done
  done
  if (( count > 4 || total > 8388608 )); then bounds=1; fi
  if test "$(jq -r .file_count "$artifacts/diagnostics.json")" != "$count" || test "$(jq -r .observed_bytes "$artifacts/diagnostics.json")" != "$total"; then bounds=1; fi
  if (( bounds != 0 )); then status=1; fi
  exit "$status"
}
trap cleanup EXIT

docker run -d --name sealed-lab-registry --network host registry:2@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373
node --test "$lab/prefetch/verify-tree.test.mjs"

source_hash="$(sha256sum "$lab/images.lock.v1.json" | cut -d' ' -f1)"
codex_version="$(jq -r '.cli_packages[] | select(.id=="codex-production") | .version' "$lab/images.lock.v1.json")"
claude_version="$(jq -r '.cli_packages[] | select(.id=="claude-code-production") | .version' "$lab/images.lock.v1.json")"

build_cli() {
  local client="$1" package_id="$2"
  local package version integrity arch context tag
  package="$(jq -r --arg id "$package_id" '.cli_packages[] | select(.id==$id) | .package' "$lab/images.lock.v1.json")"
  version="$(jq -r --arg id "$package_id" '.cli_packages[] | select(.id==$id) | .version' "$lab/images.lock.v1.json")"
  integrity="$(jq -r --arg id "$package_id" '.cli_packages[] | select(.id==$id) | .integrity' "$lab/images.lock.v1.json")"
  for arch in amd64 arm64; do
    context="$build/$client-$arch"; mkdir -p "$context/offline" "$context/seed"
    docker buildx build --platform "linux/$arch" --file "$lab/Dockerfile.prefetch" \
      --build-arg "CLI_PACKAGE=$package" --build-arg "CLI_VERSION=$version" --build-arg "CLI_INTEGRITY=$integrity" \
      --output "type=local,dest=$context/offline" "$lab"
    (cd "$lab" && GOWORK=off CGO_ENABLED=0 GOOS=linux GOARCH="$arch" go build -trimpath -ldflags='-s -w' -o "$context/cell-init" ./cmd/cell-init)
    cp -R "$lab/seed/$client/." "$context/seed/"
    tag="$registry/sealed-$client:$run_id-$arch"
    docker buildx build --network=none --platform "linux/$arch" --file "$lab/Dockerfile.runner" --push --tag "$tag" "$context"
  done
  docker buildx imagetools create --tag "$registry/sealed-$client:$run_id" \
    "$registry/sealed-$client:$run_id-amd64" "$registry/sealed-$client:$run_id-arm64"
}

build_cli codex codex-production
build_cli claude claude-code-production

mkdir -p "$build/source"
git -C "$root" archive HEAD | tar -x -C "$build/source"
test -f "$build/source/tests/conformance/lab/cmd/config-seed/main.go"
test -f "$build/source/tests/conformance/lab/mantleservice/integration.go"
docker buildx build --platform linux/amd64,linux/arm64 --file "$build/source/tests/conformance/lab/Dockerfile.gateway" --push --tag "$registry/bifrost:$run_id" "$build/source"
for arch in amd64 arm64; do
  mkdir -p "$build/sentinel-$arch/offline"
  (cd "$lab" && GOWORK=off CGO_ENABLED=0 GOOS=linux GOARCH="$arch" go build -trimpath -ldflags='-s -w' -o "$build/sentinel-$arch/offline/egress-sentinel" ./cmd/egress-sentinel)
  docker buildx build --network=none --platform "linux/$arch" --file "$lab/Dockerfile.sentinel" --push --tag "$registry/sentinel:$run_id-$arch" "$build/sentinel-$arch"
done
docker buildx imagetools create --tag "$registry/sentinel:$run_id" "$registry/sentinel:$run_id-amd64" "$registry/sentinel:$run_id-arm64"

reference() {
  local image="$1" digest
  digest="$(docker buildx imagetools inspect "$image" --format '{{json .Manifest.Digest}}' | tr -d '"')"
  printf '%s@%s' "${image%:*}" "$digest"
}
bifrost_ref="$(reference "$registry/bifrost:$run_id")"
codex_ref="$(reference "$registry/sealed-codex:$run_id")"
claude_ref="$(reference "$registry/sealed-claude:$run_id")"
sentinel_ref="$(reference "$registry/sentinel:$run_id")"
export BIFROST_IMAGE="$bifrost_ref" CODEX_RUNNER_IMAGE="$codex_ref" CLAUDE_RUNNER_IMAGE="$claude_ref" EGRESS_SENTINEL_IMAGE="$sentinel_ref"

jq -n --arg run "$run_id" --arg source "$source_hash" --arg bifrost "$bifrost_ref" --arg codex "$codex_ref" --arg claude "$claude_ref" --arg sentinel "$sentinel_ref" --arg cv "$codex_version" --arg av "$claude_version" '{schema:"sealed-lab-runtime-lock/v1",run_id:$run,source_lock_sha256:$source,images:[{id:"bifrost",reference:$bifrost,platforms:["linux/amd64","linux/arm64"],source:("git:"+env.GITHUB_SHA)},{id:"claude-runner",reference:$claude,platforms:["linux/amd64","linux/arm64"],source:("lock:"+$av),client_version:$av},{id:"codex-runner",reference:$codex,platforms:["linux/amd64","linux/arm64"],source:("lock:"+$cv),client_version:$cv},{id:"egress-sentinel",reference:$sentinel,platforms:["linux/amd64","linux/arm64"],source:("git:"+env.GITHUB_SHA)}]}' >"$artifacts/runtime-lock.json"

(cd "$lab" && GOWORK=off go run ./cmd/lab-runner --runtime-lock "$artifacts/runtime-lock.json" --source-lock "$lab/images.lock.v1.json" --compose "$lab/compose.yaml" --docker "$(command -v docker)" --failure-diagnostics-artifact "$artifacts/failure-diagnostics.json") >"$artifacts/lifecycle.json"
jq -e '.schema=="sealed-lab-lifecycle-result/v2" and .teardown_clean==true and .codex_inference_boundary.exit_code==0 and .codex_inference_boundary.transport_outcome=="completed"' "$artifacts/lifecycle.json" >/dev/null
