#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: run-replacement-oracle.sh BASELINE_CHART CURRENT_CHART IMAGE_REPOSITORY BASELINE_INDEX_DIGEST CURRENT_INDEX_DIGEST

Proves that a public FrankenGate Helm chart can install, upgrade, roll back,
and re-upgrade a three-replica gateway without losing a virtual key.

Required tools: crane, helm, jq, kubectl

Environment:
  NAMESPACE       Test namespace (default: frankengate-helm-replacement)
  RELEASE_NAME    Helm release name (default: frankengate-replacement)
  KEEP_FIXTURE    Keep namespace and node labels when set to 1 (default: 0)
  HELM_TIMEOUT    Helm operation timeout (default: 10m)
EOF
}

if [[ $# -ne 5 ]]; then
  usage >&2
  exit 2
fi

BASELINE_CHART=$1
CURRENT_CHART=$2
IMAGE_REPOSITORY=${3%/}
BASELINE_INDEX_DIGEST=$4
CURRENT_INDEX_DIGEST=$5
NAMESPACE=${NAMESPACE:-frankengate-helm-replacement}
RELEASE_NAME=${RELEASE_NAME:-frankengate-replacement}
KEEP_FIXTURE=${KEEP_FIXTURE:-0}
HELM_TIMEOUT=${HELM_TIMEOUT:-10m}
FULLNAME=frankengate-replacement
NODE_LABEL_KEY=frankengate.dev/helm-replacement-node
WORK_DIR=$(mktemp -d)
VALUES_FILE=$WORK_DIR/values.yaml
LABELED_NODES_FILE=$WORK_DIR/labeled-nodes
PREVIOUS_UIDS_FILE=$WORK_DIR/previous-uids

cleanup() {
  local status=$?
  trap - EXIT
  if [[ $KEEP_FIXTURE != 1 ]]; then
    kubectl delete namespace "$NAMESPACE" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    if [[ -s $LABELED_NODES_FILE ]]; then
      while IFS= read -r node; do
        kubectl label node "$node" "$NODE_LABEL_KEY-" >/dev/null 2>&1 || true
      done < "$LABELED_NODES_FILE"
    fi
  fi
  rm -rf "$WORK_DIR"
  exit "$status"
}
trap cleanup EXIT

for command in crane helm jq kubectl; do
  command -v "$command" >/dev/null || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

for chart in "$BASELINE_CHART" "$CURRENT_CHART"; do
  if [[ ! -e $chart ]]; then
    echo "chart does not exist: $chart" >&2
    exit 1
  fi
done
for digest in "$BASELINE_INDEX_DIGEST" "$CURRENT_INDEX_DIGEST"; do
  if [[ ! $digest =~ ^sha256:[a-f0-9]{64}$ ]]; then
    echo "invalid image digest: $digest" >&2
    exit 2
  fi
done
if [[ $BASELINE_INDEX_DIGEST == "$CURRENT_INDEX_DIGEST" ]]; then
  echo "baseline and current digests must differ" >&2
  exit 2
fi

mapfile -t eligible_nodes < <(
  kubectl get nodes -o json | jq -r '
    [.items[]
      | select(.spec.unschedulable != true)
      | select(any(.status.conditions[]?; .type == "Ready" and .status == "True"))
      | .metadata.name]
    | sort[]'
)
if [[ ${#eligible_nodes[@]} -lt 3 ]]; then
  echo "replacement oracle requires at least three Ready schedulable nodes" >&2
  exit 1
fi
printf '%s\n' "${eligible_nodes[@]:0:3}" > "$LABELED_NODES_FILE"
while IFS= read -r node; do
  kubectl label node "$node" "$NODE_LABEL_KEY=true" --overwrite >/dev/null
done < "$LABELED_NODES_FILE"

kubectl create namespace "$NAMESPACE" >/dev/null

cat > "$VALUES_FILE" <<EOF
fullnameOverride: $FULLNAME
replicaCount: 3
image:
  repository: $IMAGE_REPOSITORY
  pullPolicy: Always
  tag: ""
  digest: $BASELINE_INDEX_DIGEST
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: "1"
    memory: 512Mi
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1
nodeSelector:
  $NODE_LABEL_KEY: "true"
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app.kubernetes.io/name: bifrost
            app.kubernetes.io/instance: $RELEASE_NAME
            app.kubernetes.io/component: server
        topologyKey: kubernetes.io/hostname
storage:
  mode: postgres
  persistence:
    enabled: false
  configStore:
    enabled: true
    type: postgres
  logsStore:
    enabled: true
    type: postgres
postgresql:
  enabled: true
  auth:
    username: bifrost
    password: replacement-oracle-only
    database: bifrost
  primary:
    persistence:
      enabled: true
      size: 1Gi
bifrost:
  client:
    enforceAuthOnInference: true
    enableLogging: false
  plugins:
    governance:
      enabled: true
      version: 1
      config:
        is_vk_mandatory: true
  governance:
    virtualKeys: []
    authConfig:
      isEnabled: false
      disableAuthOnInference: false
EOF

selector="app.kubernetes.io/name=bifrost,app.kubernetes.io/instance=$RELEASE_NAME,app.kubernetes.io/component=server"
db_selector="app.kubernetes.io/instance=$RELEASE_NAME,app.kubernetes.io/component=database"

platform_digest() {
  local index_digest=$1 digest
  digest=$(crane digest --platform linux/amd64 "$IMAGE_REPOSITORY@$index_digest")
  if [[ ! $digest =~ ^sha256:[a-f0-9]{64}$ ]]; then
    echo "crane returned invalid linux/amd64 digest for $index_digest: $digest" >&2
    return 1
  fi
  printf '%s\n' "$digest"
}

wait_for_no_forbidden_uids() {
  local deadline now pod_json
  [[ ! -s $PREVIOUS_UIDS_FILE ]] && return 0
  deadline=$(( $(date +%s) + 300 ))
  while :; do
    pod_json=$(kubectl -n "$NAMESPACE" get pods -l "$selector" -o json)
    if ! jq -e --rawfile old "$PREVIOUS_UIDS_FILE" '
      ($old | split("\n") | map(select(length > 0))) as $uids
      | all(.items[]; (.metadata.uid as $uid | ($uids | index($uid))) == null)
    ' <<<"$pod_json" >/dev/null; then
      now=$(date +%s)
      if (( now >= deadline )); then
        echo "old gateway pod UIDs still exist after rollout" >&2
        return 1
      fi
      sleep 2
      continue
    fi
    return 0
  done
}

assert_rollout() {
  local expected_index=$1 expected_platform deploy_json pod_json rs_json
  local expected_image="$IMAGE_REPOSITORY@$expected_index"
  expected_platform=$(platform_digest "$expected_index")

  kubectl -n "$NAMESPACE" rollout status "deployment/$FULLNAME" --timeout=5m
  wait_for_no_forbidden_uids
  deploy_json=$(kubectl -n "$NAMESPACE" get "deployment/$FULLNAME" -o json)
  jq -e '
    .metadata.generation == .status.observedGeneration
    and .spec.replicas == 3
    and .status.replicas == 3
    and .status.updatedReplicas == 3
    and .status.readyReplicas == 3
    and .status.availableReplicas == 3
    and (.status.unavailableReplicas // 0) == 0
  ' <<<"$deploy_json" >/dev/null || {
    echo "deployment did not complete a full three-replica rollout" >&2
    jq '.spec.replicas, .status' <<<"$deploy_json" >&2
    return 1
  }

  pod_json=$(kubectl -n "$NAMESPACE" get pods -l "$selector" -o json)
  jq -e --arg image "$expected_image" --arg index "$expected_index" --arg platform "$expected_platform" '
    (.items | length) == 3
    and ([.items[].spec.nodeName] | unique | length) == 3
    and all(.items[];
      .metadata.deletionTimestamp == null
      and any(.status.conditions[]?; .type == "Ready" and .status == "True")
      and ([.spec.containers[] | select(.name == "bifrost") | .image] == [$image])
      and (([.status.containerStatuses[] | select(.name == "bifrost") | .imageID]) as $image_ids
        | ($image_ids | length) == 1
        # containerd commonly records the pulled OCI index digest in imageID;
        # some runtimes record the resolved platform child digest instead.
        and (($image_ids[0] | endswith("@" + $index))
          or ($image_ids[0] | endswith("@" + $platform)))))
  ' <<<"$pod_json" >/dev/null || {
    echo "gateway pods do not satisfy exact count, node, readiness, or digest assertions" >&2
    jq '.items[] | {name:.metadata.name,uid:.metadata.uid,node:.spec.nodeName,images:.spec.containers,statuses:.status.containerStatuses}' <<<"$pod_json" >&2
    return 1
  }

  rs_json=$(kubectl -n "$NAMESPACE" get replicasets -l "$selector" -o json)
  jq -e --arg image "$expected_image" '
    all(.items[];
      ([.spec.template.spec.containers[] | select(.name == "bifrost") | .image] == [$image])
      or (((.spec.replicas // 0) == 0) and ((.status.replicas // 0) == 0)))
  ' <<<"$rs_json" >/dev/null || {
    echo "an old gateway ReplicaSet still owns pods" >&2
    jq '.items[] | {name:.metadata.name,specReplicas:.spec.replicas,statusReplicas:.status.replicas,images:.spec.template.spec.containers}' <<<"$rs_json" >&2
    return 1
  }
}

capture_uids() {
  kubectl -n "$NAMESPACE" get pods -l "$selector" -o json |
    jq -r '.items[].metadata.uid' | sort > "$PREVIOUS_UIDS_FILE"
}

database_pod() {
  kubectl -n "$NAMESPACE" get pods -l "$db_selector" -o json |
    jq -r '.items[] | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .metadata.name' |
    head -1
}

create_virtual_key() {
  local db_pod response
  db_pod=$(database_pod)
  if [[ -z $db_pod ]]; then
    echo "chart-managed PostgreSQL pod is not Ready" >&2
    return 1
  fi
  response=$(kubectl -n "$NAMESPACE" exec "$db_pod" -- wget -qO- \
    --header 'Content-Type: application/json' \
    --post-data "{\"name\":\"helm-retained-${RANDOM}-${SECONDS}\"}" \
    "http://$FULLNAME:8080/api/governance/virtual-keys")
  VK_ID=$(jq -er '.virtual_key.id' <<<"$response")
  VK_SECRET=$(jq -er '.secret' <<<"$response")
  printf '::add-mask::%s\n' "$VK_SECRET"
}

call_models() {
  local db_pod=$1 ip=$2 secret=$3
  # The program is evaluated by the in-container shell. Dynamic values are
  # supplied exclusively as positional arguments below.
  # shellcheck disable=SC2016
  kubectl -n "$NAMESPACE" exec "$db_pod" -- sh -c '
    ip=$1
    secret=$2
    printf "GET /v1/models HTTP/1.1\r\nHost: %s\r\nx-bf-vk: %s\r\nConnection: close\r\n\r\n" "$ip" "$secret" |
      nc "$ip" 8080
  ' sh "$ip" "$secret"
}

assert_retained_vk() {
  local db_pod deadline all_valid pod ip memory response pod_count
  db_pod=$(database_pod)
  deadline=$(( $(date +%s) + 30 ))
  while :; do
    all_valid=1
    pod_count=0
    while IFS=$'\t' read -r pod ip; do
      [[ -n $pod && -n $ip ]] || continue
      pod_count=$((pod_count + 1))
      memory=$(kubectl -n "$NAMESPACE" exec "$db_pod" -- \
        wget -qO- "http://$ip:8080/api/governance/virtual-keys?from_memory=true" 2>/dev/null || true)
      if ! jq -e --arg id "$VK_ID" 'any(.virtual_keys[]?; .id == $id)' <<<"$memory" >/dev/null 2>&1; then
        all_valid=0
        break
      fi
      response=$(call_models "$db_pod" "$ip" "$VK_SECRET" 2>/dev/null || true)
      if [[ "$(sed -n '1p' <<<"$response")" != 'HTTP/1.1 200 OK' ]]; then
        echo "retained VK was not accepted by pod $pod" >&2
        all_valid=0
        break
      fi
    done < <(kubectl -n "$NAMESPACE" get pods -l "$selector" -o json |
      jq -r '.items[] | [.metadata.name,.status.podIP] | @tsv')
    if [[ $all_valid -eq 1 && $pod_count -eq 3 ]]; then
      return 0
    fi
    if (( $(date +%s) >= deadline )); then
      echo "retained VK did not converge on all gateway hotpaths" >&2
      return 1
    fi
    sleep 1
  done
}

assert_history() {
  local revision=$1 history
  history=$(helm -n "$NAMESPACE" history "$RELEASE_NAME" -o json)
  jq -e --arg revision "$revision" '
    (map(select(.status == "deployed")) | length) == 1
    and (map(select(.status == "deployed"))[0].revision | tostring) == $revision
  ' <<<"$history" >/dev/null || {
    echo "Helm revision $revision is not the sole deployed revision" >&2
    jq '.' <<<"$history" >&2
    return 1
  }
}

helm install "$RELEASE_NAME" "$BASELINE_CHART" \
  --namespace "$NAMESPACE" --values "$VALUES_FILE" \
  --wait --timeout "$HELM_TIMEOUT"
assert_history 1
assert_rollout "$BASELINE_INDEX_DIGEST"
create_virtual_key
assert_retained_vk
capture_uids

helm upgrade "$RELEASE_NAME" "$CURRENT_CHART" \
  --namespace "$NAMESPACE" --reuse-values \
  --set-string "image.digest=$CURRENT_INDEX_DIGEST" \
  --wait --timeout "$HELM_TIMEOUT" --cleanup-on-fail
assert_history 2
assert_rollout "$CURRENT_INDEX_DIGEST"
assert_retained_vk
capture_uids

helm rollback "$RELEASE_NAME" 1 \
  --namespace "$NAMESPACE" --wait --timeout "$HELM_TIMEOUT" --cleanup-on-fail
assert_history 3
assert_rollout "$BASELINE_INDEX_DIGEST"
assert_retained_vk
capture_uids

helm upgrade "$RELEASE_NAME" "$CURRENT_CHART" \
  --namespace "$NAMESPACE" --reuse-values \
  --set-string "image.digest=$CURRENT_INDEX_DIGEST" \
  --wait --timeout "$HELM_TIMEOUT" --cleanup-on-fail
assert_history 4
assert_rollout "$CURRENT_INDEX_DIGEST"
assert_retained_vk

jq -n \
  --arg baseline_chart "$BASELINE_CHART" \
  --arg current_chart "$CURRENT_CHART" \
  --arg image "$IMAGE_REPOSITORY" \
  --arg baseline "$BASELINE_INDEX_DIGEST" \
  --arg current "$CURRENT_INDEX_DIGEST" \
  --arg vk_id "$VK_ID" \
  '{ok:true,baseline_chart:$baseline_chart,current_chart:$current_chart,image:$image,baseline_index_digest:$baseline,current_index_digest:$current,replicas:3,nodes:3,helm_revisions:["install","upgrade","rollback","re-upgrade"],retained_virtual_key_id:$vk_id}'
