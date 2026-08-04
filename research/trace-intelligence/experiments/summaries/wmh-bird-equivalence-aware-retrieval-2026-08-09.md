# WMH-BIRD exact versus execution-equivalent retrieval

## Question

Does strict exact-target scoring hide useful artifact reuse when a different
exposed table independently produces the same result under the recorded SQL?

## Protocol

The probe uses the same 149 deterministic successful WMH-BIRD traces and
SQLite counterfactual substitutions as the exposure study. The ordinary target
set is the recorded SQL table references. The additional target set includes
any exposed-but-unused table whose substitution for at least one used table
returns the identical result rows. Retrieval is evaluated on held-out tasks
with lexical and train-only TermSuite-style termhood expansion.

Execution-equivalent is deliberately weaker than semantic equivalence. It is a
compatibility label for one query/database snapshot, not an alias label.

## Result

The replay pass found **1,236** substitutions: 1,210 execution errors, 22
result mismatches, and only **4** result-preserving candidates. On the 71-task
held-out retrieval split, exact-target and execution-equivalent scores were
identical for both lexical and termhood arms (`MRR .775659` and `.788514`,
respectively). The alternate-artifact-only target was almost never surfaced:
Recall@10 was `.028169` and MRR `.003521` for both arms.

This is a useful boundary, not a null about artifact reuse. The public cohort
contains too few result-preserving alternatives to change ranking, and the
two held-out alternatives were not discoverable in the top five. The benchmark
must therefore retain both exact and execution-equivalent labels, but it cannot
justify training a semantic alias model from these four examples.

## Interpretation gate

The receipt reports both exact and execution-equivalent metrics. If the latter
is higher, that is evidence that strict exact labels undercount reusable
artifacts; it is not evidence that the alternate table should replace the
recorded table in another query, tenant, time period, or authorization scope.
Any promotion still requires independent semantic labels and changed-system
replay.

## Claim boundary

This is a public SQL mechanics proxy. It does not establish enterprise intent,
alias quality, embedding value, or user utility. The result-preserving examples
are useful for constructing the hard-negative/acceptable-alternative strata
that the current public corpora lack.

Receipts:

- [content-free result](../results/wmh-bird-equivalence-aware-retrieval-2026-08-09.json)
- [independent verification](../results/wmh-bird-equivalence-aware-retrieval-verification-2026-08-09.json)
- [`wmh_bird_equivalence_aware_retrieval.py`](../../wmh_bird_equivalence_aware_retrieval.py)
