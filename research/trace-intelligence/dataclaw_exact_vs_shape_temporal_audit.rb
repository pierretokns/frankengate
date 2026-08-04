#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def shape_for(command)
  command.to_s.downcase
         .gsub(/[0-9a-f]{8,}/, "<id>")
         .gsub(/(?:\/|\\)[^\s]+/, "<path>")
         .gsub(/(['"])(?:\\.|(?!\1).)*\1/, "<str>")
         .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
         .split.first(6).join(" ")
end

def command_features(row)
  features = []
  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      arguments = call.dig("function", "arguments")
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      command = arguments.is_a?(Hash) ? (arguments["command"] || arguments["cmd"]) : nil
      next unless command.is_a?(String) && !command.empty?

      features << {
        "digest" => Digest::SHA256.hexdigest(command),
        "shape" => shape_for(command)
      }
    rescue JSON::ParserError
      # Skip malformed argument payloads.
    end
  end
  features.uniq { |feature| [feature["digest"], feature["shape"]] }
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
rows = []
File.foreach(input_path) do |line|
  row = JSON.parse(line)
  rows << {
    "project" => row.dig("metadata", "project").to_s,
    "start_time" => row.dig("metadata", "start_time").to_s,
    "features" => command_features(row)
  }
end

train = []
evaluation = []
excluded = 0
rows.group_by { |row| row["project"] }.each_value do |project_rows|
  ordered = project_rows.sort_by { |row| row["start_time"] }
  if ordered.length < 2
    excluded += 1
    next
  end
  cut = [[(ordered.length * 0.7).floor, 1].max, ordered.length - 1].min
  train.concat(ordered.first(cut))
  evaluation.concat(ordered.drop(cut))
end

train_by_project = Hash.new { |hash, key| hash[key] = { "digest" => {}, "shape" => {} } }
train_any = { "digest" => {}, "shape" => {} }
train.each do |row|
  row["features"].each do |feature|
    %w[digest shape].each do |key|
      train_by_project[row["project"]][key][feature[key]] = true
      train_any[key][feature[key]] = true
    end
  end
end

event_counts = Hash.new(0)
session_counts = Hash.new(0)
evaluation.each do |row|
  next if row["features"].empty?

  session_counts["evaluation_with_features"] += 1
  project_seen = { "digest" => false, "shape" => false }
  any_seen = { "digest" => false, "shape" => false }
  row["features"].each do |feature|
    %w[digest shape].each do |key|
      event_counts["#{key}_events"] += 1
      if train_by_project[row["project"]][key].key?(feature[key])
        event_counts["#{key}_same_project"] += 1
        project_seen[key] = true
      end
      if train_any[key].key?(feature[key])
        event_counts["#{key}_any_project"] += 1
        any_seen[key] = true
      end
    end
  end
  %w[digest shape].each do |key|
    session_counts["#{key}_same_project_sessions"] += 1 if project_seen[key]
    session_counts["#{key}_any_project_sessions"] += 1 if any_seen[key]
  end
end

def rate(numerator, denominator)
  denominator.zero? ? nil : numerator.to_f / denominator
end

receipt = {
  "schema_version" => "frankengate-dataclaw-exact-vs-shape-temporal-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "split" => {
    "method" => "per-project chronological 70/30",
    "train_sessions" => train.length,
    "evaluation_sessions" => evaluation.length,
    "excluded_single_session_projects" => excluded
  },
  "events" => event_counts.merge(
    "digest_same_project_rate" => rate(event_counts["digest_same_project"], event_counts["digest_events"]),
    "digest_any_project_rate" => rate(event_counts["digest_any_project"], event_counts["digest_events"]),
    "shape_same_project_rate" => rate(event_counts["shape_same_project"], event_counts["shape_events"]),
    "shape_any_project_rate" => rate(event_counts["shape_any_project"], event_counts["shape_events"])
  ),
  "sessions" => session_counts.merge(
    "digest_same_project_rate" => rate(session_counts["digest_same_project_sessions"], session_counts["evaluation_with_features"]),
    "shape_same_project_rate" => rate(session_counts["shape_same_project_sessions"], session_counts["evaluation_with_features"]),
    "digest_any_project_rate" => rate(session_counts["digest_any_project_sessions"], session_counts["evaluation_with_features"]),
    "shape_any_project_rate" => rate(session_counts["shape_any_project_sessions"], session_counts["evaluation_with_features"])
  ),
  "claim_boundary" => {
    "exact_vs_shape_recurrence_measured" => true,
    "semantic_artifact_correctness_established" => false,
    "task_equivalence_established" => false,
    "promotion_authorized" => false,
    "reason" => "Exact string recurrence is a necessary but insufficient signal; a changed parameter, authority scope, tool version, or outcome can make an exact-looking command unsafe."
  },
  "decision" => "Use shape recurrence for candidate generation and exact recurrence as a stronger prior, but require typed binding, scope/epoch/schema checks, and independent replay before reuse."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
