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

cleanup() {
  if [[ "$KEEP_FIXTURE" != "1" ]]; then
    kubectl -n "$NAMESPACE" delete deployment/frankengate-vk service/frankengate-vk \
      pod/frankengate-binary service/frankengate-binary configmap/frankengate-vk-config \
      --ignore-not-found --wait=false >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

for command in git go jq kubectl shasum; do
  command -v "$command" >/dev/null || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

if [[ -z "${FRANKENGATE_BINARY:-}" ]]; then
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
sed "s/__BINARY_SERVICE_IP__/$binary_service_ip/g" "$MANIFEST" > "$WORK_DIR/gateway.yaml"
kubectl apply -f "$WORK_DIR/gateway.yaml"
binary_sha256="$(shasum -a 256 "$BINARY" | awk '{print $1}')"
# The init container copies bytes from a stable in-cluster Service URL. The
# rendered Deployment can therefore be unchanged even when those bytes differ;
# stamp the content digest into the pod template so every tested binary gets a
# real rollout and no run can accidentally exercise stale gateway processes.
kubectl -n "$NAMESPACE" patch deployment/frankengate-vk --type=merge \
  -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"frankengate.dev/test-binary-sha256\":\"$binary_sha256\"}}}}}"
kubectl -n "$NAMESPACE" rollout status deployment/frankengate-vk --timeout=240s

list_ready_gateway_ips() {
  kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name=frankengate-vk -o json |
    jq -r '.items[] | select(.metadata.deletionTimestamp == null) | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .status.podIP' |
    sort
}

pod_ips=()
while IFS= read -r ip; do
  [[ -n "$ip" ]] && pod_ips+=("$ip")
done < <(list_ready_gateway_ips)
if [[ "${#pod_ips[@]}" -ne 3 ]]; then
  echo "expected 3 gateway pod IPs, got ${#pod_ips[@]}" >&2
  exit 1
fi

wait_for_cache() {
  local expected_state="$1" expected_id="$2" expected_value="${3:-}"
  # The single-quoted program is evaluated by the in-cluster BusyBox shell;
  # positional arguments below intentionally provide all dynamic values.
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c '
    expected_state="$1"
    expected_id="$2"
    expected_value="$3"
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
          present:*"$expected_id"*"$expected_value"*) ;;
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
  ' sh "$expected_state" "$expected_id" "$expected_value" "${pod_ips[@]}"
}

created="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- \
  --header 'Content-Type: application/json' \
  --post-data "{\"name\":\"horizontal-coherence-proof-${RANDOM}-${SECONDS}\"}" \
  "http://${pod_ips[0]}:8080/api/governance/virtual-keys")"
vk_id="$(jq -er '.virtual_key.id' <<<"$created")"
original_value="$(jq -er '.virtual_key.value' <<<"$created")"
wait_for_cache present "$vk_id" "$original_value"

rotated="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- --post-data '' \
  "http://${pod_ips[1]}:8080/api/governance/virtual-keys/$vk_id/rotate")"
rotated_value="$(jq -er '.virtual_key.value' <<<"$rotated")"
if [[ "$rotated_value" == "$original_value" ]]; then
  echo "rotation did not change the virtual-key value" >&2
  exit 1
fi
wait_for_cache present "$vk_id" "$rotated_value"

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
pod_ips=()
while IFS= read -r ip; do
  [[ -n "$ip" ]] && pod_ips+=("$ip")
done < <(list_ready_gateway_ips)
wait_for_cache absent "$vk_id"

jq -n --arg vk_id "$vk_id" --arg original "$original_value" --arg rotated "$rotated_value" \
  --argjson pods "${#pod_ips[@]}" \
  '{ok:true,pods:$pods,virtual_key_id:$vk_id,create_value:$original,rotated_value:$rotated,outbox:["reload","reload","delete"],restart_replay:"passed"}'
