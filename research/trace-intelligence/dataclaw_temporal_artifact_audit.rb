#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def command_shape(arguments)
  return nil unless arguments.is_a?(Hash)

  command = arguments["command"] || arguments["cmd"]
  return nil unless command.is_a?(String) && !command.empty?

  command.downcase
         .gsub(/[0-9a-f]{8,}/, "<id>")
         .gsub(/(?:\/|\\)[^\s]+/, "<path>")
         .gsub(/(['"])(?:\\.|(?!\1).)*\1/, "<str>")
         .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
         .split.first(6).join(" ")
end

def shapes_for(row)
  shapes = []
  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      shape = command_shape(arguments)
      shapes << shape if shape
    rescue JSON::ParserError
      # Ignore malformed argument payloads for this shape-only audit.
    end
  end
  shapes.uniq
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
    "shapes" => shapes_for(row)
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

same_project_seen = 0
any_project_seen = 0
evaluation_sessions_with_shapes = 0
evaluation_shape_events = 0
same_project_shape_events = 0
any_project_shape_events = 0

train_by_project = Hash.new { |hash, key| hash[key] = {} }
train_any = {}
train.each do |row|
  row["shapes"].each do |shape|
    train_by_project[row["project"]][shape] = true
    train_any[shape] = true
  end
end

evaluation.each do |row|
  shapes = row["shapes"]
  next if shapes.empty?

  evaluation_sessions_with_shapes += 1
  evaluation_shape_events += shapes.length
  same = shapes.count { |shape| train_by_project[row["project"]].key?(shape) }
  any = shapes.count { |shape| train_any.key?(shape) }
  same_project_shape_events += same
  any_project_shape_events += any
  same_project_seen += 1 if same.positive?
  any_project_seen += 1 if any.positive?
end

train_shape_projects = Hash.new { |hash, key| hash[key] = {} }
train.each do |row|
  row["shapes"].each { |shape| train_shape_projects[shape][row["project"]] = true }
end
cross_project_train_shapes = train_shape_projects.count { |_shape, projects| projects.length >= 2 }

receipt = {
  "schema_version" => "frankengate-dataclaw-temporal-artifact-audit-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "split" => {
    "method" => "per-project chronological 70/30",
    "projects_with_train_and_eval" => by_project.count { |_project, project_rows| project_rows.length >= 2 },
    "projects_excluded_for_single_session" => excluded_small_projects,
    "train_sessions" => train.length,
    "evaluation_sessions" => evaluation.length,
    "evaluation_sessions_with_shapes" => evaluation_sessions_with_shapes
  },
  "reuse" => {
    "evaluation_shape_events" => evaluation_shape_events,
    "same_project_seen_shape_events" => same_project_shape_events,
    "any_project_seen_shape_events" => any_project_shape_events,
    "same_project_event_reuse_rate" => evaluation_shape_events.zero? ? nil : same_project_shape_events.to_f / evaluation_shape_events,
    "any_project_event_reuse_rate" => evaluation_shape_events.zero? ? nil : any_project_shape_events.to_f / evaluation_shape_events,
    "sessions_with_same_project_reuse" => same_project_seen,
    "sessions_with_any_project_reuse" => any_project_seen,
    "same_project_session_reuse_rate" => evaluation_sessions_with_shapes.zero? ? nil : same_project_seen.to_f / evaluation_sessions_with_shapes,
    "any_project_session_reuse_rate" => evaluation_sessions_with_shapes.zero? ? nil : any_project_seen.to_f / evaluation_sessions_with_shapes
  },
  "hard_negative_proxy" => {
    "unique_train_shapes" => train_shape_projects.length,
    "cross_project_train_shapes" => cross_project_train_shapes,
    "cross_project_train_shape_rate" => train_shape_projects.empty? ? nil : cross_project_train_shapes.to_f / train_shape_projects.length
  },
  "claim_boundary" => {
    "temporal_recurrence_measured" => true,
    "same_task_or_artifact_correctness_established" => false,
    "semantic_alias_quality_established" => false,
    "skill_or_user_outcome_established" => false,
    "promotion_authorized" => false,
    "reason" => "Command-shape recurrence is an exposure/provenance signal. It does not prove that repeated invocations are semantically equivalent or safe to reuse."
  },
  "decision" => "Use temporal recurrence to prioritize review and generate cross-project hard negatives. Require parameter/authority/schema contracts and independent replay before artifact release."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
