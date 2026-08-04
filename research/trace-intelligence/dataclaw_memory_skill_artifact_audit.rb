#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

ARTIFACT_PATTERNS = {
  "memory_file" => /(?:^|[\s\/\\])memory\.md\b/i,
  "claude_config" => /(?:^|[\s\/\\])CLAUDE\.md\b|\.claude(?:[\/\\]|$)/i,
  "codex_config" => /(?:^|[\s\/\\])AGENTS\.md\b|\.codex(?:[\/\\]|$)/i,
  "skill_file" => /(?:^|[\s\/\\])SKILL\.md\b|(?:^|[\s\/\\])skills?(?:[\/\\]|\s|$)/i
}.freeze

def content_text(value)
  case value
  when String
    value
  when Array
    value.map { |item| content_text(item) }.join(" ")
  when Hash
    value.values.map { |item| content_text(item) }.join(" ")
  else
    ""
  end
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
sessions = 0
category_session_counts = Hash.new(0)
category_mention_counts = Hash.new(0)
context_counts = Hash.new(0)
read_calls = 0
write_calls = 0
write_sessions = {}
read_sessions = {}
artifact_path_hashes = Hash.new { |hash, key| hash[key] = {} }

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  sessions += 1
  session_id = row.dig("metadata", "session_id").to_s
  session_categories = {}
  session_reads = false
  session_writes = false

  prompt_text = row["prompt"].to_s
  prompt_categories = ARTIFACT_PATTERNS.select { |_category, pattern| prompt_text.match?(pattern) }.keys
  prompt_categories.each do |category|
    category_mention_counts[category] += 1
    session_categories[category] = true
    context_counts["prompt_#{category}"] += 1
  end

  Array(row["messages"]).each do |message|
    role = message["role"].to_s
    content = content_text(message["content"])
    ARTIFACT_PATTERNS.each do |category, pattern|
      next unless content.match?(pattern)

      category_mention_counts[category] += 1
      session_categories[category] = true
      context_counts["#{role}_#{category}"] += 1
    end

    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      name = function["name"].to_s.downcase
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      argument_text = content_text(arguments)
      matched_categories = ARTIFACT_PATTERNS.select { |_category, pattern| argument_text.match?(pattern) }.keys
      matched_categories.each do |category|
        category_mention_counts[category] += 1
        session_categories[category] = true
        context_counts["tool_argument_#{category}"] += 1
        # Store only a digest of a referenced path/name, never the path itself.
        artifact_path_hashes[category][Digest::SHA256.hexdigest(argument_text)] = true
      end

      artifact_reference = matched_categories.any?
      read_like = %w[read_file search_code find_files].include?(name) || (name == "run_command" && artifact_reference)
      write_like = %w[write_file edit_file].include?(name) || (name == "run_command" && argument_text.match?(/(?:>|tee|cat\s+>>|printf\s+)/i) && artifact_reference)
      if read_like && artifact_reference
        read_calls += 1
        session_reads = true
      end
      if write_like && artifact_reference
        write_calls += 1
        session_writes = true
      end
    rescue JSON::ParserError
      # Do not let a malformed argument hide the rest of the session.
    end
  end

  session_categories.each_key { |category| category_session_counts[category] += 1 }
  read_sessions[session_id] = true if session_reads
  write_sessions[session_id] = true if session_writes
end

receipt = {
  "schema_version" => "frankengate-dataclaw-memory-skill-artifact-audit-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "cohort" => { "sessions" => sessions },
  "artifact_mentions" => {
    "sessions_by_category" => category_session_counts,
    "mention_events_by_category" => category_mention_counts,
    "context_counts" => context_counts,
    "unique_argument_context_hashes_by_category" => artifact_path_hashes.transform_values(&:length)
  },
  "lifecycle_proxies" => {
    "artifact_reference_read_calls" => read_calls,
    "artifact_reference_write_calls" => write_calls,
    "sessions_with_artifact_reads" => read_sessions.length,
    "sessions_with_artifact_writes" => write_sessions.length
  },
  "claim_boundary" => {
    "durable_artifact_mentions_measured" => true,
    "memory_content_quality_established" => false,
    "skill_correctness_established" => false,
    "artifact_lifecycle_semantics_established" => false,
    "user_outcome_established" => false,
    "promotion_authorized" => false,
    "reason" => "Markers and tool names identify candidate artifact interactions only. This projection lacks typed tool results and independent semantic outcomes."
  },
  "decision" => "Use artifact references to route review and import candidates. Require explicit read/write provenance, bitemporal scope, citations, contradiction handling, deletion, and replay before treating memory or skill files as durable knowledge."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
