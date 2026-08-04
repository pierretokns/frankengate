#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"
require "time"

HEX64 = /\A[0-9a-f]{64}\z/i
FORBIDDEN_CONTENT_KEYS = %w[prompt sql tool_arguments command rows content transcript output].freeze

def error(errors, path, message)
  errors << { "path" => path, "message" => message }
end

def require_fields(hash, fields, path, errors)
  fields.each { |field| error(errors, "#{path}.#{field}", "required field is missing") unless hash.key?(field) }
end

def hash_value(value, path, errors)
  error(errors, path, "expected SHA-256 hex digest") unless value.is_a?(String) && value.match?(HEX64)
end

def receipt(value, path, errors)
  unless value.is_a?(Hash)
    error(errors, path, "expected an object")
    return
  end
  require_fields(value, %w[uri sha256], path, errors)
  error(errors, "#{path}.uri", "raw local paths are not allowed") if value["uri"].to_s.start_with?("/", "file://")
  hash_value(value["sha256"], "#{path}.sha256", errors)
end

def scan_forbidden(value, path, errors)
  case value
  when Hash
    value.each do |key, child|
      error(errors, "#{path}.#{key}", "raw content field is forbidden") if FORBIDDEN_CONTENT_KEYS.include?(key.to_s.downcase)
      scan_forbidden(child, "#{path}.#{key}", errors)
    end
  when Array
    value.each_with_index { |child, index| scan_forbidden(child, "#{path}[#{index}]", errors) }
  end
end

contract_path, manifest_path, output_path = ARGV
abort "usage: trajectory_retrieval_supervision_validator.rb CONTRACT MANIFEST OUTPUT" unless output_path

contract = JSON.parse(File.read(contract_path))
manifest = JSON.parse(File.read(manifest_path))
errors = []
blockers = []

error(errors, "schema_version", "contract version mismatch") unless manifest["schema_version"] == contract["schema_version"]
scan_forbidden(manifest, "$", errors)
require_fields(manifest, contract.fetch("required_study_fields"), "$", errors)
error(errors, "candidate_pool_frozen_before_labels", "must be true") unless manifest["candidate_pool_frozen_before_labels"] == true
error(errors, "exposure_log_complete", "must be true") unless manifest["exposure_log_complete"] == true

holdouts = manifest["holdouts"]
unless holdouts.is_a?(Hash)
  error(errors, "holdouts", "expected object")
else
  contract.fetch("required_holdouts").each do |field|
    error(errors, "holdouts.#{field}", "required holdout is not enabled") unless holdouts[field] == true
  end
end

arms = Array(manifest["arms"])
contract.fetch("required_arms").each do |arm|
  error(errors, "arms", "missing required arm #{arm}") unless arms.include?(arm)
end

episodes = manifest["episodes"]
unless episodes.is_a?(Array) && !episodes.empty?
  error(errors, "episodes", "at least one episode is required")
  episodes = []
end

counts = Hash.new(0)
episodes.each_with_index do |episode, index|
  path = "episodes[#{index}]"
  unless episode.is_a?(Hash)
    error(errors, path, "expected object")
    next
  end
  require_fields(episode, contract.fetch("required_episode_fields"), path, errors)
  case_class = episode["case_class"]
  error(errors, "#{path}.case_class", "unknown case class") unless contract.fetch("case_classes").include?(case_class)
  counts[case_class] += 1 if case_class
  error(errors, "#{path}.split", "unknown split") unless contract.fetch("split_values").include?(episode["split"])
  %w[principal_hash team_hash project_hash system_hash source_environment_hash changed_environment_hash candidate_pool_hash].each do |field|
    hash_value(episode[field], "#{path}.#{field}", errors)
  end
  %w[source_authority_epoch changed_authority_epoch].each do |field|
    error(errors, "#{path}.#{field}", "must be a positive integer") unless episode[field].is_a?(Integer) && episode[field].positive?
  end
  begin
    Time.iso8601(episode["effective_at"].to_s)
  rescue ArgumentError
    error(errors, "#{path}.effective_at", "must be ISO-8601")
  end
  %w[exposure_receipt trajectory_receipt outcome_receipt deletion_receipt].each do |field|
    receipt(episode[field], "#{path}.#{field}", errors)
  end
  exposure = episode["exposure_receipt"]
  if exposure.is_a?(Hash)
    error(errors, "#{path}.exposure_receipt.candidate_set_complete", "must be true") unless exposure["candidate_set_complete"] == true
    error(errors, "#{path}.exposure_receipt.before_selection", "must be true") unless exposure["before_selection"] == true
  end
  trajectory = episode["trajectory_receipt"]
  if trajectory.is_a?(Hash)
    error(errors, "#{path}.trajectory_receipt.tool_result_edges_present", "must be true") unless trajectory["tool_result_edges_present"] == true
    error(errors, "#{path}.trajectory_receipt.complete", "must be true") unless trajectory["complete"] == true
  end
  outcome = episode["outcome_receipt"]
  error(errors, "#{path}.outcome_receipt.independent_verifier", "must be true") unless outcome.is_a?(Hash) && outcome["independent_verifier"] == true

  labels = episode["labels"]
  unless labels.is_a?(Array) && labels.length == contract.dig("minimum_promotion_counts", "annotators_per_episode")
    error(errors, "#{path}.labels", "must contain exactly two independent labels")
    labels = []
  end
  labels.each_with_index do |label, label_index|
    label_path = "#{path}.labels[#{label_index}]"
    require_fields(label, %w[annotator_hash label concept_id_hash evidence_span_hashes temporal_validity], label_path, errors)
    hash_value(label["annotator_hash"], "#{label_path}.annotator_hash", errors)
    hash_value(label["concept_id_hash"], "#{label_path}.concept_id_hash", errors)
    error(errors, "#{label_path}.label", "unknown label") unless contract.fetch("label_values").include?(label["label"])
    error(errors, "#{label_path}.evidence_span_hashes", "must be non-empty array") unless label["evidence_span_hashes"].is_a?(Array) && !label["evidence_span_hashes"].empty?
    temporal = label["temporal_validity"]
    error(errors, "#{label_path}.temporal_validity", "valid_from is required") unless temporal.is_a?(Hash) && temporal["valid_from"].is_a?(String)
    if label["label"] == "not_exposed"
      error(errors, "#{label_path}.label", "not_exposed is missing data, not a negative label")
    end
  end
  if labels.length == 2 && labels.map { |label| label["label"] }.uniq.length > 1
    adjudication = episode["adjudication"]
    unless adjudication.is_a?(Hash) && adjudication["required"] == true && contract.fetch("label_values").include?(adjudication["label"])
      error(errors, "#{path}.adjudication", "third-party adjudication is required for disagreement")
    end
  end
  retention = episode["retention"]
  unless retention.is_a?(Hash) && retention["raw_content_external_only"] == true
    error(errors, "#{path}.retention", "must declare raw content external-only")
  else
    hash_value(retention["deletion_policy_hash"], "#{path}.retention.deletion_policy_hash", errors)
  end
end

minimums = contract.fetch("minimum_promotion_counts")
blockers << "target count #{counts["target"]} < #{minimums["target"]}" if counts["target"] < minimums["target"]
blockers << "hard_negative count #{counts["hard_negative"]} < #{minimums["hard_negative"]}" if counts["hard_negative"] < minimums["hard_negative"]
blockers << "nil_or_unclear count #{counts["nil"].to_i + counts["unclear"].to_i} < #{minimums["nil_or_unclear"]}" if counts["nil"].to_i + counts["unclear"].to_i < minimums["nil_or_unclear"]

result = {
  "schema_version" => "frankengate-trajectory-retrieval-supervision-conformance-v1",
  "contract_sha256" => Digest::SHA256.file(contract_path).hexdigest,
  "manifest_sha256" => Digest::SHA256.file(manifest_path).hexdigest,
  "raw_content_committed" => false,
  "structural_valid" => errors.empty?,
  "promotion_ready" => errors.empty? && blockers.empty?,
  "episode_counts" => counts,
  "promotion_blockers" => blockers,
  "errors" => errors
}
File.write(output_path, JSON.pretty_generate(result) + "\n")
puts JSON.generate(result)
exit(1) unless errors.empty?
