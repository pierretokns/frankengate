# LRAT trajectory-distilled ranker proxy

Date: 2026-08-02  
Status: completed; silver-label exposure experiment only

We trained a small TF–IDF + balanced logistic ranker on nine LRAT trajectories
and evaluated the tenth, repeating this leave-one-trajectory-out over all ten
trajectories. Positives were documents that were both search-exposed and later
browsed. Search-exposed but unbrowsed documents were used as negatives. Raw
document identifiers were excluded from model text, and only hashes and
aggregate metrics were committed.

| arm | MRR | R@1 | R@5 | R@10 | positive-pool recall |
|---|---:|---:|---:|---:|---:|
| search order | .630682 | .500 | .700 | .800 | 1.000 |
| lexical overlap | **.766667** | **.600** | **1.000** | **1.000** | 1.000 |
| trajectory-distilled ranker | .594490 | .500 | .700 | .700 | 1.000 |

The trajectory-trained proxy did not beat lexical ranking on this cohort. That
is a useful negative result, not evidence that trajectory supervision is
useless: the labels are only browsing behavior, the cohort is ten public
trajectories, and the ranker is deliberately simple. Browsing may reflect
exploration, confirmation, or tool behavior rather than document correctness.
There are no independent answer labels, principal/authority labels, changed
system outcomes, or prospective task-success measurements.

**Decision:** keep later inspection/open behavior as a candidate supervision
source, but do not promote a ranker from it alone. The next fair test needs
human/adjudicated relevance plus same-surface wrong-system, temporal, and NIL
negatives, and must evaluate downstream artifact or task utility rather than
silver retrieval alone.

Receipt: [`lrat-trajectory-distilled-ranker-proxy-2026-08-02.json`](../results/lrat-trajectory-distilled-ranker-proxy-2026-08-02.json)  
Runner: [`lrat_trajectory_distilled_ranker_proxy.py`](../../lrat_trajectory_distilled_ranker_proxy.py)  
Verifier: [`verify_lrat_trajectory_distilled_ranker_proxy.py`](../../verify_lrat_trajectory_distilled_ranker_proxy.py)
