# Train-only validated SQL-artifact retrieval benchmark

## Question

Can a train-only library of validated SQL artifacts be retrieved from terse
questions and directly solve held-out questions without target-task pairing?

## Protocol

The pinned Defog cohort was split by source file. Ten held-out
`questions_gen_postgres` tasks from the broker and car-dealership databases
were queried against a same-database pool of validated, executable artifacts
from `instruct_basic_postgres` and `instruct_advanced_postgres`. A deterministic
lexical token-overlap retriever selected one artifact per target. Artifacts were
admitted only after governed PostgreSQL policy and execution validation. The
retrieved query was then executed against the target and compared with the
target gold result. No target question or target SQL entered the artifact pool.

## Result

| Measure | Result |
| --- | ---: |
| held-out targets | 10 |
| validated source artifacts | 18 broker, 15 car-dealership |
| retrieved/executed candidates | 10/10 |
| authority-authorized candidates | 10/10 |
| exact semantic matches | 0/10 |
| source artifacts rejected before admission | 5 (`SQLPolicyError`) |

The independent verifier reproduced the deterministic receipt hash and all
five checks passed.

## Interpretation

This is the first unpaired artifact-reuse result. A validated artifact can be
executed safely, but lexical similarity alone did not transfer any artifact to
a different held-out question in this small public cohort. This is not a
disproof of reusable artifacts: the retriever is intentionally simple, the
tasks are heterogeneous, and no model regeneration control or parameterized
template abstraction was included. It does establish that “store successful
SQL and retrieve the nearest question” is not enough.

The next gate should compare exact/structured, lexical, dense, and frontier
candidate generation on the same frozen train-only pool; admit parameterized
templates and explicit NIL/wrong-system labels; then replay selected artifacts
on changed schemas and compare against regeneration.

Receipts: [`../results/validated-artifact-retrieval-benchmark-2026-08-03.json`](../results/validated-artifact-retrieval-benchmark-2026-08-03.json) and its [verification](../results/validated-artifact-retrieval-benchmark-2026-08-03-verification.json).
