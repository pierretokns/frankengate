#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "json"

def sha256(value)
  Digest::SHA256.hexdigest(value.to_s)
end

def q1_metrics(task)
  task.dig("answer", "exact_metrics", "q1") || {}
end

def q3_metrics(task)
  task.dig("answer", "exact_metrics", "q3") || {}
end

def full?(metrics)
  metrics["precision"] == 1.0 && metrics["recall"] == 1.0
end

def summarize_tasks(tasks)
  q1 = tasks.map { |task| q1_metrics(task) }
  q3 = tasks.map { |task| q3_metrics(task) }
  {
    "task_count" => tasks.length,
    "q1_full_count" => q1.count { |metrics| full?(metrics) },
    "q1_full_rate" => tasks.empty? ? 0.0 : q1.count { |metrics| full?(metrics) }.to_f / tasks.length,
    "q1_mean_recall" => tasks.empty? ? 0.0 : q1.sum { |metrics| metrics.fetch("recall", 0.0).to_f } / tasks.length,
    "q1_mean_precision" => tasks.empty? ? 0.0 : q1.sum { |metrics| metrics.fetch("precision", 0.0).to_f } / tasks.length,
    "q3_full_count" => q3.count { |metrics| full?(metrics) },
    "q3_full_rate" => tasks.empty? ? 0.0 : q3.count { |metrics| full?(metrics) }.to_f / tasks.length
  }
end

def paired(left, right)
  wins = losses = ties = 0
  left.each_with_index do |left_task, index|
    left_full = full?(q1_metrics(left_task))
    right_full = full?(q1_metrics(right[index]))
    if left_full && !right_full
      wins += 1
    elsif !left_full && right_full
      losses += 1
    else
      ties += 1
    end
  end
  {
    "left_wins" => wins,
    "left_losses" => losses,
    "ties" => ties,
    "paired_task_count" => left.length,
    "interpretation" => "Descriptive task-level q1-full comparison; no causal inference when receipts came from separate runs."
  }
end

primary_path = ARGV.fetch(0)
composite_path = ARGV.fetch(1)
output_path = ARGV.fetch(2)
primary = JSON.parse(File.read(primary_path))
composite = JSON.parse(File.read(composite_path))

primary_tasks = primary.fetch("tasks")
by_arm = {}
primary_tasks.each do |task|
  task.fetch("arms").each do |arm|
    (by_arm[arm.fetch("arm")] ||= []) << arm
  end
end

# The composite receipt is a separate run, so retain only a task-hash join and
# label all comparisons as descriptive rather than treating them as randomized.
composite_tasks = composite.fetch("tasks")
composite_by_id = composite_tasks.to_h { |task| [task.fetch("task_id"), task] }
shared_ids = primary_tasks.map { |task| task.fetch("task_id") }.select { |id| composite_by_id.key?(id) }
composite_join = shared_ids.map do |task_id|
  primary_task = primary_tasks.find { |task| task.fetch("task_id") == task_id }
  composite_task = composite_by_id.fetch(task_id)
  {
    "task_id_sha256" => sha256(task_id),
    "primary_null_q1_full" => full?(q1_metrics(primary_task.fetch("arms").find { |arm| arm.fetch("arm") == "none" })),
    "primary_human_q1_full" => full?(q1_metrics(primary_task.fetch("arms").find { |arm| arm.fetch("arm") == "human_authored" })),
    "composite_q1_full" => full?(q1_metrics(composite_task))
  }
end

receipt = {
  "schema" => "frankengate-skilllearnbench-paired-statistics-v1",
  "sources" => {
    "three_arm_receipt_sha256" => Digest::SHA256.file(primary_path).hexdigest,
    "composite_receipt_sha256" => Digest::SHA256.file(composite_path).hexdigest,
    "dataset_revision" => primary.dig("source", "dataset_revision"),
    "raw_content_committed" => false
  },
  "arms" => by_arm.transform_values { |tasks| summarize_tasks(tasks) },
  "paired_within_three_arm_run" => {
    "human_authored_vs_none" => paired(by_arm.fetch("human_authored"), by_arm.fetch("none")),
    "generated_vs_none" => paired(by_arm.fetch("b1-one-shot-claude-sonnet-4-6"), by_arm.fetch("none"))
  },
  "separate_run_composite_join" => {
    "shared_task_count" => composite_join.length,
    "composite_answer_present_count" => composite_tasks.count { |task| task.dig("answer", "exact_metrics", "q1") },
    "receipt_metadata_completed_tasks" => composite.dig("execution", "completed_tasks"),
    "receipt_metadata_answer_presence_mismatch" => composite.dig("execution", "completed_tasks").to_i != composite_tasks.count { |task| task.dig("answer", "exact_metrics", "q1") },
    "composite_q1_full_count" => composite_join.count { |row| row["composite_q1_full"] },
    "composite_vs_none" => {
      "wins" => composite_join.count { |row| row["composite_q1_full"] && !row["primary_null_q1_full"] },
      "losses" => composite_join.count { |row| !row["composite_q1_full"] && row["primary_null_q1_full"] }
    },
    "composite_vs_human" => {
      "wins" => composite_join.count { |row| row["composite_q1_full"] && !row["primary_human_q1_full"] },
      "losses" => composite_join.count { |row| !row["composite_q1_full"] && row["primary_human_q1_full"] }
    },
    "task_rows" => composite_join,
    "claim_boundary" => "Separate-run descriptive join; not a randomized comparison or causal estimate."
  },
  "claim_boundary" => {
    "task_level_verifier_statistics_measured" => true,
    "skill_causal_utility_proven" => false,
    "enterprise_transfer_proven" => false,
    "reason" => "One public task family, host-harness adaptation, incomplete q2 labels, and separate composite/control runs."
  }
}

File.write(output_path, JSON.pretty_generate(receipt) + "\n")
join_summary = receipt["separate_run_composite_join"].dup
join_summary.delete("task_rows")
puts JSON.generate({"arms" => receipt["arms"], "paired" => receipt["paired_within_three_arm_run"], "composite_join" => join_summary})
