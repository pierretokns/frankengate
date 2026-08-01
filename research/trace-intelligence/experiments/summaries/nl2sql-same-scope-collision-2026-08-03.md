# Same-scope schema collision benchmark

## Question

Can retrieval distinguish schema objects with the same identifier inside one
database—such as `sales.id` versus `salespersons.id`—rather than only
resolving cross-database scope?

## Protocol

We reused the pinned real Defog NL2SQL cohort and selected 17 cases with at
least one same-scope normalized-name collision. Each case uses one deterministic
gold-SQL focus object as a proxy target and adds every sibling object with the
same normalized identifier, plus lexical distractors. The focus object is not
semantic-alias ground truth. Luna saw only the question, scope, and candidates;
gold targets and source row IDs were hidden. All 17 calls returned valid
structured output.

## Result

| Arm | MRR | Recall@1 | Recall@5 | Same-scope collision before target |
| --- | ---: | ---: | ---: | ---: |
| Exact + scope | .573 | .353 | 1.000 | 0.000 |
| Lexical + scope | .522 | .353 | .882 | .059 |
| Nomic embedding + scope | .586 | .471 | .765 | .235 |
| Luna reranker | .947 | .941 | .941 | 0.000 |

The frontier model retrieved the focus proxy on 16/17 cases. The one miss was
not a collision-before-target event; it was a ranking miss within the bounded
candidate pool.

## Interpretation

This is the first result showing the specific failure mode that the earlier
cross-scope benchmark could not measure. Generic dense retrieval was more
likely than lexical retrieval to put a same-scope sibling ahead of the focus
object. Exact matching avoided that error but often could not choose among
same-name tables. Frontier reranking resolved most of these cases after the
candidate pool was constructed.

This does not prove semantic alias discovery: the target is a deterministic
gold-SQL proxy, the cohort is small, and no SME labels or changed-schema replay
were used. The production implication is still clear: preserve table/column
identity in candidate representations, use exact/structured retrieval for
recall and authority, and reserve frontier adjudication for ambiguous
same-scope collisions.

Receipts: [`../results/nl2sql-same-scope-collision-2026-08-03.json`](../results/nl2sql-same-scope-collision-2026-08-03.json) and
[`../results/nl2sql-same-scope-collision-2026-08-03-verification.json`](../results/nl2sql-same-scope-collision-2026-08-03-verification.json).
