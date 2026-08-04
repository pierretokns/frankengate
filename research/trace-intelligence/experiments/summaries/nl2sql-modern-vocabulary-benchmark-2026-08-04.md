# Modern vocabulary port on held-out NL2SQL schemas (2026-08-04)

The current-Python TermSuite/Termolator-style port was evaluated on the
42-case public Defog alias cohort. Each cross-schema fold held out one database,
mined terms from targeted questions in the other databases, and checked whether
the resulting candidates covered gold-SQL table/column target surfaces in the
held-out database. A within-schema split is included as a control. Scope-swapped
NIL questions supplied the background corpus.

This is a **schema-transfer diagnostic**, not semantic-alias ground truth.
Gold-SQL objects identify what the query executed, but they do not tell us that
a user used an undocumented corporate alias or that a candidate is useful to a
person.

Receipt: [`nl2sql-modern-vocabulary-benchmark-2026-08-04.json`](../results/nl2sql-modern-vocabulary-benchmark-2026-08-04.json)

Verifier: [`nl2sql-modern-vocabulary-benchmark-verification-2026-08-04.json`](../results/nl2sql-modern-vocabulary-benchmark-verification-2026-08-04.json)

## Result

| Condition | Targets | Direct surface recall | Termhood recall |
|---|---:|---:|---:|
| Cross-schema held-out | 137 | 0.489 | 0.015 |
| Within-schema control | 67 | 0.388 | 0.358 |

The large gap is the useful finding: termhood can recover recurring vocabulary
when the schema is represented in the mining corpus, but it transfers poorly
to an unseen schema. That is consistent with a search-enrichment role for
approved internal vocabulary, not a generic replacement for identifiers or a
custom enterprise embedding model.

Interpretation should compare `direct_surface_recall` with `termhood_recall`
within each condition. The cross-schema arm tests portability; the
within-schema control tests whether repeated vocabulary is present at all. If
termhood does not exceed the direct-surface baseline, this is evidence that
generic termhood is not a substitute for enterprise aliases, identifiers, or
reviewed ontology links. It does not disprove the port: the decisive next test
requires same-enterprise reformulations, same-surface/different-system
negatives, temporal renames, and independent review labels.
