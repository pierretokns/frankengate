#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

EXTENSIONS = %w[
  .c .cc .cpp .cs .css .csv .go .h .hpp .html .ini .java .js .json .jsx .md
  .mdx .php .py .rb .rs .sh .sql .swift .toml .ts .tsx .txt .xml .yaml .yml
].freeze

def path_candidate?(token)
  return false if token.empty? || token.start_with?("http://", "https://")
  return false if token.length > 256 || token.include?("\n") || token.include?("\r")

  normalized = token.tr("\\", "/")
  basename = normalized.split("/").last.to_s.downcase
  return false unless basename.match?(/\A[a-z0-9_.-]+\z/)
  normalized.include?("/") || EXTENSIONS.any? { |extension| basename.end_with?(extension) }
end

def clean_token(token)
  value = token.to_s.strip
  value = value.sub(/\A(?:[A-Za-z_][A-Za-z0-9_]*=)/, "")
  value = value.gsub(/\A[\"'`(\[]+/, "").gsub(/[\"'`,;:)}\]]+\z/, "")
  value
end

def path_surfaces(command)
  command.to_s.scan(/(?:"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^\s]+)/).each_with_object([]) do |raw, surfaces|
    token = clean_token(raw)
    next unless path_candidate?(token)

    normalized = token.tr("\\", "/")
    basename = normalized.split("/").last.to_s.downcase
    next if basename.empty? || basename.start_with?("-") || basename.length > 128

    surfaces << [basename, Digest::SHA256.hexdigest(normalized.downcase)]
  end.uniq
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)

basename_projects = Hash.new { |hash, key| hash[key] = {} }
basename_sessions = Hash.new { |hash, key| hash[key] = {} }
basename_paths = Hash.new { |hash, key| hash[key] = {} }
extension_counts = Hash.new(0)
projects = {}
path_events = 0
command_events = 0
malformed_argument_events = 0
session_count = 0

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  session_count += 1
  project = row.dig("metadata", "project").to_s
  session_id = row.dig("metadata", "session_id").to_s
  projects[project] = true

  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      command = arguments.is_a?(Hash) ? (arguments["command"] || arguments["cmd"]) : nil
      next unless command.is_a?(String) && !command.empty?

      command_events += 1
      path_surfaces(command).each do |basename, path_digest|
        path_events += 1
        basename_projects[basename][project] = true
        basename_sessions[basename][session_id] = true
        basename_paths[basename][path_digest] = true
        extension = File.extname(basename).downcase
        extension_counts[extension] += 1 if EXTENSIONS.include?(extension)
      end
    rescue JSON::ParserError
      malformed_argument_events += 1
    end
  end
end

project_support = basename_projects.values.map(&:length)
path_support = basename_paths.values.map(&:length)
cross_project_basenames = basename_projects.count { |_basename, values| values.length >= 2 }
cross_project_collision_events = basename_projects.sum do |basename, values|
  next 0 unless values.length >= 2

  basename_sessions.fetch(basename, {}).length
end
multi_path_basenames = basename_paths.count { |_basename, values| values.length >= 2 }
cross_project_multi_path_basenames = basename_projects.count do |basename, values|
  values.length >= 2 && basename_paths.fetch(basename, {}).length >= 2
end

receipt = {
  "schema_version" => "frankengate-dataclaw-path-identifier-collision-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false,
    "raw_paths_emitted" => false
  },
  "cohort" => {
    "sessions" => session_count,
    "projects" => projects.length,
    "command_events" => command_events,
    "path_events" => path_events,
    "malformed_argument_events" => malformed_argument_events,
    "unique_basename_surfaces" => basename_projects.length,
    "unique_full_path_digests" => basename_paths.values.sum(&:length)
  },
  "collisions" => {
    "cross_project_basename_surfaces" => cross_project_basenames,
    "cross_project_basename_surface_rate" => basename_projects.empty? ? 0.0 : cross_project_basenames.to_f / basename_projects.length,
    "cross_project_collision_session_events" => cross_project_collision_events,
    "cross_project_collision_event_rate" => path_events.zero? ? 0.0 : cross_project_collision_events.to_f / path_events,
    "basename_surfaces_with_multiple_full_path_digests" => multi_path_basenames,
    "cross_project_surfaces_with_multiple_full_path_digests" => cross_project_multi_path_basenames,
    "median_projects_per_basename" => project_support.empty? ? 0 : project_support.sort[project_support.length / 2],
    "max_projects_per_basename" => project_support.max || 0,
    "median_full_path_digests_per_basename" => path_support.empty? ? 0 : path_support.sort[path_support.length / 2],
    "max_full_path_digests_per_basename" => path_support.max || 0
  },
  "surface_distribution" => {
    "extension_event_counts" => extension_counts.sort.to_h
  },
  "claim_boundary" => {
    "identifier_collision_proxy_measured" => true,
    "same_basename_means_same_system" => false,
    "same_basename_means_same_task" => false,
    "enterprise_alias_quality_established" => false,
    "artifact_correctness_established" => false,
    "semantic_hard_negative_label_established" => false,
    "promotion_authorized" => false,
    "reason" => "A repeated basename can be a generic filename, a shared repository convention, or a true cross-project identifier. Full-path digests distinguish surfaces but do not establish semantic identity or correctness."
  },
  "decision" => "Use same-basename/different-path/project cases as hard-negative candidates for reviewed alias and identifier datasets. Require task labels, scope, temporal validity, and independent replay before promoting any alias, embedding edge, or artifact."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
