# DataClaw project-held-out representation adaptation

## Question

Can a fold-local domain adapter improve retrieval of sessions from an unseen
project for one user, without putting project names into the representation?

## Protocol

The benchmark uses prompt tokens, tool-name tokens, or both from DataClaw
messages. It uses leave-one-project-out evaluation, TF-IDF cosine retrieval as
the baseline, and a fold-local same-project versus cross-project token
log-ratio adapter. Project labels are silver workstream proxies. The full
Peter cohort uses all 549 sessions and Vaynelee uses all 38 sessions. A 500
co-occurrence-pair cap per token keeps the full adapter run reproducible and
bounded. No raw text or project names are committed.

## Result

Peter (10 eligible projects, 545 sessions) showed a combined prompt+tool
adapter improvement from MRR `.769341` to `.854452` and Recall@1
`.666055→.787156`. Prompt-only improvement was smaller (`.851532→.868002`
MRR), while tool-only MRR slightly declined (`.675115→.665805`) and Recall@1
declined (`.561468→.539450`).

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
benefit. The two-project Vaynelee cohort and silver project labels remain
exploratory evidence only.

Receipts:

- [Peter result](../results/dataclaw-project-adapter-full-2026-08-09.json)
- [Peter verification](../results/dataclaw-project-adapter-full-verification-2026-08-09.json)
- [Vaynelee result](../results/dataclaw-project-adapter-vaynelee-full-2026-08-09.json)
- [Vaynelee verification](../results/dataclaw-project-adapter-vaynelee-full-verification-2026-08-09.json)
- [`dataclaw_project_adapter_benchmark.py`](../../dataclaw_project_adapter_benchmark.py)
