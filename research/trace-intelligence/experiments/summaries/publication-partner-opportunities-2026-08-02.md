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

## Empirical update for a paper/partner packet

The vocabulary ports now have a sharper result to share: on the public Defog
proxy, termhood recall was `.015` on unseen schemas versus `.358` in a
within-schema control. A train-only termhood alias field widened Recall@5
`.846→.923` but lowered MRR `.860→.815` and Recall@1 `.846→.769` on 13 held-out
cases, while removing the observed same-scope collision. This supports a
candidate-recall/search-enrichment hypothesis, not automatic alias or ontology
promotion.

The publishable next experiment is therefore a larger, sealed enterprise
reformulation benchmark with: (a) same-enterprise train/test splits; (b)
same-surface/different-system, temporal-renaming, and NIL hard negatives; (c)
human/SME alias labels; and (d) changed-system replay and reviewer-acceptance
outcomes. This separates vocabulary discovery from retrieval rank and from
actual user benefit—the distinction a partner can reproduce and extend.

The newer prior-art review sharpens the methods contribution for outreach:
[SkillAdaptor](https://arxiv.org/abs/2606.01311) supplies step-attributed
revision, [HASP](https://arxiv.org/abs/2605.17734) supplies executable skill
guards, and [Recovery-Bench](https://github.com/letta-ai/recovery-bench) supplies
failure-state replay. Combined with the enterprise hard-negative framework
([arXiv:2505.18366](https://arxiv.org/abs/2505.18366)), these support a paper
framing around **diagnose → compile → replay → promote**, while corporate
labels and changed-system outcomes remain the novel contribution.

The latest corpus-fit evidence should be included in every outreach packet.
Across 242 parse-valid BIRD gold queries and 314 parse-valid Defog queries,
there were zero shared exact normalized templates, one shared typed
schema-agnostic template, and two shared coarse operator shapes. Every shared
shape had multiple exact variants, so both structural collision rates were
`1.0`. This is a dataset-fit result, not a universal negative about artifact
learning: these public SQL corpora do not contain a compatible cross-system
artifact library.

The vocabulary ports show the same boundary. Across four independent Claude
trace cohorts, 217/293 frequent term hashes were unique to one cohort and only
5 appeared in all four. The contextual acronym port found 40 valid acronym
hashes and 56 valid acronym/full-form pairs, with no cross-cohort overlap.
TermSuite/Termolator and AcronymExpansion therefore contribute deterministic,
auditable review candidates and abstention behavior, not global enterprise
ontology or embedding-training data. The corresponding receipts are the
[cross-corpus SQL artifact study](cross-corpus-sql-artifact-signatures-2026-08-09.md),
[termhood stability study](termhood-cross-cohort-stability-2026-08-09.md), and
[acronym stability study](acronym-cross-cohort-stability-2026-08-09.md).

## Latest empirical packet for outreach

The WMH-BIRD bridge now gives the packet a stronger hard-negative story than
the earlier 13-case vocabulary proxy. Across 149 independently replayable task
traces, 1,236 exposed-table substitutions produced 1,210 execution errors, 22
result mismatches, and only 4 result-preserving substitutions. A small learned
ranker reached Recall@1 `.704` and Recall@5 `.958` on 71 held-out cases,
improving over lexical `.676/.887`; the termhood field alone reached
`.676/.930`. Replay-filtered and naive exposed-negative training tied because
the training split contained no ambiguous substitutions.

This is a useful partner-facing result precisely because it contains both a
positive and a null: structured/identifier-aware retrieval is promising, while
replay-derived negative filtering is not yet an optimization gain. The next
joint study should deliberately add result-preserving alternatives,
same-surface/different-system pairs, temporal replacements, and NILs. Those
labels are what distinguish a real enterprise hard-negative contribution from
ordinary table-surface classification.

The partner-facing claim matrix should keep three questions separate: (1) is a
candidate representation stable across cohorts, (2) is the candidate
compatible and independently replayable, and (3) does presenting or compiling
it improve the next task? The new cross-corpus result is negative on (1) for
public SQL artifacts; the BIRD replay results are bounded evidence for (2);
and (3) remains open. A collaboration should not pool these datasets or treat
structural overlap as a substitute for a consented changed-system cohort.

The same distinction appears in the two-user DataClaw study: a permissive audit
found 11 shared non-trivial tool-call forms, but strict tool-plus-input
identities had zero overlap between Peter and Vaynelee. This is a useful
partner-facing negative because it separates candidate recall from artifact
identity. The [strict cross-user receipt](dataclaw-cross-user-artifact-transfer-2026-08-09.md)
supports a study design with broad-recall, strict-scope, intent-adjudication,
and replay stages rather than direct crowdsourced skill transfer.

The complementary same-user support study found 3,158 Peter candidates
repeated across sessions, 518 across projects, and 460 cross-project candidates
near broad friction signals. This gives the partner program a more credible
first intervention: validate and replay a user's own scoped candidates before
testing cross-user transfer. It is a positive candidate-supply result, not a
correctness or user-benefit claim. Recurrence was only a cohort-dependent
prioritization signal: Peter's repeated candidates had a `.480813` friction
context rate versus `.436807` for single-session candidates, while Vaynelee's
small repeated sample was lower than its single-session rate. A partner study
must therefore measure this relationship rather than hard-code it.

The project-held-out adapter probe supplies a useful adaptation result for a
partner conversation: the full Peter cohort's combined prompt/tool MRR rose `.769341→.854452`,
while Vaynelee's combined MRR remained `.978495` at ceiling and Peter's
tool-only arm slightly declined. This is the right shape of evidence for a
custom-representation study—an improvement with a matched null and a weak
feature-only arm—not a reason to promote an embedding trained on raw logs.

The paired Claude tool-history benchmark gives the artifact-learning paper a
stronger temporal result. Across 70,949 calls, no-prior strict identities
succeeded `88.7216%` of the time, versus `96.8268%` after same-project prior
success and `97.1615%` after prior success in another project. The tempting
input-key-only template prior was negative (`90.5514%` same-project and
`90.7613%` cross-project versus `92.3108%` with no prior key shape). The
tool-class split explains why a single aggregate policy is unsafe: exact
same-project priors lifted shell success `.697511→.938326` and mutation
`.941272→.993243`, while read/search was already `.993934`.

This supports a publishable, falsifiable methods claim: **exact, scoped,
tool-class-aware prior artifacts can rank candidates; coarse templates cannot
authorize reuse**. Same-session error→success transitions add a second paper
contribution: 3,866/4,506 retries recovered, but shell recovery was only
`.335766` and mutation `.762500`. These transitions should seed targeted evals
and repair studies. They are not independent correctness labels, so a partner
study still needs semantic intent, safety contracts, and changed-system replay.
Receipts: [strict artifact miner](claude-history-tool-artifact-miner-2026-08-09.md)
and [temporal prior benchmark](claude-history-tool-artifact-temporal-2026-08-09.md).

The follow-up [frozen artifact-drift holdout](claude-history-tool-artifact-drift-2026-08-09.md)
used only the first half of the history to build priors and evaluated the
second half without updating them. Exact same-project priors retained a
`+6.3798` percentage-point success association and other-project priors
`+5.3078` points, while key-shape priors were negative by `−6.2541` and
`−9.0060` points. This gives the paper a time-aware falsification result:
artifact priors can remain useful under drift, but coarse templates degrade
and require expiry/versioning. It also motivates a partner study with explicit
time-held-out splits rather than random trace splits.

Tracking remains split by research obligation: [#118](https://github.com/pierretokns/frankengate/issues/118)
for the authorized changed-system cohort, [#121](https://github.com/pierretokns/frankengate/issues/121)
for domain-adaptive embeddings, [#122](https://github.com/pierretokns/frankengate/issues/122)
for the embedding/model cascade, and [#123](https://github.com/pierretokns/frankengate/issues/123)
for hard-negative mining. This avoids presenting the public proxy as a
completed enterprise study.
