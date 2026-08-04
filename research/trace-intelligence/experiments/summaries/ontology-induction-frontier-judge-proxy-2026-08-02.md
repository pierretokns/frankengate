# Silver evidence judge for ontology proposals

Date: 2026-08-02  
Status: completed silver-label diagnostic; not ground truth

We ran a second Luna pass over the five-case repeat. The judge received each
source excerpt and one proposed graph, and classified every emitted entity or
relation as `supported`, `unsupported`, or `unclear` using only the excerpt.
Raw excerpts, proposals, and judge responses remain external; the receipt
contains hashes and counts only.

| arm | judged items | supported | unsupported | unclear |
|---|---:|---:|---:|---:|
| GOI-style proposal | 75 | **.866667** | .013333 | .120000 |
| starter-schema population | 57 | .807018 | **.035088** | .157895 |

This is the first direct signal of “mostly garbage” risk in the pipeline, but
it is still a silver label: the same frontier model family performed both
extraction and judgment, and there are no human adjudicators or downstream
outcomes. Evidence grounding is also not semantic truth. The constrained arm
emitted fewer items, while the judge marked a larger fraction unsupported or
unclear. One population case emitted no judgeable items, which is represented
as zero items rather than silently treated as success.

**Decision:** use the judge only to prioritize human review and compare prompt
changes. Do not convert its supported rate into ontology precision or allow it
to promote aliases, relations, skills, or memories. The required next study is
two independent SME labels plus NIL/temporal/authority and changed-system
replay outcomes.

Receipt: [`ontology-induction-frontier-judge-proxy-2026-08-02.json`](../results/ontology-induction-frontier-judge-proxy-2026-08-02.json)

Runner: [`ontology_induction_frontier_judge_proxy.py`](../../ontology_induction_frontier_judge_proxy.py)

Verifier: [`verify_ontology_induction_frontier_judge_proxy.py`](../../verify_ontology_induction_frontier_judge_proxy.py)
