# MLOps feedback-loop canary and rollback mechanics (2026-08-02)

The real intervention studies exercise the safety-critical quarantine path:
all non-improving memory, feedback, and skill candidates receive zero exposure.
This complementary deterministic fixture exercises the lifecycle path that
those real results cannot reach:

1. a verified candidate beats baseline and placebo without a validity
   regression;
2. the candidate is released to a 10% canary;
3. the first canary window is healthy;
4. the second window regresses below baseline and increases invalid actions;
5. the monitor triggers rollback and restores the previous artifact hash with
   zero canary exposure.

All ten lifecycle stages completed, including monitor and rollback. The run
made no model, database, or network calls, so it is **lifecycle mechanics
evidence only**, not model efficacy or production-release evidence.

Receipt: [`mlops-feedback-canary-rollback-2026-08-02.json`](../results/mlops-feedback-canary-rollback-2026-08-02.json).
