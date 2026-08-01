# Integration promotion audit (2026-08-02)

The machine-readable receipt in `../results/integration-promotion-audit-2026-08-02.json`
is the release boundary for the current independent research program. It records
eleven tested mechanisms, their source receipt hashes, and an explicit disposition.

**Decision: zero mechanisms are eligible for automatic Frankengate integration.**

- SkillGen, RHO, and Codex-adapted ReasoningBank are quarantined after negative
  matched held-out utility on the bounded slices.
- SkillOpt is utility-unproven at the measured horizon; GEPA produced no holdout
  lift.
- MATM retrieval and governed PostgreSQL are shadow-only: offline retrieval or
  RLS/backend mechanics do not establish changed-agent or enterprise utility.
- The MLOps canary/rollback loop is mechanics-only until a real candidate passes
  an independent outcome gate.
- The Azure ReasoningBank path is provider-unavailable; Graphiti/LangMem is
  incomplete in the natural run; the AgentRx artifact is blocked by static
  trigger/compile defects.

This is not a universal rejection of the methods. It is a promotion rule: a
mechanism must first beat a matched control on an adequately powered, independently
graded held-out outcome before it can affect production traces, memory, skills, or
user-facing recommendations. Passing infrastructure tests or a self-preference
judge is insufficient.
