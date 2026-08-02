# Cross-corpus SQL artifact signatures

## Question

If BIRD and Defog provide independent SQL corpora, does a schema-agnostic
representation create a realistic reusable-artifact pool, or only broad
structural candidates that still need schema-specific validation?

## Protocol

The probe parsed 242 BIRD gold queries and 314 Defog queries. It compared three
content-free signatures:

1. exact normalized templates, retaining table and column identifiers while
   replacing literals;
2. typed schema-agnostic templates, replacing tables and columns with ordered
   placeholders; and
3. a deliberately coarse AST operator-shape signature used only as an upper
   bound for candidate generation.

The BIRD and Defog rows are public gold/query sources. This run is a signature
and collision study, not a cross-database execution test; no SQL or question
text is committed.

## Result

There were **0** shared exact templates across the corpora. The typed
schema-agnostic representation found only **1** shared structural template,
and that template had multiple exact variants, giving a **1.0 collision rate**.
The coarse operator-shape upper bound found only **2** shared shapes; both had
multiple exact variants and therefore also had a **1.0 collision rate**. Only
1 Defog row had a typed structural match to a BIRD row, and only 2 had a coarse
operator match.

The result is not that schema-agnostic retrieval can never help. It shows that
these two public corpora contain almost no compatible reusable SQL artifacts;
the few schema-free matches are ambiguous enough that identifiers, schema
compatibility, dialect, authority, and independent result validation remain
mandatory. A vector index over these artifacts would increase candidate recall
only after a compatible artifact library exists; it cannot manufacture that
library.

## Claim boundary

This does not measure natural user intent, semantic aliases, changed-system
transfer, or agent utility. BIRD/Defog are task corpora, not a longitudinal
enterprise artifact stream. The experiment therefore supports a dataset-fit
diagnosis and a retrieval safety rule, not a universal negative about artifact
learning.

Receipts:

- [content-free result](../results/cross-corpus-sql-artifact-signatures-2026-08-09.json)
- [independent verification](../results/cross-corpus-sql-artifact-signatures-verification-2026-08-09.json)
- [`cross_corpus_sql_artifact_signatures.py`](../../cross_corpus_sql_artifact_signatures.py)
