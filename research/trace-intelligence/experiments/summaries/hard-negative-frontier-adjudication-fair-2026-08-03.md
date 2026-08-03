# Fair-cohort hard-negative control comparison

## Design correction

The initial frontier receipt sampled candidates using a query-plus-candidate
hash, so each arm could contain different questions. That receipt remains a
valid exploratory screen, but it was not a fair arm comparison. The runner now
selects one deterministic query cohort by query hash and uses that same cohort
for every arm; only the selected negative page changes.

The corrected run used 12 questions per arm, two independent
`gpt-5.6-luna` calls per candidate, and four arms:

- LaBSE inequality-selected negatives;
- six-encoder composite inequality-selected negatives;
- TF-IDF lexical-nearest negatives;
- deterministic random negatives.

Gold page IDs were withheld from all judge packets.

## Results

| Arm | Near miss | Unrelated | Judged relevant false negative | Repeat agreement |
| --- | ---: | ---: | ---: | ---: |
| Six-encoder composite | 12/24 (50.0%) | 8/24 (33.3%) | 4/24 (16.7%) | 10/12 (83.3%) |
| LaBSE | 8/24 (33.3%) | 13/24 (54.2%) | 3/24 (12.5%) | 8/12 (66.7%) |
| Lexical nearest | 14/24 (58.3%) | 7/24 (29.2%) | 3/24 (12.5%) | 8/12 (66.7%) |
| Random | 2/24 (8.3%) | 22/24 (91.7%) | 0/24 (0.0%) | 12/12 (100%) |

Machine-readable receipt:
[`hard-negative-frontier-adjudication-fair-2026-08-03.json`](../results/hard-negative-frontier-adjudication-fair-2026-08-03.json).

## Interpretation

The fair result changes the conclusion from the exploratory screen:

1. The composite is a stronger source of semantically close candidates than
   LaBSE on this cohort, but it also has the highest observed false-negative
   rate (`4/24`).
2. LaBSE is not safe merely because the first small screen found no explicit
   false negatives; the corrected cohort found `3/24` judged relevant pages.
3. Lexical retrieval produced the most near-misses (`14/24`) but the same
   judged false-negative rate as LaBSE. It remains a strong baseline.
4. Random negatives are a useful sanity control, not a viable hard-negative
   generator.
5. The frontier judge disagreed on `2/12` LaBSE and lexical cases and `2/12`
   composite cases. The high-confidence labels are silver, not ground truth.

This is still a small public-document transfer test. It does not establish
enterprise alias quality, SQL/tool outcome correctness, or safe contrastive
training. The apparent false-negative rates require blinded SME adjudication.

## Required next gate

Use the same query cohort and add blinded SME labels for exact identifiers,
same-scope siblings, aliases, NILs, temporal renames, and changed systems.
Compare downstream reranker and replay utility, not only candidate labels, and
reject any arm whose false-negative or wrong-system rate rises without a
measurable outcome gain.
