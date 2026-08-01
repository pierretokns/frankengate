# SkillGen upstream mechanics audit (2026-08-01)

## Scope

This is a bounded, independent reproduction of the checked-out upstream
`yccm/SkillGen` source at commit `3c4537bb12ac287ceb1b5d410b491206089fdcb7`.
It is intentionally offline: no provider, model, benchmark, or external
judge was called. The audit checks mechanics that can be tested without
claiming an efficacy result.

## Results

- Python `compileall` completed successfully (`returncode=0`).
- Imports of `models`, `skill_store`, `router`, and `effectiveness` completed.
- Candidate-to-active promotion and JSON round-trip preserved the skill ID,
  body, and scripts; the helper module was emitted.
- A deterministic paired fixture exercised the effectiveness gate: one target
  repair and one boundary regression produced `paired_n=4`,
  `repair_count=1`, `regression_count=1`, `net_gain=0`, and `passed=false`.
  This validates accounting and the strict-positive gate, not model quality.
- A forced router exception returned `apply=false` with a `router_error:`
  reason, confirming fail-closed behavior.

Machine receipt: [`skillgen-upstream-mechanics-audit-2026-08-01.json`](../results/skillgen-upstream-mechanics-audit-2026-08-01.json).
Runner: [`skillgen_upstream_mechanics_audit.py`](../../skillgen_upstream_mechanics_audit.py).

## Interpretation and next gate

SkillGen is mechanically importable and its persistence, router safety, and
paired accounting contracts are reproducible. There is no bundled top-level
unit-test suite in this checkout, and this run did not sample trajectories,
induce a skill, replay an agent, or measure held-out task outcomes. Therefore
SkillGen remains **mechanics-reproduced / efficacy-unverified**. It must not be
integrated or promoted until a powered, independent benchmark run fixes the
model, task split, evaluator, horizon, and cost budget and reports paired
before/after outcomes with an independently checked grader.
