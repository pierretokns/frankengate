# Project-held-out lexical adaptation on Claude histories

## Question

Does a fold-local, domain-adaptive representation improve retrieval across
real project histories, independently of the earlier DataClaw result?

## Protocol

The benchmark used the same public Claude Code history export as the legacy
candidate studies: 432 sessions in 65 project directories. Projects with at
least two sessions supplied 37 leave-one-project-out folds (404 eligible
sessions). Project names were excluded from features. The baseline was TF-IDF
cosine similarity; the adapted arm multiplied token weights by a fold-local
same-project versus cross-project log-ratio learned only from the training
projects. Two representations were tested: user-message tokens and all
textual message tokens. The receipt contains only aggregate metrics and hashed
project labels.

## Results

| Representation | MRR baseline → adapted | Recall@1 baseline → adapted | Recall@5 baseline → adapted |
|---|---:|---:|---:|
| User messages | `.885892 → .915765` (+.029873) | `.851485 → .883663` (+.032178) | `.933168 → .952970` (+.019802) |
| All textual messages | `.899585 → .921237` (+.021652) | `.866337 → .891089` (+.024752) | `.940594 → .957921` (+.017327) |

## Interpretation

This independently reproduces the direction of the earlier DataClaw project
adapter result: fold-local domain weighting improves a project-held-out
similarity proxy when the frozen lexical baseline has headroom. The effect is
smaller than Peter DataClaw's combined gain (`.769341 → .854452`) and the
Vaynelee cohort's ceiling null, which is consistent with a corpus- and
headroom-dependent method rather than a universal custom embedding result.

The benchmark does **not** establish that retrieved sessions share user
intent, contain reusable artifacts, or improve a downstream agent. Project
directories are silver workstream labels. It is evidence for a cheap scoped
adaptation/re-ranking lane—not permission to train or deploy a corporate
embedding from raw traces alone.

## Recommended use

Keep the adapter behind the structured cascade:

```text
scope / identifiers / compatibility
  -> lexical + fold-local domain weighting
  -> optional dense recall
  -> reviewed intent/artifact validation
```

The next decisive test still needs entity/project/time-held-out reviewed
aliases, hard negatives, replayable artifacts, and terminal outcomes.

## Receipts

- [content-free result](../results/claude-history-project-adapter-2026-08-09.json)
- [independent verification](../results/claude-history-project-adapter-verification-2026-08-09.json)
- [`claude_history_project_adapter_benchmark.py`](../../claude_history_project_adapter_benchmark.py)
