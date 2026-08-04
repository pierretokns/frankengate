#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def load_inputs(arguments)
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

inputs = load_inputs(ARGV)
paths = inputs.transform_values(&:first)
receipts = inputs.transform_values(&:last)
miner = receipts.fetch("miner")
temporal = receipts.fetch("temporal")
drift = receipts.fetch("drift")
normalization = receipts.fetch("normalization")
cross_cohort = receipts.fetch("cross_cohort")
codex = receipts.fetch("codex")

exact = normalization.dig("representations", "exact")
normalized = normalization.dig("representations", "normalized")
cross_exact = cross_cohort.dig("cross_cohort_transfer", "exact")
cross_normalized = cross_cohort.dig("cross_cohort_transfer", "normalized")
codex_aggregate = codex.fetch("aggregate")

observations = {
  "claude_recurrence" => {
    "paired_calls" => miner.dig("coverage", "paired_tool_call_count"),
    "successful_recurring_artifacts" => miner.dig("recurrence", "successful_artifacts_recurring_across_sessions"),
    "cross_project_successful_artifacts" => miner.dig("recurrence", "successful_artifacts_recurring_across_projects"),
    "mixed_outcome_artifacts" => miner.dig("recurrence", "artifacts_recurring_with_mixed_outcomes"),
    "error_to_success_recoveries" => miner.dig("recurrence", "error_to_success_recovery_count")
  },
  "claude_temporal_exact" => {
    "same_project_lift" => temporal.dig("comparison", "same_project_lift_vs_no_prior"),
    "other_project_lift" => temporal.dig("comparison", "other_project_lift_vs_no_prior"),
    "same_project_keyshape_lift" => temporal.dig("comparison", "parameter_same_project_lift_vs_no_prior_keyshape"),
    "other_project_keyshape_lift" => temporal.dig("comparison", "parameter_other_project_lift_vs_no_prior_keyshape")
  },
  "claude_frozen_drift" => {
    "same_project_exact_lift" => drift.dig("comparison", "early_same_project_lift_vs_no_early_prior"),
    "other_project_exact_lift" => drift.dig("comparison", "early_other_project_lift_vs_no_early_prior"),
    "same_project_keyshape_lift" => drift.dig("comparison", "early_same_project_keyshape_lift_vs_no_early_prior_keyshape"),
    "other_project_keyshape_lift" => drift.dig("comparison", "early_other_project_keyshape_lift_vs_no_early_prior_keyshape")
  },
  "normalization_collision" => {
    "extra_exact_command_collisions" => normalized.fetch("parameterized_extra_exact_command_collisions"),
    "multi_exact_buckets" => normalized.fetch("parameterized_buckets_with_multiple_exact_commands"),
    "mixed_outcome_buckets" => normalized.fetch("mixed_outcome_artifact_buckets"),
    "exact_mixed_outcome_buckets" => exact.fetch("mixed_outcome_artifact_buckets")
  },
  "cross_cohort_transfer" => {
    "exact_artifacts" => cross_exact.fetch("cross_cohort_artifact_count"),
    "exact_occurrences" => cross_exact.fetch("eligible_occurrences"),
    "exact_success_rate" => cross_exact.fetch("cross_cohort_success_rate"),
    "normalized_artifacts" => cross_normalized.fetch("cross_cohort_artifact_count"),
    "normalized_occurrences" => cross_normalized.fetch("eligible_occurrences"),
    "normalized_success_rate" => cross_normalized.fetch("cross_cohort_success_rate")
  },
  "codex_scope_transfer" => {
    "same_scope_success_rate" => rounded(codex_aggregate.fetch("same_scope_prior_success_later_success").fdiv(codex_aggregate.fetch("repeated_occurrences_after_same_scope_success"))),
    "other_scope_success_rate" => rounded(codex_aggregate.fetch("other_scope_prior_success_later_success").fdiv(codex_aggregate.fetch("other_scope_prior_success_later_success") + codex_aggregate.fetch("other_scope_prior_success_later_failure"))),
    "overall_success_rate" => rounded(codex_aggregate.fetch("success_occurrences").fdiv(codex_aggregate.fetch("labeled_command_occurrences"))),
    "same_scope_repeats" => codex_aggregate.fetch("repeated_occurrences_after_same_scope_success"),
    "other_scope_reuses" => codex_aggregate.fetch("other_scope_prior_success_later_success") + codex_aggregate.fetch("other_scope_prior_success_later_failure")
  }
}

result = {
  "schema_version" => "frankengate-artifact-promotion-audit-v1",
  "input_receipts" => paths.transform_values { |path| {"sha256" => sha(path), "raw_content_committed" => false} },
  "observations" => observations,
  "claim_boundary" => {
    "semantic_correctness_established" => false,
    "safe_replay_established" => false,
    "causal_user_benefit_established" => false,
    "interpretation" => "Exact scoped recurrence is an operational candidate prior; normalization, cross-scope transfer, process exit, and is_error are not semantic correctness or authorization labels."
  }
}
result["result_sha256"] = Digest::SHA256.hexdigest(JSON.generate(result))

output = ENV.fetch("ARTIFACT_AUDIT_OUTPUT")
File.write(output, JSON.pretty_generate(result) + "\n")
puts JSON.generate({"output" => output, "result_sha256" => result["result_sha256"]})
