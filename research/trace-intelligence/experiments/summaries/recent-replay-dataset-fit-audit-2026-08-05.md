# Recent replay/diagnosis dataset fit audit (2026-08-05)

This audit uses pinned local checkouts of
[TRAIL](https://github.com/patronus-ai/trail-benchmark) and
[Recovery-Bench](https://github.com/letta-ai/recovery-bench). It records
counts and field availability only; no prompts, commands, tool arguments, or
raw trace content is copied into this repository. The machine-readable receipt
is [`recent-replay-dataset-fit-audit-2026-08-05.json`](../results/recent-replay-dataset-fit-audit-2026-08-05.json).

## What the datasets actually contain

### TRAIL

- 148 OTel-shaped records: 117 GAIA and 31 SWE Bench.
- 154 spans, four project IDs, and four service names.
- 147 annotation files parse, but only 142 unique annotation trace IDs align
  with the 148 data trace IDs; one annotation file is malformed. Effective
  trace-ID coverage is `0.959459`.
- 836 annotated errors are parseable in this checkout (the upstream README says
  841, but the malformed annotation file prevents reproducing that total
  exactly); the labels do include
  categories and HIGH/MEDIUM/LOW impact, plus reliability/security/
  instruction-adherence/plan-opt scores.
- No principal or tenant identity fields were present. `pat.project.id` is a
  workload/project proxy, not a person or enterprise identity.
- The span status distribution is mostly `Unset` (143/154); this is not an
  independent task-success outcome.

**Fit:** good for independent first-fault/error-taxonomy calibration and
AgentRx/Signals-style diagnosis prompts. It is not evidence for cross-user
similarity, skill gaps, enterprise intent, or causal skill improvement.

### Recovery-Bench

- The acquired LFS checkout contains 89 trial result files and 89 ATIF-v1.6
  trajectories for 89 unique Terminal-Bench tasks.
- Verifier rewards are 62 failures, 25 successes, and 2 records without a
  readable reward file. The 62 failures are the usable initial failure set for
  a recovery intervention.
- The trajectories contain 4,348 agent steps, 89 user task steps, and 5,148
  tool-call records. The model/agent is single-condition in this checkout
  (`claude-haiku-4-5-20251001` / `terminus-2`) and the environment is Modal.
- No recovery-agent result files are present; all result files are under the
  `initial-*` run. Thus the checkout supplies failure-state replay fixtures,
  not a measured recovery-treatment comparison.
- The repository checkout has no license file. Keep raw LFS data outside the
  Frankengate repository and obtain permission before redistribution or
  publication.

**Fit:** the closest public fixture for diagnosis → replay → recovery. It is
ready for a separately funded baseline that runs no-context/full-context/
summary recovery agents on the 62 failed tasks. It is not yet evidence that a
mined skill improves recovery.

## Claim boundary

Neither corpus satisfies the enterprise causal gate: stable principal/team/
project/system/time identity, independent task-intent labels, hard-negative
and NIL strata, changed-system replay, and independent outcome verification.
The audit therefore sets `ready_for_enterprise_causal_skill_claim=false` while
setting diagnosis calibration and recovery-fixture readiness true.

The next fair experiment is to hold the failure tasks fixed and compare:

1. no prior trajectory context;
2. full failed trajectory;
3. a structured summary;
4. a diagnosed/reviewed artifact or skill;
5. a formatting/placebo control.

Every arm needs task-disjoint episodes, verifier reward, repair-regression
checks, tool/cost/latency receipts, and explicit abstention on unusable traces.
Only after that baseline should we compare SkillOpt/SkillRL/Trace2Skill-style
interventions or claim transfer into Frankengate.
