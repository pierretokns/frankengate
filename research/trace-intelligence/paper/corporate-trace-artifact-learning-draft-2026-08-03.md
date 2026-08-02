# Corporate trace-artifact learning: a governed path from agent histories to reusable tools

**Draft status:** empirical systems paper outline, updated 2026-08-06;
enterprise outcome gates remain open.

The receipt-linked [current evidence matrix](../experiments/summaries/current-evidence-matrix-2026-08-06.md)
is the authoritative result index. This draft is intentionally narrower than
the full research program and does not claim enterprise transfer.

## Abstract

Agent traces contain repeated SQL, tool calls, corrections, failures, and
recoveries that could become reusable artifacts. The difficult case is not
generic semantic search: enterprise systems contain undocumented aliases,
same-surface identifiers in different systems, changing schemas, authority
epochs, and incomplete evidence of user intent. We study a governed lifecycle
that represents a trajectory as a loss-aware event graph, retrieves candidates
with exact identifiers and scope before optional dense search, asks models to
propose or adjudicate only ambiguous cases, and validates artifacts through
independent replay.

Across public NL2SQL, agent-trajectory, and tool-replay cohorts, we find that
structured identity is more reliable than generic embedding adaptation,
frontier models are useful as selective adjudicators but not hot-path
retrievers, and trace-mined procedures have not yet improved changed-task
outcomes. These are transfer-boundary results, not refutations of the source
papers. The paper's main contribution is a claim-disciplined artifact
admission protocol: a retrieval hit is not a semantic label, a valid SQL
execution is not semantic equivalence, and a model-generated procedure is not
a released skill without changed-system replay.

The latest artifact probe adds a positive mechanics result with an explicit
negative control: parameterized retrieval recovered `52/52` value mutations
and abstained on `10/10` template-absence NIL proxies only when compatibility
gates were enforced. The modernized TermSuite/Termolator and AcronymExpansion
ports remain candidate-generation baselines, not enterprise ontology or
embedding-training systems.

## Research questions

**RQ1 — Identity and retrieval.** Can exact, lexical, dense, or
identifier-aware representations find the intended corporate object while
rejecting same-scope and wrong-system collisions?

**RQ2 — Adaptation.** Does hard-negative or embedding adaptation transfer to an
unseen database family, or do structured identifiers and scope dominate?

**RQ3 — Insight cascades.** What should embeddings, local models, and frontier
models each do when mining traces for procedures, evals, memories, or skill
signals?

**RQ4 — Artifact reuse.** Can validated SQL/tool artifacts survive schema,
tool-contract, authority, and temporal drift without false semantic acceptance?

**RQ5 — Utility.** Do trace-mined artifacts improve changed-task outcomes,
human work, or cross-user transfer?

## Position relative to prior work

The program combines adjacent ideas rather than claiming to rediscover them:

| Prior family | Exact contribution | Adaptation needed here |
|---|---|---|
| [NVIDIA ASPIRE](https://research.nvidia.com/labs/gear/aspire/) and [ENPIRE](https://research.nvidia.com/labs/gear/enpire/) | Reset, execute, verify, repair, and admit reusable skills | Replace robotics state/action assumptions with SQL/tool authority, schema drift, and result-equivalence oracles |
| [SKILL-DISCO](https://arxiv.org/abs/2606.26669) | Distills repeated successful traces into parameterized control-flow subgraphs and compiles executable, verifiable skills | Preserve the executable subgraph, but add hidden-intent, authority-epoch, schema/tool-drift, and semantic-ID gates |
| [Enterprise hard-negative mining](https://aclanthology.org/2025.acl-industry.72/) | Contextually irrelevant but semantically close negatives | Add same-scope aliases, stale versions, tenant authority, and executable replay |
| [Schema retrieval](https://arxiv.org/abs/2607.13311) | Corpus adaptation, schema-generated queries, and granularity-aware hard negatives for table/column retrieval | Reproduce on enterprise schemas with user/project/time/system holdouts, then add raw trace branches, tool results, and temporal provenance |
| [TRACE](https://arxiv.org/abs/2607.22639) | Rule-grounded enterprise tool retrieval | Add artifact lifecycle, authorization epochs, and changed-system outcomes |
| Memo-SQL / Query Capsules / workload mining | Typed SQL fragments, failure memory, and workload reuse | Add tenant-safe governance, migration mappings, and rollback |
| Graph/process-memory systems | Temporal entities, event graphs, and provenance | Do not treat graph or embedding proximity as semantic truth |
| [RESOURCE2SKILL](https://arxiv.org/abs/2606.29538) and [SoK: Agentic Skills](https://arxiv.org/abs/2602.20867) | Multimodal/provenance-rich skill libraries and a full skill lifecycle/security taxonomy | Add source diversity, trust tiers, and lifecycle receipts without making raw trace summaries promotion-eligible |
| Generic RAG and episodic memory | Candidate recall and evidence previews | Insufficient for authority, freshness, execution, deletion, or utility on their own |

The complete intersection—private tool-rich histories, identity collisions,
validation-carrying artifacts, authority epochs, changed-system replay, and
prospective enterprise outcomes—was not found as one evaluated prior system.

## Experimental design

All committed receipts are content-minimized. Raw prompts, SQL, model output,
rows, and vectors remain in explicitly external audit directories. Every
experiment records its dataset/source hash, split, candidate construction,
claim boundary, and independent verifier where applicable.

### Retrieval cohorts

- **Real public NL2SQL alias/NIL:** 22 Defog-derived cases: 6 explicit, 8
  implicit, and 8 constructed scope-swapped NILs.
- **Same-scope collision:** 17 Defog-derived cases with same-normalized-name
  siblings inside one database; the target is a deterministic gold-SQL focus
  proxy, not an SME alias label.
- **Database-family adaptation:** the collision cohort split across three
  held-out families.
- **MATM:** 2,130 ALFWorld trajectories and 33 leave-one-model-out folds for
  embedding candidate recall and outcome-neighbor prioritization.
- **Wisp:** blinded structural recovery candidates for model agreement and
  evidence-grounded procedure proposals.

### Artifact and utility cohorts

- A real PostgreSQL governed capsule lab tests authority, epoch, expiry,
  parameter, schema, RLS, and bound-parameter gates.
- A five-case changed-system artifact matrix tests unchanged, additive,
  approved rename, semantic collision, and same-name semantic drift.
- A family-disjoint BIRD-SQL changed-agent replay pairs candidate and control
  on 20 future tasks.
- Disjoint car→broker and other sequential replays test trace-mined procedure
  transfer with no-skill, neutral, placebo, and mined arms.

## Results

| Question | Result | Interpretation |
|---|---|---|
| Public alias/NIL retrieval | Exact/lexical/dense target MRR `.893/.806/.690`; Luna `1.000`; Luna abstained on all 8 constructed NILs | Frontier abstention is useful after candidate generation; public gold-derived candidate pools are not enterprise semantic truth |
| Same-scope identity | Dense sibling-before-target `.235`; lexical `.059`; exact `.0`; Luna `.0` with Recall@1 `.941` | Cross-database scope is insufficient; preserve table/column identity |
| Identifier-aware ranker | Leave-one-database-out MRR `.737`, Recall@1 `.647`, Recall@5 `.882`, collision-before-target `.0` | A cheap structured lane is promising before frontier review |
| Embedding adaptation | Table-aware embedding Recall@1 `.373`; structured `.337`; learned hard-negative adapter `.302` and collision-before-target `.512`; a separate schema-grounded 2026 study reports large leave-one-corpus-out gains from synthesized schema queries and granularity-aware hard negatives | No promotion on the MATM proxy; the matched schema recipe remains open |
| Embedding/model cascade | MATM action embeddings improve Recall@20 by `+.123`; outcome-neighbor AUC delta `-.056`; Luna proposal grounding `3/4` | Separate candidate recall, review prioritization, and proposal quality; never pool unlike labels |
| Local/frontier label agreement | Six Wisp candidates: all-field agreement `0%`; usefulness agreement `0%`; cause agreement `33.3%` | Cheap models are not interchangeable with frontier/human adjudicators |
| Changed-agent utility | Expanded BIRD 40-task replay: trace procedure `8/40` exact, equal to no-skill `8/40`; paired trace-vs-no-skill `1–1` with 38 ties; mean latency `11.102s` vs `10.306s` | No measured trace-mined utility lift; the larger checkpoint remains a bounded no-lift result |
| Changed-system artifact safety | Strict fingerprints accept `1/5`; name-only adaptation `5/5` with 2 false semantic accepts; semantic IDs `3/5` with 0 false accepts | Use explicit semantic mappings plus result/outcome validation |
| Validated subplan composition | Two seeded frontier replays on five broker tasks: composed library `10/10`, fresh generation and placebo `5/10` each; three stable wins and no stable losses | Decompose validated examples into typed subplans; promising but small, single-family, and not yet a promotion result |
| Family-disjoint composition transfer | Two BIRD replays: library `8/40` versus `6/40` for both controls; one stable win and zero stable losses | Aggregate signal is stable but low-headroom; insufficient for a causal or enterprise claim |

## Main conclusions

1. **Identity beats generic similarity for corporate retrieval.** Database,
   project, tenant, table, column, tool, version, and authority scope are
   first-class features. Embeddings should not decide authority or identity.
2. **Frontier models belong in the gray zone.** They can structure evidence and
   resolve ambiguous candidates, but low local/frontier agreement prevents
   automatic promotion.
3. **Hard-negative weighting is not enough.** The hard-negative adapter lost to
   deterministic structured scoring and increased collision errors. Better
   labels and representation may matter more than a larger optimizer.
   Recent industrial-log and process-industry studies similarly construct
   contrastive examples from expert comments, graph/lineage structure, or
   interpretable event features; they do not show raw logs alone recovering
   enterprise semantics.
4. **Artifacts must carry validation.** A reusable SQL/tool object needs schema
   and semantic IDs, parameter contracts, authority/epoch, result shape,
   provenance, expiry, migration mappings, replay outcomes, and rollback.
5. **Skill utility is not established.** The largest changed-agent replay is a
   no-lift result. Nulls are not paper disproof because the protocols differ
   from same-environment skill-learning benchmarks.

## Proposed Frankengate architecture

```text
loss-aware trajectory DAG
  -> authority/deletion/temporal filters
  -> exact identifiers + structured scope
  -> lexical retrieval
  -> optional dense candidate recall
  -> cheap identifier-aware rerank
  -> frontier/human ambiguity + NIL adjudication
  -> validation-carrying artifact proposal
  -> independent replay/result equivalence
  -> release, quarantine, rollback, or deletion
```

The minimum production dependency set is one governed relational evidence and
artifact store, a canonical trajectory representation, exact/lexical search,
optional vectors, and an isolated replay/evaluation service. A custom embedding
model, graph database, automatic memory writer, or cross-user recommender is an
experimental add-on, not a required dependency.

## Threats to validity

- Public positives are gold-SQL or structural proxies, not enterprise semantic
  truth.
- Candidate pools are bounded and sometimes constructed using gold objects;
  these are not end-to-end alias-discovery tests.
- Most cohorts lack independent user satisfaction, skill-gap, or collaboration
  labels.
- Small local/frontier agreement samples measure disagreement, not correctness.
- Changed-system fixtures are controlled and do not represent production
  migration prevalence.
- Cost and latency are not comparable across all receipts.

## Preregistered next study

The [enterprise semantic-label and changed-system replay protocol](../experiments/protocols/enterprise-semantic-label-and-drift-2026-08-03.md)
requires two independent SME labels, frozen candidate generation, user/
project/system/time holdouts, true NIL/unclear cases, migration/tool drift,
independent outcome oracles, and release-blocking false semantic acceptance.
The complementary [skill-representation and replay protocol](../experiments/protocols/skill-representation-and-replay-2026-08-01.md)
isolates executable control-flow from prose and retrieval memory with
length-matched controls before any positive skill claim is made.
The [schema-adaptive embedding protocol](../experiments/protocols/schema-adaptive-embedding-2026-08-01.md)
separately reproduces schema-generated positives and granularity-aware hard
negatives, avoiding the task mismatch in the MATM adapter null.

## Publication and collaboration

The narrow publishable claim is a **governed evidence-to-artifact lifecycle**,
not “enterprise memory improves agents.” Suitable venues are ACL/EMNLP Industry
for alias retrieval, SIGMOD/VLDB for governed artifacts and workload reuse, and
ICSE/FSE for trace-to-replay lifecycle design. The first partner conversations
should target CMU LTI/SkillLearnBench, MIT DSAIL, Harvard CHARM/DASlab/Variation
Lab, MIT CLEAR/TRAC, and NVIDIA GEAR. The [partner package](../experiments/summaries/publication-partner-opportunities-2026-08-02.md)
contains the proposed 6–8 week reproduction plan.

## Reproducibility links

- [Requirement-level status ledger](../experiments/summaries/corporate-artifact-learning-status-2026-08-03.md)
- [Research epic #118](https://github.com/pierretokns/frankengate/issues/118)
- [Research branch](https://github.com/pierretokns/frankengate/tree/codex/trace-intelligence-academic-program)
