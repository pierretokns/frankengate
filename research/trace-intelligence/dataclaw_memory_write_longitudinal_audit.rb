#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

ARTIFACT_MARKER = /(?:memory\.md|CLAUDE\.md|AGENTS\.md|SKILL\.md|\.claude|\.codex|skills?)/i
STOPWORDS = %w[a an and are as at be by can do for from get give has have how i if in is it me my of on or please so that the this to what when where with you your].freeze

def tokens(text)
  text.to_s.downcase.scan(/[a-z][a-z0-9_]{2,}/).reject { |word| STOPWORDS.include?(word) }.uniq
end

def jaccard(left, right)
  union = (left | right).length
  return 0.0 if union.zero?

  (left & right).length.to_f / union
end

def command_features(row)
  features = []
  write = false
  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      name = function["name"].to_s.downcase
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      argument_text = arguments.is_a?(Hash) ? JSON.generate(arguments) : arguments.to_s
      artifact_reference = argument_text.match?(ARTIFACT_MARKER)
      write_like = %w[write_file edit_file].include?(name) || (name == "run_command" && argument_text.match?(/(?:>|tee|cat\s+>>|printf\s+)/i))
      write ||= artifact_reference && write_like
      command = arguments.is_a?(Hash) ? (arguments["command"] || arguments["cmd"]) : nil
      next unless command.is_a?(String) && !command.empty?

      normalized = command.downcase
                         .gsub(/[0-9a-f]{8,}/, "<id>")
                         .gsub(/(?:\/|\\)[^\s]+/, "<path>")
                         .gsub(/(['"])(?:\\.|(?!\1).)*\1/, "<str>")
                         .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
                         .split.first(6).join(" ")
      features << {
        "digest" => Digest::SHA256.hexdigest(command),
        "shape" => normalized
      }
    rescue JSON::ParserError
      # Keep write detection conservative when an argument payload is malformed.
    end
  end

  user_messages = Array(row["messages"]).select { |message| message["role"] == "user" }.map { |message| tokens(message["content"]) }
  rephrases = user_messages.each_cons(2).count do |left, right|
    score = jaccard(left, right)
    score >= 0.35 && score < 0.98 && [left.length, right.length].min >= 3
  end
  { "features" => features.uniq, "artifact_write" => write, "rephrase_pairs" => rephrases }
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
rows_by_project = Hash.new { |hash, key| hash[key] = [] }
File.foreach(input_path) do |line|
  row = JSON.parse(line)
  metadata = row.fetch("metadata", {})
  rows_by_project[metadata["project"].to_s] << {
    "start_time" => metadata["start_time"].to_s,
    "audit" => command_features(row)
  }
end

observations = []
rows_by_project.each_value do |rows|
  ordered = rows.sort_by { |row| row["start_time"] }
  prior_shapes = {}
  prior_digests = {}
  prior_writes = 0
  ordered.each_with_index do |row, index|
    features = row["audit"]["features"]
    next if index.zero?

    shape_hits = features.count { |feature| prior_shapes.key?(feature["shape"]) }
    digest_hits = features.count { |feature| prior_digests.key?(feature["digest"]) }
    observations << {
      "features" => features.length,
      "shape_hits" => shape_hits,
      "digest_hits" => digest_hits,
      "prior_write" => prior_writes.positive?,
      "direct_after_write" => ordered[index - 1]["audit"]["artifact_write"],
      "rephrase_pairs" => row["audit"]["rephrase_pairs"]
    }

    features.each do |feature|
      prior_shapes[feature["shape"]] = true
      prior_digests[feature["digest"]] = true
    end
    prior_writes += 1 if row["audit"]["artifact_write"]
  end
end

def summarize(rows)
  feature_events = rows.sum { |row| row["features"] }
  shape_hits = rows.sum { |row| row["shape_hits"] }
  digest_hits = rows.sum { |row| row["digest_hits"] }
  {
    "sessions" => rows.length,
    "feature_events" => feature_events,
    "shape_hit_events" => shape_hits,
    "digest_hit_events" => digest_hits,
    "shape_hit_rate" => feature_events.zero? ? nil : shape_hits.to_f / feature_events,
    "digest_hit_rate" => feature_events.zero? ? nil : digest_hits.to_f / feature_events,
    "sessions_with_shape_hit" => rows.count { |row| row["shape_hits"].positive? },
    "sessions_with_digest_hit" => rows.count { |row| row["digest_hits"].positive? },
    "sessions_with_rephrase" => rows.count { |row| row["rephrase_pairs"].positive? }
  }
end

prior_write = observations.select { |row| row["prior_write"] }
no_prior_write = observations.reject { |row| row["prior_write"] }
direct_after_write = observations.select { |row| row["direct_after_write"] }

receipt = {
  "schema_version" => "frankengate-dataclaw-memory-write-longitudinal-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "split" => {
    "method" => "per-project chronology; each session compared with all earlier sessions",
    "projects" => rows_by_project.length,
    "observed_sessions_after_first" => observations.length,
    "sessions_with_prior_artifact_write" => prior_write.length,
    "sessions_without_prior_artifact_write" => no_prior_write.length,
    "sessions_directly_after_artifact_write" => direct_after_write.length
  },
  "groups" => {
    "prior_artifact_write" => summarize(prior_write),
    "no_prior_artifact_write" => summarize(no_prior_write),
    "directly_after_artifact_write" => summarize(direct_after_write)
  },
  "claim_boundary" => {
    "observational_association_measured" => true,
    "memory_or_skill_causal_effect_established" => false,
    "artifact_correctness_established" => false,
    "user_outcome_established" => false,
    "promotion_authorized" => false,
    "reason" => "Artifact writes are inferred from path markers and write-like tool names. Projects, task mix, and user behavior confound all longitudinal comparisons."
  },
  "decision" => "Use post-write associations to prioritize a controlled memory/skill replay study, not to claim that durable files improve later work."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
