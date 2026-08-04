# Family-disjoint broker replay with schema-injected protocol

This replay uses six broker tasks not used in the earlier car-dealership or
broker pilot receipts: four advanced tasks (categories `instructions_cte_join`,
`instructions_cte_window`, and `instructions_date_join`) and two basic tasks.
The same Llama 3.2 loopback model, three arms, governed authority, common
authorized schema injection, and 10-turn/5-attempt/8,192-token protocol were
used for every arm.

| arm | tasks | submitted candidates | semantic-correct | semantic-incorrect | abstained | unauthorized observations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no-skill | 6 | 0 | 0 | 0 | 6 | 0 |
| formatting placebo | 6 | 1 | 1 | 0 | 5 | 0 |
| trace-mined terminal discipline | 6 | 0 | 0 | 0 | 6 | 0 |

The independent semantic verifier re-executed the one submitted candidate and
all sealed gold alternatives; stored and recomputed outcomes matched. The raw
security verifier passed all 18 audit files. The family-disjoint trace-mined
contrast is 0/6 versus 0/6, while the formatting placebo happened to produce
one correct answer. This is a small, abstention-heavy transfer result—not a
causal skill estimate—and it does not authorize promotion.
