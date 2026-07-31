# Frontier Luna meaningful-trace procedure extraction

This follow-up corrected the earlier deterministic sample selection. It admits
only public Wisp sessions with at least 20 observed tool calls and one recovery
candidate, avoiding empty or malformed fixture files. Four eligible sessions
were evaluated using content-free structural summaries and `gpt-5.6-luna` via
the Codex subscription harness.

Luna returned valid JSON for all four sessions and passed the controlled
evidence-grounding/procedure-shape rubric for 3/4. The independent verifier
passed all four rows. This is stronger evidence about frontier structured
proposal generation than the earlier 1/3 mixed-fixture sample, but it still
does not measure procedure utility, changed-system outcomes, causal skill
benefit, or enterprise transfer.

The first sandboxed attempt is retained as a typed harness failure and is not
counted as model evidence. The successful receipt is:
`experiments/results/natural-model-dream-procedure-luna-meaningful-2026-08-02.json`.
