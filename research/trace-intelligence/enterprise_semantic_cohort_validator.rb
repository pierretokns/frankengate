#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"
require "time"

HEX64 = /\A[0-9a-f]{64}\z/i
FORBIDDEN_CONTENT_KEYS = %w[prompt sql tool_arguments command rows content transcript].freeze

def add_error(errors, path, message)
  errors << { "path" => path, "message" => message }
end

def required_fields(hash, fields, path, errors)
  fields.each do |field|
    add_error(errors, "#{path}.#{field}", "required field is missing") unless hash.key?(field)
  end
end

def validate_hash(value, path, errors)
  add_error(errors, path, "expected a SHA-256 hex digest") unless value.is_a?(String) && value.match?(HEX64)
end

def validate_receipt(receipt, path, errors)
  unless receipt.is_a?(Hash)
    add_error(errors, path, "expected an object")
    return
  end
  required_fields(receipt, %w[uri sha256], path, errors)
  add_error(errors, "#{path}.uri", "raw local paths are not allowed") if receipt["uri"].to_s.start_with?("/", "file://")
  validate_hash(receipt["sha256"], "#{path}.sha256", errors)
end

def scan_forbidden_keys(value, path, errors)
  case value
  when Hash
    value.each do |key, child|
      add_error(errors, "#{path}.#{key}", "raw content field is forbidden in a content-free manifest") if FORBIDDEN_CONTENT_KEYS.include?(key.to_s.downcase)
      scan_forbidden_keys(child, "#{path}.#{key}", errors)
    end
  when Array
    value.each_with_index { |child, index| scan_forbidden_keys(child, "#{path}[#{index}]", errors) }
  end
end

contract_path = ARGV.fetch(0)
manifest_path = ARGV.fetch(1)
output_path = ARGV.fetch(2)
contract = JSON.parse(File.read(contract_path))
manifest = JSON.parse(File.read(manifest_path))
errors = []
promotion_blockers = []

add_error(errors, "schema_version", "contract version mismatch") unless manifest["schema_version"] == contract["schema_version"]
scan_forbidden_keys(manifest, "$", errors)
required_fields(manifest, contract.fetch("required_study_fields"), "$", errors)
add_error(errors, "candidate_pool_frozen_before_labels", "must be true") unless manifest["candidate_pool_frozen_before_labels"] == true

holdouts = manifest["holdouts"]
unless holdouts.is_a?(Hash)
  add_error(errors, "holdouts", "expected an object")
else
  contract.fetch("required_holdouts").each do |name|
    add_error(errors, "holdouts.#{name}", "required holdout is not enabled") unless holdouts[name] == true
  end
end

arms = Array(manifest["arms"])
contract.fetch("required_arms").each do |arm|
  add_error(errors, "arms", "missing required arm #{arm}") unless arms.include?(arm)
end

tasks = manifest["tasks"]
unless tasks.is_a?(Array) && !tasks.empty?
  add_error(errors, "tasks", "at least one task is required for structural conformance")
  tasks = []
end

counts = Hash.new(0)
tasks.each_with_index do |task, index|
  path = "tasks[#{index}]"
  unless task.is_a?(Hash)
    add_error(errors, path, "expected an object")
    next
  end
  required_fields(task, contract.fetch("required_task_fields"), path, errors)
  case_class = task["case_class"]
  add_error(errors, "#{path}.case_class", "unknown case class") unless contract.fetch("case_classes").include?(case_class)
  counts[case_class] += 1 if case_class
  %w[principal_hash team_hash project_hash source_system_hash source_environment_hash changed_environment_hash candidate_pool_hash].each do |field|
    validate_hash(task[field], "#{path}.#{field}", errors)
  end
  %w[source_authority_epoch changed_authority_epoch].each do |field|
    add_error(errors, "#{path}.#{field}", "must be a positive integer") unless task[field].is_a?(Integer) && task[field].positive?
  end
  begin
    Time.iso8601(task["effective_at"].to_s)
  rescue ArgumentError
    add_error(errors, "#{path}.effective_at", "must be an ISO-8601 timestamp")
  end
  add_error(errors, "#{path}.mutation_class", "unknown mutation class") unless contract.fetch("mutation_classes").include?(task["mutation_class"])
  validate_receipt(task["trajectory_receipt"], "#{path}.trajectory_receipt", errors)
  validate_receipt(task["outcome_receipt"], "#{path}.outcome_receipt", errors)
  validate_receipt(task["deletion_receipt"], "#{path}.deletion_receipt", errors)
  retention = task["retention"]
  unless retention.is_a?(Hash) && retention["raw_content_external_only"] == true && retention["deletion_policy_hash"].is_a?(String)
    add_error(errors, "#{path}.retention", "must declare external-only raw content and a deletion-policy hash")
  else
    validate_hash(retention["deletion_policy_hash"], "#{path}.retention.deletion_policy_hash", errors)
  end
  trajectory = task["trajectory_receipt"]
  if trajectory.is_a?(Hash)
    add_error(errors, "#{path}.trajectory_receipt.tool_result_edges_present", "must be true") unless trajectory["tool_result_edges_present"] == true
    add_error(errors, "#{path}.trajectory_receipt.complete", "must be true") unless trajectory["complete"] == true
  end
  outcome = task["outcome_receipt"]
  add_error(errors, "#{path}.outcome_receipt.independent_verifier", "must be true") unless outcome.is_a?(Hash) && outcome["independent_verifier"] == true
  labels = task["labels"]
  unless labels.is_a?(Array) && labels.length == contract.dig("minimum_promotion_counts", "annotators_per_task")
    add_error(errors, "#{path}.labels", "must contain exactly two independent labels")
    labels = []
  end
  labels.each_with_index do |label, label_index|
    label_path = "#{path}.labels[#{label_index}]"
    required_fields(label, %w[annotator_hash label concept_id_hash evidence_span_hashes temporal_validity executable], label_path, errors)
    validate_hash(label["annotator_hash"], "#{label_path}.annotator_hash", errors)
    validate_hash(label["concept_id_hash"], "#{label_path}.concept_id_hash", errors)
    add_error(errors, "#{label_path}.label", "unknown label") unless contract.fetch("label_values").include?(label["label"])
    add_error(errors, "#{label_path}.evidence_span_hashes", "must be a non-empty array") unless label["evidence_span_hashes"].is_a?(Array) && !label["evidence_span_hashes"].empty?
    temporal = label["temporal_validity"]
    add_error(errors, "#{label_path}.temporal_validity", "valid_from is required") unless temporal.is_a?(Hash) && temporal["valid_from"].is_a?(String)
  end
  if labels.length == 2
    disagree = labels.map { |label| label["label"] }.uniq.length > 1
    adjudication = task["adjudication"]
    if disagree
      add_error(errors, "#{path}.adjudication", "third-SME adjudication is required for disagreement") unless adjudication.is_a?(Hash) && adjudication["required"] == true && contract.fetch("label_values").include?(adjudication["label"])
    elsif adjudication.is_a?(Hash) && adjudication["required"] == true
      add_error(errors, "#{path}.adjudication", "adjudication cannot be required when labels agree")
    end
  end
end

minimums = contract.fetch("minimum_promotion_counts")
promotion_blockers << "target count #{counts["target"]} < #{minimums["target"]}" if counts["target"] < minimums["target"]
promotion_blockers << "hard_negative count #{counts["hard_negative"]} < #{minimums["hard_negative"]}" if counts["hard_negative"] < minimums["hard_negative"]
promotion_blockers << "nil_or_unclear count #{counts["nil"].to_i + counts["unclear"].to_i} < #{minimums["nil_or_unclear"]}" if counts["nil"].to_i + counts["unclear"].to_i < minimums["nil_or_unclear"]

mutation_counts = Hash.new(0)
tasks.each { |task| mutation_counts[task["mutation_class"]] += 1 if task.is_a?(Hash) && task["mutation_class"] }
contract.fetch("minimum_mutation_counts", {}).each do |mutation_class, minimum|
  actual = mutation_counts[mutation_class].to_i
  promotion_blockers << "#{mutation_class} count #{actual} < #{minimum}" if actual < minimum
end

result = {
  "schema_version" => "frankengate-enterprise-semantic-cohort-conformance-v1",
  "contract_sha256" => Digest::SHA256.file(contract_path).hexdigest,
  "manifest_sha256" => Digest::SHA256.file(manifest_path).hexdigest,
  "raw_content_committed" => false,
  "structural_valid" => errors.empty?,
  "promotion_ready" => errors.empty? && promotion_blockers.empty?,
  "task_counts" => counts,
  "mutation_counts" => mutation_counts,
  "promotion_blockers" => promotion_blockers,
  "errors" => errors
}
File.write(output_path, JSON.pretty_generate(result) + "\n")
puts JSON.generate(result)
exit(1) unless errors.empty?
