# Recent RAG and trace-learning audit

This audit covers the newly named LRAT, UNO, ComRAG, SWE-ContextBench,
AgentTrails, SkillAxe, SAGE variants, EnterpriseRAG-Bench, DQA, Trendyol's
real-interaction study, and the unresolved “ACRM” reference. It distinguishes
new mechanisms from work already represented in the Frankengate receipts.

## New mechanisms worth testing

| System | New idea for Frankengate | Evidence status | Proposed controlled experiment |
| --- | --- | --- | --- |
| [UNO](https://github.com/bebr2/UNO) | Convert accepted/corrected answers into semi-structured rules and preference pairs; cluster by cognitive gap; route a primary expert and reflective critic. | Official repository/README, not peer-reviewed evidence. | Rule-only vs cluster retrieval vs adapter vs reflective critic, holding out user/project/time; score validated SQL/tool outcomes, not BLEU or raw judge preference. |
| [ComRAG](https://aclanthology.org/2025.acl-industry.53/) | Dynamic centroid memory and consolidation to control index growth and latency. | ACL Industry paper; not trace-artifact or authority evidence. | Static vs centroid vs hybrid indexes under append, stale-fact, contradiction, and churn workloads; require immutable artifact lineage and replay. |
| [SWE-ContextBench](https://arxiv.org/abs/2602.08316) | Relation-aware sequential task chains; compares full trajectories, summaries, and retrieval under accuracy/time/cost. | Preprint; code/task relationships may leak. | No memory vs full trace vs validated summary vs retrieved artifact on same-family chains, project-held-out chains, and changed schemas/tools. |
| [AgentTrails](https://arxiv.org/abs/2607.18816) | Bipartite provenance graph linking actions/tools to data artifacts, then joined-quotient alignment across runs. | Workshop/preprint prototype. | Stable action/artifact IDs and exact dataflow edges; graph retrieval vs text/vector retrieval; review inferred edges and replay executable subgraphs. |
| [SkillAxe](https://arxiv.org/abs/2606.10546) | Separates skill quality, trigger precision, instruction compliance/fault attribution, and solution-path coverage. | Preprint; diagnostics depend on model judgments. | Add these four diagnostics to artifact activation/binding/replay; compare no-skill, placebo, reviewed, generated, and SkillAxe-style refinement on changed systems. |
| [DQA](https://aclanthology.org/2026.acl-industry.79/) | Persistent competing diagnostic hypotheses and evidence aggregation, rather than repeated clarification alone. | ACL Industry paper; replay/data protocol still needs audit. | DQA hypothesis-state arm vs clarification-only and over-questioning placebo; measure premature execution, correction turns, SQL/tool outcome, and independent root-cause evidence. |
| SAGE retrieval benchmark ([paper](https://arxiv.org/abs/2602.05975)) | Keyword subqueries and corpus-level metadata enrichment can beat LLM/dense retrievers. | Preprint benchmark. | Add offline metadata/keyword expansion before dense retrieval; preserve exact identifiers and compare candidate recall, NIL, and cost. |
| Trendyol production study ([paper](https://aclanthology.org/2026.mme-main.12.pdf)) | 150k real QA interactions; combines satisfaction labels, multiple judges, and factorized retrieval/context/generation diagnostics. | Production study with proprietary data/models. | Add satisfaction, retry, acceptance, and replay outcomes; calibrate judge disagreement and separate retrieval from context and generation failures. |
| A-RAG ([paper](https://arxiv.org/abs/2602.03442), likely intended by “ACRM”) | Hierarchical retrieval tools expose keyword search, semantic search, and chunk-read so the agent chooses retrieval granularity. | Adjacent preprint. | Compare fixed hybrid retrieval with tool-mediated keyword/semantic/chunk retrieval under a token and latency budget. |
| ACGM ([paper](https://arxiv.org/abs/2604.07863), another possible “ACRM”) | Task-adaptive graph retrieval optimized using downstream success, with modality/time decay. | Adjacent preprint; web/GUI domain. | Only test after provenance and authority edges exist; use downstream replay reward, not graph similarity alone. |

## Already represented or not direct evidence

- [LRAT](https://arxiv.org/abs/2604.04949) is already audited locally. Its
  browse/rejection/post-browse signals are useful propensity-weighted candidate
  supervision, but the current receipts lack explicit outcomes, failures, and
  rewards. Use LRAT only as a retrieval/exposure arm.
- [EnterpriseRAG-Bench](https://github.com/onyx-dot-app/EnterpriseRAG-Bench) is
  already extensively tested. Its synthetic multi-source corpus, conflict,
  completeness, NIL, and metadata slices are valuable document-side fixtures,
  not trace, skill, or employee-capability evidence.
- SAGE skill-augmented GRPO is already covered by the skill prior-art and
  changed-system receipts. Its headline gains depend on expert SFT/RL and
  sequential same-scenario rollout, not frozen artifact retrieval.
- Generic trajectory extraction, hard negatives, dense/lexical retrieval,
  artifact replay, and frontier review are already implemented in this branch;
  the new value is the specific diagnostic/provenance/lifecycle variants above.

The first independent ComRAG-style trace benchmark is now complete. On 40
chronologically sampled public sessions, centroid memory matched full-history
shape/project recurrence at 11–12 clusters, but lost `.083` shape and project
hit at a four-cluster budget. High/low quality routing added no lift. This is a
proxy memory-compression result, not evidence for answer or artifact utility;
see [`comrag-centroid-trace-benchmark-2026-08-03.md`](comrag-centroid-trace-benchmark-2026-08-03.md).

## Cross-cutting factorial

The highest-value next experiment is one fixed, consented, outcome-labelled
cohort with identical query/task splits and these retrieval/learning arms:

```text
exact + scope
  -> BM25 / metadata enrichment
  -> frozen dense
  -> LRAT exposure-weighted ranker
  -> AgentTrails provenance graph
  -> ComRAG centroid memory
  -> UNO rule/preference + critic
  -> SkillAxe diagnostics
  -> DQA hypothesis state
  -> A-RAG retrieval tools
  -> frontier review
```

Measure candidate Recall/MRR, false-negative and wrong-system rates, NIL and
temporal-renaming abstention, authority/security success, execution outcome,
turns/tokens/latency, repair/regression, and user satisfaction. Promote only
after independent changed-system replay. Do not combine every mechanism into a
single opaque stack before each component has a separate arm.

## ACRM ambiguity

No authoritative agent/RAG paper matching “ACRM” was found. It should not be
silently treated as A-RAG or ACGM in an issue or publication claim. Verify the
article's expansion first; both candidates are recorded above as separate,
adjacent hypotheses.

## Source quality

ComRAG, DQA, and the Trendyol study have peer-reviewed industry/proceedings
evidence. LRAT, SWE-ContextBench, SkillAxe, AgentTrails, and SAGE graph/retrieval
are preprints or prototypes. UNO is currently repository/README evidence. The
reported headline numbers therefore guide experiment design, not Frankengate
promotion decisions.

## A-RAG reproduction result

The first bounded A-RAG-style frontier run is complete. On the same synthetic
1/5/10/25-wiki fixture and `gpt-5.6-luna` harness used by the fixed-hybrid
baseline, exposing `keyword_search`, `semantic_search`, and `read_chunk` did
not improve target answer accuracy: both arms were `1.00/1.00/1.00/0.75` at
1/5/10/25 wikis. The 25-wiki A-RAG arm again had one step-limit failure and had
higher p95 wall time (`50.7s` versus `39.4s` in the earlier run). The agent
used keyword search 24 times, semantic search 6 times, and chunk reads 16
times across 20 cases.

This is a negative result for the **unconditioned tool-interface change on
this identifier-heavy fixture**, not a disproof of A-RAG. The next test must
use balanced paraphrase, multi-hop, temporal, and NIL cohorts with a fixed
question/model-seed comparison and an oracle tool-choice upper bound. See
[`wiki-arag-frontier-reproduction-2026-08-03.md`](wiki-arag-frontier-reproduction-2026-08-03.md).
