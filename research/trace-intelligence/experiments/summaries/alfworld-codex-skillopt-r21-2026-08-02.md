# Codex SkillOpt transfer pilot (r21)

The real `gpt-5.6-luna` Codex-backed SkillOpt candidate was evaluated on a
sealed `pick_clean_then_place_in_recep` task whose independent hand-coded
expert solved the task in six steps. With an eight-step cap, no-skill,
formatting placebo, and candidate were all `0/1` wins; each arm made eight
admissible actions with zero parser-invalid actions.

Fresh-environment replay verified all three sequences with zero mismatches.
This is a negative transfer result with a sufficient expert horizon, but it is
still one task and does not authorize promotion.
