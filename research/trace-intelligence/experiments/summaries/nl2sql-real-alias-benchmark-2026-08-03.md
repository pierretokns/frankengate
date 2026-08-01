# Real NL2SQL alias, wrong-system, and NIL benchmark

## Protocol

The cohort was constructed from pinned public Defog PostgreSQL questions and
DDL. The manifest contains 42 available cases; the frozen benchmark selected
22 cases (two per database/category group): 6 explicit target cases, 8
implicit-target cases, and 8 scope-swapped NIL cases. Each candidate set had
11–20 schema objects. The frontier prompt saw only the question, stated
database scope, and candidate objects—not gold SQL, target labels, or source
row IDs.

The four ranking arms were exact identifier + scope, lexical + scope, local
`nomic-embed-text` + scope, and `gpt-5.6-luna` with an explicit retrieve/abstain
decision. Raw questions, SQL, and frontier responses remain external.

Receipts:

- [`../results/nl2sql-real-alias-benchmark-luna-2026-08-03.json`](../results/nl2sql-real-alias-benchmark-luna-2026-08-03.json)
- [`../results/nl2sql-real-alias-benchmark-luna-verification-2026-08-03.json`](../results/nl2sql-real-alias-benchmark-luna-verification-2026-08-03.json)

## Result on target-bearing cases

| Arm | MRR | Recall@1 | Recall@5 |
| --- | ---: | ---: | ---: |
| exact + scope | .8929 | .7857 | 1.0000 |
| lexical + scope | .8058 | .7857 | .7857 |
| local embedding + scope | .6900 | .5714 | .8571 |
| frontier Luna | 1.0000 | 1.0000 | 1.0000 |

All arms had zero wrong-system-before-target events on this candidate pool.

## NIL and abstention result

The eight scope-swapped NIL cases expose an important distinction:

- exact, lexical, and dense retrieval always return a top candidate because
  retrieval has no abstention semantics in this fixture;
- Luna abstained on all eight NIL cases (`8/8`), while retrieving all target
  bearing cases.

This is the first run that measures a useful model behavior beyond ranking:
explicit refusal when the authorized scope has no plausible target. It is still
not proof of semantic alias quality—the NILs are constructed by swapping a
real question into a different public database family, and the target labels
come from gold SQL rather than human/SME adjudication.

## Claim boundary and next gate

This proves a content-minimized benchmark and abstention contract can run on a
real public NL2SQL cohort. It does not establish enterprise semantic aliases,
undocumented corporate terms, human agreement, changed-agent utility, or
production performance. The next gate is an authorized enterprise cohort with
two independent SME labels, true NIL/unclear examples, user/project/time
holdouts, and changed-database/tool replay. Any adapter or reranker that raises
recall while increasing wrong-system or NIL false positives remains rejected.
