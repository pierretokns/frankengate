#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def normalized_shape(command)
  command.to_s.downcase
         .gsub(/[0-9a-f]{8,}/, "<id>")
         .gsub(/(?:\/|\\)[^\s]+/, "<path>")
         .gsub(/(['"])(?:\\.|(?!\1).)*\1/, "<str>")
         .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
         .split.first(6).join(" ")
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
shape_commands = Hash.new { |hash, key| hash[key] = {} }
shape_projects = Hash.new { |hash, key| hash[key] = {} }
shape_sessions = Hash.new { |hash, key| hash[key] = {} }
command_events = 0
malformed_argument_events = 0
session_count = 0
projects = {}

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  session_count += 1
  project = row.dig("metadata", "project").to_s
  projects[project] = true
  session_id = row.dig("metadata", "session_id").to_s

  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      command = arguments.is_a?(Hash) ? (arguments["command"] || arguments["cmd"]) : nil
      next unless command.is_a?(String) && !command.empty?

      command_events += 1
      shape = normalized_shape(command)
      digest = Digest::SHA256.hexdigest(command)
      shape_commands[shape][digest] = true
      shape_projects[shape][project] = true
      shape_sessions[shape][session_id] = true
    rescue JSON::ParserError
      malformed_argument_events += 1
    end
  end
end

shape_variant_counts = shape_commands.values.map(&:length)
recurrent_shapes = shape_variant_counts.select { |count| count >= 2 }
shape_support = shape_sessions.transform_values(&:length)
cross_project_shapes = shape_projects.count { |_shape, projects_for_shape| projects_for_shape.length >= 2 }
recurrent_cross_project_shapes = shape_projects.count do |shape, projects_for_shape|
  shape_support.fetch(shape, 0) >= 2 && projects_for_shape.length >= 2
end
multi_variant_recurrent = recurrent_shapes.count { |count| count >= 2 }
high_variant_recurrent = recurrent_shapes.count { |count| count >= 5 }

sorted_variants = shape_variant_counts.sort
median = if sorted_variants.empty?
           0
         else
           sorted_variants[sorted_variants.length / 2]
         end

receipt = {
  "schema_version" => "frankengate-dataclaw-command-shape-variants-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "cohort" => {
    "sessions" => session_count,
    "projects" => projects.length,
    "command_events" => command_events,
    "malformed_argument_events" => malformed_argument_events,
    "unique_shapes" => shape_commands.length,
    "unique_exact_command_digests" => shape_commands.values.sum(&:length)
  },
  "shape_variants" => {
    "median_exact_variants_per_shape" => median,
    "max_exact_variants_per_shape" => shape_variant_counts.max || 0,
    "shapes_with_multiple_exact_variants" => multi_variant_recurrent,
    "shapes_with_at_least_five_exact_variants" => high_variant_recurrent,
    "recurrent_shapes" => recurrent_shapes.length,
    "cross_project_shapes" => cross_project_shapes,
    "recurrent_cross_project_shapes" => recurrent_cross_project_shapes,
    "exact_variants_per_shape_ratio" => shape_commands.empty? ? nil : shape_commands.values.sum(&:length).to_f / shape_commands.length
  },
  "claim_boundary" => {
    "parameter_diversity_measured" => true,
    "shape_is_semantic_template" => false,
    "artifact_correctness_established" => false,
    "safe_parameter_binding_established" => false,
    "promotion_authorized" => false,
    "reason" => "A normalized prefix/shape can collapse distinct command arguments, projects, and outcomes. Shape recurrence is a candidate-template signal only."
  },
  "decision" => "Represent mined commands as parameterized proposals with explicit argument schemas, scope, authority, expiry, and independent replay. Never promote a normalized shape by recurrence alone."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
