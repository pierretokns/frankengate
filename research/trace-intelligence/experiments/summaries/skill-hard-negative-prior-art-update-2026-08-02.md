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

## Closest skill-lifecycle precedents

[Trace2Skill](https://arxiv.org/abs/2603.25158) distills trajectory-local lessons
into portable skills and reports cross-model/OOD transfer. [Anything2Skill](https://arxiv.org/abs/2606.09316)
compiles heterogeneous external knowledge into retrievable and executable
skills. [SkillAdaptor](https://arxiv.org/abs/2606.01311) focuses on attributing a
failure to the specific step or skill that caused it before adaptation.

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
