#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

EXTENSIONS = %w[
  .c .cc .cpp .cs .css .csv .go .h .hpp .html .ini .java .js .json .jsx .md
  .mdx .php .py .rb .rs .sh .sql .swift .toml .ts .tsx .txt .xml .yaml .yml
].freeze

def clean_token(token)
  token.to_s.strip
       .sub(/\A(?:[A-Za-z_][A-Za-z0-9_]*=)/, "")
       .gsub(/\A[\"'`(\[]+/, "")
       .gsub(/[\"'`,;:)}\]]+\z/, "")
end

def path_pairs(command)
  pattern = /(?:"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^\s]+)/
  command.to_s.scan(pattern).each_with_object([]) do |raw, pairs|
    token = clean_token(raw)
    next if token.empty? || token.start_with?("http://", "https://")
    next if token.length > 256 || token.include?("\n") || token.include?("\r")

    normalized = token.tr("\\", "/")
    basename = normalized.split("/").last.to_s.downcase
    next if basename.empty? || basename.start_with?("-") || basename.length > 128
    next unless basename.match?(/\A[a-z0-9_.-]+\z/)
    next unless normalized.include?("/") || EXTENSIONS.any? { |extension| basename.end_with?(extension) }

    pairs << [basename, Digest::SHA256.hexdigest(normalized.downcase)]
  end.uniq
end

def row_pairs(row)
  pairs = []
  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      arguments = call.fetch("function", {})["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      next unless arguments.is_a?(Hash)

      command = arguments["command"] || arguments["cmd"]
      next unless command.is_a?(String) && !command.empty?

      pairs.concat(path_pairs(command))
    rescue JSON::ParserError
      # Malformed arguments cannot contribute a trustworthy identifier.
    end
  end
  pairs.uniq
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
rows = []

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  metadata = row.fetch("metadata", {})
  rows << {
    "project" => metadata["project"].to_s,
    "start_time" => metadata["start_time"].to_s,
    "pairs" => row_pairs(row)
  }
end

by_project = rows.group_by { |row| row["project"] }
train = []
evaluation = []
excluded_small_projects = 0

by_project.each_value do |project_rows|
  ordered = project_rows.sort_by { |row| row["start_time"] }
  if ordered.length < 2
    excluded_small_projects += 1
    next
  end

  cut = [(ordered.length * 0.7).floor, 1].max
  cut = [cut, ordered.length - 1].min
  train.concat(ordered.first(cut))
  evaluation.concat(ordered.drop(cut))
end

train_project_basenames = Hash.new { |hash, key| hash[key] = {} }
train_project_digests = Hash.new { |hash, key| hash[key] = {} }
train_any_basenames = {}
train_any_digests = {}
train.each do |row|
  row["pairs"].each do |basename, digest|
    project = row["project"]
    train_project_basenames[project][basename] = true
    train_project_digests[project][digest] = true
    train_any_basenames[basename] = true
    train_any_digests[digest] = true
  end
end

eval_path_events = 0
same_project_basename_events = 0
same_project_exact_events = 0
any_project_basename_events = 0
any_project_exact_events = 0
eval_sessions_with_paths = 0
same_project_basename_sessions = 0
same_project_exact_sessions = 0
any_project_basename_sessions = 0
any_project_exact_sessions = 0

evaluation.each do |row|
  pairs = row["pairs"]
  next if pairs.empty?

  eval_sessions_with_paths += 1
  same_basename = pairs.count { |basename, _digest| train_project_basenames[row["project"]].key?(basename) }
  same_exact = pairs.count { |_basename, digest| train_project_digests[row["project"]].key?(digest) }
  any_basename = pairs.count { |basename, _digest| train_any_basenames.key?(basename) }
  any_exact = pairs.count { |_basename, digest| train_any_digests.key?(digest) }

  same_project_basename_events += same_basename
  same_project_exact_events += same_exact
  any_project_basename_events += any_basename
  any_project_exact_events += any_exact
  same_project_basename_sessions += 1 if same_basename.positive?
  same_project_exact_sessions += 1 if same_exact.positive?
  any_project_basename_sessions += 1 if any_basename.positive?
  any_project_exact_sessions += 1 if any_exact.positive?
  eval_path_events += pairs.length
end

train_basename_projects = Hash.new { |hash, key| hash[key] = {} }
train_digest_projects = Hash.new { |hash, key| hash[key] = {} }
train.each do |row|
  row["pairs"].each do |basename, digest|
    train_basename_projects[basename][row["project"]] = true
    train_digest_projects[digest][row["project"]] = true
  end
end

cross_project_basenames = train_basename_projects.count { |_key, projects| projects.length >= 2 }
cross_project_digests = train_digest_projects.count { |_key, projects| projects.length >= 2 }

receipt = {
  "schema_version" => "frankengate-dataclaw-identifier-temporal-reuse-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false,
    "raw_identifiers_emitted" => false
  },
  "split" => {
    "method" => "per-project chronological 70/30",
    "projects_with_train_and_eval" => by_project.count { |_project, project_rows| project_rows.length >= 2 },
    "projects_excluded_for_single_session" => excluded_small_projects,
    "train_sessions" => train.length,
    "evaluation_sessions" => evaluation.length,
    "evaluation_sessions_with_paths" => eval_sessions_with_paths,
    "evaluation_path_events" => eval_path_events
  },
  "training_surface_collisions" => {
    "cross_project_basenames" => cross_project_basenames,
    "cross_project_full_path_digests" => cross_project_digests,
    "basename_surface_count" => train_basename_projects.length,
    "full_path_digest_count" => train_digest_projects.length
  },
  "reuse" => {
    "same_project_basename_events" => same_project_basename_events,
    "same_project_exact_path_events" => same_project_exact_events,
    "any_project_basename_events" => any_project_basename_events,
    "any_project_exact_path_events" => any_project_exact_events,
    "same_project_basename_event_rate" => eval_path_events.zero? ? nil : same_project_basename_events.to_f / eval_path_events,
    "same_project_exact_path_event_rate" => eval_path_events.zero? ? nil : same_project_exact_events.to_f / eval_path_events,
    "any_project_basename_event_rate" => eval_path_events.zero? ? nil : any_project_basename_events.to_f / eval_path_events,
    "any_project_exact_path_event_rate" => eval_path_events.zero? ? nil : any_project_exact_events.to_f / eval_path_events,
    "exact_within_same_project_basename_hit_rate" => same_project_basename_events.zero? ? nil : same_project_exact_events.to_f / same_project_basename_events,
    "same_project_basename_sessions" => same_project_basename_sessions,
    "same_project_exact_path_sessions" => same_project_exact_sessions,
    "any_project_basename_sessions" => any_project_basename_sessions,
    "any_project_exact_path_sessions" => any_project_exact_sessions,
    "same_project_basename_session_rate" => eval_sessions_with_paths.zero? ? nil : same_project_basename_sessions.to_f / eval_sessions_with_paths,
    "same_project_exact_path_session_rate" => eval_sessions_with_paths.zero? ? nil : same_project_exact_sessions.to_f / eval_sessions_with_paths,
    "any_project_basename_session_rate" => eval_sessions_with_paths.zero? ? nil : any_project_basename_sessions.to_f / eval_sessions_with_paths,
    "any_project_exact_path_session_rate" => eval_sessions_with_paths.zero? ? nil : any_project_exact_sessions.to_f / eval_sessions_with_paths
  },
  "claim_boundary" => {
    "temporal_identifier_recurrence_measured" => true,
    "same_task_established" => false,
    "same_work_established" => false,
    "semantic_alias_quality_established" => false,
    "artifact_correctness_established" => false,
    "promotion_authorized" => false,
    "reason" => "Exact path recurrence is an identity/exposure signal. A basename recurrence can represent unrelated files, renamed systems, repository conventions, or true aliases; neither recurrence measure establishes task intent or correctness."
  },
  "decision" => "Use exact path identity as a high-precision feature and basename surfaces as a lower-precision recall/hard-negative feature. Require scope, authority, reviewed semantics, and independent replay before artifact or alias promotion."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
