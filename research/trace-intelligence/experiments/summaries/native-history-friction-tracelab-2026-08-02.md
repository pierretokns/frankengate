# Native Claude history friction screen — 2026-08-02

## Scope

This run uses the 28 native Claude Code JSONL histories in the Trace Commons
Claude cohort (the committed manifest identifies the cohort and its license).
Raw histories were extracted into a private temporary directory and were not
committed to this branch. The adapter emits only aggregate counts, tool-name
histograms, timestamps, working-directory cardinality, and source hashes.

This is a detector screen, not a user study and not a correctness benchmark.
It does not infer the users' private business intent, and it does not label a
prompt as a friction case merely because a model or shell output contains the
word `error`.

## Observed aggregate signals

| Signal | Count |
| --- | ---: |
| sessions | 28 |
| user prompts (tool-result turns excluded) | 413 |
| assistant turns | 7,499 |
| tool calls | 4,264 |
| tool results | 4,262 |
| structured tool-result errors (`is_error: true`) | 269 |
| non-empty executor stderr records | 56 |
| interrupted executor records | 0 |
| keyword error markers in result text (screening only) | 762 |
| explicit dissatisfaction prompt signals | 22 |
| correction prompt signals | 51 |
| retry/repair prompt signals | 89 |
| clarification prompt signals | 11 |
| exact adjacent prompt repeats | 2 |
| adjacent rephrase pairs (Jaccard >= 0.35) | 12 |
| sessions with repeated tool-use signatures | 17 |

The structured error rate is 269/4,262 = 6.31% of tool-result blocks. A
keyword-only detector would have reported 762 markers (17.88%), demonstrating
why prose matching must not be used as the executor-failure label. The 56
stderr records are a separate signal: stderr can be diagnostic output without
being a failed task. The dataset contains no interruption records in this
cohort.

## What this does and does not establish

The run establishes that native histories contain enough event structure to
separate tool lifecycle events, explicit executor failures, stderr, retries,
corrections, rephrases, and repeated tool proposals. It therefore supports a
content-preserving canonical trajectory adapter and a cheap first-pass signal
detector.

It does **not** establish that any of those signals are user friction, that a
session ended successfully, that a repair fixed the user's real task, or that a
repeated tool call is a reusable skill. In particular, `is_error: true` is a
tool execution outcome, not a user-level failure label; a successful tool can
still produce an undesirable answer, and a failed exploratory command can be
productive.

## Next empirical step

Sample episodes stratified by structured error, explicit dissatisfaction,
rephrase/retry, and clean controls. Have two blinded reviewers label (a)
productive iteration vs genuine friction, (b) observed intent vs unknown, (c)
whether a replayable eval oracle exists, and (d) whether a clarification is
required. Measure inter-rater agreement before training a classifier. Promote
only cases with tool-complete provenance and an explicit expected outcome;
otherwise retain them as hypotheses or clarification candidates.

