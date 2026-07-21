#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCOPE="$ROOT/provenance/aws-observation-scope.json"
PRICING="$ROOT/docs/data/pricing/latest.json"
DOC="$ROOT/docs/architecture/aws-observation-scope-and-client-matrix.md"
TS_LOCK="$ROOT/tests/integrations/typescript/package-lock.json"
PY_LOCK="$ROOT/tests/integrations/python/uv.lock"
DOCKERFILE="$ROOT/transports/Dockerfile.release"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "missing required file: $path" >&2
    exit 1
  fi
}

require_jq() {
  local expr="$1"
  local file="$2"
  local message="$3"
  if ! jq -e "$expr" "$file" >/dev/null; then
    echo "verification failed: $message" >&2
    exit 1
  fi
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

require_file "$SCOPE"
require_file "$PRICING"
require_file "$DOC"
require_file "$TS_LOCK"
require_file "$PY_LOCK"
require_file "$DOCKERFILE"

require_jq '.schema_version == 1' "$SCOPE" "schema_version must be 1"
require_jq '.bead_id == "bg-pg-config-mantle-program-gzg9.10"' "$SCOPE" "bead id mismatch"
require_jq '.scope_policy.aws_calls_in_this_bead == false and .scope_policy.credentials_in_this_bead == false and .scope_policy.paid_inference_in_this_bead == false' "$SCOPE" "this bead must not authorize live calls, credentials, or paid inference"
require_jq '.scope_policy.future_observations_require_explicit_consent == true and .scope_policy.future_observations_require_preconnect_verification == true' "$SCOPE" "future observations must require consent and preconnect verification"
require_jq '.scope_policy.naturally_occurring_safe_errors_only == true and .scope_policy.unsafe_failure_provocation_allowed == false' "$SCOPE" "unsafe failure provocation must be forbidden"
require_jq '.authorization.regions.allowed == ["us-east-1"]' "$SCOPE" "region scope must be pinned"
require_jq '.authorization.retention.raw_wire_observations_max_days == 7 and .authorization.retention.redacted_facts_max_days == 90' "$SCOPE" "retention windows must be pinned"

expected_lanes='["bifrost-mantle-anthropic","bifrost-mantle-openai","bifrost-native-bedrock","direct-mantle-anthropic","direct-mantle-openai","direct-native-bedrock"]'
jq -e --argjson expected "$expected_lanes" '([.lanes[].id] | sort) == ($expected | sort)' "$SCOPE" >/dev/null || {
  echo "verification failed: lane matrix mismatch" >&2
  exit 1
}

require_jq '([.lanes[] | select(.mode == "direct_client")] | length) == 3' "$SCOPE" "must define three direct-client lanes"
require_jq '([.lanes[] | select(.mode == "through_bifrost")] | length) == 3' "$SCOPE" "must define three through-Bifrost lanes"
require_jq 'all(.lanes[] | select(.surface == "mantle_anthropic"); .preconnect_enabled == false and (.blocked_reason | length > 0))' "$SCOPE" "Mantle Anthropic lanes must be blocked before connect until pricing/maxima are pinned"
require_jq '. as $root | all($root.lanes[] | select(.preconnect_enabled == true); . as $lane | any($root.models[]; .id == $lane.model_scope_id and .pricing.required == true and (.max_input_tokens | type == "number") and (.max_output_tokens | type == "number")))' "$SCOPE" "every enabled lane must have required pricing and numeric maxima"

for field in consent_id consent_timestamp_utc aws_account_id_or_alias region endpoint_host endpoint_path_template model_id project_or_workspace_id retention_policy_id operator allowed_facts client_id client_version lane_id billable_call_ceiling token_ceiling dollar_ceiling account_budget_evidence pricing_source pricing_retrieved_at pricing_sha256; do
  jq -e --arg field "$field" '.required_run_record_fields | index($field)' "$SCOPE" >/dev/null || {
    echo "verification failed: missing required run field $field" >&2
    exit 1
  }
done

for exclusion in github_models localstack unsafe_failure_provocation aws_cli_mantle_without_pinned_code; do
  jq -e --arg exclusion "$exclusion" '.exclusions[] | select(.id == $exclusion)' "$SCOPE" >/dev/null || {
    echo "verification failed: missing exclusion $exclusion" >&2
    exit 1
  }
done

require_jq '.ceilings.max_attempts_total == 6 and .ceilings.max_attempts_per_lane == 1' "$SCOPE" "attempt ceilings mismatch"
require_jq '.ceilings.max_billable_calls_total == 4 and .ceilings.max_billable_calls_per_lane == 1' "$SCOPE" "billable-call ceilings mismatch"
require_jq '.ceilings.max_input_tokens_per_call == 512 and .ceilings.max_output_tokens_per_call == 64 and .ceilings.max_total_tokens_all_calls == 4096' "$SCOPE" "token ceilings mismatch"
require_jq '.ceilings.max_estimated_dollars_total == 0.25 and .ceilings.max_estimated_dollars_per_lane == 0.05 and .ceilings.required_independently_verified_account_budget_usd_lte == 0.1' "$SCOPE" "dollar or account-budget ceilings mismatch"
require_jq '.ceilings.max_redirects_per_call == 0 and .ceilings.max_client_retries_per_call == 0 and .ceilings.max_gateway_retries_per_call == 0 and .ceilings.max_provider_fallbacks_per_call == 0' "$SCOPE" "redirect/retry/fallback ceilings mismatch"

expected_pricing_hash="$(jq -r '.pricing.locked_sha256' "$SCOPE")"
actual_pricing_hash="$(sha256_file "$PRICING")"
if [[ "$actual_pricing_hash" != "$expected_pricing_hash" ]]; then
  echo "verification failed: pricing hash mismatch: expected $expected_pricing_hash got $actual_pricing_hash" >&2
  exit 1
fi

jq -e --slurpfile scope "$SCOPE" '.source == $scope[0].pricing.source and .retrieved_at == $scope[0].pricing.retrieved_at' "$PRICING" >/dev/null || {
  echo "verification failed: pricing source or retrieved_at mismatch" >&2
  exit 1
}

jq -e --slurpfile scope "$SCOPE" '
  . as $pricing |
  all($scope[0].models[] | select(.pricing.required == true);
    . as $m |
    ($pricing.models[$m.pricing.key] // null) as $p |
    $p != null and
    $p.provider == $m.pricing.provider and
    $p.max_input_tokens == $m.max_input_tokens and
    $p.max_output_tokens == $m.max_output_tokens and
    $p.input_cost_per_token == $m.pricing.input_cost_per_token and
    $p.output_cost_per_token == $m.pricing.output_cost_per_token
  )
' "$PRICING" >/dev/null || {
  echo "verification failed: enabled model pricing rows do not match local catalog" >&2
  exit 1
}

docker_hash_expected="$(jq -r '.containers.bifrost_release.source_dockerfile_sha256' "$SCOPE")"
docker_hash_actual="$(sha256_file "$DOCKERFILE")"
if [[ "$docker_hash_actual" != "$docker_hash_expected" ]]; then
  echo "verification failed: Dockerfile.release hash mismatch: expected $docker_hash_expected got $docker_hash_actual" >&2
  exit 1
fi

while IFS= read -r image_ref; do
  grep -F "$image_ref" "$DOCKERFILE" >/dev/null || {
    echo "verification failed: missing digest-pinned base image $image_ref" >&2
    exit 1
  }
done < <(jq -r '.containers.bifrost_release.base_images[]' "$SCOPE")

openai_ts_version="$(jq -r '.packages["node_modules/openai"].version' "$TS_LOCK")"
anthropic_ts_version="$(jq -r '.packages["node_modules/@anthropic-ai/sdk"].version' "$TS_LOCK")"
aws_bedrock_runtime_ts_version="$(jq -r '.packages["node_modules/@aws-sdk/client-bedrock-runtime"].version' "$TS_LOCK")"

jq -e --arg v "$openai_ts_version" '.client_pins.sdk_artifacts[] | select(.id == "openai-typescript" and .version == $v)' "$SCOPE" >/dev/null || {
  echo "verification failed: OpenAI TypeScript SDK pin mismatch" >&2
  exit 1
}
jq -e --arg v "$anthropic_ts_version" '.client_pins.sdk_artifacts[] | select(.id == "anthropic-typescript" and .version == $v)' "$SCOPE" >/dev/null || {
  echo "verification failed: Anthropic TypeScript SDK pin mismatch" >&2
  exit 1
}
jq -e --arg v "$aws_bedrock_runtime_ts_version" '.client_pins.sdk_artifacts[] | select(.id == "aws-sdk-js-bedrock-runtime" and .version == $v and .mantle_allowed == false)' "$SCOPE" >/dev/null || {
  echo "verification failed: AWS SDK JS Bedrock Runtime pin mismatch" >&2
  exit 1
}

for package_pin in 'openai 2.40.0 openai-python' 'anthropic 0.105.2 anthropic-python' 'boto3 1.43.19 boto3-python' 'botocore 1.43.19 boto3-python'; do
  set -- $package_pin
  pkg="$1"
  version="$2"
  manifest_id="$3"
  if ! awk -v pkg="$pkg" -v version="$version" '
    $0 == "name = \"" pkg "\"" { found = 1; next }
    found && $0 == "version = \"" version "\"" { ok = 1; exit }
    found && /^\[\[package\]\]/ { found = 0 }
    END { exit ok ? 0 : 1 }
  ' "$PY_LOCK"; then
    echo "verification failed: Python lock missing $pkg==$version" >&2
    exit 1
  fi
  if [[ "$pkg" != "botocore" ]]; then
    jq -e --arg id "$manifest_id" --arg version "$version" '.client_pins.sdk_artifacts[] | select(.id == $id and .version == $version)' "$SCOPE" >/dev/null || {
      echo "verification failed: manifest missing Python pin $manifest_id==$version" >&2
      exit 1
    }
  fi
done

require_jq '.client_pins.coding_cli_tiers[] | select(.id == "codex-cli" and .tiers.minimum == "0.144.6" and .tiers.production == "0.144.6" and .tiers.advisory == "0.144.6")' "$SCOPE" "Codex CLI tiers must be exact"
require_jq '.client_pins.coding_cli_tiers[] | select(.id == "claude-code" and .tiers.minimum == "2.1.214" and .tiers.production == "2.1.214" and .tiers.advisory == "2.1.214")' "$SCOPE" "Claude Code tiers must be exact"

if [[ "${VERIFY_LOCAL_CLI:-0}" == "1" ]]; then
  codex_expected="$(jq -r '.client_pins.coding_cli_tiers[] | select(.id == "codex-cli") | .local_verification.observed' "$SCOPE")"
  claude_expected="$(jq -r '.client_pins.coding_cli_tiers[] | select(.id == "claude-code") | .local_verification.observed' "$SCOPE")"
  codex_actual="$(CODEX_DISABLE_TELEMETRY=1 codex --version)"
  claude_actual="$(CLAUDE_CODE_DISABLE_TELEMETRY=1 claude --version)"
  [[ "$codex_actual" == "$codex_expected" ]] || {
    echo "verification failed: Codex CLI version mismatch: expected '$codex_expected' got '$codex_actual'" >&2
    exit 1
  }
  [[ "$claude_actual" == "$claude_expected" ]] || {
    echo "verification failed: Claude Code version mismatch: expected '$claude_expected' got '$claude_actual'" >&2
    exit 1
  }
fi

grep -F "provenance/aws-observation-scope.json" "$DOC" >/dev/null || {
  echo "verification failed: doc must reference manifest path" >&2
  exit 1
}
grep -F "scripts/verify-aws-observation-scope.sh" "$DOC" >/dev/null || {
  echo "verification failed: doc must reference verifier" >&2
  exit 1
}

echo "AWS observation scope verification passed (local files only; no AWS calls)."
