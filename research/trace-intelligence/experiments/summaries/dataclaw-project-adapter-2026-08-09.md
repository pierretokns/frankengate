# DataClaw project-held-out representation adaptation

## Question

Can a fold-local domain adapter improve retrieval of sessions from an unseen
project for one user, without putting project names into the representation?

## Protocol

The benchmark uses prompt tokens, tool-name tokens, or both from DataClaw
messages. It uses leave-one-project-out evaluation, TF-IDF cosine retrieval as
the baseline, and a fold-local same-project versus cross-project token
log-ratio adapter. Project labels are silver workstream proxies. The Peter
cohort uses a deterministic round-robin 250-session sample to keep the run
bounded; Vaynelee uses all 38 sessions. A 5,000 co-occurrence-pair cap per token
keeps the adapter reproducible and bounded. No raw text or project names are
committed.

## Result

Peter (10 eligible projects, 246 sessions) showed a combined prompt+tool
adapter improvement from MRR `.654946` to `.751659` and Recall@1
`.512195→.646341`. Prompt-only improvement was smaller (`.756118→.766088`
MRR), while tool-only MRR slightly declined (`.540080→.535672`) and Recall@1
declined (`.378049→.349593`).

Vaynelee (2 eligible projects, 31 sessions) was already near ceiling: prompt
and combined metrics were unchanged (MRR `.978495`), while tool-only MRR
improved `.908468→.924637`. The result is therefore directionally positive
for a scoped adapter in one larger cohort, but not universal and not powered
for enterprise claims.

## Interpretation

The useful takeaway is not “train a custom embedding now.” It is that
project-held-out, user-scoped representation adaptation is testable and may
improve candidate recall when the baseline is not saturated. Tool-only signals
are weak and inconsistent. Promotion still requires expert intent labels,
wrong-project negatives, replayable artifacts, temporal drift, and changed-task
outcomes.

## Claim boundary

This is a lexical adapter, not a neural embedding model. Project labels do not
prove task equivalence, enterprise concepts, artifact correctness, or user
benefit. The bounded Peter sample and two-project Vaynelee cohort are
exploratory evidence only.

Receipts:

- [Peter result](../results/dataclaw-project-adapter-2026-08-09.json)
- [Peter verification](../results/dataclaw-project-adapter-verification-2026-08-09.json)
- [Vaynelee result](../results/dataclaw-project-adapter-vaynelee-2026-08-09.json)
- [Vaynelee verification](../results/dataclaw-project-adapter-vaynelee-verification-2026-08-09.json)
- [`dataclaw_project_adapter_benchmark.py`](../../dataclaw_project_adapter_benchmark.py)
