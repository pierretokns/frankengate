#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def read_receipts(arguments)
  arguments.to_h do |argument|
    key, path = argument.split("=", 2)
    raise ArgumentError, "expected key=path" unless key && path

    [key, [path, JSON.parse(File.read(path))]]
  end
end

def sha(path)
  Digest::SHA256.file(path).hexdigest
end

def rounded(value)
  value.round(6)
end

inputs = read_receipts(ARGV)
paths = inputs.transform_values(&:first)
receipts = inputs.transform_values(&:last)

wmh = receipts.fetch("wmh")
alias_cascade = receipts.fetch("alias")
adapter = receipts.fetch("adapter")
claude_adapter = receipts.fetch("claude_adapter")
dataclaw_adapter = receipts.fetch("dataclaw")
identifier = receipts.fetch("identifier")
trajectory = receipts.fetch("trajectory")

wmh_arms = wmh.fetch("arms")
alias_arms = alias_cascade.fetch("arms")
adapter_arms = adapter.fetch("arms")
claude_prompt = claude_adapter.dig("aggregate", "prompt")
claude_all = claude_adapter.dig("aggregate", "all")
dataclaw_combined = dataclaw_adapter.dig("aggregate", "combined")
dataclaw_tool = dataclaw_adapter.dig("aggregate", "tool")
trajectory_prompt = trajectory.dig("summary", "prompt_only")
trajectory_context = trajectory.dig("summary", "trajectory")

observations = {
  "wmh_bird_dense_vs_lexical" => {
    "mrr_delta" => rounded(wmh_arms.dig("dense", "strict_mrr") - wmh_arms.dig("lexical", "strict_mrr")),
    "recall_at_1_delta" => rounded(wmh_arms.dig("dense", "strict_recall_at_1") - wmh_arms.dig("lexical", "strict_recall_at_1")),
    "compatible_selection_delta" => rounded(wmh_arms.dig("dense", "compatible_selected_rate") - wmh_arms.dig("lexical", "compatible_selected_rate")),
    "invalid_selection_delta" => rounded(wmh_arms.dig("dense", "invalid_selected_count") - wmh_arms.dig("lexical", "invalid_selected_count")),
    "records" => wmh_arms.dig("dense", "records")
  },
  "wmh_bird_frontier_vs_dense" => {
    "mrr_delta" => rounded(wmh_arms.dig("frontier", "strict_mrr") - wmh_arms.dig("dense", "strict_mrr")),
    "recall_at_1_delta" => rounded(wmh_arms.dig("frontier", "strict_recall_at_1") - wmh_arms.dig("dense", "strict_recall_at_1")),
    "compatible_selection_delta" => rounded(wmh_arms.dig("frontier", "compatible_selected_rate") - wmh_arms.dig("dense", "compatible_selected_rate")),
    "invalid_selection_delta" => rounded(wmh_arms.dig("frontier", "invalid_selected_count") - wmh_arms.dig("dense", "invalid_selected_count")),
    "records" => wmh_arms.dig("frontier", "records")
  },
  "alias_frontier_vs_exact" => {
    "mrr_delta" => rounded(alias_arms.dig("frontier_scope", "targeted_mrr") - alias_arms.dig("exact_scope", "targeted_mrr")),
    "recall_at_1_delta" => rounded(alias_arms.dig("frontier_scope", "targeted_recall_at_1") - alias_arms.dig("exact_scope", "targeted_recall_at_1")),
    "nil_candidate_rate_frontier" => alias_arms.dig("frontier_scope", "nil_top1_candidate_rate"),
    "nil_candidate_rate_exact" => alias_arms.dig("exact_scope", "nil_top1_candidate_rate"),
    "targeted_cases" => alias_arms.dig("frontier_scope", "targeted_cases")
  },
  "adapter_vs_dense" => {
    "mrr_delta" => rounded(adapter_arms.dig("adapted", "strict_mrr") - adapter_arms.dig("dense", "strict_mrr")),
    "recall_at_1_delta" => rounded(adapter_arms.dig("adapted", "strict_recall_at_1") - adapter_arms.dig("dense", "strict_recall_at_1")),
    "recall_at_5_delta" => rounded(adapter_arms.dig("adapted", "strict_recall_at_5") - adapter_arms.dig("dense", "strict_recall_at_5")),
    "invalid_selection_delta" => rounded(adapter_arms.dig("adapted", "invalid_selected_count") - adapter_arms.dig("dense", "invalid_selected_count")),
    "records" => adapter_arms.dig("adapted", "records")
  },
  "claude_project_adaptation" => {
    "prompt_mrr_delta" => rounded(claude_prompt.fetch("adapted_mrr") - claude_prompt.fetch("baseline_mrr")),
    "all_mrr_delta" => rounded(claude_all.fetch("adapted_mrr") - claude_all.fetch("baseline_mrr")),
    "prompt_recall_at_1_delta" => rounded(claude_prompt.fetch("adapted_recall_at_1") - claude_prompt.fetch("baseline_recall_at_1")),
    "all_recall_at_1_delta" => rounded(claude_all.fetch("adapted_recall_at_1") - claude_all.fetch("baseline_recall_at_1")),
    "prompt_projects" => claude_prompt.fetch("eligible_projects"),
    "all_sessions" => claude_all.fetch("eligible_sessions")
  },
  "dataclaw_project_adaptation" => {
    "combined_mrr_delta" => rounded(dataclaw_combined.fetch("adapted_mrr") - dataclaw_combined.fetch("baseline_mrr")),
    "combined_recall_at_1_delta" => rounded(dataclaw_combined.fetch("adapted_recall_at_1") - dataclaw_combined.fetch("baseline_recall_at_1")),
    "tool_mrr_delta" => rounded(dataclaw_tool.fetch("adapted_mrr") - dataclaw_tool.fetch("baseline_mrr")),
    "tool_recall_at_1_delta" => rounded(dataclaw_tool.fetch("adapted_recall_at_1") - dataclaw_tool.fetch("baseline_recall_at_1")),
    "projects" => dataclaw_combined.fetch("eligible_projects"),
    "sessions" => dataclaw_combined.fetch("eligible_sessions")
  },
  "trajectory_context_vs_prompt" => {
    "prompt_abstain" => trajectory_prompt.fetch("abstain"),
    "trajectory_abstain" => trajectory_context.fetch("abstain"),
    "trajectory_correct_predictions" => trajectory_context.fetch("correct_true_positive") + trajectory_context.fetch("correct_true_negative"),
    "trajectory_false_positives" => trajectory_context.fetch("correct_false_positive"),
    "trajectory_replayable" => trajectory_context.fetch("replayability_replayable"),
    "trajectory_elapsed_ms" => trajectory_context.fetch("elapsed_ms_total"),
    "prompt_elapsed_ms" => trajectory_prompt.fetch("elapsed_ms_total")
  },
  "identifier_safety" => {
    "mrr" => identifier.dig("aggregate", "identifier_reranker", "mrr"),
    "recall_at_1" => identifier.dig("aggregate", "identifier_reranker", "recall_at_1"),
    "same_scope_collision_before_target" => identifier.dig("aggregate", "identifier_reranker", "same_scope_collision_before_target"),
    "cases" => identifier.dig("aggregate", "identifier_reranker", "cases")
  }
}

result = {
  "schema_version" => "frankengate-cascade-receipt-audit-v1",
  "input_receipts" => paths.transform_values { |path| {"sha256" => sha(path), "raw_content_committed" => false} },
  "observations" => observations,
  "claim_boundary" => {
    "new_task_outcome_measured" => false,
    "enterprise_semantic_quality_established" => false,
    "custom_embedding_promotion_established" => false,
    "interpretation" => "This is a cross-receipt arithmetic and stage-comparison audit. It does not pool examples, create independent labels, or establish causal utility."
  }
}
result["result_sha256"] = Digest::SHA256.hexdigest(JSON.generate(result))

output = ENV.fetch("CASCADE_AUDIT_OUTPUT")
File.write(output, JSON.pretty_generate(result) + "\n")
puts JSON.generate({"output" => output, "result_sha256" => result["result_sha256"]})
