# Codex rollout history friction screen — 2026-08-02

This is a schema comparison run over 34 Codex rollout sessions available in
two locally cached public-history sources. It is deliberately small and
heterogeneous, not a representative sample of all Codex users. Raw content was
read from private temporary paths and was not committed.

| Signal | Count |
| --- | ---: |
| sessions | 34 |
| explicit user messages | 49 |
| assistant messages | 2,310 |
| function calls | 3,182 |
| function-call outputs | 3,175 |
| non-zero exit-code outputs | 255 |
| keyword error markers in output (screening only) | 535 |
| explicit correction signals | 4 |
| retry/repair signals | 13 |
| exact adjacent prompt repeats | 17 |
| repeated function-call signatures | 563 across 29 sessions |

The Codex format exposes structured `exit_code` values, which gives a stronger
executor-outcome signal than output-text matching. The 255 non-zero exits are
not user-friction labels: exploratory commands, expected negative tests, and
an agent that recovers can all produce them. The 17 repeated prompts are also
not automatically dissatisfaction. The cohort is too small for rates or
cross-harness conclusions.

The adapter and result are useful as a contract test: Claude and Codex can be
projected into the same episode-level fields while retaining native provenance
and keeping structured executor outcomes separate from language-level friction
signals. The next step is the same stratified, blinded adjudication used for
the Claude cohort, followed by replayable-eval promotion only when an expected
artifact or validator is present.

