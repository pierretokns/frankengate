# Embedding versus outcome-model cascade audit — 2026-08-02

This audit joins two independently run receipts over the same MATM revision
(2,130 trajectories, 34 models, leave-one-model-out folds). It intentionally
does not pool relevance-retrieval metrics with outcome-prediction metrics.

| Stage | Result | Interpretation |
| --- | --- | --- |
| Embedding action-only vs lexical action-only | Recall@20 `+0.123` (95% CI `[+0.053,+0.206]`); MRR `+0.048` (CI crosses zero) | Useful candidate-recall signal when the goal is hidden |
| Outcome-conditioned successful-neighbor vs all-neighbor | AUC delta `-0.056` (CI `[-0.112,+0.002]`); top-10 success delta `+0.067` (CI crosses zero) | Possible review prioritization, not a robust model gain |

The measured composition is therefore:

1. exact identifiers, lexical, and structured filters for precision and
   authority;
2. embeddings for candidate recall;
3. outcome-conditioned or small-model scoring for review prioritization;
4. frontier/human adjudication for ambiguous intent and expected artifacts;
5. execution/replay validation before any artifact or skill release.

The outcome-conditioned method was not a changed-agent intervention, and the
two studies target different labels. No model reranker gain, causal skill
utility, or enterprise transfer is claimed. The audit remains a design and
measurement checkpoint, not a promotion gate.

