# Codex SkillOpt transfer pilot

Microsoft SkillOpt generated a candidate with `gpt-5.6-luna` through the Codex
CLI subscription harness. The candidate was then compared with no-skill and a
formatting placebo on two previously held-out ALFWorld task paths.

All three arms were `0/2` wins over a three-step bounded pilot, with zero
invalid parser actions. A fresh ALFWorld verifier replayed all six action
sequences with zero mismatches and confirmed every executed action was
admissible.

This is the first real Codex-backed optimizer-transfer result. It does not
confirm skill utility: the horizon is intentionally short, the candidate was
rejected by SkillOpt's own selection gate, and the pilot is not powered for a
release decision. The candidate hash and model/harness metadata are in the
machine-readable receipt.
