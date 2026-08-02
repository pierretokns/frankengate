# New skill/provenance/retrieval prior art: fit to the Frankengate program

Date: 2026-08-02  
Status: source-backed adaptation map; these papers and tools have not been
treated as enterprise outcome evidence

## Executive finding

The newest work fills important component gaps, but it does not make the
corporate problem solved. The closest composable stack is:

```text
AgentTrails provenance graph
  -> SRA-Bench-style capability retrieval and distractor tests
  -> SkillOps library-health / compatibility checks
  -> SkillAdaptor first-fault, step-scoped patch proposal
  -> Waza/SkillLearnBench-style graders
  -> Frankengate authority, changed-system replay, and release gates
```

The last stage is still the differentiator required for corporate SQL/tool
artifacts: none of the sources below establishes authorization-epoch safety,
tenant scope, deletion lineage, changed-schema replay, or prospective user
utility on private multi-user traces.

## Source-by-source fit

### AgentTrails

[AgentTrails](https://arxiv.org/abs/2607.18816) converts trajectories into
provenance graphs: tool calls are computational actions, inputs/outputs are
data artifacts, and multiple executions are aligned through a joined quotient
graph. It explicitly supports pattern extraction and skill abstraction.

**Adopt:** a graph projection beside the chronological OTel record, with
stable action/resource/evidence IDs and graph alignment for recurring plans.
This complements our deterministic trace compiler and makes dependency and
divergence queries much stronger than whole-trace embeddings.

**Hard edge:** the paper does not provide our authority epochs, consent,
deletion, independent semantic outcomes, or changed-system replay. Graph
similarity can therefore propose a candidate, but cannot authorize reuse.

### SkillOps

[SkillOps](https://arxiv.org/abs/2605.13716) treats a skill library as a
maintained software ecosystem. Its typed Skill Contract (P, O, A, V, F),
hierarchical skill graph, and utility/compatibility/risk/validation health
dimensions target “skill technical debt.” The reported ALFWorld gains are
useful evidence for library maintenance on that benchmark, not corporate
trace evidence.

**Adopt:** a library-time maintenance pass before retrieval: detect duplicate
or conflicting contracts, stale dependencies, missing validators, scope
collisions, and untested composition. Map the contract to our artifact fields:
preconditions and authority, typed inputs/outputs, actions, verifier, failure
and refusal behavior, plus schema/version/epoch provenance.

**Hard edge:** ALFWorld skills and their dependency assumptions do not model
SQL result equivalence, RLS, changed schema, or enterprise aliases. SkillOps
must be a review/maintenance layer, not a promotion gate by itself.

### SkillAdaptor

[SkillAdaptor](https://arxiv.org/abs/2606.01311) attributes a failed
trajectory to the first actionable fault step, maps that fault to a candidate
skill, and proposes a targeted update under explicit acceptance checks while
keeping the backbone frozen.

**Adopt:** replace broad whole-session “memory improvement” with a first-fault
proposal containing the exact action, precondition, observed failure, expected
effect, and smallest patch. This is compatible with our negative/neutral
controls and makes repair burden measurable.

**Hard edge:** its WebShop/PinchBench/Claw-Eval results do not test corporate
semantic identity, authority, stale data, or cross-user negative transfer.
Every patch still needs the Frankengate independent replay and rollback gate.

### SRA-Bench / SR-Agents

[SRA-Bench](https://github.com/oneal2000/SR-Agents) is the closest public
benchmark for the retrieval half of skill learning. It contains 5,400
capability-intensive instances, 636 manually constructed gold skills, and
26,262 total skills including 25,626 distractors. Its pipeline separates skill
retrieval, skill incorporation, and end-task execution. The released code
compares BM25, TF-IDF, BGE, Contriever, BM25+BGE fusion, and LLM reranking,
plus explicit distractor and top-k sweeps.

**Adopt:** use its three-stage decomposition and distractor protocol. A skill
retrieval win must not be confused with a task-success win; report both, plus
authority and replay outcomes. Its corpus is a good control for retrieval
mechanics before asking private traces to supply labels.

**Hard edge:** its gold skills are manually constructed and its distractors
are web-collected. It has no enterprise same-surface/wrong-system aliases,
authorization epochs, or user-consent outcomes. It cannot validate our
corporate ontology or tool capsules.

### SkillLearnBench

[SkillLearnBench](https://github.com/cxcscmu/SkillLearnBench) exposes 20 tasks
and 100 instances across software engineering, information retrieval,
productivity, analytics, creative work, and utilities. It evaluates task
success, skill quality (coverage, executability, safety), and trajectory
quality (key-point recall, order, completeness), with one-shot, self-feedback,
teacher-feedback, and Skill Creator baselines.

**Adopt:** use its three-level reporting and teacher-feedback arm as a
calibration benchmark for our evaluator. The teacher arm is especially close
to the proposed “ask a human only when the trace is ambiguous” loop.

**Hard edge:** the public tasks are not private enterprise traces, and the
current public setup uses Claude Sonnet 4.6 plus GPT-5-mini judging. Results
must be reproduced with independent verifiers and our changed-system splits;
LLM judge scores alone are insufficient.

### Microsoft Waza

[Waza](https://github.com/microsoft/waza) is an operational skill-evaluation
CLI with code, text, file, diff, behavior, action-sequence, skill-invocation,
prompt, and trigger-test graders.

**Adopt:** translate these grader categories into a versioned artifact/skill
contract. For SQL/tool work, action-sequence and behavior graders should check
tool order, authority-preserving calls, cost/time limits, refusal, and
parameter binding; code/diff/file graders cover generated migrations or
configuration changes.

**Hard edge:** Waza supplies test primitives, not provenance, cross-user
privacy, semantic alias labels, or changed-system causal design.

### Enterprise hard-negative mining

The ACL Industry Track paper [Hard Negative Mining for Domain-Specific
Retrieval](https://aclanthology.org/2025.acl-industry.72/) dynamically mines
semantically difficult but contextually irrelevant documents using multiple
embeddings and dimensionality reduction. It reports 15% MRR@3 and 19% MRR@10
improvements on a proprietary cloud-services corpus and public domain checks.

**Adopt:** add a hard-negative miner that combines exact identifier collisions,
same-source non-targets, temporal versions, and model-disagreement candidates;
use it to train/rerank only after blinded semantic/NIL labels exist.

**Hard edge:** the reported gains are retrieval gains on document corpora, not
skill or artifact utility. Our EnterpriseRAG source-filter result shows why:
scope removes wrong-source candidates but leaves a same-source tail and NIL
false positives.

## What combines cleanly

1. **AgentTrails + our deterministic compiler:** graph structure is a richer
   projection; deterministic IDs and provenance remain authoritative.
2. **SRA retrieval + ACL hard negatives + our identifier lane:** broad recall
   can be measured without allowing vectors to bypass scope or compatibility.
3. **SkillOps + Waza graders:** library health and executable checks can run
   cheaply before frontier review.
4. **SkillAdaptor + first-fault trace labels:** targeted patches are a better
   experimental arm than rewriting a whole memory or skill file.
5. **SkillLearnBench reporting + our replay gates:** task, trajectory, and
   skill-quality metrics become useful only when paired with independent
   terminal outcomes and changed environments.

## What does not combine cleanly

- Graph quotient similarity cannot stand in for semantic identity or authority.
- Dense skill retrieval cannot authorize a SQL/tool capsule.
- ALFWorld/WebShop/Claw-Eval skill success cannot be extrapolated to enterprise
  outcomes or cross-user recommendations.
- LLM-as-judge skill quality cannot replace execution equivalence, tool safety,
  or human labels.
- A library-health score cannot prove that a proposed skill improves the next
  task; it only determines whether the library is internally maintainable.

## Reproduction matrix to add to the program

| Stage | Control arms | Primary metrics | Frankengate gate |
| --- | --- | --- | --- |
| Capability retrieval | BM25, dense, hybrid, rerank, identifier-aware | Recall@K, nDCG, collision-before-target, NIL rate | Scope/authority filtering |
| Incorporation | no skill, full injection, progressive disclosure, neutral-length placebo | tool/action sequence, incorporation precision, tokens | No unauthorized observation |
| Execution | regeneration, reviewed skill, generated skill, first-fault patch | independent terminal success, repair count, latency/cost | Changed-system replay |
| Library maintenance | raw, SkillOps checks, Waza checks, both | stale/conflicting/unsafe/untested rates | Release/rollback/deletion |
| Longitudinal transfer | same-user, cross-project, cross-user opt-in | next-task utility, negative transfer, unwanted contact | Consent and outcome labels |

The first three stages can be run on SRA-Bench and SkillLearnBench as public
controls. The final stage requires the consented semantic cohort; no public
benchmark found in this audit supplies those labels.

## Decision

Add AgentTrails-style provenance graphs, SkillOps-style library health,
SkillAdaptor-style first-fault patches, SRA-style capability retrieval
evaluation, and Waza-style graders as **experimental components**. Do not add
any of them as an automatic release or corporate ontology mechanism. The
existing Frankengate authority, replay, semantic-label, and prospective-outcome
gates remain the binding boundary.

## Sources

- https://arxiv.org/abs/2607.18816
- https://arxiv.org/abs/2605.13716
- https://arxiv.org/abs/2606.01311
- https://github.com/oneal2000/SR-Agents
- https://github.com/cxcscmu/SkillLearnBench
- https://github.com/microsoft/waza
- https://aclanthology.org/2025.acl-industry.72/
