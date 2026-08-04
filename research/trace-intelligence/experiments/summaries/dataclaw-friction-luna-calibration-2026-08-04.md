# DataClaw friction-detector calibration (2026-08-04)

Eight messages from the real-user DataClaw history were sampled across broad
friction-language, re-prompt overlap, and neutral strata. Each was classified
twice by `gpt-5.6-luna` as `friction`, `productive_iteration`, or `unclear`.

- 16/16 calls returned valid labels; 7/8 rows repeated consistently.
- Silver labels across calls: 9 friction, 6 productive iteration, 1 unclear.
- All four re-prompt-overlap calls were labeled friction.
- The broad keyword detector over-flagged one clearly productive iteration and
  one ambiguous row; among its eight calls, five were friction, two were not,
  and one was unclear.
- The two neutral rows were labeled productive iteration on all four calls.

This supports treating re-prompt/correction structure as a high-value review
queue signal, while broad words such as “actually”, “still”, and “again” need
calibration. It does not establish friction precision, user intent, or outcome
causality: the labels are frontier silver labels and the sample is tiny.

Receipt and verifier:
`experiments/results/dataclaw-friction-luna-calibration-2026-08-04.json`.
Messages and model reasons are not emitted.
