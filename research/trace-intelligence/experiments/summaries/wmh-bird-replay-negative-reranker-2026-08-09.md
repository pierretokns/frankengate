# WMH-BIRD replay-negative reranker (2026-08-09)

## Question

Do replay-derived incompatibility negatives improve a learned identifier-aware
ranker beyond treating every exposed-but-unused table as a negative?

## Protocol

- Use one deterministic successful trace per base task from the WMH-BIRD
  corpus, with an odd/even task split inside each database family.
- Positive: a table referenced by the recorded SQL.
- Naive-negative arm: every exposed-but-unused table.
- Replay-negative arm: only exposed tables whose substitution causes a SQL
  execution error or result mismatch on the pinned SQLite archive. A
  result-preserving substitution is excluded as uncertain.
- Train a deterministic logistic ranker over lexical overlap, table-token
  overlap, table length, exact table mention, and the train-only termhood alias
  indicator. Compare it with lexical and termhood-only ranking on held-out
  tasks.

## Results

All four arms had 71 held-out cases:

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Lexical | .775660 | .676056 | .887324 | 1.000000 |
| Termhood alias | .788514 | .676056 | .929577 | 1.000000 |
| Naive exposed-negative ranker | .812693 | .704225 | .957746 | 1.000000 |
| Replay-negative ranker | .812693 | .704225 | .957746 | 1.000000 |

The training half contained 77 replayable traces and 320 replay-confirmed
negative examples. No training candidate was result-preserving, so replay
filtering and naive exposed-negative training were identical on this proxy.

## Interpretation

The learned ranker improves over lexical and termhood-only retrieval on this
public schema/table proxy. However, the replay-derived negative label adds no
incremental lift because the training split has no ambiguous substitutions.
This is a useful negative result: replay validation improves the *quality and
interpretability of the negative pool*, but it is not automatically a better
training signal when all exposed candidates already fail the same simple
counterfactual.

The next decisive test needs realistic ambiguous negatives: same-surface
tables in different systems, temporal replacements, semantically valid
alternative plans, and result-preserving substitutions. Without those, a
custom embedding or hard-negative objective can appear to work while learning
only table-surface regularities.

## Claim boundary

This is a BIRD mechanics proxy. Table references in recorded SQL are not SME
intent labels, and replay incompatibility is not semantic irrelevance. The
ranker is not promoted to production, and no embedding or skill update is
authorized.

## Receipts and code

- [content-free result](../results/wmh-bird-replay-negative-reranker-2026-08-09.json)
- [independent verification](../results/wmh-bird-replay-negative-reranker-verification-2026-08-09.json)
- [`wmh_bird_replay_negative_reranker.py`](../../wmh_bird_replay_negative_reranker.py)
- [`verify_wmh_bird_replay_negative_reranker.py`](../../verify_wmh_bird_replay_negative_reranker.py)
