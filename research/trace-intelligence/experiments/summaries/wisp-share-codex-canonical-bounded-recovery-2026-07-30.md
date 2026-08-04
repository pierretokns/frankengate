# Canonical bounded recovery construction across Wisp and share-codex

Date: 2026-07-30

## Research question

Can one deterministic, content-minimized episode constructor identify
structurally comparable failure-to-later-success review candidates in two
different real-user agent-history exports?

This experiment replaces the earlier corpus-specific recovery heuristics with
one common constructor. It does **not** test whether the later operation was
correct, whether the task succeeded, whether the error caused the retry, or
whether a user learned a skill.

## Pinned sources

- Wisp: `crispwisp/wisp-claude-code-sessions` at
  `c2c90b59174318ab0b163ec9c9ac82bb879288ce`, all 104 released JSONL files.
  Source:
  <https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce>
- share-codex: `nmuendler/share-codex` at
  `3d8b1397c72dbfbf8b04f518064e2c99dde84ca0`, the preregistered sparse design
  of eight 16-session blocks (128 of 4,333 sessions). Every response revision,
  row count, and ordered row range was checked. Source:
  <https://huggingface.co/datasets/nmuendler/share-codex/tree/3d8b1397c72dbfbf8b04f518064e2c99dde84ca0>

Raw public records remained in temporary storage. The committed result is
aggregate-only and contains no transcript text, arguments, outputs, paths,
native tool names, call/session/row identifiers, or per-session records.

## Predeclared common constructor

Both adapters project only three lifecycle events:

1. `tool.proposed`
2. `tool.result.error`
3. `tool.result.success`

An episode requires all of the following:

- the error is explicitly typed by the exporter; error-like text is ignored;
- the error and success each link to one unique prior proposal and one unique
  result;
- the successful call was newly proposed after the error result, excluding a
  parallel call that was already in flight;
- the failed and successful calls map to the same controlled tool family;
- the success result occurs no more than 12 lifecycle events after the error;
- errors are processed chronologically and successes are assigned greedily
  one-to-one.

Unknown/custom tools are not collapsed into an `other` family because doing so
would create cross-tool false matches.

## Results

| Measure | Wisp released snapshot | share-codex sparse sample |
|---|---:|---:|
| Sessions/files analyzed | 104 | 128 |
| Lifecycle events | 4,416 | 12,511 |
| Tool proposals | 2,209 | 6,272 |
| Explicit typed errors | 103 | 47 |
| Errors with unique linkage and mapped family | 103 | 47 |
| Matched bounded episodes | 89 | 31 |
| Matched share of eligible errors | 86.41% | 65.96% |
| Sessions/files containing a matched episode | 7 | 6 |
| Mean lifecycle distance | 3.78 | 3.61 |
| Maximum lifecycle distance | 12 | 12 |

Matched episode families:

- Wisp: shell 55, file change 32, file read 2.
- share-codex: shell 17, file change 14.

No same-family, within-window successful result in either empirical sample had
been proposed before its corresponding error. Therefore, the in-flight
exclusion changed zero observed pairs in this run. Synthetic conformance tests
prove that such a result is excluded when present; a corpus with explicit
parallel same-family failures is still needed to estimate its real prevalence.

The earlier corpus-specific pilots reported 92 Wisp candidates and 38
share-codex “later success” observations. They were not comparable: one used
tiered family heuristics and greedy assignment while the other used any later
success without one-to-one assignment. Under the common constructor the counts
are 89 and 31. This is evidence that constructor semantics materially affect
the apparent recovery prevalence.

## Governed-loader integration

The Wisp PostgreSQL derivation now calls this same constructor rather than its
previous exact-native-tool heuristic. The derivation revision advanced from
`wisp-governed-derivation-v1` to `wisp-governed-derivation-v2`; persistence
explicitly replaces both the superseded v1 rows and current v2 rows for the
loaded source trajectories so users cannot receive duplicate old/new review
proposals.

A full content-local preparation run over the 104 trajectories produced 104
signals, 11 eval proposals, and seven procedure-review proposals containing 89
bounded transitions. The four canonical evidence event IDs for each transition
remain attached inside the RLS-governed proposal. Loader-level regression tests
prove in-flight exclusion and greedy one-to-one use of successes. This
integration was prepared and tested without mutating the local database; its
next database load must regenerate the v2 derived rows before the governed
query benchmark is interpreted.

## What is supported

- Both exporters can be loss-minimized into the same tool lifecycle vocabulary.
- Unique call/result linkage, explicit typed errors, post-error proposals,
  bounded same-family matching, and greedy one-to-one assignment work on both
  real-user corpora.
- The resulting episodes are defensible candidates for user-visible review,
  trace-to-eval promotion, or human annotation.
- The constructor is suitable as a deterministic prefilter before any
  embedding or LLM judge.

## What is not supported

The 86.41% and 65.96% values must not be interpreted as a behavioral
difference. Wisp is one released Claude Code project tree containing benchmark
and nested-agent files; share-codex is a clustered, non-random sparse sample
from another single user with a different task mix and exporter. The exporters
may also differ in what they label as an error.

Neither corpus provides an independently verified task outcome for these
episodes. Consequently, this experiment cannot establish:

- that the later call fixed the original problem;
- that the user learned or lacks a skill;
- that one user or harness is more effective;
- that a prompt, memory, skill, model, or embedding caused improvement; or
- that an episode should be written automatically to enterprise memory.

The next validity step is human annotation against an explicit outcome rubric,
followed by prospective enterprise testing where suggestions are randomized
or otherwise causally identifiable.

## Reproduction

```bash
python3 research/trace-intelligence/canonical_recovery_episodes.py \
  --wisp-root /temporary/wisp/transcripts \
  --share-codex-sample-dir /temporary/share-codex-sample \
  --wisp-manifest \
    research/trace-intelligence/configs/datasets/wisp-claude-code-sessions.json \
  --share-codex-manifest \
    research/trace-intelligence/configs/datasets/share-codex-sparse.json \
  --output \
    research/trace-intelligence/experiments/results/wisp-share-codex-canonical-bounded-recovery-2026-07-30.json \
  --max-lifecycle-distance 12
```

Implementation:
`research/trace-intelligence/canonical_recovery_episodes.py`.

Conformance tests:
`research/trace-intelligence/tests/test_canonical_recovery_episodes.py`.
