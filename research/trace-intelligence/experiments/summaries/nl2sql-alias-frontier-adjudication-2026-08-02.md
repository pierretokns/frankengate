# NL2SQL collision-sample frontier adjudication (2026-08-02)

## What was run

`gpt-5.6-luna` adjudicated 22 cases sampled from the cross-database
same-surface collision classes in the pinned Defog PostgreSQL cohort. The
model saw only a public question, stated database scope, the gold-linked
identifier, and same-surface candidates. It labeled the in-scope surface and
each candidate as `exact_alias`, `semantic_alias`, `wrong_system`, `nil`, or
`unclear`.

The raw cases and model response remain outside the repository. The committed
receipt contains hashes and aggregates only:
[`nl2sql-alias-adjudication-2026-08-02.json`](../results/nl2sql-alias-adjudication-2026-08-02.json).

## Aggregate result

- 22/22 target-scope candidates were labeled `exact_alias` or
  `semantic_alias`.
- 40/40 other-scope candidates were labeled `wrong_system`.
- Surface labels: 18 exact, 4 semantic (plural/morphological forms).
- Mean model confidence: 0.9895.
- No `nil`/`unclear` cases in this deliberately easy sample.

## Interpretation

This supports the benchmark’s hard-negative construction: a generic surface
can be valid in one database and wrong-system in another, even when the token
is identical. It does **not** validate the model’s confidence or establish
corporate semantic alias quality. The cases are public, generic, small, and
gold-linked; there was no independent human panel or family-held-out replay.
The next gate is a blinded stratified sample containing true aliases, NIL
mentions, ambiguous schemas, and undocumented corporate terms, with at least
two independent frontier judgments plus SME adjudication.
