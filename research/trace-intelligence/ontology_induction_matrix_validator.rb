#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"
require "time"

HEX64 = /\A[0-9a-f]{64}\z/i
FORBIDDEN = %w[prompt sql tool_arguments command rows content transcript raw_text output document_text].freeze

def error(errors, path, message)
  errors << { "path" => path, "message" => message }
end

def required(hash, fields, path, errors)
  fields.each { |field| error(errors, "#{path}.#{field}", "required field is missing") unless hash.key?(field) }
end

def digest?(value)
  value.is_a?(String) && value.match?(HEX64)
end

def check_digest(value, path, errors)
  error(errors, path, "expected a SHA-256 hex digest") unless digest?(value)
end

def scan_forbidden(value, path, errors)
  case value
  when Hash
    value.each do |key, child|
      error(errors, "#{path}.#{key}", "raw content field is forbidden") if FORBIDDEN.include?(key.to_s.downcase)
      scan_forbidden(child, "#{path}.#{key}", errors)
    end
  when Array
    value.each_with_index { |child, index| scan_forbidden(child, "#{path}[#{index}]", errors) }
  end
end

contract_path = ARGV.fetch(0)
manifest_path = ARGV.fetch(1)
output_path = ARGV.fetch(2)
contract = JSON.parse(File.read(contract_path))
manifest = JSON.parse(File.read(manifest_path))
errors = []
blockers = []

error(errors, "schema_version", "contract version mismatch") unless manifest["schema_version"] == contract["schema_version"]
scan_forbidden(manifest, "$", errors)
required(manifest, contract.fetch("required_study_fields"), "$", errors)
error(errors, "candidate_pool_frozen_before_labels", "must be true") unless manifest["candidate_pool_frozen_before_labels"] == true

holdouts = manifest["holdouts"]
unless holdouts.is_a?(Hash)
  error(errors, "holdouts", "expected an object")
else
  contract.fetch("required_holdouts").each { |name| error(errors, "holdouts.#{name}", "required holdout is not enabled") unless holdouts[name] == true }
end

arms = Array(manifest["arms"])
contract.fetch("required_arms").each { |arm| error(errors, "arms", "missing required arm #{arm}") unless arms.include?(arm) }
error(errors, "arms", "duplicate arms are not allowed") unless arms.uniq.length == arms.length

receipts = manifest["corpus_receipts"]
unless receipts.is_a?(Array) && !receipts.empty?
  error(errors, "corpus_receipts", "at least one receipt is required")
  receipts = []
end
receipts.each_with_index do |receipt, index|
  path = "corpus_receipts[#{index}]"
  required(receipt, %w[name uri sha256], path, errors)
  check_digest(receipt["sha256"], "#{path}.sha256", errors)
  error(errors, "#{path}.uri", "raw local paths are not allowed") if receipt["uri"].to_s.start_with?("/", "file://")
end

metrics = Array(manifest["metrics"])
contract.fetch("required_metrics").each { |metric| error(errors, "metrics", "missing required metric #{metric}") unless metrics.include?(metric) }

tasks = manifest["cases"]
unless tasks.is_a?(Array) && !tasks.empty?
  error(errors, "cases", "at least one case is required for structural conformance")
  tasks = []
end
counts = Hash.new(0)
tasks.each_with_index do |item, index|
  path = "cases[#{index}]"
  unless item.is_a?(Hash)
    error(errors, path, "expected an object")
    next
  end
  required(item, contract.fetch("required_case_fields"), path, errors)
  case_class = item["case_class"]
  error(errors, "#{path}.case_class", "unknown case class") unless contract.fetch("case_classes").include?(case_class)
  counts[case_class] += 1 if case_class
  %w[principal_hash team_hash project_hash source_system_hash source_environment_hash changed_environment_hash candidate_pool_hash].each { |field| check_digest(item[field], "#{path}.#{field}", errors) }
  %w[source_receipt label_receipt replay_receipt].each do |field|
    receipt = item[field]
    required(receipt, %w[uri sha256], "#{path}.#{field}", errors) if receipt.is_a?(Hash)
    check_digest(receipt["sha256"], "#{path}.#{field}.sha256", errors) if receipt.is_a?(Hash)
  end
  begin
    Time.iso8601(item["effective_at"].to_s)
  rescue ArgumentError
    error(errors, "#{path}.effective_at", "must be an ISO-8601 timestamp")
  end
  labels = item["labels"]
  unless labels.is_a?(Array) && labels.length == contract.dig("minimum_promotion_counts", "annotators_per_case")
    error(errors, "#{path}.labels", "must contain exactly two independent labels")
    labels = []
  end
  labels.each_with_index do |label, label_index|
    label_path = "#{path}.labels[#{label_index}]"
    required(label, %w[annotator_hash decision evidence_hashes], label_path, errors)
    check_digest(label["annotator_hash"], "#{label_path}.annotator_hash", errors)
    error(errors, "#{label_path}.decision", "unknown label") unless contract.fetch("label_values").include?(label["decision"])
    error(errors, "#{label_path}.evidence_hashes", "must be non-empty") unless label["evidence_hashes"].is_a?(Array) && !label["evidence_hashes"].empty?
    label["evidence_hashes"].to_a.each_with_index { |digest, evidence_index| check_digest(digest, "#{label_path}.evidence_hashes[#{evidence_index}]", errors) }
  end
  retention = item["retention"]
  unless retention.is_a?(Hash) && retention["raw_content_external_only"] == true
    error(errors, "#{path}.retention", "must declare external-only raw content")
  end
end

minimums = contract.fetch("minimum_promotion_counts")
blockers << "entity_or_alias target count #{counts["entity"] + counts["alias"]} < #{minimums["entity_or_alias_targets"]}"
blockers << "hard_negative count #{counts["hard_negative"]} < #{minimums["hard_negatives"]}"
blockers << "nil_or_unclear count #{counts["nil"] + counts["unclear"]} < #{minimums["nil_or_unclear"]}"
blockers << "changed-system replay count #{manifest.fetch("changed_system_replays", 0)} < #{minimums["changed_system_replays"]}"

result = {
  "schema_version" => "frankengate-ontology-induction-matrix-conformance-v1",
  "contract_sha256" => Digest::SHA256.file(contract_path).hexdigest,
  "manifest_sha256" => Digest::SHA256.file(manifest_path).hexdigest,
  "raw_content_committed" => false,
  "structural_valid" => errors.empty?,
  "promotion_ready" => errors.empty? && blockers.empty?,
  "case_counts" => counts,
  "promotion_blockers" => blockers,
  "errors" => errors
}
File.write(output_path, JSON.pretty_generate(result) + "\n")
puts JSON.generate(result)
exit(1) unless errors.empty?
