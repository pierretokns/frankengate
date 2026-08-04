# Cross-user task-equivalence adjudication pilot (2026-08-04)

## Protocol

Eight cross-user session pairs were selected from two MIT-licensed DataClaw
exports: four high lexical-candidate pairs and four low/negative candidates.
Each pair was sent twice to `gpt-5.6-luna` through the authenticated Codex
harness. Luna chose `same_task`, `related_task`, `different`, or `unclear`.
Session IDs were hashed and model reasons were not retained.

The first exploratory run exposed a representation failure: Claude harness
boilerplate (`local-command-caveat`, task notifications, temporary output paths,
and interruption text) dominated lexical similarity. That run was quarantined.
The accepted run strips those fields before candidate selection and adjudication.

## Result

- 16/16 frontier calls succeeded.
- Pair-level agreement was **8/8** on the repeated calls.
- Labels: **1 related-task**, **1 unclear**, **6 different**, **0 same-task**.
- The related-task pair involved skill/skill-library organization work across
  users; it is a silver label, not an independent ground-truth match.
- Total frontier wall time: **152.2 seconds** (mean 9.5 seconds/call).

High lexical similarity did not reliably imply the same task. The pilot found
that boilerplate normalization is a prerequisite for embeddings, lexical
retrieval, and frontier adjudication; otherwise the system will cluster harness
artifacts rather than work.

## Claim boundary

This is a silver-label review pilot. It does not prove cross-user task transfer,
skill gaps, or enterprise recommendations. The next powered study needs
independent task labels, more users, project/time-held-out splits, and outcome
replay. The receipt is
`experiments/results/dataclaw-cross-user-luna-adjudication-2026-08-04.json` and
its verifier passes.
