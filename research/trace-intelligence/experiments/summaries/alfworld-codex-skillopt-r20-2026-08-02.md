# Codex SkillOpt transfer pilot (r20)

The real `gpt-5.6-luna` Codex-backed SkillOpt candidate was evaluated at an
eight-step horizon on one previously held-out ALFWorld task. No-skill,
formatting placebo, and the candidate each produced `0/1` wins. Every arm
made eight admissible actions with zero parser-invalid actions.

An independent fresh-environment verifier replayed all three action sequences
with zero mismatches. This is stronger than the earlier three-step pilot as a
horizon check, but it is still one task and therefore underpowered. It does
not establish causal skill utility or authorize promotion.
