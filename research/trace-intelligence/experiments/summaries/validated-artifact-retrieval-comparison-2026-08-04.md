# Validated-artifact retrieval-family comparison — 2026-08-04

## Receipt

- Targets: ten held-out broker/car-dealership `questions_gen` tasks.
- Source pool: 33 governed-success SQL artifacts from the disjoint basic and
  advanced source files.
- Retrieval: lexical, frozen Nomic dense, SQL-identifier-aware, reciprocal-rank
  hybrid, and identifier-gated arms; each with scope-filtered and pooled modes.
- Evaluation: up to three selected same-scope artifacts were executed under the
  constrained PostgreSQL role and compared independently with the target gold
  result.
- Result hash: `58a78a95aa08b468d86fdd619bfe1c9ba9d6023819eedc2be38835c92ed17b83`.

## Aggregate result

| Mode / arm | Top-1 in-scope | Top-1 semantic | Top-3 semantic | Top-3 authorized | Abstained |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scope-filtered lexical | 10/10 | 0/10 | 0/10 | 30/30 | 0/10 |
| Scope-filtered dense | 10/10 | 0/10 | 0/10 | 30/30 | 0/10 |
| Scope-filtered identifier | 10/10 | 0/10 | 0/10 | 30/30 | 0/10 |
| Scope-filtered hybrid | 10/10 | 0/10 | 0/10 | 30/30 | 0/10 |
| Scope-filtered identifier gate | 6/10 | 0/10 | 0/10 | 12/12 | 4/10 |
| Pooled lexical | 7/10 | 0/10 | 0/10 | 21/21 | 0/10 |
| Pooled dense | 7/10 | 0/10 | 0/10 | 23/23 | 0/10 |
| Pooled identifier | 5/10 | 0/10 | 0/10 | 18/18 | 0/10 |
| Pooled hybrid | 5/10 | 0/10 | 0/10 | 15/15 | 0/10 |
| Pooled identifier gate | 3/10 | 0/10 | 0/10 | 12/12 | 3/10 |

All governed executions authorized by the constrained role completed without
execution errors. Four synthetic NIL cases were planned by the protocol, but
the two-database cohort produced zero cases whose target table surface was
disjoint from the alternate database's validated artifact surface. Therefore
this run does **not** provide a NIL-abstention result.

## Interpretation

The earlier `0/10` lexical transfer result is not merely a lexical-retriever
failure on this cohort. Dense, identifier-aware, and lexical+dense hybrid
retrievers also produced `0/10` top-three semantic transfer after scope
filtering. The evidence therefore supports a stronger bounded conclusion:
validated execution plus question similarity does not establish artifact
relevance for these held-out tasks.

Removing the scope filter introduced wrong-system selections: lexical and dense
selected an in-scope artifact only `7/10` times, while identifier and hybrid
selected one only `5/10` times. Database/project scope must remain a hard
retrieval boundary. The identifier gate abstained on four scoped cases, showing
that a conservative signal can reduce unsafe reuse, but it did not recover a
semantically correct artifact in the remaining cases.

This is not a disproof of reusable SQL/tool artifacts. The source and target
tasks may require different query plans, joins, grains, or parameters; the
benchmark has no regeneration control, SME intent labels, parameterized
templates, changed-schema replay, or prospective agent outcome. The next fair
test is a parameterized-template/artifact arm against a frontier regeneration
arm, with human-labeled relevance and explicit structural NIL cases.

Receipt: [`../results/validated-artifact-retrieval-comparison-2026-08-04.json`](../results/validated-artifact-retrieval-comparison-2026-08-04.json); [independent verification](../results/validated-artifact-retrieval-comparison-2026-08-04-verification.json).
