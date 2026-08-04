# Query-expansion probe (bounded synthetic fixture)

## Scope

This is a deterministic mechanics probe, not an implementation or replication
of QueryGym, ConvGQR, or SIRA. It uses six synthetic search documents and 12
queries (six alias, three exact, one collision, and two conversational cases).
The ranking function is transparent lexical overlap with a canonical-name
bonus; the expansion vocabulary is a reviewed fixture dictionary. Gold target
IDs are used only for scoring. No model calls, enterprise corpus, or human
labels are involved.

Receipt: [`query-expansion-probe-2026-08-01.json`](../results/query-expansion-probe-2026-08-01.json)
Verifier: [`verify_query_expansion_probe.py`](../../verify_query_expansion_probe.py)

## Aggregate result

| Arm | MRR | Recall@1 | Recall@3 | Wrong top-1 |
| --- | ---: | ---: | ---: | ---: |
| Lexical baseline | 0.847222 | 0.750000 | 0.916667 | 3/12 |
| QueryGym keyword proxy | 0.958333 | 0.916667 | 1.000000 | 1/12 |
| QueryGym pseudo-document proxy | 0.958333 | 0.916667 | 1.000000 | 1/12 |
| QueryGym answer/entity proxy | 0.958333 | 0.916667 | 1.000000 | 1/12 |
| QueryGym corpus-feedback proxy | 0.847222 | 0.750000 | 0.916667 | 3/12 |
| ConvGQR-style history+follow-up rewrite | 0.888889 | 0.833333 | 0.916667 | 2/12 |
| SIRA-style document enrichment | 0.958333 | 0.916667 | 1.000000 | 1/12 |

On the two conversational cases only, the history+follow-up rewrite reached
2/2 Recall@1 versus 1/2 for the raw follow-ups. Corpus feedback did not improve
this fixture and can reinforce the baseline's first mistake. Alias-oriented
query and document expansion recovered the six alias cases in this toy corpus,
but that is expected from the reviewed dictionary and is not evidence of
semantic generalization.

## Interpretation boundary

The probe supports only a narrow engineering hypothesis: approved search-only
vocabulary and explicit conversation rewriting can recover lexical omissions in
a controlled fixture, while pseudo-relevance feedback is not automatically
helpful. It does not establish enterprise relevance, acronym/alias quality,
authorization safety, or production latency. The next valid test is a blinded
Defog holdout with reviewed aliases and conversational correction chains;
the existing Defog alias result is a negative control (support≥1 covered 2/260
targets and did not improve MRR).
