# Train-only termhood alias retrieval (2026-08-04)

This experiment composes the current-Python termhood port with the existing
schema-object retrieval benchmark. For each database, half of the targeted
questions build a termhood-selected question-n-gram → gold-SQL-object mapping;
the other half are held out. Retrieval compares the existing lexical arm with
the same arm plus the approved mapping as a search-only alias boost.

Receipt: [`nl2sql-termhood-alias-retrieval-2026-08-04.json`](../results/nl2sql-termhood-alias-retrieval-2026-08-04.json)

Verifier: [`nl2sql-termhood-alias-retrieval-verification-2026-08-04.json`](../results/nl2sql-termhood-alias-retrieval-verification-2026-08-04.json)

## Result

| Arm | MRR | Recall@1 | Recall@5 | Same-scope collision before target |
|---|---:|---:|---:|---:|
| Lexical | .860 | .846 | .846 | .077 |
| Lexical + termhood alias | .815 | .769 | .923 | 0.000 |

On this small 13-case evaluation split, the alias field widened Recall@5 and
removed the observed same-scope collision, but reduced MRR and Recall@1. It is
therefore not a promotion-ready improvement: it may be useful as a candidate
recall lane, while exact/identifier-aware ranking remains necessary for the
top result. Frequency/termhood associations still need reviewed ownership and
hard-negative calibration before automatic use.

This is a public gold-SQL proxy, not reviewed enterprise alias truth. The
mapping is train-only and search-only; it is not promoted to memory, skills,
or ontology links. The useful comparison is whether the enriched arm improves
MRR/Recall without increasing same-scope or wrong-system collisions. A null or
negative result would mean sparse public associations are insufficient—not that
reviewed internal reformulations cannot help.
