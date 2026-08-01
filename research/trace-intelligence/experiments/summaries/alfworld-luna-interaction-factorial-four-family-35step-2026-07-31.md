# Frontier skill–retrieved-memory interaction factorial

This independent combination test used four reset-environment arms on the same
four family-disjoint valid-unseen tasks at a 35-step horizon:

| arm | episodes | wins | win rate | invalid decisions | steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| no component | 4 | 0 | 0.00 | 0 | 140 |
| SkillOpt | 4 | 0 | 0.00 | 0 | 140 |
| retrieved memory | 4 | 0 | 0.00 | 0 | 140 |
| SkillOpt + retrieved memory | 4 | 0 | 0.00 | 0 | 140 |

All pairwise comparisons tied on all four tasks. Independent replay passed all
16 rows with zero mismatches and zero inadmissible executed actions. There was
no SkillOpt main effect, no retrieved-memory main effect, no positive
interaction, and no validity regression in this cohort.

This is a valid small factorial null, not a general claim that the mechanisms
cannot compose. The zero-success control leaves no measurable headroom, so a
larger task cohort with a non-floor baseline is required before rejecting or
promoting any composition. No Frankengate adapter is authorized.

Receipts:

- `experiments/results/alfworld-luna-interaction-factorial-four-family-35step-2026-07-31.json`
- `experiments/results/alfworld-luna-interaction-factorial-four-family-35step-verification-2026-07-31.json`
- `experiments/results/alfworld-luna-interaction-factorial-four-family-35step-paired-2026-07-31.json`
- `experiments/manifests/alfworld-luna-interaction-factorial-four-family-35step-2026-07-31.json`
