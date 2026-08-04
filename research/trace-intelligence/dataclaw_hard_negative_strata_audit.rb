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

def combinations(count)
  count < 2 ? 0 : count * (count - 1) / 2
end

def summarize(rows)
  project_surface_digests = Hash.new { |hash, project| hash[project] = Hash.new { |inner, basename| inner[basename] = Hash.new(0) } }
  rows.each do |row|
    row["pairs"].each do |basename, digest|
      project_surface_digests[row["project"]][basename][digest] += 1
    end
  end

  by_surface_projects = Hash.new { |hash, basename| hash[basename] = Hash.new { |inner, project| inner[project] = {} } }
  by_digest_projects = Hash.new { |hash, digest| hash[digest] = {} }
  project_surface_digests.each do |project, surfaces|
    surfaces.each do |basename, digests|
      digests.each_key do |digest|
        by_surface_projects[basename][project][digest] = true
        by_digest_projects[digest][project] = true
      end
    end
  end

  same_project_exact_occurrence_pairs = 0
  same_project_diff_digest_pairs = 0
  project_surface_digests.each_value do |surfaces|
    surfaces.each_value do |digests|
      same_project_exact_occurrence_pairs += digests.values.sum { |count| combinations(count) }
      same_project_diff_digest_pairs += combinations(digests.length)
    end
  end

  cross_project_surface_project_pairs = by_surface_projects.values.sum { |projects| combinations(projects.length) }
  cross_project_exact_path_project_pairs = by_digest_projects.values.sum { |projects| combinations(projects.length) }
  cross_project_diff_digest_pairs = 0
  by_surface_projects.each_value do |projects|
    projects.keys.combination(2) do |left, right|
      projects[left].keys.each do |left_digest|
        projects[right].keys.each do |right_digest|
          cross_project_diff_digest_pairs += 1 unless left_digest == right_digest
        end
      end
    end
  end

  {
    "sessions" => rows.length,
    "path_events" => rows.sum { |row| row["pairs"].length },
    "unique_project_surface_digest_units" => project_surface_digests.sum { |_project, surfaces| surfaces.sum { |_basename, digests| digests.length } },
    "same_project_exact_identity_units_repeated" => project_surface_digests.sum { |_project, surfaces| surfaces.sum { |_basename, digests| digests.count { |_digest, count| count >= 2 } } },
    "same_project_surface_units_with_multiple_paths" => project_surface_digests.sum { |_project, surfaces| surfaces.count { |_basename, digests| digests.length >= 2 } },
    "cross_project_surface_project_pairs" => cross_project_surface_project_pairs,
    "cross_project_exact_path_project_pairs" => cross_project_exact_path_project_pairs,
    "candidate_strata" => {
      "same_project_exact_identity" => same_project_exact_occurrence_pairs,
      "same_project_same_surface_different_path" => same_project_diff_digest_pairs,
      "cross_project_same_surface_exact_path" => cross_project_exact_path_project_pairs,
      "cross_project_same_surface_different_path" => cross_project_diff_digest_pairs
    }
  }
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

full_summary = summarize(rows)
train_summary = summarize(train)
evaluation_summary = summarize(evaluation)
minimums = { "target" => 100, "hard_negative" => 50, "nil_or_unclear" => 25 }

receipt = {
  "schema_version" => "frankengate-dataclaw-hard-negative-strata-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false,
    "raw_identifiers_emitted" => false
  },
  "cohort" => {
    "sessions" => rows.length,
    "projects" => by_project.length,
    "projects_excluded_for_single_session" => excluded_small_projects,
    "chronological_train_sessions" => train.length,
    "chronological_evaluation_sessions" => evaluation.length
  },
  "full_cohort" => full_summary,
  "chronological_train_only" => train_summary,
  "chronological_evaluation_only" => evaluation_summary,
  "partner_gate_capacity" => {
    "minimum_target_cases" => minimums["target"],
    "minimum_hard_negative_cases" => minimums["hard_negative"],
    "minimum_nil_or_unclear_cases" => minimums["nil_or_unclear"],
    "train_has_at_least_minimum_hard_negative_candidates" => train_summary.dig("candidate_strata", "same_project_same_surface_different_path").to_i >= minimums["hard_negative"],
    "train_has_four_strata" => train_summary.fetch("candidate_strata").values.all?(&:positive?)
  },
  "claim_boundary" => {
    "candidate_supply_measured" => true,
    "same_work_labels_established" => false,
    "semantic_alias_quality_established" => false,
    "artifact_correctness_established" => false,
    "promotion_authorized" => false,
    "reason" => "These are content-free identity/surface strata. Same-surface or exact-path recurrence is not a semantic label and cannot substitute for dual annotation or independent replay."
  },
  "decision" => "Use the chronological train-only strata to construct a frozen review pool, then label target, alias, wrong-scope, stale, NIL, and unclear outcomes before training or promoting any reranker or embedding."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
