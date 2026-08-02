# DataClaw hard-negative strata supply audit

## Question

Does the parseable real-user trace export contain enough balanced identifier
strata to populate the enterprise cohort contract without committing raw paths?

## Method

- Dataset: `ronaldcmz/Claude-Opus-Dataclaw-Unredacted`
- Pinned revision: `918e6fb39c916d3459ef338b4c3645622b9a5126`
- 436 sessions, 46 projects; chronological per-project 70/30 split gives 279
  train and 141 evaluation sessions.
- Conservative path extraction retained only lowercase basename surfaces and
  SHA-256 digests of normalized full paths. No raw path, project, command, or
  transcript content was emitted.
- Strata are identity/surface candidate pairs, not semantic labels.

Receipt: [dataclaw-ronald-hard-negative-strata-2026-08-02.json](../results/dataclaw-ronald-hard-negative-strata-2026-08-02.json)

## Candidate supply

| Stratum | Full cohort | Chronological train only |
|---|---:|---:|
| Same-project exact identity pairs | 3,781 | 2,125 |
| Same-project same-surface/different-path pairs | 4,062 | 2,610 |
| Cross-project same-surface/exact-path pairs | 834 | 306 |
| Cross-project same-surface/different-path pairs | 4,061 | 1,601 |

The train-only pool has all four strata and easily exceeds the minimum **50
hard-negative** requirement in the cohort contract. It is therefore large
enough to create a frozen review sample without using the evaluation half for
candidate generation.

## Interpretation

This closes a dataset-capacity question, not a semantic-quality question. The
public export can supply balanced identifier collision candidates, including
cross-project exact-path cases that would be unsafe to assume are unique. It
does not tell us whether a pair is the same artifact, a true alias, an
unrelated convention, stale, or NIL.

The correct next operation is annotation, not model training:

1. sample the four strata from the chronological train pool;
2. add target, alias, wrong-scope, stale, NIL, and unclear labels;
3. hold the candidate pool fixed before unsealing labels;
4. measure annotator agreement and adjudication; and
5. evaluate lexical, exact, dense, identifier-aware, and frontier-review arms
   against changed-system replay and independent outcomes.

The two public DataClaw users do not provide enterprise semantic labels, so this
pool is suitable for a mechanics/review study or partner labeling exercise, not
for claiming corporate alias quality or cross-user skill transfer.

## Contract relation

The train-only candidate counts satisfy the hard-negative capacity requirement
of the [enterprise semantic-cohort contract](../../configs/studies/enterprise-semantic-cohort-v1.json),
but the export still lacks the contract's consented semantic labels, changed
environment outcomes, and independent terminal validators. It remains a
candidate-supply source only.

## Reproduction

```text
ruby dataclaw_hard_negative_strata_audit.rb \
  /private/tmp/ronald-dataclaw-openai.jsonl \
  experiments/results/dataclaw-ronald-hard-negative-strata-2026-08-02.json
```

