#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

FORBIDDEN_KEYS = %w[prompt sql tool_arguments command rows content transcript raw_trace].freeze
URI_PREFIXES = %w[sealed:// partner://].freeze

def error(errors, path, message)
  errors << {"path" => path, "message" => message}
end

def required_hash_fields(value, fields, path, errors)
  unless value.is_a?(Hash)
    error(errors, path, "expected an object")
    return
  end
  fields.each { |field| error(errors, "#{path}.#{field}", "required field is missing") unless value.key?(field) }
end

def scan_forbidden(value, path, errors)
  case value
  when Hash
    value.each do |key, child|
      error(errors, "#{path}.#{key}", "raw content field is forbidden") if FORBIDDEN_KEYS.include?(key.to_s.downcase)
      scan_forbidden(child, "#{path}.#{key}", errors)
    end
  when Array
    value.each_with_index { |child, index| scan_forbidden(child, "#{path}[#{index}]", errors) }
  end
end

contract_path, manifest_path, output_path = ARGV
raise ArgumentError, "usage: validator CONTRACT MANIFEST OUTPUT" unless output_path

contract = JSON.parse(File.read(contract_path))
manifest = JSON.parse(File.read(manifest_path))
errors = []

error(errors, "schema_version", "contract version mismatch") unless manifest["schema_version"] == contract["schema_version"]
scan_forbidden(manifest, "$", errors)

required_hash_fields(manifest["authorization"], %w[consent_scope_uri raw_content_access raw_content_committed], "$.authorization", errors)
required_hash_fields(manifest["promotion_gates"], %w[minimum_targets minimum_hard_negatives minimum_nil_or_unclear minimum_replay_pass_rate maximum_unauthorized_edges maximum_unsafe_actions maximum_stale_accept_rate maximum_regression_rate must_beat_A0_on_sealed_holdout must_beat_no_skill_and_placebo], "$.promotion_gates", errors)
required_hash_fields(manifest["run_contract"], %w[same_model_across_arms same_harness_across_arms same_candidate_pool_across_arms candidate_pool_frozen_before_labels same_authority_epoch independent_evaluator proposer_excluded_from_evaluator changed_system_replay_required raw_content_external_only], "$.run_contract", errors)
required_hash_fields(manifest["storage_contract"], %w[canonical_evidence_authority projection_store graph_database_required edge_evidence_required validity_interval_required policy_epoch_required], "$.storage_contract", errors)
required_hash_fields(manifest["publication_policy"], %w[receipts_content_free deletion_receipt_required publication_review_required promotion_ready], "$.publication_policy", errors)

%w[protocol_uri cohort_contract_uri].each do |field|
  error(errors, "$.#{field}", "must be sealed:// or partner://") unless URI_PREFIXES.any? { |prefix| manifest[field].to_s.start_with?(prefix) }
end
error(errors, "$.authorization.raw_content_committed", "must be false") unless manifest.dig("authorization", "raw_content_committed") == false
error(errors, "$.publication_policy.promotion_ready", "must be false before outcomes") unless manifest.dig("publication_policy", "promotion_ready") == false

{
  "representation_arms" => "representation_arms",
  "required_holdouts" => "required_holdouts",
  "required_case_classes" => "required_case_classes",
  "required_mutation_classes" => "required_mutation_classes",
  "required_object_types" => "required_object_types",
  "required_edge_statuses" => "required_edge_statuses",
  "required_action_states" => "required_action_states",
  "required_metrics" => "required_metrics"
}.each do |manifest_field, contract_field|
  values = manifest[manifest_field]
  required = contract.fetch(contract_field)
  error(errors, "$.#{manifest_field}", "must contain every required value") unless values.is_a?(Array) && required.all? { |item| values.include?(item) }
end

gates = manifest["promotion_gates"]
if gates.is_a?(Hash)
  %w[minimum_targets minimum_hard_negatives minimum_nil_or_unclear].each do |field|
    error(errors, "$.promotion_gates.#{field}", "must be a positive integer") unless gates[field].is_a?(Integer) && gates[field].positive?
  end
  %w[minimum_replay_pass_rate maximum_stale_accept_rate maximum_regression_rate].each do |field|
    error(errors, "$.promotion_gates.#{field}", "must be in [0,1]") unless gates[field].is_a?(Numeric) && gates[field].between?(0, 1)
  end
  %w[maximum_unauthorized_edges maximum_unsafe_actions].each do |field|
    error(errors, "$.promotion_gates.#{field}", "must be zero") unless gates[field] == 0
  end
  %w[must_beat_A0_on_sealed_holdout must_beat_no_skill_and_placebo].each do |field|
    error(errors, "$.promotion_gates.#{field}", "must be true") unless gates[field] == true
  end
end

run_contract = manifest["run_contract"]
if run_contract.is_a?(Hash)
  %w[same_model_across_arms same_harness_across_arms same_candidate_pool_across_arms candidate_pool_frozen_before_labels same_authority_epoch independent_evaluator proposer_excluded_from_evaluator changed_system_replay_required raw_content_external_only].each do |field|
    error(errors, "$.run_contract.#{field}", "must be true") unless run_contract[field] == true
  end
end

storage = manifest["storage_contract"]
if storage.is_a?(Hash)
  error(errors, "$.storage_contract.canonical_evidence_authority", "must be trajectory_dag") unless storage["canonical_evidence_authority"] == "trajectory_dag"
  error(errors, "$.storage_contract.projection_store", "must be postgresql_jsonb_fts_pgvector") unless storage["projection_store"] == "postgresql_jsonb_fts_pgvector"
  %w[edge_evidence_required validity_interval_required policy_epoch_required].each do |field|
    error(errors, "$.storage_contract.#{field}", "must be true") unless storage[field] == true
  end
end

result = {
  "schema_version" => "frankengate-ontology-action-trace-preflight-conformance-v1",
  "contract_sha256" => Digest::SHA256.file(contract_path).hexdigest,
  "manifest_sha256" => Digest::SHA256.file(manifest_path).hexdigest,
  "raw_content_committed" => false,
  "structural_valid" => errors.empty?,
  "promotion_ready" => false,
  "promotion_note" => "Preflight conformance does not prove ontology quality, replay outcomes, or enterprise utility.",
  "errors" => errors
}
File.write(output_path, JSON.pretty_generate(result) + "\n")
puts JSON.generate(result)
exit(1) unless errors.empty?
