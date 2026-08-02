#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

path = ARGV.fetch(0)
output = ARGV.fetch(1)
token = "[REDACTED_ENV_VALUE]"
lines = 0
raw_valid = 0
raw_session_ids = 0
salvaged_valid = 0
salvaged_session_ids = 0
redaction_tokens = 0
salvaged_required = Hash.new(0)

File.foreach(path) do |line|
  lines += 1
  redaction_tokens += line.scan(token).length

  begin
    value = JSON.parse(line)
    raw_valid += 1
    raw_session_ids += 1 if value.is_a?(Hash) && value.key?("session_id")
  rescue JSON::ParserError
    # Expected for the integrity probe; do not emit raw content.
  end

  begin
    value = JSON.parse(line.gsub(token, ""))
    salvaged_valid += 1
    if value.is_a?(Hash)
      salvaged_session_ids += 1 if value.key?("session_id")
      %w[session_id model project messages stats].each do |key|
        salvaged_required[key] += 1 if value.key?(key)
      end
    end
  rescue JSON::ParserError
    # Token removal is a diagnostic salvage attempt, not a repaired corpus.
  end
end

receipt = {
  "schema_version" => "frankengate-dataclaw-export-integrity-v1",
  "source" => {
    "dataset_id" => "MRiabov/dataclaw-march-26",
    "dataset_revision" => "3fcd9d92ca9eaf2d5b8377a7c505626880249171",
    "license_claimed" => "MIT",
    "path_sha256" => Digest::SHA256.file(path).hexdigest,
    "bytes" => File.size(path),
    "raw_content_committed" => false
  },
  "observed" => {
    "physical_lines" => lines,
    "raw_valid_json_lines" => raw_valid,
    "raw_valid_session_ids" => raw_session_ids,
    "redaction_token_occurrences" => redaction_tokens,
    "token_removal_salvaged_json_lines" => salvaged_valid,
    "token_removal_salvaged_session_ids" => salvaged_session_ids,
    "token_removal_salvaged_required_fields" => salvaged_required
  },
  "claim_boundary" => {
    "dataset_inventory_verified" => true,
    "trace_mining_executed" => false,
    "raw_json_usable_as_released" => false,
    "salvaged_rows_usable_as_ground_truth" => false,
    "reason" => "The scrubber replaces content inside JSON numbers, timestamps, and tool/code strings. Token removal restores syntax for only a minority of rows and cannot recover redacted values."
  },
  "decision" => "Inventory-only until the publisher supplies a parseable export or a loss-aware structured format. Do not train embeddings, mine aliases, infer skills, or benchmark cross-user retrieval from this file."
}

File.write(output, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
