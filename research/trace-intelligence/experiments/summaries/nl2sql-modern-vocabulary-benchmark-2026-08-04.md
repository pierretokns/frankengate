# Modern vocabulary port on held-out NL2SQL schemas (2026-08-04)

The current-Python TermSuite/Termolator-style port was evaluated on the
42-case public Defog alias cohort. Each fold held out one database, mined terms
from targeted questions in the other databases, and checked whether the
resulting candidates covered gold-SQL table/column target surfaces in the
held-out database. Scope-swapped NIL questions supplied the background corpus.

This is a **schema-transfer diagnostic**, not semantic-alias ground truth.
Gold-SQL objects identify what the query executed, but they do not tell us that
a user used an undocumented corporate alias or that a candidate is useful to a
person.

Receipt: [`nl2sql-modern-vocabulary-benchmark-2026-08-04.json`](../results/nl2sql-modern-vocabulary-benchmark-2026-08-04.json)

Verifier: [`nl2sql-modern-vocabulary-benchmark-verification-2026-08-04.json`](../results/nl2sql-modern-vocabulary-benchmark-verification-2026-08-04.json)

Interpretation should compare `direct_surface_recall` with `termhood_recall`.
If termhood does not exceed the direct-surface baseline, this is evidence that
generic termhood learned on other schemas is not a substitute for enterprise
aliases, identifiers, or reviewed ontology links. It does not disprove the
port: the decisive next test requires same-enterprise reformulations,
same-surface/different-system negatives, temporal renames, and independent
review labels.
