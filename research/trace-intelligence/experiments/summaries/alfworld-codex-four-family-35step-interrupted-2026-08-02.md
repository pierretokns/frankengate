# Frontier four-family ALFWorld attempt (interrupted)

An independent Codex-subscription attempt was started against four previously
unused `valid_unseen` ALFWorld paths, one each from four task families. The
planned arms were no-skill, formatting placebo, and the published Microsoft
SkillOpt checkpoint, with a 35-step horizon (12 episodes total).

The harness executes one Codex call per environment step and runs episodes
sequentially. The attempt was interrupted after the per-episode runtime made
the full matrix unbounded for this session. The process did not emit a
completed receipt, so **no partial episode is scored, replayed, or treated as
efficacy evidence**. The machine-readable record is a typed runtime null:
[`alfworld-codex-four-family-35step-interrupted-2026-08-02.json`](../results/alfworld-codex-four-family-35step-interrupted-2026-08-02.json).

This does not weaken the completed r9/r11/r12/r13/r14 cohorts, which have
aggregate receipts and fresh-environment replay verification. It only leaves
this additional frontier four-family cohort open for a bounded complete run.
