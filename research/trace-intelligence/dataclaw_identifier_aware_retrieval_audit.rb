#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

STOPWORDS = %w[
  a an and are as at be by can do for from get give has have how i if in is it
  me my of on or please so that the this to what when where with you your
].freeze

EXTENSIONS = %w[
  .c .cc .cpp .cs .css .csv .go .h .hpp .html .ini .java .js .json .jsx .md
  .mdx .php .py .rb .rs .sh .sql .swift .toml .ts .tsx .txt .xml .yaml .yml
].freeze

def words(text)
  text.to_s.downcase.scan(/[a-z][a-z0-9_]{2,}/).reject { |word| STOPWORDS.include?(word) }.uniq
end

def parse_arguments(call)
  arguments = call.fetch("function", {})["arguments"]
  arguments = JSON.parse(arguments) if arguments.is_a?(String)
  arguments
rescue JSON::ParserError
  nil
end

def command_from(arguments)
  return nil unless arguments.is_a?(Hash)

  command = arguments["command"] || arguments["cmd"]
  command.is_a?(String) && !command.empty? ? command : nil
end

def command_shape(command)
  command.to_s.downcase
         .gsub(/[0-9a-f]{8,}/, "<id>")
         .gsub(/(?:\/|\\)[^\s]+/, "<path>")
         .gsub(/(['\"])(?:\\.|(?!\1).)*\1/, "<str>")
         .gsub(/\b\d+(?:\.\d+)?\b/, "<num>")
         .split.first(6).join(" ")
end

def clean_token(token)
  token.to_s.strip
       .sub(/\A(?:[A-Za-z_][A-Za-z0-9_]*=)/, "")
       .gsub(/\A[\"'`(\[]+/, "")
       .gsub(/[\"'`,;:)}\]]+\z/, "")
end

def path_surface_pairs(command)
  command.to_s.scan(/(?:"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|[^\s]+)/).each_with_object([]) do |raw, surfaces|
    token = clean_token(raw)
    next if token.empty? || token.start_with?("http://", "https://")
    next if token.length > 256 || token.include?("\n") || token.include?("\r")

    normalized = token.tr("\\", "/")
    basename = normalized.split("/").last.to_s.downcase
    next if basename.empty? || basename.start_with?("-") || basename.length > 128
    next unless basename.match?(/\A[a-z0-9_.-]+\z/)
    next unless normalized.include?("/") || EXTENSIONS.any? { |extension| basename.end_with?(extension) }

    surfaces << [basename, Digest::SHA256.hexdigest(normalized.downcase)]
  end.uniq
end

def extract_features(row)
  shapes = []
  identifiers = []
  Array(row["messages"]).each do |message|
    Array(message["tool_calls"]).each do |call|
      arguments = parse_arguments(call)
      command = command_from(arguments)
      next unless command

      shapes << command_shape(command)
      path_surface_pairs(command).each { |basename, _digest| identifiers << basename }
    end
  end
  {
    "terms" => words(row["prompt"]),
    "shapes" => shapes.uniq,
    "identifiers" => identifiers.uniq
  }
end

def jaccard(left, right)
  intersection = (left & right).length
  union = (left | right).length
  union.zero? ? 0.0 : intersection.to_f / union
end

def arm_score(query, candidate, arm)
  case arm
  when "prompt_terms"
    jaccard(query["terms"], candidate["terms"])
  when "command_shapes"
    jaccard(query["shapes"], candidate["shapes"])
  when "path_identifiers"
    jaccard(query["identifiers"], candidate["identifiers"])
  when "prompt_plus_identifiers"
    0.75 * jaccard(query["terms"], candidate["terms"]) +
      0.25 * jaccard(query["identifiers"], candidate["identifiers"])
  when "prompt_plus_shapes"
    0.75 * jaccard(query["terms"], candidate["terms"]) +
      0.25 * jaccard(query["shapes"], candidate["shapes"])
  when "hybrid"
    0.5 * jaccard(query["terms"], candidate["terms"]) +
      0.25 * jaccard(query["shapes"], candidate["shapes"]) +
      0.25 * jaccard(query["identifiers"], candidate["identifiers"])
  else
    raise ArgumentError, "unknown arm: #{arm}"
  end
end

def evaluate_arm(train, evaluation, arm)
  eligible = 0
  covered = 0
  top1_same = 0
  top1_wrong = 0
  recall_at_5 = 0
  reciprocal_rank_sum = 0.0
  candidate_count_sum = 0

  evaluation.each do |query|
    same_project_exists = train.any? { |candidate| candidate["project"] == query["project"] }
    next unless same_project_exists

    eligible += 1
    ranked = train.each_with_index.map do |candidate, index|
      [arm_score(query, candidate, arm), index]
    end.select { |score, _index| score.positive? }
    ranked.sort_by! { |score, index| [-score, index] }
    candidate_count_sum += ranked.length
    next if ranked.empty?

    covered += 1
    top1_index = ranked.first[1]
    if train[top1_index]["project"] == query["project"]
      top1_same += 1
    else
      top1_wrong += 1
    end

    first_same_rank = ranked.index do |_score, index|
      train[index]["project"] == query["project"]
    end
    if first_same_rank
      reciprocal_rank_sum += 1.0 / (first_same_rank + 1)
      recall_at_5 += 1 if first_same_rank < 5
    end
  end

  {
    "eligible_queries" => eligible,
    "queries_with_any_candidate" => covered,
    "candidate_coverage" => eligible.zero? ? nil : covered.to_f / eligible,
    "same_project_recall_at_1" => eligible.zero? ? nil : top1_same.to_f / eligible,
    "same_project_recall_at_5" => eligible.zero? ? nil : recall_at_5.to_f / eligible,
    "same_project_mrr" => eligible.zero? ? nil : reciprocal_rank_sum / eligible,
    "top1_same_project_precision_when_covered" => covered.zero? ? nil : top1_same.to_f / covered,
    "top1_wrong_project_rate_when_covered" => covered.zero? ? nil : top1_wrong.to_f / covered,
    "mean_candidates_when_covered" => covered.zero? ? nil : candidate_count_sum.to_f / covered
  }
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
rows = []

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  metadata = row.fetch("metadata", {})
  rows << extract_features(row).merge(
    "project" => metadata["project"].to_s,
    "start_time" => metadata["start_time"].to_s
  )
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

arms = %w[prompt_terms command_shapes path_identifiers prompt_plus_identifiers prompt_plus_shapes hybrid]
receipt = {
  "schema_version" => "frankengate-dataclaw-identifier-aware-retrieval-v1",
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
    "evaluation_sessions" => evaluation.length
  },
  "feature_coverage" => {
    "train_sessions_with_terms" => train.count { |row| !row["terms"].empty? },
    "train_sessions_with_shapes" => train.count { |row| !row["shapes"].empty? },
    "train_sessions_with_identifiers" => train.count { |row| !row["identifiers"].empty? },
    "evaluation_sessions_with_terms" => evaluation.count { |row| !row["terms"].empty? },
    "evaluation_sessions_with_shapes" => evaluation.count { |row| !row["shapes"].empty? },
    "evaluation_sessions_with_identifiers" => evaluation.count { |row| !row["identifiers"].empty? }
  },
  "arms" => arms.each_with_object({}) do |arm, output|
    output[arm] = evaluate_arm(train, evaluation, arm)
  end,
  "claim_boundary" => {
    "temporal_project_similarity_proxy_measured" => true,
    "same_work_established" => false,
    "same_task_established" => false,
    "semantic_alias_quality_established" => false,
    "artifact_correctness_established" => false,
    "cross_user_collaboration_value_established" => false,
    "promotion_authorized" => false,
    "reason" => "Project recurrence is a silver label. Filename/path surfaces are identifier features, not semantic identity; the split measures related-project retrieval, not task equivalence or artifact reuse."
  },
  "decision" => "Retain exact identifiers and project/scope metadata as a retrieval lane beside prompt and shape features. Promote identifier-aware ranking only after reviewed same-work/NIL labels and replay outcomes replace the project proxy."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
