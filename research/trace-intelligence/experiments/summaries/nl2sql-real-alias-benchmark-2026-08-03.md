# Real NL2SQL alias and scope retrieval benchmark

## Question

Can exact/lexical retrieval, a general embedding model, or a frontier model
identify schema objects needed by real NL2SQL questions while resisting
wrong-scope candidates and abstaining when the question is paired with an
unrelated database?

## Protocol

The cohort was derived from the pinned Defog PostgreSQL question CSVs and the
pinned companion DDL. Raw questions and SQL remain external under
`/private/tmp/nl2sql-real-alias-20260803-raw.json`; only source hashes and
content-free receipts are committed. The full cohort contains 42 cases:

- 12 explicit-target cases;
- 14 implicit-target cases, where the question does not contain the exact
  target identifier surface;
- 16 scope-swapped NIL cases.

The benchmark used a deterministic 22-case stratified subset (6 explicit, 8
implicit, 8 NIL), with 11–20 candidates per case. Candidate generation was
frozen before ranking and included gold-SQL target objects, lexical same-scope
objects, and exact-morphology cross-scope collisions. Luna saw only the
question, scope, and candidate objects—not gold SQL, target labels, or source
row IDs. All 22 frontier calls returned valid structured output and were
independently verified.

Receipt: [`../results/nl2sql-real-alias-benchmark-2026-08-03.json`](../results/nl2sql-real-alias-benchmark-2026-08-03.json).
Independent verification was run with
`verify_nl2sql_real_alias_benchmark.py`; result hash
`5bd03846d6db2932f1a4ceb1072668e3794d603430ec6734f61cd90fc5be0250`.
The content-free verification receipt is
[`../results/nl2sql-real-alias-benchmark-2026-08-03-verification.json`](../results/nl2sql-real-alias-benchmark-2026-08-03-verification.json).

## Result

| Arm | MRR | Recall@1 | Recall@5 |
| --- | ---: | ---: | ---: |
| exact + scope | .893 | .786 | 1.000 |
| lexical + scope | .806 | .786 | .786 |
| Nomic embedding + scope | .690 | .571 | .857 |
| Luna reranker | 1.000 | 1.000 | 1.000 |

The frontier decision was correct on all 22 cases: retrieve on 14 targeted
cases and abstain on all 8 constructed scope-swapped NILs. The wrong-system
candidate-before-target rate was zero for every arm in this subset because the
scope-aware candidate ordering and the selected collisions were not difficult
enough to expose that failure mode.

## Interpretation

This is a useful capability checkpoint, not proof of semantic alias discovery.
It shows that a frontier model can resolve implicit target references after a
frozen candidate generator and can abstain on a simple scope mismatch. It does
not establish human semantic-alias truth, production-scale cost/latency,
changed-schema generalization, or downstream agent utility. The frontier arm
should remain a selective review/reranking stage, not a hot-path dependency.

The next decisive cohort must include SME-labelled undocumented aliases,
same-surface/different-system candidates that remain in the same scope,
temporal renames, tool/schema conflicts, and genuinely ambiguous NILs. The
candidate pool must be frozen before labels are collected, and quality must be
measured per dollar/latency as well as Recall/MRR.
