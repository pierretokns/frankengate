# Train-only alias enrichment replay

**Status:** bounded negative retrieval result
**Corpus:** pinned Defog PostgreSQL public proxy; 83 train rows and 41 held-out rows, with zero source-row overlap
**Authority:** target-object proxy from gold SQL; not semantic enterprise alias
ground truth

## Result

Train-only exact surface-to-gold-identifier associations were used as an
approved alias field. Ambiguous surfaces were withheld rather than
auto-approved.

| Arm | MRR | Recall@1 | Recall@5 | Wrong-system-before-target |
|---|---:|---:|---:|---:|
| Lexical baseline | .734885 | .634146 | .829268 | 0.0 |
| Alias support ≥1 | .734885 | .634146 | .829268 | 0.0 |
| Alias support ≥2 | .727542 | .634146 | .829268 | 0.0 |

Support ≥1 covered only 2/260 target objects (`0.77%`); support ≥2 covered
17/260 (`6.54%`). There were 506 ambiguous surface classes. The aliases
therefore added almost no coverage and did not improve ranking; support ≥2
slightly reduced MRR.

Receipt:
[`nl2sql-alias-enrichment-2026-08-04.json`](../results/nl2sql-alias-enrichment-2026-08-04.json)

## Interpretation

This does not disprove enterprise vocabulary mining. It shows that aliases
mined from sparse public gold-SQL rows are too low-coverage to improve this
retrieval task, and that frequency-based promotion is unsafe when ambiguity is
common. The next useful test needs real reformulation chains, reviewed aliases,
temporal replacements, and a larger same-scope hard-negative set. Approved
aliases should remain a search-only feature and require evidence plus owner
review before ontology or memory promotion.
