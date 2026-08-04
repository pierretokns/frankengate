#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def load(path)
  [path, JSON.parse(File.read(path))]
end

def sha(path)
  Digest::SHA256.file(path).hexdigest
end

def check(name, expected, actual)
  {"name" => name, "expected" => expected, "actual" => actual, "pass" => expected == actual}
end

paths = {}
receipts = {}
ARGV.each do |argument|
  key, path = argument.split("=", 2)
  raise ArgumentError, "expected key=path" unless key && path
  paths[key] = path
  receipts[key] = JSON.parse(File.read(path))
end

frontier = receipts.fetch("frontier")
parameterized = receipts.fetch("parameterized")
adapter = receipts.fetch("adapter")
reranker = receipts.fetch("reranker")
acronym = receipts.fetch("acronym")
context = receipts.fetch("context")
recurrence = receipts.fetch("recurrence")
hard_negative = receipts.fetch("hard_negative")
composite = receipts.fetch("composite")

checks = []
checks << check("frontier_valid_calls", 48, frontier["valid_call_count"])
checks << check("frontier_unanimous_candidates", 11, frontier["agreement_count"])
checks << check("parameterized_positive_targets", 52, parameterized.dig("aggregate", "template_gate", "targets"))
checks << check("parameterized_positive_top1", 52, parameterized.dig("aggregate", "template_gate", "top1_correct"))
checks << check("parameterized_nil_abstentions", 10, parameterized.dig("aggregate", "template_gate", "abstained_nil"))
checks << check("adapter_records", 44, adapter.dig("arms", "adapted", "records"))
checks << check("adapter_mrr", 0.947917, adapter.dig("arms", "adapted", "strict_mrr"))
checks << check("identifier_reranker_cases", 17, reranker.dig("aggregate", "identifier_reranker", "cases"))
checks << check("identifier_reranker_mrr", 0.736567, reranker.dig("aggregate", "identifier_reranker", "mrr"))
checks << check("acronym_unique", 40, acronym.dig("valid_acronym_cohort_frequency", "unique_acronyms"))
checks << check("acronym_cross_cohort", 0, acronym.dig("valid_acronym_cohort_frequency", "two_or_more_cohorts"))
checks << check("context_term_only_valid", 24, context.dig("summary", "term_only", "high_context", "valid_call_count").to_i + context.dig("summary", "term_only", "low_context", "valid_call_count").to_i)
checks << check("context_low_overlap_agreement", 3, context.dig("summary", "term_plus_context", "low_context", "pair_agreement_count"))
checks << check("recurrence_shape_same_project_rate", 0.15870746354017728, recurrence.dig("events", "shape_same_project_rate"))
checks << check("recurrence_digest_same_project_rate", 0.06405490420360309, recurrence.dig("events", "digest_same_project_rate"))
checks << check("hard_negative_train_same_surface_diff_path", 2610, hard_negative.dig("chronological_train_only", "candidate_strata", "same_project_same_surface_different_path"))
checks << check("hard_negative_train_cross_project_diff_path", 1601, hard_negative.dig("chronological_train_only", "candidate_strata", "cross_project_same_surface_different_path"))
checks << check("composite_answer_presence", 5, composite.dig("separate_run_composite_join", "composite_answer_present_count"))
checks << check("composite_metadata_mismatch", true, composite.dig("separate_run_composite_join", "receipt_metadata_answer_presence_mismatch"))

result = {
  "schema" => "frankengate-headline-receipt-consistency-audit-v1",
  "receipts" => paths.transform_values { |path| {"sha256" => sha(path), "raw_content_committed" => false} },
  "checks" => checks,
  "passed" => checks.all? { |entry| entry["pass"] },
  "claim_boundary" => "This verifies published aggregate arithmetic and receipt consistency only; it does not upgrade proxy labels into enterprise semantic truth or causal utility."
}
output = ENV.fetch("AUDIT_OUTPUT")
File.write(output, JSON.pretty_generate(result) + "\n")
puts JSON.generate({"passed" => result["passed"], "failed_checks" => checks.reject { |entry| entry["pass"] }.map { |entry| entry["name"] }})
exit(result["passed"] ? 0 : 1)
