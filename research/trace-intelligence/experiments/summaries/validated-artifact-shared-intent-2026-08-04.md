# Controlled shared-intent artifact retrieval — 2026-08-04

## Result

This is the preregistered upper-bound companion to the natural held-out
retrieval null. It uses 20 validated broker/car basic tasks as source artifacts
and creates one deterministic prompt-only paraphrase per source task. The
target SQL and intent remain source-pinned, so every target has a known
semantically reusable artifact in the library.

| Arm | Known source top-1 | Known source top-3 | Semantic top-1 | Semantic top-3 | Authorized top-3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 20/20 | 20/20 | 20/20 | 20/20 | 60/60 |
| Frozen Nomic dense | 20/20 | 20/20 | 20/20 | 20/20 | 60/60 |
| Lexical+dense hybrid | 20/20 | 20/20 | 20/20 | 20/20 | 60/60 |
| Identifier-aware | 8/20 | 12/20 | 8/20 | 12/20 | 60/60 |

Receipt hash: `985011c3b8b7e4d7a7a03d93e3b0056ef3cb226f8283c43abd15ad33d305fe71`;
the independent verifier passed with the same hash.

## Interpretation

This establishes that the artifact-retrieval and governed-execution path can
recover and reuse a known shared-intent artifact. It also explains why the
earlier natural `0/10` result cannot be interpreted as a universal artifact or
embedding failure: that cohort had zero source-pool coverage, while this
controlled cohort recovered the known artifact at `20/20` for lexical, dense,
and hybrid retrieval.

The result is intentionally an upper bound. The paraphrases are deterministic,
not human-authored enterprise requests; there is no regeneration control,
changed-schema replay, or causal agent outcome. The next fair utility test must
use natural or SME-labeled paraphrases with shared parameterized intent and
compare artifact reuse against fresh frontier generation.

Receipt: [`../results/validated-artifact-shared-intent-2026-08-04.json`](../results/validated-artifact-shared-intent-2026-08-04.json); [independent verification](../results/validated-artifact-shared-intent-2026-08-04-verification.json).
