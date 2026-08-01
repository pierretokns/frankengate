# Skill mining and enterprise hard-negative prior-art update

**Reviewed:** 2026-08-02

This update separates work that is directly reusable for Frankengate from work
that only resembles the problem. The papers below do not invalidate our
negative SQL transfer result; they sharpen the next experiments.

## Closest hard-negative precedent

[Hard Negative Mining for Domain-Specific Retrieval in Enterprise Systems](https://aclanthology.org/2025.acl-industry.72/)
is the closest match to corporate alias collision mining. It dynamically mines
semantically challenging but contextually irrelevant enterprise documents using
multiple embedding models and dimensionality reduction. On a proprietary cloud
services corpus it reports +15% MRR@3 and +19% MRR@10 over its baselines, with
public-domain validation on FiQA, Climate Fever, and TechQA.

What transfers:

- mine negatives from high-similarity, wrong-context candidates rather than
  random negatives;
- use multiple representation views before selecting a negative;
- evaluate on context/entity/time holdouts, not only random splits;
- keep a human or SME gate for whether a collision is truly irrelevant.

What it does not establish for us: semantic alias truth for agent traces,
identifier-level SQL correctness, multi-tenant authorization, or downstream
skill transfer. Our existing NL2SQL benchmark already shows why known database
scope and exact identifiers must remain a first lane: scope filtering beats
generic dense retrieval on the measured collision task.

### Newly confirmed production-shaped precedent

[Scaling and Stabilizing Large-Scale Embedding-Based Retrieval](https://arxiv.org/abs/2607.10096)
is a useful second precedent because it reports a deployed Walmart pipeline,
not only a static benchmark. Its method combines online cross-batch hard
negatives, offline cross-encoder plus metadata hard-negative mining, and
legacy-aware warm-start distillation when replacing an embedding backbone. The
paper reports +7.34% NDCG@5 and +0.50% gross revenue in its production setting.

The transferable idea is **model evolution with a continuity constraint**: a
new encoder must retain the old model's domain behavior while learning from
new hard negatives. This is stronger than our MATM adapter experiment, which
only measured a small fold-local Recall@20 change. It still does not solve
corporate trace authorization, alias truth, or artifact utility. Our version
must add user/project/time holdouts, deletion and scope checks, and a changed
tool/database replay before claiming a production benefit.

The ACL Industry paper's concrete selection rule is also directly useful. It
selects a negative only when it is closer to the query than the positive and
farther from the positive than from the query, reducing near-duplicate false
negatives. Its internal corpus contained 36,871 documents and 5,250 annotated
query-positive pairs; the reported in-house reranker reached MRR@3 `.57` and
MRR@10 `.64` versus `.42` and `.45` without fine-tuning. Those are enterprise
retrieval results, not trace or skill results, and the proprietary corpus and
labeling process are not independently reproducible from the paper.

## Closest skill-lifecycle precedents

[SAGE](https://arxiv.org/abs/2512.17102), the 2025/2026 “Reinforcement Learning
for Self-Improving Agent with Skill Library” paper, is especially informative
about our null transfer. It reports an 8.9-point Scenario Goal Completion gain
on AppWorld, but its idealized sequential rollout retains skills within the
same scenario and therefore does not require retrieval. The paper explicitly
notes that the base prompt-only skill-library agent underperformed until expert
SFT and RL were added; practical retrieval variants (query n-gram, query
embedding, and skill embedding) are a later ablation. This means its headline
result is not a counterexample to our cross-database null: it benefits from
scenario-local continuity, expert trajectories, reward shaping, and a trained
policy, while our replay tested a frozen frontier model with a mined procedure
and no task-specific training.

This yields a sharper hypothesis for the next study: **artifact reuse may need
sequential task chains and an outcome-trained consumer**, not just a good text
procedure inserted into an unrelated task. The design must compare same-family
sequential chains, family-held-out transfer, and retrieval/no-retrieval arms.

[Trace2Skill](https://arxiv.org/abs/2603.25158) (with an
[official implementation](https://github.com/Qwen-Applications/Trace2Skill)) distills trajectory-local lessons
into portable skills and reports cross-model/OOD transfer. [Anything2Skill](https://arxiv.org/abs/2606.09316)
compiles heterogeneous external knowledge into retrievable and executable
skills. [SkillAdaptor](https://arxiv.org/abs/2606.01311) focuses on attributing a
failure to the specific step or skill that caused it before adaptation. Its
paper says the implementation is forthcoming, so it is a method reference,
not yet a directly reproducible dependency for our benchmark.

These are much closer to our artifact-learning hypothesis than plain vector
memory. Their hard edge for corporate use is evaluation: a paper-level skill
can look transferable while still failing a governed, changed-system replay.
Our native and proxy SQL screens therefore test the missing deployment-side
question: does the released artifact beat no-skill and length-matched controls
on renamed tasks under independent semantic and authority verification?

[From Raw Experience to Skill Consumption](https://www.microsoft.com/en-us/research/publication/from-raw-experience-to-skill-consumption-a-systematic-study-of-model-generated-agent-skills/)
is particularly relevant because it studies the full lifecycle—experience
generation, skill extraction, and skill consumption—rather than extraction in
isolation. [Experience-Evolving Multi-Turn Tool-Use Agent](https://www.microsoft.com/en-us/research/publication/experience-evolving-multi-turn-tool-use-agent-with-hybrid-episodica%C2%A2a%C2%ACaeoeprocedural-memory/?lang=ko-kr)
combines episodic and procedural reuse, but still assumes task evaluators and
does not supply our enterprise authority/provenance contract.

## Domain-specific embeddings and logs

The [semiconductor-equipment-log study](https://papers.ssrn.com/sol3/papers.cfm?abstractid=5800425)
is a useful adjacent pattern: construct query-positive-negative triplets from
event logs and engineer comments, train a dual encoder contrastively, and retain
field-engineer assessment. It supports our proposed recipe for corporate
embeddings, but not training on raw logs alone. The labels and expert review are
the mechanism that makes the domain distinctions learnable.

This aligns with our empirical results:

- fold-local adaptation on MATM was effectively neutral (+0.0029 Recall@20);
- generic dense retrieval improved candidate recall, but not proven artifact
  utility;
- identifier-aware scope filtering beat the generic embedding arm;
- hard negatives and human labels are the missing ingredient, not simply a
  larger embedding model.

### 2026 domain-representation refresh

Recent industrial-log and schema-retrieval work makes the supervision
requirement even clearer:

| Work | What it contributes | Transfer boundary |
|---|---|---|
| [Semiconductor equipment-log retrieval](https://papers.ssrn.com/sol3/papers.cfm?abstractid=5800425) | Constructs query/positive/negative triplets from event logs plus engineer comments, fine-tunes a dual encoder contrastively, and evaluates with field-engineer judgments. | The expert comments and assessment are the signal; raw logs alone are not shown to recover the domain ontology. |
| [Graph-embedding contrastive learning for process-industry text](https://aclanthology.org/2025.emnlp-industry.103/) | Derives triplets from sparse process-industry graphs and reports gains over a larger general encoder on a proprietary benchmark. | Graph structure and domain labels are supplied; this does not establish that a generic embedding can infer enterprise aliases from unannotated traces. |
| [Embedding-Aware Feature Discovery](https://arxiv.org/abs/2603.15713) | Combines latent representations with interpretable event-sequence features and reports gains over embedding-only baselines. | Supports hybrid identifier/event features, but its anomaly/sequence targets differ from semantic alias truth and artifact utility. |
| [RASL: Retrieval-Augmented Schema Linking](https://arxiv.org/abs/2507.23104) | Treats massive enterprise schema linking as a retrieval problem rather than asking a model to ingest the entire catalog. | Schema linking still needs scope, temporal lineage, and independent query/result validation in Frankengate. |

The strongest positive precedent for a *properly matched* embedding experiment
is [Finding the Right Tables and Columns](https://arxiv.org/abs/2607.13311).
It recasts schema linking as its own table/column retrieval task, synthesizes
natural-language queries from the target schema corpus, mines
granularity-aware hard negatives, and reports leave-one-corpus-out gains in
Recall@10 from `60.4` to `75.6` (nDCG@10 from `51.9` to `68.0`). This is
materially different from our MATM adapter, which used trajectory similarity
proxies rather than schema-grounded query/column labels. Our MATM result is
therefore a **negative promotion result for that proxy recipe**, not evidence
against corpus-adaptive schema embeddings.

[TRACE](https://arxiv.org/abs/2607.22639) is a complementary, more parametric
tool-retrieval direction: it trains on business-rule-curated queries and
reports large gains over an embedding baseline on an 8,300-tool enterprise
catalog. It is not a drop-in Frankengate component because it requires model
training, curated business rules, and a closed tool vocabulary; however, it
supports testing structured business-rule features alongside vectors rather
than assuming nearest-neighbor similarity is enough.

The convergent pattern is not “train a bigger embedding model on logs.” It is:

1. derive candidate positives from repeated validated artifacts, lineage, and
   explicit user/SME links;
2. generate hard negatives from high-similarity wrong-scope, same-surface,
   stale-version, and tool-contract-conflict objects;
3. add structured fields and graph/lineage features beside the text vector;
4. hold out users, systems, projects, and time; and
5. promote only when retrieval lift also improves changed-system artifact
   outcomes without false semantic acceptance.

This gives a concrete explanation for our current negative adapter result:
the adapter was asked to learn corporate semantics from proxy trajectory labels
without the expert/lineage supervision that these industrial systems use.

The revised schema experiment must therefore use the Defog/BIRD schemas as the
corpus, synthesize question-like positives from table/column metadata, mine
same-scope and granularity-conflict negatives, and evaluate leave-one-database-
family-out. Only after that should we compare an adapted embedder with the
identifier-aware ranker and replay its top candidates in changed systems.

## Revised Frankengate experiment

The next embedding/alias study should be a four-stage, frozen protocol:

1. derive candidate positives from exact identifiers, repeated successful
   artifacts, and approved cross-user links;
2. mine hard negatives from high-cosine/wrong-scope, same-surface/different-
   system, temporal-neighbor, and tool-schema-conflict candidates;
3. have frontier adjudication and stratified SMEs label positive, negative, NIL,
   and “insufficient evidence” cases;
4. compare exact+scope, lexical, generic dense, fold-local adapter, and
   adapter+cross-encoder/reranker on family/user/project/time holdouts, then
   replay only the top candidates in a changed governed environment.

Promotion requires both retrieval lift and downstream artifact lift. A model
that increases Recall@20 but creates wrong-system SQL/tool suggestions is a
regression. Every candidate must retain the evidence chain, hard-negative
provenance, authority scope, deletion state, and replay receipt.

## Bottom line

We have not found a paper that exactly answers “mine months of private Claude/
Codex traces across an enterprise, discover aliases and missing skills, and
release validated reusable tools.” The closest work supplies individual
components—hard-negative selection, trajectory-to-skill distillation, hybrid
episodic/procedural memory, and lifecycle evaluation. Frankengate’s defensible
research gap is their conjunction with exact identifier channels, governed
artifact capsules, cross-user consent, and changed-system replay.
