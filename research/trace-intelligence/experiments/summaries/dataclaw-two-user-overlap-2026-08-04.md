# Two-user DataClaw overlap audit (2026-08-04)

We compared two public, MIT-licensed DataClaw exports with explicit dataset
owner provenance: `peteromallet` (549 sessions) and `vaynelee` (38 sessions).
This is a descriptive corpus audit, not a task-similarity evaluation.

- Prompt vocabulary Jaccard: **0.028** (2,009 shared terms / 71,619 union).
- Shared non-trivial exact tool-call forms: **11** of 38,014 union forms.
- Shared tool-name count: 15.
- The broad friction detector rates sessions at 72.9% and 28.9% respectively,
  demonstrating that detector rates are user/corpus-dependent and cannot be
  compared as failure rates without calibration.

The low exact overlap shows why naïve cross-user artifact sharing will have low
coverage. It does not show that semantic retrieval, aliases, or task-level
representations cannot connect equivalent work: task labels, outputs, and
outcome equivalence are absent. The next valid test is a blinded, SME- or
frontier-adjudicated task-equivalence set with principal/project/time-held-out
splits, then exact versus dense versus identifier-aware retrieval.

Receipt and verifier:
`experiments/results/dataclaw-two-user-overlap-2026-08-04.json`.
No prompt or tool text is emitted.
