# Frontier Luna SkillOpt fair-horizon replay

This follow-up holds the task and model fixed while extending the four-family
pilot's 12-step budget to 35 steps on one held-out `look_at_obj_in_light`
task. It compares no-skill, formatting placebo, and the published Microsoft
SkillOpt ALFWorld checkpoint through the Codex subscription harness with
`gpt-5.6-luna`.

| arm | steps | wins | invalid actions | terminal outcome | wall time |
| --- | ---: | ---: | ---: | --- | ---: |
| no-skill | 35 | 0 | 0 | no win | 241.0 s |
| formatting placebo | 35 | 0 | 0 | no win | 251.1 s |
| SkillOpt checkpoint | 35 | 0 | 0 | no win | 326.7 s |

The fresh-environment verifier replayed all three 35-action sequences with
zero mismatches and confirmed that all executed actions were admissible. The
longer horizon removes the 12-step truncation explanation for this task, but
the result is still a one-task model/harness slice and cannot establish a
general skill effect or enterprise transfer. The checkpoint remains
non-promotable.

Receipts:

- `experiments/results/alfworld-luna-skillopt-long-horizon-2026-08-02.json`
- `experiments/results/alfworld-luna-skillopt-long-horizon-verification-2026-08-02.json`
