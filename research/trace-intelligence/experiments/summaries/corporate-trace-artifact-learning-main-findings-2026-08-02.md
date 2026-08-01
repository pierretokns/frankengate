# Corporate trace-artifact learning: main findings

**Status:** current evidence synthesis  
**Scope:** reusable SQL/tool artifacts, corporate identifiers and aliases,
hard negatives, domain embedding adaptation, model-vs-embedding analysis,
trace-derived procedures, and publication fit

## Bottom line

The work has not disproven the academic papers. It has tested whether their
mechanisms transfer to a governed, identifier-heavy corporate setting and has
rejected several broad product interpretations of those mechanisms.

The strongest evidence is for a small, structured system:

```text
canonical loss-aware trajectory
  -> current authority and deletion gate
  -> exact identifiers / scope / lexical retrieval
  -> optional dense candidate recall
  -> evidence-linked eval, memory, or artifact proposal
  -> human or independent-verifier review
  -> isolated replay or prospective outcome
```

No automatic skill, memory, embedding adapter, or cross-user recommendation is
promotion-eligible yet.

## Supported mechanisms and useful corporate results

| Finding | Evidence | What it establishes |
| --- | --- | --- |
| Canonical trajectories outperform lossy projections as evidence | Native imports preserve branches, tool/result pairing, malformed records, and explicit OTel/ATIF loss receipts | Use one trajectory DAG and versioned projections; do not make OTel or ATIF a second authority |
| Deterministic mining can produce review queues | Wisp analysis reconstructed 92 structural recovery candidates, 103 eval proposals, and 7 procedure-review candidates; automatic writes were zero | Signals and reconstruction are useful proposal selectors, not skill or intent labels |
| Reusable artifacts can be governed safely | PostgreSQL capsule lab accepted a bound query and denied stale epoch, wrong scope, expiry, parameter mismatch, schema drift, and unsafe SQL interpolation | Build validation-carrying SQL/tool capsules before autonomous memory promotion |
| Structured corporate identity is the highest-value retrieval intervention measured | Exact identifier + known scope: MRR `.4441 -> .6867`, R@1 `.1992 -> .4492`, R@5 `.8150 -> .9980`; wrong-system-before-target `14.43% -> .20%` | Exact identifiers, aliases, database/project/team scope must be the first retrieval lane |
| Dense retrieval is useful after structured filtering | CodeTraceBench exact+structured+dense reached R@20 `.818`; a separate MATM cascade found action-only embedding Recall@20 lift `+.123` over lexical | Treat vectors as candidate recall, not authority or replacement for identifiers |
| Frontier models can create bounded, evidence-grounded proposals | Luna produced valid, structurally grounded proposals for 3/4 meaningful content-minimized sessions; independent receipt verification passed | Model passes are viable after deterministic projection, but proposal quality and utility still require outcome labels |
| Frontier reranking adds value after lexical/dense candidate generation | On nine MATM leave-one-model-out queries, lexical and Luna both had MRR/Recall@1/3/5 `1.0`; embedding MRR `.674`; Luna's top-3 success `.704` tied lexical | Do not put a frontier model on every retrieval request; reserve it for ambiguous, high-value, human-reviewed cases |
| Alias adjudication can represent abstention | Two independent Luna roles scored 23 synthetic exact/semantic/collision/NIL/unclear cases with 1.0 surface, candidate, wrong-system, abstention, and inter-judge agreement | Preserve `nil` and `unclear` as first-class outcomes; this is only a capability gate until enterprise/SME labels exist |
| Frontier abstention works on a real public NL2SQL cohort | On 22 Defog-derived cases, Luna abstained on 8/8 constructed scope-swapped NILs and retrieved all 14 target-bearing cases; exact/lexical/dense retrieval could not abstain | Add an explicit late-stage abstention decision; this is still public/gold-SQL evidence, not enterprise semantic truth |

## Nulls and corrections

| Hypothesis | Correct result | Interpretation |
| --- | --- | --- |
| A Trace2Skill-style compiler transfers a procedure across databases | On a genuinely disjoint car-to-broker replay: no-skill `3/4`, neutral `3/4`, compiled procedure `3/4`, formatting placebo `4/4`; compiled vs controls McNemar `p=1.0` | Compilation, hashing, isolation, and replay are feasible; transfer utility is currently null |
| The earlier native Trace2Skill positive was held-out evidence | The seed-430000 source and replay shared all four broker task IDs; the earlier `4/4` is contaminated development smoke | It must not be cited as transfer evidence |
| The earlier sequential-prefix `2/2` was held out | Source and replay shared broker task IDs `2` and `11` | It must not be cited as transfer evidence |
| A small domain embedding adapter is enough | MATM Recall@20 `.5301 -> .5331`; confidence interval crosses zero and MRR slightly decreased | No adapter promotion; corporate hard-negative labels and stronger splits are required |
| Generic embeddings solve corporate aliases | Dense-only retrieval underperformed exact/scope retrieval on the identifier benchmark | Dense search is complementary, not the primary solution |
| SkillOpt/memory composition already improves agents | Multiple ALFWorld cohorts were floor-effect or null; the real-candidate Codex replay was `0/2` across no-skill, placebo, and candidate | The methods are not disproven; this fixture does not show a positive transfer effect |

The source/replay overlap auditor is now an executable gate. A family-disjoint
aggregate cannot be produced without a zero-overlap receipt:

- contaminated native replay: 4 overlapping task IDs;
- contaminated sequential prefix: 2 overlapping task IDs;
- authoritative car-to-broker replay: 0 overlapping task IDs.

## What the academic literature does and does not show

SkillLearnBench, SkillFlow, SkillFoundry, MUSE-Autoskill, SkillOpt, ReasoningBank,
Dreams, LangMem, Graphiti, AgentRx, AgentEvals, Phoenix, Opik, and Langfuse each
validate useful components or benchmark-specific learning loops. None of the
reviewed work establishes the complete Frankengate claim: private multi-user
traces, same-surface identifier collisions, governed artifact capsules,
authorization/deletion epochs, changed-system replay, and prospective enterprise
outcomes in one protocol.

Therefore the correct interpretation is **boundary finding**, not paper
disproof. A null on our four-task or eight-task cohort can mean the candidate,
task family, horizon, harness, or outcome oracle was insufficient. It cannot
refute a paper's result on its own benchmark.

Two newer results sharpen the next experiment rather than overturning this
boundary:

- [SAGE](https://arxiv.org/abs/2512.17102) reports a strong AppWorld gain, but
  its main sequential rollout keeps skills inside the same scenario and uses
  expert SFT plus RL and a skill-integrated reward. Its practical retrieval
  ablation is therefore not equivalent to dropping a mined procedure into a
  different database family. Our null is a test of frozen-procedure transfer,
  not a refutation of outcome-trained sequential skill learning.
- [Walmart's retrieval-evolution pipeline](https://arxiv.org/abs/2607.10096)
  combines cross-batch and metadata-aware hard negatives with warm-start
  distillation when changing embedding backbones, reporting production lift.
  This supports testing continuity-preserving adapter updates, not blindly
  replacing the current encoder. It still lacks our authority, deletion, and
  changed-tool replay requirements.

The closest enterprise hard-negative study, [ACL Industry
2025](https://aclanthology.org/2025.acl-industry.72/), selects negatives that
are closer to the query than the positive but farther from the positive than
the query. It reports internal reranker MRR@3 `.57`/MRR@10 `.64` versus
`.42`/`.45` without fine-tuning. This is a strong recipe for our alias and
wrong-system corpus, but not proof of trace or skill utility.

## Architecture decision

Keep the required production core to:

1. Aurora PostgreSQL as the evidence, authority, artifact, and experiment store.
2. A loss-aware canonical trajectory DAG with explicit tool proposal,
   authorization, execution, observation, and state-delta events.
3. Exact identifiers, aliases, structured scope, and lexical retrieval.
4. Optional pgvector/dense retrieval behind authorized structured candidates.
5. Versioned SQL/tool capsules with provenance, schema/parameter contracts,
   expiry, replay, rollback, and deletion lineage.
6. A frontier/SME review queue and a no-skill/placebo/neutral experiment harness.

Graph databases, TurboVec/VectorChord/pgContext, custom embeddings, automatic
memory writes, and cross-user recommendations remain experimental add-ons. The
current evidence does not justify making any of them a mandatory dependency.

## Required next experiments

1. Run 20–40 sequential tasks across multiple source/evaluation families with
   user/project/time disjointness, no-skill, neutral, formatting, mined,
   SkillOpt, SkillGen, and RHO arms.
2. Use a changed database or tool environment, sealed outcome labels, independent
   semantic/security verification, paired repair/regression metrics, and cost and
   latency accounting.
3. Build a corporate alias/hard-negative set with SME adjudication, including
   same token/different system, undocumented aliases, NIL cases, and temporal
   renames; hold out users, projects, tenants, and time.
4. Compare exact/lexical/structured, dense, reranking, and frontier-model passes
   on the same candidate set with blinded quality labels and a fixed cost budget.
5. Measure prospective human usefulness and skill-gap recommendations only in a
   consented, privacy-reviewed cohort; public traces cannot establish employee
   capability or collaboration claims.

## Research and publication fit

The publishable contribution is a governed evidence-to-artifact lifecycle with
leakage gates and explicit claim boundaries, not “enterprise memory improves
agents.” The proposed public/sealed reproduction package and partner shortlist
are in [`publication-partner-opportunities-2026-08-02.md`](publication-partner-opportunities-2026-08-02.md).
The tracking epic is [#118](https://github.com/pierretokns/frankengate/issues/118).

All current receipts and code are on the pushed branch
`codex/trace-intelligence-academic-program`.
