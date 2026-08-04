# BIRD-Interact ambiguity and clarification cohort profile (2026-08-06)

The pinned public `birdsql/bird-interact-full` task file contains 600
annotated PostgreSQL interaction tasks. The released file includes injected
ambiguity and follow-up labels, but intentionally omits gold SQL and executable
test cases; those require the upstream evaluator package/request process.

## Observed structure

- 22 database domains are represented; task categories are 410 `Query` and
  190 `Management`.
- All 600 records contain a labeled follow-up: 266 result-based, 120
  aggregation, 114 attribute-change, 51 topic-pivot, and 49 constraint-change.
- 588 records contain at least one critical ambiguity annotation, with 1,307
  annotations total: knowledge-linking 573, intent 236, semantic 248,
  schema-linking 203, lexical 40, and syntactic 7.
- Non-critical ambiguity annotations total 574 (sort 186, decimal 160, null
  146, join 38, distinct 17, divide-zero 14, rank 8, date-format 5).
- Knowledge-ambiguity annotations total 451.

## What this enables

This is a strong cohort for testing whether an agent should clarify before
executing SQL, how many turns clarification costs, and whether a mined
clarification procedure transfers across database families. The labels also
provide a principled friction taxonomy: semantic/knowledge/schema ambiguity
should be separated from harmless formatting or ordering ambiguity.

## What it does not enable yet

The public file does not contain observed human interaction histories, hidden
gold SQL, executable tests, or simulator outcomes. Therefore this profile does
not measure agent quality, friction reduction, skill gaps, or enterprise user
behavior. A fair intervention requires the upstream evaluator/test bundle and
must compare no-procedure, clarification-procedure, over-questioning placebo,
and frontier regeneration arms with hidden execution outcomes.

Receipt: [`bird-interact-ambiguity-profile-2026-08-06.json`](../results/bird-interact-ambiguity-profile-2026-08-06.json)

Verifier result hash: `2b02423e4d267fb49af940f4f522f8da52d42123b69ee0e5536bc23f80d5303b`.

Raw task content remains in `/private/tmp`; no gold/test material was
downloaded or committed.
