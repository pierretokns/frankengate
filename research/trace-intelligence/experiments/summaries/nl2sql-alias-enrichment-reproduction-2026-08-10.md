# NL2SQL alias-enrichment reproduction

Date: 2026-08-10  
Status: reproduced; public proxy only

The train-only alias enrichment benchmark was rerun against the pinned
external Defog CSV and schema roots. The resulting SHA-256 is identical to the
2026-08-04 receipt, confirming deterministic source hashing, split selection,
and aggregate computation.

| arm | MRR | Recall@1 | train-link target coverage |
|---|---:|---:|---:|
| lexical | `.734885` | `.634146` | — |
| support-1 aliases | `.734885` | `.634146` | `.007692` |
| support-2 aliases | `.727542` | `.634146` | `.065385` |

There were `506` ambiguous surfaces. Even with 79 support-2 links, the alias
arm did not improve retrieval and slightly reduced MRR. This is not evidence
that alias learning is useless; it shows that frequency-derived links from
gold SQL are sparse and not a substitute for reviewed semantic aliases,
same-surface wrong-system negatives, temporal versions, or NIL labels.

Receipt: [`nl2sql-alias-enrichment-reproduction-2026-08-10.json`](../results/nl2sql-alias-enrichment-reproduction-2026-08-10.json)

The next valid adaptation test remains a task/database-disjoint cohort with
independent semantic labels and changed-system replay. A model or embedding
should not be promoted from this lexical proxy.
