#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

FORBIDDEN_KEYS = %w[prompt sql tool_arguments command rows content transcript raw_trace].freeze

def add_error(errors, path, message)
  errors << {"path" => path, "message" => message}
end

def required_fields(object, fields, path, errors)
  fields.each do |field|
    add_error(errors, "#{path}.#{field}", "required field is missing") unless object.is_a?(Hash) && object.key?(field)
  end
end

def scan_forbidden(value, path, errors)
  case value
  when Hash
    value.each do |key, child|
      add_error(errors, "#{path}.#{key}", "raw content field is forbidden") if FORBIDDEN_KEYS.include?(key.to_s.downcase)
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

add_error(errors, "schema_version", "contract version mismatch") unless manifest["schema_version"] == contract["schema_version"]
scan_forbidden(manifest, "$", errors)
required_fields(manifest, contract.fetch("required_top_level_fields"), "$", errors)

cohort_uri = manifest["cohort_contract_uri"].to_s
add_error(errors, "cohort_contract_uri", "must be a sealed or partner URI") unless cohort_uri.start_with?("sealed://", "partner://")

authorization = manifest["authorization"]
required_fields(authorization, %w[consent_scope_uri source_license_or_authorization raw_content_access], "$.authorization", errors)
add_error(errors, "$.authorization.consent_scope_uri", "must be sealed or partner URI") unless authorization && authorization["consent_scope_uri"].to_s.start_with?("sealed://", "partner://")

design = manifest["design"]
required_fields(design, %w[holdouts retrieval_arms artifact_arms skill_arms environment_splits paired_factorial same_task_set_across_arms], "$.design", errors)
holdouts = design && design["holdouts"]
contract.fetch("required_holdouts").each do |holdout|
  add_error(errors, "$.design.holdouts.#{holdout}", "holdout must be enabled") unless holdouts.is_a?(Hash) && holdouts[holdout] == true
end

{
  "retrieval_arms" => "required_retrieval_arms",
  "artifact_arms" => "required_artifact_arms",
  "skill_arms" => "required_skill_arms",
  "environment_splits" => "required_environment_splits"
}.each do |field, contract_field|
  values = design && design[field]
  required = contract.fetch(contract_field)
  add_error(errors, "$.design.#{field}", "must be an array containing every required value") unless values.is_a?(Array) && required.all? { |value| values.include?(value) }
end
add_error(errors, "$.design.paired_factorial", "must be true") unless design && design["paired_factorial"] == true
add_error(errors, "$.design.same_task_set_across_arms", "must be true") unless design && design["same_task_set_across_arms"] == true

%w[required_case_classes required_metrics].each do |field|
  values = manifest[field]
  required = contract.fetch(field)
  add_error(errors, "$.#{field}", "must contain every required value") unless values.is_a?(Array) && required.all? { |value| values.include?(value) }
end

gates = manifest["promotion_gates"]
required_fields(gates, contract.fetch("required_promotion_gate_fields"), "$.promotion_gates", errors)
if gates.is_a?(Hash)
  add_error(errors, "$.promotion_gates.minimum_replay_pass_rate", "must be in [0,1]") unless gates["minimum_replay_pass_rate"].is_a?(Numeric) && gates["minimum_replay_pass_rate"].between?(0, 1)
  add_error(errors, "$.promotion_gates.maximum_regression_rate", "must be in [0,1]") unless gates["maximum_regression_rate"].is_a?(Numeric) && gates["maximum_regression_rate"].between?(0, 1)
  add_error(errors, "$.promotion_gates.minimum_reviewer_agreement", "must be in [0,1]") unless gates["minimum_reviewer_agreement"].is_a?(Numeric) && gates["minimum_reviewer_agreement"].between?(0, 1)
  add_error(errors, "$.promotion_gates.maximum_unsafe_accepts", "must be zero") unless gates["maximum_unsafe_accepts"] == 0
  %w[minimum_targets minimum_hard_negatives minimum_nil_or_unclear].each do |field|
    add_error(errors, "$.promotion_gates.#{field}", "must be a positive integer") unless gates[field].is_a?(Integer) && gates[field].positive?
  end
end

run_contract = manifest["run_contract"]
required_fields(run_contract, contract.fetch("required_run_contract_fields"), "$.run_contract", errors)
contract.fetch("required_run_contract_fields").each do |field|
  add_error(errors, "$.run_contract.#{field}", "must be true") unless run_contract.is_a?(Hash) && run_contract[field] == true
end
add_error(errors, "$.run_contract.skill_generated_from_evaluation_task", "must be false") unless run_contract.is_a?(Hash) && run_contract["skill_generated_from_evaluation_task"] == false

output_policy = manifest["output_policy"]
required_fields(output_policy, contract.fetch("required_output_policy_fields"), "$.output_policy", errors)
contract.fetch("required_output_policy_fields").each do |field|
  add_error(errors, "$.output_policy.#{field}", "must be true") unless output_policy.is_a?(Hash) && output_policy[field] == true
end

partner_packet = manifest["partner_packet"]
required_fields(partner_packet, %w[manifest_uri receipt_uri publication_review_required raw_trace_export], "$.partner_packet", errors)
%w[manifest_uri receipt_uri].each do |field|
  add_error(errors, "$.partner_packet.#{field}", "must be sealed or partner URI") unless partner_packet && partner_packet[field].to_s.start_with?("sealed://", "partner://")
end
add_error(errors, "$.partner_packet.publication_review_required", "must be true") unless partner_packet && partner_packet["publication_review_required"] == true
add_error(errors, "$.partner_packet.raw_trace_export", "must be false") unless partner_packet && partner_packet["raw_trace_export"] == false

result = {
  "schema_version" => "frankengate-enterprise-trace-learning-pilot-conformance-v1",
  "contract_sha256" => Digest::SHA256.file(contract_path).hexdigest,
  "manifest_sha256" => Digest::SHA256.file(manifest_path).hexdigest,
  "raw_content_committed" => false,
  "structural_valid" => errors.empty?,
  "promotion_ready" => false,
  "promotion_note" => "Plan conformance does not prove that an authorized cohort, labels, replay outcomes, or user outcomes exist.",
  "errors" => errors
}
File.write(output_path, JSON.pretty_generate(result) + "\n")
puts JSON.generate(result)
exit(1) unless errors.empty?
