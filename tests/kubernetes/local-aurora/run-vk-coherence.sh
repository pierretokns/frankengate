#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
NAMESPACE="${NAMESPACE:-frankengate-test}"
KEEP_FIXTURE="${KEEP_FIXTURE:-0}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-docker.io/pgvector/pgvector:0.8.1-pg16@sha256:33198da2828a14c30348d2ccb4750833d5ed9a44c88d840a0e523d7417120337}"
# Utility-only pods need wget, sha256sum, and nc for binary transfer. Database
# images intentionally do not guarantee those tools, so keep this image
# independently configurable.
BINARY_SERVER_IMAGE="${BINARY_SERVER_IMAGE:-docker.io/library/alpine:3.20}"
MANIFEST="$ROOT/tests/kubernetes/local-aurora/gateway-vk-coherence.yaml"
SERVER_SCRIPT="$ROOT/tests/kubernetes/local-aurora/serve-binary.sh"
WORK_DIR="$(mktemp -d)"
BINARY="${FRANKENGATE_BINARY:-$WORK_DIR/frankengate}"
FRANKENGATE_IMAGE="${FRANKENGATE_IMAGE:-}"
FRANKENGATE_IMAGE_PULL_POLICY="${FRANKENGATE_IMAGE_PULL_POLICY:-Always}"
# Stress scale defaults to the 100-pod oracle. Set VK_COHERENCE_REPLICAS=3
# for a fast smoke run. Distinct-node placement is opt-in because local k3d
# clusters often have fewer nodes than replicas.
VK_COHERENCE_REPLICAS="${VK_COHERENCE_REPLICAS:-100}"
VK_COHERENCE_MIN_REPLICAS="${VK_COHERENCE_MIN_REPLICAS:-2}"
REQUIRE_DISTINCT_NODES="${REQUIRE_DISTINCT_NODES:-0}"
VK_COHERENCE_STORM_REQUESTS="${VK_COHERENCE_STORM_REQUESTS:-$((VK_COHERENCE_REPLICAS * 2))}"
BINARY_SERVER_REPLICAS="${BINARY_SERVER_REPLICAS:-5}"
VK_COHERENCE_READY_TIMEOUT="${VK_COHERENCE_READY_TIMEOUT:-240}"
[[ "$VK_COHERENCE_REPLICAS" =~ ^[1-9][0-9]*$ ]] || { echo "VK_COHERENCE_REPLICAS must be a positive integer" >&2; exit 1; }
[[ "$VK_COHERENCE_MIN_REPLICAS" =~ ^[1-9][0-9]*$ ]] || { echo "VK_COHERENCE_MIN_REPLICAS must be a positive integer" >&2; exit 1; }
(( VK_COHERENCE_MIN_REPLICAS < VK_COHERENCE_REPLICAS )) || { echo "VK_COHERENCE_MIN_REPLICAS must be less than VK_COHERENCE_REPLICAS" >&2; exit 1; }
[[ "$VK_COHERENCE_STORM_REQUESTS" =~ ^[1-9][0-9]*$ ]] || { echo "VK_COHERENCE_STORM_REQUESTS must be a positive integer" >&2; exit 1; }
[[ "$BINARY_SERVER_REPLICAS" =~ ^[1-9][0-9]*$ ]] || { echo "BINARY_SERVER_REPLICAS must be a positive integer" >&2; exit 1; }
[[ "$VK_COHERENCE_READY_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || { echo "VK_COHERENCE_READY_TIMEOUT must be a positive integer" >&2; exit 1; }

cleanup() {
  local status=$?
  trap - EXIT
  if [[ "$KEEP_FIXTURE" != "1" ]]; then
    kubectl -n "$NAMESPACE" delete deployment/frankengate-vk service/frankengate-vk \
      service/frankengate-binary configmap/frankengate-vk-config \
      --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "$NAMESPACE" delete pod -l app.kubernetes.io/name=frankengate-vk \
      --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "$NAMESPACE" delete pod -l app.kubernetes.io/name=frankengate-binary \
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
  # The transport embeds the generated UI tree. A clean checkout does not
  # contain transports/bifrost-http/ui, so build it explicitly before the
  # binary-only oracle instead of letting go:embed fail opaquely.
  if [[ ! -f "$ROOT/transports/bifrost-http/ui/index.html" ]]; then
    echo "generated UI artifact missing; building UI for clean binary oracle" >&2
    make -C "$ROOT" build-ui
  fi
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
# The fixture is explicitly disposable. Reset the StatefulSet and its PVC so
# interrupted runs cannot retain a volume with host-specific ownership or a
# partially initialized database that prevents PostgreSQL from starting.
kubectl -n "$NAMESPACE" delete statefulset/postgres --ignore-not-found --wait=true >/dev/null 2>&1 || true
kubectl -n "$NAMESPACE" delete pvc/data-postgres-0 --ignore-not-found --wait=true >/dev/null 2>&1 || true
if [[ -n "$existing_postgres_ip" && "$existing_postgres_ip" != "None" ]]; then
  echo "recreating drifted test-only postgres Service (clusterIP=$existing_postgres_ip, expected headless)" >&2
  kubectl -n "$NAMESPACE" delete service/postgres --wait=true
fi
sed -E "s#^([[:space:]]*)image: (postgres|pgvector/pgvector):[^[:space:]]+#\\1image: $POSTGRES_IMAGE#" \
  "$ROOT/tests/kubernetes/local-aurora/postgres.yaml" > "$WORK_DIR/postgres.yaml"
kubectl apply -f "$WORK_DIR/postgres.yaml"
live_postgres_image="$(kubectl -n "$NAMESPACE" get pod/postgres-0 -o jsonpath='{.spec.containers[0].image}' 2>/dev/null || true)"
if [[ -n "$live_postgres_image" && "$live_postgres_image" != "$POSTGRES_IMAGE" ]]; then
  echo "restarting drifted test-only postgres pod (image=$live_postgres_image, expected=$POSTGRES_IMAGE)" >&2
  kubectl -n "$NAMESPACE" delete pod/postgres-0 --wait=true
fi
kubectl -n "$NAMESPACE" rollout status statefulset/postgres --timeout=180s
vector_version="$(kubectl -n "$NAMESPACE" exec postgres-0 -- \
  psql -At -U frankengate -d frankengate \
    -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'")"
if [[ "$vector_version" != "0.8.1" ]]; then
  echo "pgvector 0.8.1 is required, found: ${vector_version:-not installed}" >&2
  exit 1
fi

# This namespace and database are explicitly test-only. A retained fixture may
# contain encrypted rows or schema mutations from focused PostgreSQL tests,
# which can make governance fail closed before this oracle begins. Stop every
# old gateway connection and rebuild the disposable public schema so each run
# proves the current binary from a deterministic authority state.
kubectl -n "$NAMESPACE" delete deployment/frankengate-vk --ignore-not-found --wait=true >/dev/null
kubectl -n "$NAMESPACE" exec postgres-0 -- psql -v ON_ERROR_STOP=1 -U frankengate -d frankengate \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO frankengate; CREATE EXTENSION vector;'

kubectl -n "$NAMESPACE" delete pod -l app.kubernetes.io/name=frankengate-binary --ignore-not-found --wait=true >/dev/null
for i in $(seq 0 $((BINARY_SERVER_REPLICAS - 1))); do
  binary_pod="frankengate-binary"
  (( i == 0 )) || binary_pod="frankengate-binary-$i"
  kubectl -n "$NAMESPACE" run "$binary_pod" \
    --image="$BINARY_SERVER_IMAGE" --image-pull-policy=IfNotPresent \
    --labels='app.kubernetes.io/name=frankengate-binary,frankengate.dev/test-only=true' \
    --overrides='{"spec":{"affinity":{"podAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":[{"labelSelector":{"matchLabels":{"app.kubernetes.io/name":"postgres"}},"topologyKey":"kubernetes.io/hostname"}]}}}}' \
    --restart=Never --command -- sleep 3600
done
for i in $(seq 0 $((BINARY_SERVER_REPLICAS - 1))); do
  binary_pod="frankengate-binary"
  (( i == 0 )) || binary_pod="frankengate-binary-$i"
  kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$binary_pod" --timeout=120s
done
if [[ -z "$FRANKENGATE_IMAGE" ]]; then
  for i in $(seq 0 $((BINARY_SERVER_REPLICAS - 1))); do
    pod="frankengate-binary"
    (( i == 0 )) || pod="frankengate-binary-$i"
    kubectl -n "$NAMESPACE" cp "$BINARY" "$pod":/tmp/frankengate
    kubectl -n "$NAMESPACE" cp "$SERVER_SCRIPT" "$pod":/tmp/serve-binary.sh
    kubectl -n "$NAMESPACE" exec "$pod" -- chmod 0555 /tmp/frankengate /tmp/serve-binary.sh
    kubectl -n "$NAMESPACE" exec "$pod" -- sh -c \
      'nohup /tmp/serve-binary.sh /tmp/frankengate 18080 >/tmp/binary-server.log 2>&1 &'
  done
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
  -e "s/replicas: 3/replicas: $VK_COHERENCE_REPLICAS/" \
  "$MANIFEST" > "$WORK_DIR/gateway.yaml"
kubectl apply -f "$WORK_DIR/gateway.yaml"

# Poll the current Deployment instead of holding a rollout watch on one object
# UID. Disposable oracle runs may replace the Deployment during scale/recreate;
# kubectl rollout status then reports the misleading "object has been deleted".
wait_for_gateway_deployment() {
  local timeout_seconds="${1:-240}"
  local deadline=$(( $(date +%s) + timeout_seconds ))
  while :; do
    deployment_json="$(kubectl -n "$NAMESPACE" get deployment/frankengate-vk -o json 2>/dev/null || true)"
    if [[ -n "$deployment_json" ]]; then
      desired="$(jq -r '.spec.replicas // 0' <<<"$deployment_json")"
      available="$(jq -r '.status.availableReplicas // 0' <<<"$deployment_json")"
      generation="$(jq -r '.metadata.generation // 0' <<<"$deployment_json")"
      observed="$(jq -r '.status.observedGeneration // 0' <<<"$deployment_json")"
      if [[ "$generation" -le "$observed" && "$available" -ge "$desired" ]]; then
        return 0
      fi
    fi
    if [[ "$(date +%s)" -ge "$deadline" ]]; then
      echo "gateway deployment did not become ready within ${timeout_seconds}s" >&2
      kubectl -n "$NAMESPACE" get deployment/frankengate-vk -o wide >&2 || true
      return 1
    fi
    sleep 2
  done
}

if [[ -n "$FRANKENGATE_IMAGE" ]]; then
  # The checked-in manifest intentionally starts with the binary-transfer init
  # container. Remove that ReplicaSet completely before switching to the image
  # template so required one-pod-per-node anti-affinity cannot deadlock a
  # rolling update behind an obsolete init pod.
  kubectl -n "$NAMESPACE" scale deployment/frankengate-vk --replicas=0
  wait_for_gateway_deployment 120
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
  kubectl -n "$NAMESPACE" scale deployment/frankengate-vk --replicas="$VK_COHERENCE_REPLICAS"
fi
  wait_for_gateway_deployment "$VK_COHERENCE_READY_TIMEOUT"

list_ready_gateway_ips() {
  kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name=frankengate-vk -o json |
    jq -r '.items[] | select(.metadata.deletionTimestamp == null) | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .status.podIP' |
    sort
}

wait_for_ready_gateway_ips() {
  local expected_count="$1"
  local deadline
  deadline=$(( $(date +%s) + VK_COHERENCE_READY_TIMEOUT ))
  while :; do
    pod_ips=()
    while IFS= read -r ip; do
      [[ -n "$ip" ]] && pod_ips+=("$ip")
    done < <(list_ready_gateway_ips)
    if [[ "${#pod_ips[@]}" -eq "$expected_count" ]]; then
      return 0
    fi
    if [[ "$(date +%s)" -ge "$deadline" ]]; then
      echo "expected $expected_count non-terminating Ready gateway pod IPs, got ${#pod_ips[@]}" >&2
      return 1
    fi
    sleep 1
  done
}

wait_for_configured_ready_gateway_ips() {
  wait_for_ready_gateway_ips "$VK_COHERENCE_REPLICAS"
}

assert_release_image_spans_nodes() {
  [[ "$REQUIRE_DISTINCT_NODES" == "1" ]] || return 0
  [[ -z "$FRANKENGATE_IMAGE" ]] && return 0
  distinct_nodes="$(kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name=frankengate-vk -o json |
    jq -r '.items[] | select(.metadata.deletionTimestamp == null) | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .spec.nodeName' | sort -u | wc -l | tr -d ' ')"
  if [[ "$distinct_nodes" -ne "$VK_COHERENCE_REPLICAS" ]]; then
    echo "release-image proof expected $VK_COHERENCE_REPLICAS distinct Kubernetes nodes, got $distinct_nodes" >&2
    return 1
  fi
}

pod_ips=()
wait_for_configured_ready_gateway_ips
assert_release_image_spans_nodes

wait_for_cache() {
  local expected_state="$1" expected_id="$2" expected_marker="${3:-}"
  # The single-quoted program is evaluated by the in-cluster BusyBox shell;
  # positional arguments below intentionally provide all dynamic values.
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec frankengate-binary -- env \
    "EXPECTED_STATE=$expected_state" "EXPECTED_ID=$expected_id" \
    "EXPECTED_MARKER=$expected_marker" "POD_IPS=${pod_ips[*]}" \
    sh -c '
    deadline=$(( $(date +%s) + 8 ))
    while [ "$(date +%s)" -le "$deadline" ]; do
      all_match=1
      for ip in $POD_IPS; do
        body="$(wget -T 2 -qO- "http://$ip:8080/api/governance/virtual-keys?from_memory=true")" || {
          all_match=0
          break
        }
        case "$EXPECTED_STATE:$body" in
          present:*"$EXPECTED_ID"*"$EXPECTED_MARKER"*) ;;
          absent:*"$EXPECTED_ID"*) all_match=0; break ;;
          absent:*) ;;
          *) all_match=0; break ;;
        esac
      done
      [ "$all_match" -eq 1 ] && exit 0
      sleep 1
    done
    echo "pod caches did not converge to state=$EXPECTED_STATE id=$EXPECTED_ID" >&2
    for ip in $POD_IPS; do
      diagnostic="$(wget -T 2 -qO- "http://$ip:8080/api/governance/virtual-keys?from_memory=true" 2>&1 || true)"
      echo "cache diagnostic pod=$ip: $(printf '%s' "$diagnostic" | head -c 320)" >&2
    done
    exit 1
  '
}

# Exercise a real inference route through the released image's HTTP middleware,
# governance PreLLMHook, and pod-local VK authority cache. Cache inspection alone
# cannot detect a binary that constructs the poller but never consults it while
# serving inference requests.
call_list_models() {
  local ip="$1" secret="$2"
  # The single-quoted program runs inside the utility pod; dynamic values are
  # supplied only as positional arguments.
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c '
    ip="$1"
    secret="$2"
    printf "GET /v1/models HTTP/1.1\r\nHost: %s\r\nx-bf-vk: %s\r\nConnection: close\r\n\r\n" \
      "$ip" "$secret" | nc "$ip" 8080
  ' sh "$ip" "$secret"
}

# Exercise the ordinary body-bearing inference pipeline as well as the
# route-specific /v1/models handler. There is deliberately no upstream provider
# in this authority fixture: a live key may reach provider resolution and fail
# there, but an unknown/revoked key must be rejected by governance first.
call_chat_completion() {
  local ip="$1" secret="$2"
  local body='{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"authority probe"}]}'
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c '
    ip="$1"
    secret="$2"
    body="$3"
    length="${#body}"
    printf "POST /v1/chat/completions HTTP/1.1\r\nHost: %s\r\nx-bf-vk: %s\r\nContent-Type: application/json\r\nContent-Length: %s\r\nConnection: close\r\n\r\n%s" \
      "$ip" "$secret" "$length" "$body" | nc "$ip" 8080
  ' sh "$ip" "$secret" "$body"
}

assert_vk_status_on_all_pods() {
  local secret="$1" expected_status="$2" expected_body="${3:-}"
  local ip response
  for ip in "${pod_ips[@]}"; do
    response="$(call_list_models "$ip" "$secret" 2>/dev/null || true)"
    if ! grep -q "$expected_status" <<<"$response"; then
      echo "VK inference hotpath on pod $ip did not return $expected_status" >&2
      echo "$response" >&2
      return 1
    fi
    if [[ -n "$expected_body" ]] && ! grep -q "$expected_body" <<<"$response"; then
      echo "VK inference hotpath on pod $ip omitted expected body marker: $expected_body" >&2
      echo "$response" >&2
      return 1
    fi
  done
}

assert_chat_vk_rejected_on_all_pods() {
  local secret="$1" expected_status="$2" expected_body="${3:-}"
  local ip response
  for ip in "${pod_ips[@]}"; do
    response="$(call_chat_completion "$ip" "$secret" 2>/dev/null || true)"
    if ! grep -q "$expected_status" <<<"$response"; then
      echo "VK body-bearing inference hotpath on pod $ip did not return $expected_status" >&2
      echo "$response" >&2
      return 1
    fi
    if [[ -n "$expected_body" ]] && ! grep -q "$expected_body" <<<"$response"; then
      echo "VK body-bearing inference hotpath on pod $ip omitted expected body marker: $expected_body" >&2
      echo "$response" >&2
      return 1
    fi
  done
}

assert_chat_vk_reaches_provider_phase_on_all_pods() {
  local secret="$1"
  local ip response status_line
  for ip in "${pod_ips[@]}"; do
    response="$(call_chat_completion "$ip" "$secret" 2>/dev/null || true)"
    status_line="$(sed -n '1p' <<<"$response")"
    if [[ "$status_line" == 'HTTP/1.1 401 Unauthorized' || "$status_line" == 'HTTP/1.1 503 Service Unavailable' ]] ||
       grep -q 'virtual key authority is stale\|does not exist or has been revoked' <<<"$response"; then
      echo "fresh VK did not reach provider phase on pod $ip" >&2
      echo "$response" >&2
      return 1
    fi
  done
}

# The governance handler validates VK provider policies against configured
# providers, so seed a disposable provider and key before creating the budget VK.
# The bootstrap config may already contain the disposable provider/key. Treat
# an idempotent HTTP 409 from these seed calls as success; subsequent VK
# lifecycle assertions remain fail-closed.
seed_post_allow_conflict() {
  local url="$1" payload="$2" response
  if response="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- \
      --server-response --header 'Content-Type: application/json' \
      --post-data "$payload" "$url" 2>&1)"; then
    return 0
  fi
  if grep -q 'HTTP/1\.1 409 Conflict' <<<"$response"; then
    return 0
  fi
  echo "$response" >&2
  return 1
}
seed_post_allow_conflict "http://${pod_ips[0]}:8080/api/providers" '{"provider":"openai"}'
seed_post_allow_conflict "http://${pod_ips[0]}:8080/api/providers/openai/keys" \
  '{"name":"vk-coherence-probe-key","value":"sk-coherence-probe-key","models":["*"]}'

created="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- \
  --header 'Content-Type: application/json' \
  --post-data "{\"name\":\"horizontal-coherence-proof-${RANDOM}-${SECONDS}\",\"budgets\":[{\"max_limit\":0.001,\"reset_duration\":\"1h\"}],\"provider_configs\":[{\"provider\":\"openai\",\"weight\":1,\"allowed_models\":[\"*\"]}]}" \
  "http://${pod_ips[0]}:8080/api/governance/virtual-keys")"
vk_id="$(jq -er '.virtual_key.id' <<<"$created")"
original_secret="$(jq -er '.secret' <<<"$created")"
budget_id="$(jq -er '.virtual_key.budgets[0].id' <<<"$created")"
created_updated_at="$(jq -er '.virtual_key.updated_at' <<<"$created")"
wait_for_cache present "$vk_id" "$created_updated_at"
assert_vk_status_on_all_pods "$original_secret" '200 OK'

# Fan out concurrent reads through every ready replica. This is deliberately
# independent of the later lifecycle mutations: it detects listener/outbox
# backpressure and admission errors during a notification-shaped request
# burst without making a timing claim about provider inference.
storm_dir="$WORK_DIR/vk-storm"
mkdir -p "$storm_dir"
storm_started_ms=$(( $(date +%s%N) / 1000000 ))
for ((storm_i = 0; storm_i < VK_COHERENCE_STORM_REQUESTS; storm_i++)); do
  storm_ip="${pod_ips[$((storm_i % ${#pod_ips[@]}))]}"
  (call_list_models "$storm_ip" "$original_secret" >"$storm_dir/$storm_i" 2>&1 || true) &
done
wait
storm_finished_ms=$(( $(date +%s%N) / 1000000 ))
storm_failures=0
for storm_file in "$storm_dir"/*; do
  grep -q '200 OK' "$storm_file" || storm_failures=$((storm_failures + 1))
done
if [[ "$storm_failures" -ne 0 ]]; then
  echo "VK bootstrap/admission storm had $storm_failures/$VK_COHERENCE_STORM_REQUESTS failures" >&2
  # Preserve enough response context to diagnose status mismatches without
  # flooding CI logs when a larger storm is configured.
  shown=0
  for storm_file in "$storm_dir"/*; do
    if ! grep -q '200 OK' "$storm_file"; then
      echo "--- failed storm response $(basename "$storm_file") ---" >&2
      sed -n '1,12p' "$storm_file" >&2
      shown=$((shown + 1))
      [[ "$shown" -ge 3 ]] && break
    fi
  done
  exit 1
fi
storm_elapsed_ms=$((storm_finished_ms - storm_started_ms))

# Exercise durable admission with the disposable provider key. The provider
# has no reachable upstream in this fixture, so the request is expected to fail
# at provider execution; the reservation must still be recorded and refunded.
call_chat_completion "${pod_ips[0]}" "$original_secret" >/dev/null 2>&1 || true
reservation_row="$(kubectl -n "$NAMESPACE" exec postgres-0 -- psql -At -U frankengate -d frankengate \
  -c "select state || '|' || reserved_tokens || '|' || refunded_tokens from governance_reservations where budget_id = '$budget_id' order by created_at desc limit 1")"
if [[ "$reservation_row" != refunded\|*\|* ]]; then
  echo "durable admission did not record/refund budget $budget_id: $reservation_row" >&2
  exit 1
fi

# Exercise a real horizontal lifecycle, not only a pod restart: remove one
# replica, prove the surviving pods still accept the shared key, then add a
# fresh pod and prove it converges from the durable authority before serving.
kubectl -n "$NAMESPACE" scale deployment/frankengate-vk --replicas="$VK_COHERENCE_MIN_REPLICAS" >/dev/null
wait_for_gateway_deployment "$VK_COHERENCE_READY_TIMEOUT"
wait_for_ready_gateway_ips "$VK_COHERENCE_MIN_REPLICAS"
wait_for_cache present "$vk_id" "$created_updated_at"
assert_vk_status_on_all_pods "$original_secret" '200 OK'
kubectl -n "$NAMESPACE" scale deployment/frankengate-vk --replicas="$VK_COHERENCE_REPLICAS" >/dev/null
wait_for_gateway_deployment "$VK_COHERENCE_READY_TIMEOUT"
wait_for_configured_ready_gateway_ips
assert_release_image_spans_nodes
wait_for_cache present "$vk_id" "$created_updated_at"
assert_vk_status_on_all_pods "$original_secret" '200 OK'

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
assert_vk_status_on_all_pods "$original_secret" '401 Unauthorized' 'does not exist or has been revoked'
assert_chat_vk_rejected_on_all_pods "$original_secret" '401 Unauthorized' 'does not exist or has been revoked'
assert_vk_status_on_all_pods "$rotated_secret" '200 OK'

delete_response="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- sh -c \
  "printf 'DELETE /api/governance/virtual-keys/$vk_id HTTP/1.1\\r\\nHost: ${pod_ips[2]}\\r\\nConnection: close\\r\\n\\r\\n' | nc ${pod_ips[2]} 8080")"
grep -q '200 OK' <<<"$delete_response"
wait_for_cache absent "$vk_id"
assert_vk_status_on_all_pods "$rotated_secret" '401 Unauthorized' 'does not exist or has been revoked'
assert_chat_vk_rejected_on_all_pods "$rotated_secret" '401 Unauthorized' 'does not exist or has been revoked'

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
wait_for_gateway_deployment "$VK_COHERENCE_READY_TIMEOUT"
wait_for_configured_ready_gateway_ips
assert_release_image_spans_nodes
wait_for_cache absent "$vk_id"
assert_vk_status_on_all_pods "$rotated_secret" '401 Unauthorized' 'does not exist or has been revoked'
assert_chat_vk_rejected_on_all_pods "$rotated_secret" '401 Unauthorized' 'does not exist or has been revoked'

partition_created="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- \
  --header 'Content-Type: application/json' \
  --post-data "{\"name\":\"mcp-partition-proof-${RANDOM}-${SECONDS}\"}" \
  "http://${pod_ips[0]}:8080/api/governance/virtual-keys")"
partition_vk_id="$(jq -er '.virtual_key.id' <<<"$partition_created")"
partition_secret="$(jq -er '.secret' <<<"$partition_created")"
partition_updated_at="$(jq -er '.virtual_key.updated_at' <<<"$partition_created")"
wait_for_cache present "$partition_vk_id" "$partition_updated_at"
assert_vk_status_on_all_pods "$partition_secret" '200 OK'
assert_chat_vk_reaches_provider_phase_on_all_pods "$partition_secret"

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
readiness_partition_proven=0
while :; do
  all_stale_closed=1
  for ip in "${pod_ips[@]}"; do
    readiness="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- --server-response "http://$ip:8080/readyz" 2>&1 || true)"
    if grep -q '503 Service Unavailable' <<<"$readiness"; then
      readiness_partition_proven=1
    fi
    response="$(call_mcp_initialize "$ip" "$partition_secret" 2>/dev/null || true)"
    if ! grep -q '401 Unauthorized' <<<"$response" ||
       ! grep -q 'virtual key authority is stale' <<<"$response"; then
      all_stale_closed=0
      break
    fi
    response="$(call_list_models "$ip" "$partition_secret" 2>/dev/null || true)"
    if ! grep -q '503 Service Unavailable' <<<"$response" ||
       ! grep -q 'virtual key authority is stale' <<<"$response"; then
      all_stale_closed=0
      break
    fi
    response="$(call_chat_completion "$ip" "$partition_secret" 2>/dev/null || true)"
    if ! grep -q '503 Service Unavailable' <<<"$response" ||
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

if [[ "$readiness_partition_proven" -ne 1 ]]; then
  echo "readiness did not fail closed while the authority database was unavailable" >&2
  exit 1
fi

# Restore the authority database and prove the readiness fence reopens only
# after the pollers can complete a fresh durable snapshot.
kubectl -n "$NAMESPACE" scale statefulset/postgres --replicas=1 >/dev/null
kubectl -n "$NAMESPACE" rollout status statefulset/postgres --timeout=120s
kubectl -n "$NAMESPACE" wait --for=condition=ready pod/postgres-0 --timeout=120s
db_deadline=$(( $(date +%s) + 60 ))
while ! kubectl -n "$NAMESPACE" exec postgres-0 -- pg_isready -U frankengate -d frankengate >/dev/null 2>&1; do
  if [[ "$(date +%s)" -ge "$db_deadline" ]]; then
    echo "PostgreSQL did not become query-ready after authority restoration" >&2
    exit 1
  fi
  sleep 1
done
recovery_deadline=$(( $(date +%s) + 90 ))
while :; do
  recovered=1
  for ip in "${pod_ips[@]}"; do
    readiness="$(kubectl -n "$NAMESPACE" exec frankengate-binary -- wget -qO- --server-response "http://$ip:8080/readyz" 2>&1 || true)"
    if ! grep -q '200 OK' <<<"$readiness"; then
      recovered=0
      break
    fi
  done
  [[ "$recovered" -eq 1 ]] && break
  if [[ "$(date +%s)" -ge "$recovery_deadline" ]]; then
    echo "readiness did not recover after authority database restoration" >&2
    exit 1
  fi
  sleep 1
done

jq -n --arg vk_id "$vk_id" --argjson pods "${#pod_ips[@]}" \
  --argjson storm_requests "$VK_COHERENCE_STORM_REQUESTS" --argjson storm_failures "$storm_failures" \
  --argjson storm_elapsed_ms "$storm_elapsed_ms" \
  --arg artifact "${FRANKENGATE_IMAGE:-loose-binary}" \
  '{ok:true,pods:$pods,artifact:$artifact,virtual_key_id:$vk_id,bootstrap_storm:{requests:$storm_requests,failures:$storm_failures,elapsed_ms:$storm_elapsed_ms},create_secret_revealed_once:true,rotation_secret_revealed_once:true,inference_hotpath:{list_models:{create:"accepted-on-all-pods",old_secret_after_rotation:"rejected-on-all-pods",rotated_secret:"accepted-on-all-pods",deleted_secret:"rejected-on-all-pods"},chat_completions:{old_secret_after_rotation:"rejected-on-all-pods",deleted_secret:"rejected-on-all-pods"}},outbox:["reload","reload","delete"],restart_replay:"passed",authority_partition:"list-models-chat-and-mcp-stale-closed-on-all-pods"}'
