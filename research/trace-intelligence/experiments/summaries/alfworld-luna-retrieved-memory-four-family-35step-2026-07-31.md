# Retrieval-conditioned frontier memory on ALFWorld (four-family, 35-step)

Each held-out task was paired with one successful family-matched source episode
from a disjoint valid-seen split. The source was selected by a frozen family-key
retrieval policy, expert-preflighted, and distilled by `gpt-5.6-luna`. The
held-out agent saw only its released memory and live observation/action list.

| arm | episodes | wins | win rate | invalid decisions | steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| no memory | 4 | 0 | 0.00 | 0 | 140 |
| formatting placebo | 4 | 0 | 0.00 | 0 | 140 |
| retrieved memory | 4 | 0 | 0.00 | 0 | 140 |

Retrieved memory tied both controls on every paired target. All four source
expert preflights and all four memory-synthesis calls succeeded. Fresh
environment replay passed all 12 rows with zero mismatches and zero
inadmissible executed actions.

This is a valid small null for retrieval-conditioned memory: source selection
did not add measurable success or protocol-validity utility beyond the controls
on this cohort. It is not a general claim that vector retrieval, family
retrieval, or memory systems are ineffective; the target agent solved none of
the tasks, so a larger cohort with measurable control headroom is required.

Receipts:

- `experiments/results/alfworld-luna-retrieved-memory-four-family-35step-2026-07-31.json`
- `experiments/results/alfworld-luna-retrieved-memory-four-family-35step-verification-2026-07-31.json`
- `experiments/results/alfworld-luna-retrieved-memory-four-family-35step-paired-2026-07-31.json`
- `experiments/manifests/alfworld-luna-retrieved-memory-four-family-35step-2026-07-31.json`
