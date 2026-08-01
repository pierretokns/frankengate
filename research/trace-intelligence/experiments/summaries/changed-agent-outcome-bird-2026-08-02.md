# Changed-agent future-task outcome checkpoint

The sealed BIRD-SQL trace-mined-procedure factorial was independently
recomputed from task-level hashes and exact execution outcomes. The candidate
and no-skill control were evaluated on the same 20 family-disjoint held-out
tasks with an independent SQLite evaluator.

- Candidate wins: `0`
- Candidate losses: `0`
- Ties: `20`
- Exact-match mean delta: `0.0` (bootstrap CI `[0.0, 0.0]`, sign p `1.0`)
- Mean latency: candidate `10,355.6 ms`, control `10,467.7 ms` (ratio `0.989`)

This is a valid changed-agent future-task outcome measurement and a bounded
zero-headroom/no-lift result. It is not evidence of causal skill benefit,
cross-user transfer, friction reduction, or automatic Frankengate promotion.

Machine receipt: `experiments/results/changed-agent-outcome-bird-2026-08-02.json`.
