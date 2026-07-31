# BIRD-SQL skill-release feedback-loop gate (2026-07-31)

This receipt exercises the architecture-neutral MLOps loop against the sealed
BIRD-SQL factorial: collect → segment → cluster → retrieve → propose → replay
→ evaluate → release → monitor → rollback.

The candidate procedure had 3 exact results in 20 episodes, equal to no-skill
(3/20) and below the formatting placebo (4/20). The independent verifier passed,
but the promotion predicate requires a verified positive lift over no-skill and
no regression versus placebo. The candidate was therefore **quarantined** with
zero users, zero tasks, and zero canary exposure. Monitoring and rollback were
not started because no release occurred.

This demonstrates a real outcome-aware release gate and provenance chain, not
skill utility. No causal benefit or automatic promotion is claimed.

Artifact: `../results/bird-sql-skill-release-gate-2026-07-31.json`.
