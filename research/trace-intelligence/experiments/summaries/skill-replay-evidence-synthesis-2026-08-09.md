# Skill and artifact replay evidence synthesis (2026-08-09)

This synthesis keeps four independent protocols separate. It is a decision map,
not a pooled effect estimate.

## What actually worked

| Intervention | Evidence | Decision |
|---|---|---|
| Reviewed human guidance under changed data | SkillLearnBench one-task/two-run mutation: null recall `.9375`, reviewed guidance `1.0`, generated composite `.9375`; reviewed precision `1.0`. | Keep reviewed guidance as a candidate arm; do not infer a general skill effect from one task. |
| Typed semantic-ID subplan admission | Five changed-system fixtures: name-only accepted `5/5` with 2 unsafe accepts; semantic-ID admission accepted `3/3` with 0 unsafe accepts. | Promote the admission/gating pattern, not mined content. |
| Validated subplan composition | Two replays over 20 family-disjoint BIRD tasks: composed `8/40`, no-skill `6/40`, placebo `6/40`; one stable win, zero stable losses, 19 ties/mixed. | Directionally promising, underpowered, and low-headroom; keep behind replay and scope gates. |

## What did not improve outcomes

| Intervention | Evidence | Decision |
|---|---|---|
| Generic trace-mined SQL procedure | Family-disjoint BIRD factorial: trace-mined `8/40`, no-skill `8/40`, placebo `5/40`; latency was also higher than no-skill. | No promotion; this is a null causal result on the tested consumer. |
| SkillOpt candidate on ALFWorld | Codex/Luna, two unseen tasks: no-skill `0/2`, placebo `0/2`, candidate `0/2`. | Negative bounded replication; not a disproof of SkillOpt's published results. |
| Generated composition under changed data | Composite retained precision but missed one expected ID in the second run. | Treat automatic composition as a regression risk until task-disjoint changed fixtures pass. |
| Name-only artifact reuse | Accepted both semantic collision cases in the deterministic changed-system replay. | Never use name-only admission; require typed semantic identity and verification. |

## Practical adoption boundary

```text
trace candidate
  -> typed scope / semantic-ID / authority admission
  -> independent replay on the current system
  -> reviewed or generated procedure as a candidate
  -> no-skill / placebo / reviewed / mined / composed comparison
  -> changed-system outcome and rollback gate
```

The strongest positive is a control pattern—typed admission plus reviewed
guidance—not automatic skill mining. Reusable validated subplans are worth
testing as a separate artifact granularity, but the evidence does not support
global memory, raw-log skill promotion, or automatic composition.

## Remaining causal gate

Run a powered, task-disjoint changed-system cohort with at least two principals
or teams and independent terminal outcomes. Keep no-skill, formatting placebo,
reviewed guidance, trace-mined, SkillGen/SkillOpt/RHO, and composed arms
separate; include irrelevant-library NILs, semantic collisions, schema drift,
and rollback. Do not pool public proxy outcomes as if they were enterprise
effect sizes.

Tracking: [skill improvement #111](https://github.com/pierretokns/frankengate/issues/111),
[artifact reuse #119](https://github.com/pierretokns/frankengate/issues/119),
and [changed-system research epic #118](https://github.com/pierretokns/frankengate/issues/118).

## Receipts

- [synthesis result](../results/skill-replay-evidence-synthesis-2026-08-09.json)
- [independent verification](../results/skill-replay-evidence-synthesis-verification-2026-08-09.json)
- [`skill_replay_evidence_synthesis.py`](../../skill_replay_evidence_synthesis.py)
- [`verify_skill_replay_evidence_synthesis.py`](../../verify_skill_replay_evidence_synthesis.py)
