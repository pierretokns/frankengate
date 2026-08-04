# NL2SQL surface-to-schema alias baseline — 2026-08-02

This analysis uses 314 rows from the pinned public Defog PostgreSQL NL2SQL
cohort (questions, basic instructions, and advanced instructions). It extracts
table/qualified-column identifiers from gold SQL and links only exact
morphological variants in the question (underscore normalization and simple
singular/plural rules). It is intentionally a lower bound, not a semantic
alias detector.

| Measure | Result |
| --- | ---: |
| rows | 314 |
| rows with extracted SQL identifiers | 314 |
| surface-to-identifier links | 492 |
| distinct surface hashes, summed per source file | 186 |
| ambiguous surface hashes | 13 |
| same-database collision hashes | 1 |
| cross-database collision hashes | 13 |

This demonstrates that even a conservative lexical baseline produces repeated
surface forms that map to different canonical identifiers or database scopes.
It does **not** prove that those collisions are true corporate aliases: some
are ordinary language or schema-name reuse. The next experiment must add
frontier/SME adjudication for alias, NIL, and wrong-system labels, then create
same-surface/different-system hard negatives and evaluate exact, lexical, dense,
and rule-aware retrieval on user/project/time-held-out splits.

The committed receipts contain hashes and counts only; questions, SQL, and
schema identifiers remain in the external pinned dataset.

