#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

ERROR_MARKERS = /\b(error|failed|failure|traceback|exception|not found|permission denied|timed out|timeout|invalid|cannot|could not)\b/i
USER_FRICTION_MARKERS = /\b(again|still|retry|doesn['"]?t work|not working|failed|error|wrong|fix this|try again)\b/i
STOPWORDS = %w[a an and are as at be by can do for from get has have how i if in is it me my of on or please so that the this to what when where with you your].freeze

def text_of(content)
  return content if content.is_a?(String)
  return "" unless content.is_a?(Array)

  content.filter_map do |part|
    if part.is_a?(Hash)
      part["text"] || part["content"]
    end
  end.join(" ")
end

def tokens(text)
  text.to_s.downcase.scan(/[a-z][a-z0-9_]{2,}/).reject { |word| STOPWORDS.include?(word) }.uniq
end

def jaccard(left, right)
  union = (left | right).length
  return 0.0 if union.zero?

  (left & right).length.to_f / union
end

input_path = ARGV.fetch(0)
output_path = ARGV.fetch(1)
sessions = 0
user_messages = 0
tool_outputs = 0
explicit_tool_output_messages = 0
tool_call_messages = 0
role_counts = Hash.new(0)
error_outputs = 0
error_followed_by_non_error_output = 0
rephrase_pairs = 0
exact_repeat_pairs = 0
user_marker_messages = 0
structural_friction_sessions = 0
rephrase_sessions = 0
error_sessions = 0
multi_user_sessions = 0
resolution_candidate_sessions = 0
session_user_counts = []

File.foreach(input_path) do |line|
  row = JSON.parse(line)
  sessions += 1
  messages = Array(row["messages"])
  messages.each { |message| role_counts[message["role"].to_s] += 1 }
  users = messages.each_with_index.each_with_object([]) do |(message, index), list|
    next unless message["role"] == "user"

    content = text_of(message["content"])
    user_messages += 1
    user_marker_messages += 1 if content.match?(USER_FRICTION_MARKERS)
    list << { index: index, content: content, tokens: tokens(content) }
  end
  session_user_counts << users.length
  multi_user_sessions += 1 if users.length >= 2

  session_rephrase = false
  users.each_cons(2) do |left, right|
    score = jaccard(left[:tokens], right[:tokens])
    next if left[:content].strip.empty? || right[:content].strip.empty?

    if left[:content].strip.downcase == right[:content].strip.downcase
      exact_repeat_pairs += 1
      session_rephrase = true
    elsif score >= 0.35 && score < 0.98 && [left[:tokens].length, right[:tokens].length].min >= 3
      rephrase_pairs += 1
      session_rephrase = true
    end
  end
  rephrase_sessions += 1 if session_rephrase

  session_error = false
  last_error = false
  messages.each do |message|
    tool_call_messages += 1 if Array(message["tool_calls"]).any?
    if message["role"] == "tool"
      explicit_tool_output_messages += 1
      tool_outputs += 1
      content = text_of(message["content"])
      is_error = content.match?(ERROR_MARKERS)
      error_outputs += 1 if is_error
      if is_error
        session_error = true
        last_error = true
      elsif last_error
        error_followed_by_non_error_output += 1
        last_error = false
      end
    end
  end
  error_sessions += 1 if session_error

  if session_error && (session_rephrase || users.length >= 2)
    structural_friction_sessions += 1
  end
  if session_error && messages.each_with_index.any? { |message, index| message["role"] == "user" && messages[index - 1]&.dig("role") == "tool" }
    resolution_candidate_sessions += 1
  end
end

receipt = {
  "schema_version" => "frankengate-dataclaw-structural-friction-audit-v1",
  "source" => {
    "dataset_id" => "ronaldcmz/Claude-Opus-Dataclaw-Unredacted",
    "dataset_revision" => "918e6fb39c916d3459ef338b4c3645622b9a5126",
    "path_sha256" => Digest::SHA256.file(input_path).hexdigest,
    "raw_content_committed" => false,
    "external_model_calls" => false
  },
  "cohort" => {
    "sessions" => sessions,
    "user_messages" => user_messages,
    "tool_outputs" => tool_outputs,
    "explicit_tool_output_messages" => explicit_tool_output_messages,
    "tool_call_messages" => tool_call_messages,
    "role_counts" => role_counts,
    "sessions_with_multiple_user_messages" => multi_user_sessions,
    "median_user_messages_per_session" => session_user_counts.sort[session_user_counts.length / 2]
  },
  "signals" => {
    "tool_error_outputs" => error_outputs,
    "sessions_with_tool_error" => error_sessions,
    "error_followed_by_non_error_tool_output" => error_followed_by_non_error_output,
    "adjacent_exact_repeat_pairs" => exact_repeat_pairs,
    "adjacent_rephrase_pairs" => rephrase_pairs,
    "sessions_with_rephrase_or_repeat" => rephrase_sessions,
    "user_messages_with_friction_markers" => user_marker_messages,
    "structural_friction_candidate_sessions" => structural_friction_sessions,
    "resolution_candidate_sessions" => resolution_candidate_sessions
  },
  "claim_boundary" => {
    "structural_signals_measured" => true,
    "explicit_tool_error_sequence_measured" => false,
    "human_friction_established" => false,
    "satisfaction_or_intent_established" => false,
    "skill_gap_established" => false,
    "causal_intervention_effect_established" => false,
    "promotion_authorized" => false,
    "reason" => "The projection exposes user and assistant messages plus tool calls but no explicit tool-result messages, so rephrase/retry candidates are measurable while error-to-success sequences are not. All signals can represent productive iteration and have no independent human labels here."
  },
  "decision" => "Use structural ordering and error-to-follow-up sequences to prioritize review; do not label friction, evals, skills, or memories automatically without independent adjudication and terminal outcomes."
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
puts JSON.generate(receipt)
