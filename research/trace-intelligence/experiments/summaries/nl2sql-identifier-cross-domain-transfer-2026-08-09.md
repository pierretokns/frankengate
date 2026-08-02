# Identifier-aware cross-domain SQL transfer

## Question

Do the cheap identifier/scope/collision features that improve the Defog
same-scope proxy transfer to WMH-BIRD, and does a BIRD-trained ranker transfer
back to Defog?

## Protocol

The experiment uses the Defog real-alias raw cohort and the WMH-BIRD native
trace cohort. It converts each BIRD exposed table into the same candidate shape
used by the Defog identifier benchmark, trains the deterministic logistic
ranker on every case in one domain, and evaluates on every target case in the
other. Lexical retrieval is retained as a control. The labels remain recorded
gold-SQL focus proxies.

## Interpretation gate

Cross-domain performance is evidence about feature/ranker portability, not
semantic alias discovery. The candidate constructions differ: Defog contains
column-level identifier collisions, while BIRD contains exposed schema-table
references. Any positive transfer must still be followed by SME labels,
same-surface wrong-system negatives, and changed-system replay.

## Result

Defog-trained ranking transferred positively to WMH-BIRD: identifier-aware
ranking reached MRR `.760996`, Recall@1 `.621622`, and Recall@5 `.952703`,
versus lexical `.731684/.581081/.932432`. The hard-negative-weighted arm
underperformed at MRR `.685674`.

The reverse direction failed to transfer: BIRD-trained ranking reached MRR
`.622864`, Recall@1 `.500000`, and Recall@5 `.769231` on Defog, below lexical
`.682284/.576923/.846154`. This is an asymmetric portability result, not a
contradiction: BIRD table-exposure features do not encode Defog's column-level
identifier collisions, while Defog's identifier/surface features still help
rank BIRD's table candidates.

## Claim boundary

No semantic alias labels, enterprise transfer, or embedding promotion are
claimed. This is a public proxy comparison designed to decide whether
identifier-aware ranking belongs ahead of dense retrieval.

Receipts:

- [content-free result](../results/nl2sql-identifier-cross-domain-transfer-2026-08-09.json)
- [independent verification](../results/nl2sql-identifier-cross-domain-transfer-verification-2026-08-09.json)
- [`nl2sql_identifier_cross_domain_transfer.py`](../../nl2sql_identifier_cross_domain_transfer.py)
