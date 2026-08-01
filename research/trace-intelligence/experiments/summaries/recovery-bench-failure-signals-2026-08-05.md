# Recovery-Bench failure-signal mining (2026-08-05)

This experiment mined only structural features from the 62 failed initial
Recovery-Bench trajectories. It did not emit prompts, commands, tool
arguments, task names, or trace content. Each signature combines coarse step,
tool, and observation buckets, dominant tool family, error flags, and the
terminal completion flag.

## Result

The cohort contained 47 coarse signatures, 11 signatures repeated at least
twice, and 3 with support of at least three. A deterministic top-25% signal
selection (15 trajectories) was compared with a trajectory-length baseline and
32 deterministic random selections:

| selector | repeated-mode rate | support-3-mode rate | unique modes |
| --- | ---: | ---: | ---: |
| error-signal score | `.6000` | `.2667` | 13 |
| length baseline | `.7333` | `.4000` | 9 |
| random mean | `.4146` | `.1708` | 13.81 |

Cheap signals therefore concentrated recurring modes better than random, but
did not beat the length baseline. This is a useful negative result: a Signals-
style detector is a plausible triage feature, not a demonstrated best selector
for reusable recovery skills.

Receipt:
[`recovery-bench-failure-signals-2026-08-05.json`](../results/recovery-bench-failure-signals-2026-08-05.json).

## Boundary and next test

No recovery outcomes were present, so no signature can be called a skill or
repair procedure. The next fair experiment should keep the 62-task failure set
fixed, add blinded failure-category labels and recovery rewards, and compare
signal-only, length-only, combined, and random candidate selection before
testing SkillOpt/SkillRL/Trace2Skill-style interventions.
