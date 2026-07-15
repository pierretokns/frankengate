#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
NAMESPACE="${NAMESPACE:-frankengate-test}"
KEEP_FIXTURE="${KEEP_FIXTURE:-0}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-docker.io/library/postgres:16-alpine}"
MANIFEST="$ROOT/tests/kubernetes/local-aurora/gateway-vk-coherence.yaml"
SERVER_SCRIPT="$ROOT/tests/kubernetes/local-aurora/serve-binary.sh"
WORK_DIR="$(mktemp -d)"
BINARY="${FRANKENGATE_BINARY:-$WORK_DIR/frankengate}"
FRANKENGATE_IMAGE="${FRANKENGATE_IMAGE:-}"
FRANKENGATE_IMAGE_PULL_POLICY="${FRANKENGATE_IMAGE_PULL_POLICY:-Always}"

cleanup() {
  local status=$?
  trap - EXIT
  if [[ "$KEEP_FIXTURE" != "1" ]]; then
    kubectl -n "$NAMESPACE" delete deployment/frankengate-vk service/frankengate-vk \
      pod/frankengate-binary service/frankengate-binary configmap/frankengate-vk-config \
      --ignore-not-found --wait=false >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
  exit "$status"
}
trap cleanup EXIT

for command in git go jq kubectl shasum; do
  command -v "$command" >/dev/null || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

if [[ -z "$FRANKENGATE_IMAGE" && -z "${FRANKENGATE_BINARY:-}" ]]; then
  node_arch="$(kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.architecture}')"
  case "$node_arch" in
    arm64|amd64) ;;
    *) echo "unsupported Kubernetes node architecture: $node_arch" >&2; exit 1 ;;
  esac

  module_dirs=("$ROOT/core" "$ROOT/framework" "$ROOT/transports")
  while IFS= read -r plugin_mod; do
    module_dirs+=("${plugin_mod%/go.mod}")
  done < <(find "$ROOT/plugins" -mindepth 2 -maxdepth 2 -name go.mod -print | sort)
  (
    cd "$WORK_DIR"
    go work init "${module_dirs[@]}"
    cd "$ROOT/transports/bifrost-http"
    GOWORK="$WORK_DIR/go.work" CGO_ENABLED=0 GOOS=linux GOARCH="$node_arch" \
      go build -trimpath -ldflags '-s -w -X main.version=vk-coherence-test' -o "$BINARY" .
  )
fi

existing_postgres_ip="$(kubectl -n "$NAMESPACE" get service/postgres -o jsonpath='{.spec.clusterIP}' 2>/dev/null || true)"
if [[ -n "$existing_postgres_ip" && "$existing_postgres_ip" != "None" ]]; then
  echo "recreating drifted test-only postgres Service (clusterIP=$existing_postgres_ip, expected headless)" >&2
  kubectl -n "$NAMESPACE" delete service/postgres --wait=true
fi
sed -E "s#^([[:space:]]*)image: postgres:16-alpine@sha256:[[:xdigit:]]+#\\1image: $POSTGRES_IMAGE#" \
  "$ROOT/tests/kubernetes/local-aurora/postgres.yaml" > "$WORK_DIR/postgres.yaml"
kubectl apply -f "$WORK_DIR/postgres.yaml"
live_postgres_image="$(kubectl -n "$NAMESPACE" get pod/postgres-0 -o jsonpath='{.spec.containers[0].image}' 2>/dev/null || true)"
if [[ -n "$live_postgres_image" && "$live_postgres_image" != "$POSTGRES_IMAGE" ]]; then
  echo "restarting drifted test-only postgres pod (image=$live_postgres_image, expected=$POSTGRES_IMAGE)" >&2
  kubectl -n "$NAMESPACE" delete pod/postgres-0 --wait=true
fi
kubectl -n "$NAMESPACE" rollout status statefulset/postgres --timeout=180s

# This namespace and database are explicitly test-only. A retained fixture may
# contain encrypted rows or schema mutations from focused PostgreSQL tests,
# which can make governance fail closed before this oracle begins. Stop every
# old gateway connection and rebuild the disposable public schema so each run
# proves the current binary from a deterministic authority state.
kubectl -n "$NAMESPACE" delete deployment/frankengate-vk --ignore-not-found --wait=true >/dev/null
kubectl -n "$NAMESPACE" exec postgres-0 -- psql -v ON_ERROR_STOP=1 -U frankengate -d frankengate \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO frankengate;'

kubectl -n "$NAMESPACE" delete pod/frankengate-binary --ignore-not-found --wait=true >/dev/null
kubectl -n "$NAMESPACE" run frankengate-binary \
  --image="$POSTGRES_IMAGE" --image-pull-policy=IfNotPresent \
  --labels='app.kubernetes.io/name=frankengate-binary,frankengate.dev/test-only=true' \
  --overrides='{"spec":{"affinity":{"podAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":[{"labelSelector":{"matchLabels":{"app.kubernetes.io/name":"postgres"}},"topologyKey":"kubernetes.io/hostname"}]}}}}' \
  --restart=Never --command -- sleep 3600
kubectl -n "$NAMESPACE" wait --for=condition=Ready pod/frankengate-binary --timeout=120s
if [[ -z "$FRANKENGATE_IMAGE" ]]; then
  kubectl -n "$NAMESPACE" cp "$BINARY" frankengate-binary:/tmp/frankengate
  kubectl -n "$NAMESPACE" cp "$SERVER_SCRIPT" frankengate-binary:/tmp/serve-binary.sh
  kubectl -n "$NAMESPACE" exec frankengate-binary -- chmod 0555 /tmp/frankengate /tmp/serve-binary.sh
  kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c \
    'nohup /tmp/serve-binary.sh /tmp/frankengate 18080 >/tmp/binary-server.log 2>&1 &'
  if ! kubectl -n "$NAMESPACE" get service/frankengate-binary >/dev/null 2>&1; then
    kubectl -n "$NAMESPACE" expose pod/frankengate-binary --name=frankengate-binary --port=18080 --target-port=18080
  fi
  binary_service_ip="$(kubectl -n "$NAMESPACE" get service/frankengate-binary -o jsonpath='{.spec.clusterIP}')"
  if [[ -z "$binary_service_ip" || "$binary_service_ip" == "None" ]]; then
    echo "binary service has no usable ClusterIP" >&2
    exit 1
  fi
else
  # The release-image path removes the test-only init transfer and runs the
  # image's own ENTRYPOINT/CMD. Keep the utility pod for in-cluster HTTP oracles.
  binary_service_ip="127.0.0.1"
fi
if [[ -n "$FRANKENGATE_IMAGE" ]]; then
  artifact_sha256="$(printf '%s' "$FRANKENGATE_IMAGE" | shasum -a 256 | awk '{print $1}')"
else
  artifact_sha256="$(shasum -a 256 "$BINARY" | awk '{print $1}')"
fi
sed -e "s/__BINARY_SERVICE_IP__/$binary_service_ip/g" \
  -e "s/__ARTIFACT_SHA256__/$artifact_sha256/g" \
  "$MANIFEST" > "$WORK_DIR/gateway.yaml"
kubectl apply -f "$WORK_DIR/gateway.yaml"
if [[ -n "$FRANKENGATE_IMAGE" ]]; then
  # The checked-in manifest intentionally starts with the binary-transfer init
  # container. Remove that ReplicaSet completely before switching to the image
  # template so required one-pod-per-node anti-affinity cannot deadlock a
  # rolling update behind an obsolete init pod.
  kubectl -n "$NAMESPACE" scale deployment/frankengate-vk --replicas=0
  kubectl -n "$NAMESPACE" rollout status deployment/frankengate-vk --timeout=120s
  image_patch="$(jq -cn --arg image "$FRANKENGATE_IMAGE" '[
    {op:"remove",path:"/spec/template/spec/initContainers"},
    {op:"replace",path:"/spec/template/spec/containers/0/image",value:$image},
    {op:"replace",path:"/spec/template/spec/containers/0/imagePullPolicy",value:$pull_policy},
    {op:"remove",path:"/spec/template/spec/containers/0/command"},
    {op:"remove",path:"/spec/template/spec/containers/0/args"},
    {op:"remove",path:"/spec/template/spec/containers/0/volumeMounts/0"},
    {op:"remove",path:"/spec/template/spec/volumes/0"},
    {op:"remove",path:"/spec/template/spec/affinity"},
    {op:"add",path:"/spec/template/spec/affinity",value:{podAntiAffinity:{requiredDuringSchedulingIgnoredDuringExecution:[{
      labelSelector:{matchLabels:{"app.kubernetes.io/name":"frankengate-vk"}},
      topologyKey:"kubernetes.io/hostname"
    }]}}},
    {op:"add",path:"/spec/template/spec/topologySpreadConstraints",value:[{
      maxSkew:1,
      topologyKey:"kubernetes.io/hostname",
      whenUnsatisfiable:"DoNotSchedule",
      labelSelector:{matchLabels:{"app.kubernetes.io/name":"frankengate-vk"}}
    }]}
  ]' --arg pull_policy "$FRANKENGATE_IMAGE_PULL_POLICY")"
  kubectl -n "$NAMESPACE" patch deployment/frankengate-vk --type=json -p "$image_patch"
  kubectl -n "$NAMESPACE" scale deployment/frankengate-vk --replicas=3
fi
kubectl -n "$NAMESPACE" rollout status deployment/frankengate-vk --timeout=240s

list_ready_gateway_ips() {
  kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name=frankengate-vk -o json |
    jq -r '.items[] | select(.metadata.deletionTimestamp == null) | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .status.podIP' |
    sort
}

wait_for_three_ready_gateway_ips() {
  local deadline
  deadline=$(( $(date +%s) + 240 ))
  while :; do
    pod_ips=()
    while IFS= read -r ip; do
      [[ -n "$ip" ]] && pod_ips+=("$ip")
    done < <(list_ready_gateway_ips)
    if [[ "${#pod_ips[@]}" -eq 3 ]]; then
      return 0
    fi
    if [[ "$(date +%s)" -ge "$deadline" ]]; then
      echo "expected 3 non-terminating Ready gateway pod IPs, got ${#pod_ips[@]}" >&2
      return 1
    fi
    sleep 1
  done
}

assert_release_image_spans_three_nodes() {
  [[ -z "$FRANKENGATE_IMAGE" ]] && return 0
  distinct_nodes="$(kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name=frankengate-vk -o json |
    jq -r '.items[] | select(.metadata.deletionTimestamp == null) | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .spec.nodeName' | sort -u | wc -l | tr -d ' ')"
  if [[ "$distinct_nodes" -ne 3 ]]; then
    echo "release-image proof expected 3 distinct Kubernetes nodes, got $distinct_nodes" >&2
    return 1
  fi
}

pod_ips=()
wait_for_three_ready_gateway_ips
assert_release_image_spans_three_nodes

wait_for_cache() {
  local expected_state="$1" expected_id="$2" expected_marker="${3:-}"
  # The single-quoted program is evaluated by the in-cluster BusyBox shell;
  # positional arguments below intentionally provide all dynamic values.
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c '
    expected_state="$1"
    expected_id="$2"
    expected_marker="$3"
    shift 3
    deadline=$(( $(date +%s) + 8 ))
    while [ "$(date +%s)" -le "$deadline" ]; do
      all_match=1
      for ip do
        body="$(wget -T 2 -qO- "http://$ip:8080/api/governance/virtual-keys?from_memory=true")" || {
          all_match=0
          break
        }
        case "$expected_state:$body" in
          present:*"$expected_id"*"$expected_marker"*) ;;
          absent:*"$expected_id"*) all_match=0; break ;;
          absent:*) ;;
          *) all_match=0; break ;;
        esac
      done
      [ "$all_match" -eq 1 ] && exit 0
      sleep 1
    done
    echo "pod caches did not converge to state=$expected_state id=$expected_id" >&2
    exit 1
  ' sh "$expected_state" "$expected_id" "$expected_marker" "${pod_ips[@]}"
}

created="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- \
  --header 'Content-Type: application/json' \
  --post-data "{\"name\":\"horizontal-coherence-proof-${RANDOM}-${SECONDS}\"}" \
  "http://${pod_ips[0]}:8080/api/governance/virtual-keys")"
vk_id="$(jq -er '.virtual_key.id' <<<"$created")"
original_secret="$(jq -er '.secret' <<<"$created")"
created_updated_at="$(jq -er '.virtual_key.updated_at' <<<"$created")"
wait_for_cache present "$vk_id" "$created_updated_at"

rotated="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- --post-data '' \
  "http://${pod_ips[1]}:8080/api/governance/virtual-keys/$vk_id/rotate")"
rotated_secret="$(jq -er '.secret' <<<"$rotated")"
rotated_updated_at="$(jq -er '.virtual_key.updated_at' <<<"$rotated")"
if [[ "$rotated_secret" == "$original_secret" ]]; then
  echo "rotation did not change the virtual-key value" >&2
  exit 1
fi
if [[ "$rotated_updated_at" == "$created_updated_at" ]]; then
  echo "rotation did not advance virtual-key updated_at" >&2
  exit 1
fi
wait_for_cache present "$vk_id" "$rotated_updated_at"

delete_response="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c \
  "printf 'DELETE /api/governance/virtual-keys/$vk_id HTTP/1.1\\r\\nHost: ${pod_ips[2]}\\r\\nConnection: close\\r\\n\\r\\n' | nc ${pod_ips[2]} 8080")"
grep -q '200 OK' <<<"$delete_response"
wait_for_cache absent "$vk_id"

actions="$(kubectl -n "$NAMESPACE" exec postgres-0 -- psql -At -U frankengate -d frankengate \
  -c "select action from governance_virtual_key_invalidation_outbox where entity_id = '$vk_id' order by id")"
if [[ "$actions" != $'reload\nreload\ndelete' ]]; then
  echo "unexpected durable invalidation sequence for $vk_id:" >&2
  echo "$actions" >&2
  exit 1
fi

restarted_pod="$(kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name=frankengate-vk \
  -o jsonpath='{.items[0].metadata.name}')"
kubectl -n "$NAMESPACE" delete pod "$restarted_pod" --wait=false >/dev/null
kubectl -n "$NAMESPACE" rollout status deployment/frankengate-vk --timeout=240s
wait_for_three_ready_gateway_ips
assert_release_image_spans_three_nodes
wait_for_cache absent "$vk_id"

partition_created="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- \
  --header 'Content-Type: application/json' \
  --post-data "{\"name\":\"mcp-partition-proof-${RANDOM}-${SECONDS}\"}" \
  "http://${pod_ips[0]}:8080/api/governance/virtual-keys")"
partition_vk_id="$(jq -er '.virtual_key.id' <<<"$partition_created")"
partition_secret="$(jq -er '.secret' <<<"$partition_created")"
partition_updated_at="$(jq -er '.virtual_key.updated_at' <<<"$partition_created")"
wait_for_cache present "$partition_vk_id" "$partition_updated_at"

# A release image must fail direct MCP authorization closed when this pod can
# no longer prove its cached VK authority is current. Removing the disposable
# PostgreSQL authority severs both LISTEN/NOTIFY and the mandatory cursor poll;
# after the five-second lease, every pod must reject a previously valid key
# before consulting its per-VK MCP server cache.
kubectl -n "$NAMESPACE" scale statefulset/postgres --replicas=0
kubectl -n "$NAMESPACE" wait --for=delete pod/postgres-0 --timeout=120s

call_mcp_initialize() {
  local ip="$1" secret="$2"
  # The single-quoted program runs inside the utility pod; all dynamic values
  # enter as positional arguments so host-shell interpolation is impossible.
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c '
    ip="$1"
    secret="$2"
    body='"'"'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"frankengate-vk-oracle","version":"1"}}}'"'"'
    length="$(printf %s "$body" | wc -c | tr -d " ")"
    printf "POST /mcp HTTP/1.1\r\nHost: %s\r\nx-bf-vk: %s\r\nContent-Type: application/json\r\nContent-Length: %s\r\nConnection: close\r\n\r\n%s" \
      "$ip" "$secret" "$length" "$body" | nc "$ip" 8080
  ' sh "$ip" "$secret"
}

deadline=$(( $(date +%s) + 20 ))
while :; do
  all_stale_closed=1
  for ip in "${pod_ips[@]}"; do
    response="$(call_mcp_initialize "$ip" "$partition_secret" 2>/dev/null || true)"
    if ! grep -q '401 Unauthorized' <<<"$response" ||
       ! grep -q 'virtual key authority is stale' <<<"$response"; then
      all_stale_closed=0
      break
    fi
  done
  if [[ "$all_stale_closed" -eq 1 ]]; then
    break
  fi
  if [[ "$(date +%s)" -ge "$deadline" ]]; then
    echo "MCP virtual-key authorization did not fail closed on every pod after authority partition" >&2
    exit 1
  fi
  sleep 1
done

jq -n --arg vk_id "$vk_id" --argjson pods "${#pod_ips[@]}" \
  --arg artifact "${FRANKENGATE_IMAGE:-loose-binary}" \
  '{ok:true,pods:$pods,artifact:$artifact,virtual_key_id:$vk_id,create_secret_revealed_once:true,rotation_secret_revealed_once:true,outbox:["reload","reload","delete"],restart_replay:"passed",mcp_authority_partition:"stale-closed-on-all-pods"}'
