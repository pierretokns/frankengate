# Publication and partner opportunities

## Recommended collaboration order

### 1. CMU LTI / SkillLearnBench team — benchmark and continual-learning protocol

The [CMU Language Technologies Institute](https://www.lti.cs.cmu.edu/about-lti/index.html)
covers information retrieval, question answering, text mining, knowledge
representation, and trustworthy language technology. The
[SkillLearnBench repository](https://github.com/cxcscmu/SkillLearnBench)
is MIT-licensed and exposes task verifiers, skill generators, and evaluation
reports. Its public protocol separates task success, skill quality, and
trajectory quality, and its authors explicitly report that no continual method
wins across all tasks and models. This is the closest methodological partner
for adapting our four-arm Defog study into a real enterprise-SQL continual
benchmark.

**Proposed joint artifact:** a license-cleared, content-minimized SQL/tool
skill benchmark with sequential family tasks, hard-negative aliases,
independent semantic replay, and governed release receipts.

### 2. MIT DSAIL — learned data systems and enterprise evaluation

MIT's [Data Systems and AI Lab](https://dsg.csail.mit.edu/dsail/) explicitly
targets learned components in large-scale data systems and enterprise
applications, including query optimization, schema design, data integration,
and the tooling needed to prepare data and integrate models into deployed
systems. That matches the SQL artifact, schema-drift, planner, and Aurora-scale
questions more directly than a generic agent-memory group.

**Proposed joint artifact:** an open governed workload/trace benchmark that
measures artifact reuse, schema drift, query-plan regressions, and retrieval
latency under controlled authority scopes.

### 3. Harvard CHARM / Variation Lab / CRCS / DASlab — human outcomes and data-system boundaries

Harvard's [CHARM](https://charm.seas.harvard.edu/) focuses on whether AI leaves
people better prepared rather than merely completing the current task. That is
the right partner for validating “skill-gap” and “user improvement” claims.
The [Variation Lab](https://glassmanlab.seas.harvard.edu/) studies AI-resilient
interfaces and human sensemaking, which fits the review UX for trace-derived
suggestions. Harvard [CRCS](https://crcs.seas.harvard.edu/publishing-research) contributes
multi-agent collaboration and goal-recognition design, while
[DASlab](https://daslab.seas.harvard.edu/) is a strong fit for data-system
architecture, adaptive indexing, workload behavior, and SQL systems.

**Proposed joint artifact:** a consented user study measuring whether a
trace-derived suggestion improves the next task, reduces correction burden,
or teaches a transferable cloud/SQL skill. Trace similarity alone is not a
human-outcome label.

### 4. MIT CLEAR / TRAC and Microsoft Research — reliability, uncertainty, and accountability

The [CLEAR Lab](https://clear.csail.mit.edu/) studies agents learning tasks
with and around people through experiments and user studies. The
[MIT–Microsoft TRAC collaboration](https://trac.csail.mit.edu/) is explicitly
organized around robustness, intelligibility, safety, fairness, and
accountability. These are natural partners for the claim boundary around
uncertainty, abstention, deletion, and negative transfer.

**Proposed joint artifact:** a public evidence-chain and release-gate protocol
for trace-derived skills, including calibrated abstention, counterfactual
negatives, changed-system replay, and rollback.

## Best paper framing

The strongest paper is not “enterprise memory improves agents.” It is:

> **A governed evidence-to-artifact lifecycle for enterprise agent traces:**
> exact/structured identity and scope first, hard-negative-aware retrieval,
> frontier-assisted procedure compilation, independent replay, and
> changed-system promotion gates.

The paper should report three separately held-out outcomes:

1. retrieval: Recall@k/MRR for same-work positives and wrong-system negatives;
2. artifact quality: contract completeness, grounding, tests, reviewer
   agreement, and provenance; and
3. changed-agent utility: paired no-skill, neutral, and candidate runs with
   semantic verifiers, latency/cost, unsafe actions, and rollback.

## What we should offer partners

* a reproducible branch and machine-readable receipts rather than private raw
  traces;
* synthetic or license-cleared task families plus a sealed enterprise replay
  API;
* explicit negative, null, and refusal results;
* a contribution agreement covering data ownership, deletion, and publication
  review; and
* a small, well-powered first study rather than an open-ended request to mine
  employee logs.

## First collaboration package

The first 6–8 week package should use public or synthetic tasks and a sealed
enterprise replay endpoint:

1. 20–40 sequential SQL/tool tasks across several families;
2. one-shot, self-feedback, teacher-feedback, and Trace2Skill-style arms;
3. skill-quality, trajectory-quality, retrieval, and changed-task outcome
   receipts;
4. same-surface/wrong-scope hard negatives, schema drift, stale authority,
   deletion, and negative-transfer cases; and
5. reproducible manifests, hashes, verifiers, and a publication-ready claim
   matrix.

The collaboration request should be a methods reproduction, not access to raw
employee logs or a promise of positive results.

The current evidence supports approaching CMU and MIT DSAIL first, with Harvard
CHARM/CRCS/DASlab and MIT CLEAR/TRAC as complementary collaborators. This is a
fit assessment, not a claim that any group has agreed to participate.
