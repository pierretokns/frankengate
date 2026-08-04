# Frontier self-feedback loop on ALFWorld (four-family, 35-step)

This independent intervention tests whether a frontier model can improve a
fresh second attempt from its own first trajectory. The first attempt exposed
only bounded action names and aggregate outcome to the feedback synthesizer;
expert actions, expert horizons, hidden state, and future outcomes were never
exposed. Every second attempt ran in a reset environment.

| arm | episodes | wins | win rate | invalid decisions | steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| no feedback | 4 | 0 | 0.00 | 0 | 140 |
| formatting placebo | 4 | 0 | 0.00 | 0 | 140 |
| self feedback | 4 | 0 | 0.00 | 2 | 140 |

The paired result is four ties for self-feedback versus no-feedback and four
ties versus the formatting placebo. Self-feedback added two parser-invalid
decisions on one task; both controls added none. The independent fresh-
environment verifier passed all 12 rows with zero mismatches and zero
inadmissible executed actions.

This is a valid small negative signal for this particular feedback-loop
formulation: no success lift and a small protocol-validity regression. It is
not evidence that self-improvement, reflection, or SkillOpt in general cannot
work. All arms were 0/4 on this cohort despite expert solutions fitting within
the 35-step horizon, so a larger task cohort and a feedback protocol that
retains richer state-grounded evidence are required before a general claim.

Receipts:

- `experiments/results/alfworld-luna-self-feedback-four-family-35step-2026-07-31.json`
- `experiments/results/alfworld-luna-self-feedback-four-family-35step-verification-2026-07-31.json`
- `experiments/results/alfworld-luna-self-feedback-four-family-35step-paired-2026-07-31.json`
- `experiments/manifests/alfworld-luna-self-feedback-four-family-35step-2026-07-31.json`
