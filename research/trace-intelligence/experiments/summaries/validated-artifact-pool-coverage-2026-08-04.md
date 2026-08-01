# Validated-artifact pool coverage diagnostic — 2026-08-04

## Result

The retrieval comparison's `0/10` semantic transfer is not explained only by
bad ranking. Using the target gold SQL as an evaluation-only oracle, every
validated same-scope source artifact was executed and independently compared
with every held-out target result:

- 10 held-out broker/car targets;
- 165 validated source-artifact executions (all authorized, zero execution
  errors);
- 0 targets with any semantically matching source artifact;
- 0/10 oracle-structured top-1 matches and 0/10 top-3 matches.

Receipt hash: `51922e221abbb50054e37207dbcd6f1fb793a443960d007227d7a0641f5ebcea`.
The independent verifier also passed with the same hash.

## Interpretation

On this cohort, the admitted basic/advanced source pool has a measured
semantic-reuse ceiling of zero for the held-out generated questions. Therefore
the earlier lexical/dense/identifier/hybrid retrieval null cannot be called an
embedding failure or a retriever failure alone: the source artifacts themselves
do not contain a result-equivalent reusable query for these targets.

This is an evaluation oracle, not a deployable retriever: target gold SQL is
used only to label pool coverage. It does not prove that reusable artifacts are
unhelpful in production. It does establish that a fair next test must add
parameterized templates, source/target tasks with known shared intent, or a
prospective agent/regeneration control. Re-ranking the same non-overlapping
pool cannot produce transfer.

Receipt: [`../results/validated-artifact-pool-coverage-2026-08-04.json`](../results/validated-artifact-pool-coverage-2026-08-04.json); [independent verification](../results/validated-artifact-pool-coverage-2026-08-04-verification.json).
