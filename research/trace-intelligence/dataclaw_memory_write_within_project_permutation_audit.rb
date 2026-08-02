#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

ARTIFACT_MARKER = /(?:memory\.md|CLAUDE\.md|AGENTS\.md|SKILL\.md|\.claude|\.codex|skills?)/i

def command_audit(row)
  features = []
  artifact_write = false
  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      function = call.fetch("function", {})
      name = function["name"].to_s.downcase
      arguments = function["arguments"]
      arguments = JSON.parse(arguments) if arguments.is_a?(String)
      argument_text = arguments.is_a?(Hash) ? JSON.generate(arguments) : arguments.to_s
      artifact_reference = argument_text.match?(ARTIFACT_MARKER)
      write_like = %w[write_file edit_file].include?(name) ||
        (name == "run_command" && argument_text.match?(/(?:>|tee|cat\s+>>|printf\s+)/i))
      artifact_write ||= artifact_reference && write_like
      command = arguments.is_a?(Hash) ? (arguments["command"] || arguments["cmd"]) : nil
      next unless command.is_a?(String) && !command.empty?

      normalized = command.downcase
                         .gsub(/[0-9a-f]{8,}/, "<id>")
                         .gsub(/(?:\/|\\)[^\s]+/, "<path>")
                         .gsub(/(['\"])(?:\\.|(?!\1).)*\1/, "<str>")
                         .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
                         .split.first(6).join(" ")
      features << {
        "shape" => normalized,
        "digest" => Digest::SHA256.hexdigest(command)
      }
    rescue JSON::ParserError
      # A malformed argument cannot prove a write or reusable command.
    end
  end
  { "features" => features.uniq, "artifact_write" => artifact_write }
end

def rate(rows, hit_key)
  events = rows.sum { |row| row["features"] }
  hits = rows.sum { |row| row[hit_key] }
  [events, hits, events.zero? ? nil : hits.to_f / events]
end

def fisher_yates(values, rng)
  result = values.dup
  (result.length - 1).downto(1) do |index|
    swap = rng.rand(index + 1)
    result[index], result[swap] = result[swap], result[index]
  end
  result
end

def pooled_difference(project_rows, hit_key, labels_by_project = nil)
  true_rows = []
  false_rows = []
  project_rows.each do |project, rows|
    labels = labels_by_project && labels_by_project[project]
    rows.each_with_index do |row, index|
      is_true = labels ? labels[index] : row["prior_write"]
      (is_true ? true_rows : false_rows) << row.merge(hit_key => row[hit_key])
    end
  end
  true_rate = rate(true_rows, hit_key)[2]
  false_rate = rate(false_rows, hit_key)[2]
  return nil if true_rate.nil? || false_rate.nil?

  true_rate - false_rate
end

def quantile(values, fraction)
  return nil if values.empty?

  sorted = values.sort
  sorted[[((sorted.length - 1) * fraction).round, sorted.length - 1].min]
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
rows_by_project = Hash.new { |hash, key| hash[key] = [] }

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  metadata = row.fetch("metadata", {})
  rows_by_project[metadata["project"].to_s] << {
    "start_time" => metadata["start_time"].to_s,
    "audit" => command_audit(row)
  }
end

observations_by_project = Hash.new { |hash, key| hash[key] = [] }
rows_by_project.each do |project, project_rows|
  ordered = project_rows.sort_by { |row| row["start_time"] }
  prior_shapes = {}
  prior_digests = {}
  prior_writes = 0
  ordered.each_with_index do |row, index|
    features = row["audit"]["features"]
    next if index.zero?

    observations_by_project[project] << {
      "features" => features.length,
      "shape_hits" => features.count { |feature| prior_shapes.key?(feature["shape"]) },
      "digest_hits" => features.count { |feature| prior_digests.key?(feature["digest"]) },
      "prior_write" => prior_writes.positive?
    }
    features.each do |feature|
      prior_shapes[feature["shape"]] = true
      prior_digests[feature["digest"]] = true
    end
    prior_writes += 1 if row["audit"]["artifact_write"]
  end
end

project_rows = observations_by_project.select { |_project, rows| rows.any? { |row| row["prior_write"] } && rows.any? { |row| !row["prior_write"] } }
observed = {
  "shape" => pooled_difference(project_rows, "shape_hits"),
  "digest" => pooled_difference(project_rows, "digest_hits")
}

macro_rates = {}
%w[shape_hits digest_hits].each do |hit_key|
  prior_rates = []
  no_prior_rates = []
  project_rows.each_value do |rows|
    prior_rate = rate(rows.select { |row| row["prior_write"] }, hit_key)[2]
    no_prior_rate = rate(rows.reject { |row| row["prior_write"] }, hit_key)[2]
    prior_rates << prior_rate unless prior_rate.nil?
    no_prior_rates << no_prior_rate unless no_prior_rate.nil?
  end
  macro_rates[hit_key] = {
    "prior_write_mean_rate" => prior_rates.empty? ? nil : prior_rates.sum / prior_rates.length,
    "no_prior_write_mean_rate" => no_prior_rates.empty? ? nil : no_prior_rates.sum / no_prior_rates.length,
    "mean_project_difference" => if prior_rates.empty? || no_prior_rates.empty?
                                   nil
                                 else
                                   (prior_rates.sum / prior_rates.length) - (no_prior_rates.sum / no_prior_rates.length)
                                 end
  }
end

iterations = 5_000
rng = Random.new(420_000)
null_differences = { "shape" => [], "digest" => [] }
iterations.times do
  labels_by_project = {}
  project_rows.each do |project, rows|
    true_count = rows.count { |row| row["prior_write"] }
    labels = Array.new(rows.length, false)
    fisher_yates((0...rows.length).to_a, rng).first(true_count).each { |index| labels[index] = true }
    labels_by_project[project] = labels
  end
  %w[shape_hits digest_hits].each do |hit_key|
    name = hit_key == "shape_hits" ? "shape" : "digest"
    difference = pooled_difference(project_rows, hit_key, labels_by_project)
    null_differences[name] << difference unless difference.nil?
  end
end

permutation = null_differences.each_with_object({}) do |(name, values), output|
  observed_difference = observed[name]
  output[name] = {
    "iterations" => values.length,
    "seed" => 420_000,
    "observed_pooled_difference" => observed_difference,
    "null_mean_difference" => values.empty? ? nil : values.sum / values.length,
    "null_p95_difference" => quantile(values, 0.95),
    "one_sided_p_value" => if observed_difference.nil? || values.empty?
                             nil
                           else
                             (values.count { |value| value >= observed_difference } + 1).to_f / (values.length + 1)
                           end
  }
end

receipt = {
  "schema_version" => "frankengate-dataclaw-memory-write-within-project-permutation-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "split" => {
    "method" => "within-project chronology with first-session exclusion",
    "projects" => rows_by_project.length,
    "projects_with_both_write_states" => project_rows.length,
    "observed_sessions_after_first" => observations_by_project.values.sum(&:length),
    "observed_sessions_in_paired_projects" => project_rows.values.sum(&:length),
    "sessions_with_prior_write" => project_rows.values.sum { |rows| rows.count { |row| row["prior_write"] } },
    "sessions_without_prior_write" => project_rows.values.sum { |rows| rows.count { |row| !row["prior_write"] } }
  },
  "observed" => {
    "pooled_difference_prior_minus_no_prior" => observed,
    "macro_project_rates" => macro_rates
  },
  "permutation" => permutation,
  "claim_boundary" => {
    "within_project_association_tested" => true,
    "permutation_null_tested" => true,
    "causal_memory_or_skill_effect_established" => false,
    "temporal_trend_controlled" => false,
    "artifact_correctness_established" => false,
    "user_outcome_established" => false,
    "promotion_authorized" => false,
    "reason" => "Stratification removes pooled project mix and permutation tests whether the observed association is unusual under fixed per-project write counts. Writes still occur at a time chosen by users and may mark a transition to harder or more active work; no intervention or terminal outcome is observed."
  },
  "decision" => "Treat post-write recurrence as a prioritization signal only. Run randomized no-memory/placebo/reviewed/generated memory replay on matched changed-system tasks before claiming memory or skill benefit."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
