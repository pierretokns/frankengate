#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

STOPWORDS = %w[
  a an and are as at be by can do for from get give has have how i if in is it
  me my of on or please so that the this to what when where with you your
].freeze

def words(text)
  text.to_s.downcase.scan(/[a-z][a-z0-9_]{2,}/).reject { |word| STOPWORDS.include?(word) }.uniq
end

def command_shape(arguments)
  return nil unless arguments.is_a?(Hash)

  command = arguments["command"] || arguments["cmd"]
  return nil unless command.is_a?(String) && !command.empty?

  normalized = command.downcase
                     .gsub(/[0-9a-f]{8,}/, "<id>")
                     .gsub(/(?:\/|\\)[^\s]+/, "<path>")
                     .gsub(/(['"])(?:\\.|(?!\1).)*\1/, "<str>")
                     .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
  normalized.split.first(6).join(" ")
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)

sessions = []
tool_signature_sessions = Hash.new { |hash, key| hash[key] = [] }
term_sessions = Hash.new { |hash, key| hash[key] = [] }
term_projects = Hash.new { |hash, key| hash[key] = {} }
shape_sessions = Hash.new { |hash, key| hash[key] = [] }
total_tool_calls = 0

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  metadata = row.fetch("metadata", {})
  prompt = row["prompt"].to_s
  project = metadata["project"].to_s
  terms = words(prompt)
  tools = []
  shapes = []

  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      name = function["name"].to_s
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      signature = [name, arguments.is_a?(Hash) ? arguments.keys.sort.join(",") : ""].join("|")
      tools << signature
      total_tool_calls += 1
      shape = command_shape(arguments)
      shapes << shape if shape
    rescue JSON::ParserError
      # A malformed tool argument is counted as an observed call but cannot
      # create a reusable artifact signature.
    end
  end

  index = sessions.length
  sessions << { project: project, terms: terms, tools: tools.uniq, shapes: shapes.uniq }
  terms.each do |term|
    term_sessions[term] << index
    term_projects[term][project] = true
  end
  tools.uniq.each { |signature| tool_signature_sessions[signature] << index }
  shapes.uniq.each { |shape| shape_sessions[shape] << index }
end

def group_stats(groups, sessions)
  values = groups.values.map(&:length)
  cross_project = groups.values.count do |indexes|
    indexes.map { |index| sessions[index][:project] }.uniq.length >= 2
  end
  {
    "unique" => groups.length,
    "repeated" => values.count { |value| value >= 2 },
    "cross_project" => cross_project,
    "max_session_support" => values.max || 0,
    "max_project_support" => groups.values.map { |indexes| indexes.map { |i| sessions[i][:project] }.uniq.length }.max || 0
  }
end

def overlap_score(left, right, key)
  a = left[key]
  b = right[key]
  intersection = (a & b).length
  union = (a | b).length
  return 0.0 if union.zero?

  intersection.to_f / union
end

def retrieval_proxy(sessions, key)
  eligible = 0
  positive = 0
  same_project = 0

  sessions.each_with_index do |query, query_index|
    same_project_candidates = sessions.each_index.count { |index| index != query_index && sessions[index][:project] == query[:project] }
    next if same_project_candidates.zero?

    eligible += 1
    candidates = sessions.each_index.reject { |index| index == query_index }
    scored = candidates.map { |index| [overlap_score(query, sessions[index], key), index] }
                     .select { |score, _| score.positive? }
    next if scored.empty?

    positive += 1
    scored.sort_by! { |score, index| [-score, index] }
    best = scored.first[1]
    same_project += 1 if sessions[best][:project] == query[:project]
  end

  {
    "eligible_queries" => eligible,
    "positive_queries" => positive,
    "same_project_top1_rate" => positive.zero? ? nil : (same_project.to_f / positive),
    "same_project_top1_count" => same_project
  }
end

lexical = retrieval_proxy(sessions, :terms)
tool_overlap = retrieval_proxy(sessions, :tools)

receipt = {
  "schema_version" => "frankengate-dataclaw-openai-artifact-audit-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "license_claimed" => "MIT",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "bytes" => File.size(input_path),
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "cohort" => {
    "sessions" => sessions.length,
    "projects" => sessions.map { |session| session[:project] }.uniq.length,
    "total_tool_calls" => total_tool_calls,
    "prompt_term_vocabulary" => term_sessions.length,
    "prompt_terms_cross_project" => term_projects.count { |_term, projects| projects.length >= 2 }
  },
  "recurring_artifacts" => {
    "tool_signature" => group_stats(tool_signature_sessions, sessions),
    "command_shape" => group_stats(shape_sessions, sessions)
  },
  "retrieval_proxy" => {
    "lexical_prompt_terms" => lexical,
    "tool_signature_overlap" => tool_overlap
  },
  "claim_boundary" => {
    "content_free_artifact_recurrence_measured" => true,
    "project_labels_used_as_silver_proxies" => true,
    "same_work_established" => false,
    "artifact_correctness_established" => false,
    "skill_gap_or_collaboration_established" => false,
    "promotion_authorized" => false,
    "reason" => "Project recurrence and tool-shape overlap are provenance signals, not semantic intent or terminal-outcome labels."
  },
  "decision" => "Use recurring tool signatures and command shapes only as review-queue candidates. Require semantic labels, authority/schema contracts, and independent replay before artifact promotion."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
