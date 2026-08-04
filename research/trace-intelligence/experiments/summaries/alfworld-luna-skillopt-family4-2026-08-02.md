# Frontier Luna SkillOpt checkpoint family replication

This is a four-family, held-out public ALFWorld replication using the Codex
subscription harness with `gpt-5.6-luna`. It compares the no-skill baseline,
a formatting placebo, and the published Microsoft SkillOpt ALFWorld checkpoint
(`gpt5.5_skill.md`). The four task hashes were previously unused by this
branch's ALFWorld receipts and cover `look_at_obj_in_light`,
`pick_and_place_simple`, `pick_clean_then_place_in_recep`, and
`pick_heat_then_place_in_recep`. Every arm received the same 12-step budget,
environment, model, and task order.

| arm | episodes | wins | win rate | invalid actions | mean wall time | verifier |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| no-skill | 4 | 0 | 0.00 | 0 | 78.4 s | pass |
| formatting placebo | 4 | 0 | 0.00 | 0 | 87.1 s | pass |
| published SkillOpt checkpoint | 4 | 0 | 0.00 | 0 | 103.0 s | pass |

The fresh-environment verifier replayed all 12 action sequences with zero
mismatches and confirmed that every executed action was admissible. The
SkillOpt checkpoint therefore produced no observed task-success lift over
either control on this four-family frontier slice. This is stronger model and
family coverage than the earlier two-task Codex pilots, but it remains
underpowered for a general skill claim: the 12-step horizon truncated all
episodes before a win, and there are no enterprise task labels or human outcome
annotations. Promotion remains closed.

The committed receipt contains only aggregate rows, controlled family labels,
action sequences, hashes, and timing; prompts, model responses, and raw user
trace content remain outside the checkout.

Receipts:

- `experiments/results/alfworld-luna-skillopt-family4-2026-08-02.json`
- `experiments/results/alfworld-luna-skillopt-family4-verification-2026-08-02.json`
