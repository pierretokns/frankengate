# MATM fold-local domain embedding adapter — 2026-08-02

This is the first executable domain-adaptation experiment in the program. It
uses the pinned MATM trajectory shard (2,130 rows, 34 models) and evaluates
leave-one-model-out. The goal is hidden from the representation: only task
type and observed action templates are embedded.

For each training fold, a logistic metric learns from repeated-work positives
and high-base-cosine candidates with a different work signature. The adapter is
then evaluated on the held-out model. No outcomes, held-out rows, or raw vectors
are used for training.

| Metric | Base Nomic action embedding | Fold-local adapter | Delta |
| --- | ---: | ---: | ---: |
| Recall@20 | 0.5301 | 0.5331 | +0.0029 (95% CI `[-0.0135,+0.0189]`) |
| MRR | 0.3315 | 0.3300 | -0.0015 (95% CI `[-0.0065,+0.0013]`) |

The adapter is effectively neutral on this silver same-work task. This is not
evidence that custom corporate embeddings are useless: the corpus is public,
the labels are exact repeated-work signatures rather than adjudicated corporate
aliases, and the adapter is a simple metric learner. It does establish that
“train a small adapter on available traces” is not automatically a retrieval
gain. Promotion remains gated on human hard negatives, entity/time/project
holdouts, exact-identifier preservation, and downstream artifact utility.

The receipt is deterministic across two runs (SHA-256
`daeae1a8f1aa25c455eab0819ed30f5e392a0437cea5a0d71aa58d8d2`).

