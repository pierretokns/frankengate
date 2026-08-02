# Publication and partner evidence packet — 2026-08-10

**Status:** outreach-ready methods package; no enterprise efficacy claim and no
partner commitment implied.

## Defensible contribution

The strongest paper is:

> **A governed evidence-to-artifact lifecycle for enterprise agent traces:**
> structured identity and scope, hard-negative-aware retrieval, selective
> model review, independent replay, and changed-system promotion gates.

This is more precise than “enterprise memory improves agents.” The current
receipts support the lifecycle mechanics and several bounded retrieval/prior
signals, but not causal skill improvement or cross-user learning.

## Evidence that belongs in the paper

| Layer | Evidence | Claim boundary |
|---|---|---|
| Candidate scope | Full EnterpriseRAG source-filter run: MRR `.511064 -> .593602`, wrong-source extras `4.851064 -> 0`, same-source non-targets `8.963830`, all 30 NIL cases non-empty | Source scope is necessary; semantic identity and abstention remain open |
| Identifier retrieval | Defog/WMH-BIRD identifier ranker reaches MRR `.737` on its public collision proxy; cross-domain transfer is asymmetric | Exact identifiers and scope are a cheap front end, not semantic aliases |
| Alias mining | Deterministic train-only alias reproduction: lexical MRR `.734885`, support-2 `.727542`, only `.065385` target coverage | Frequency links are sparse review candidates, not ontology truth |
| Dense adaptation | Fold-local Nomic adapter MRR `.940152 -> .947917`, Recall@1 `.909091 -> .931818`, but Recall@5 and invalid-selection precision did not improve | Shadow reranker result, not universal corporate embedding |
| Model review | Frontier improves ordering when targets are already in the candidate pool; every tested retrieval arm still proposes on NILs | Model review can prioritize/abstain; it cannot authorize or recover absent evidence |
| Validated artifacts | Only `76/193` recorded BIRD executable queries matched independent gold; typed parameter replay passed `75/75` controlled mutations | Store immutable identity, bindings, scope, schema/epoch, and replay evidence |
| Prior reuse | Frozen Claude-history holdout preserved a same-project success association while coarse key-shape priors were negative | Exact, scoped, tool-class-aware priors rank candidates; templates do not authorize reuse |
| Skill intervention | Validated subplans show one stable win across 20 held-out BIRD tasks; generic trace-mined prose tied no-skill; SkillOpt candidate tied controls | Keep skills/procedures quarantined until changed-system outcomes |

The supporting source and receipt links are collected in the [current research
status](research-program-status-2026-08-09.md), [full EnterpriseRAG result](enterprise-rag-source-filter-ceiling-full-2026-08-10.md), and [objective audit](objective-completion-audit-2026-08-06.md).

## What remains scientifically open

No current public or synthetic receipt proves:

- that a mined alias is correct for a real organization across systems or time;
- that a custom embedding improves downstream SQL/tool artifact utility;
- that a trace-derived skill improves a later task against no-skill/placebo;
- that users with similar traces are doing the same work or need the same skill;
- that a recommendation improves a human outcome without negative transfer; or
- that a model-generated ontology can safely become canonical knowledge.

These are not merely engineering gaps. They require labels and outcomes that
the public corpora do not contain.

## Partner-specific study fit

### CMU LTI / SkillLearnBench

Joint question: does reviewed or generated guidance improve changed SQL/tool
tasks under family, project, principal, and time holdouts?

We bring validated artifact capsules, no-skill/placebo/reviewed/generated arms,
independent replay, and the explicit mutation-stratum contract. CMU contributes
continual-learning benchmark design, skill-quality/trajectory-quality separation,
and task-disjoint evaluation. The [SkillLearnBench repository](https://github.com/cxcscmu/SkillLearnBench) is the closest public methodological analogue.

### MIT DSAIL / Harvard DASlab

Joint question: what is the smallest data-system architecture for governed
artifact retrieval under schema drift, authority epochs, deletion, and latency?

We bring the PostgreSQL/SQLite capsule contract, source-filter ceiling, exact
identifier results, replay fixtures, and cost/latency receipts. They contribute
learned data-system, query-workload, adaptive-indexing, and scale expertise.

### Harvard CHARM / Variation Lab / CRCS

Joint question: do trace-derived review suggestions improve the user's next
task, correction burden, time-to-success, or transferable skill?

We bring review-only suggestions, explicit `nil`/`unclear`, friction/retry
signals, and reciprocal opt-in rules. They contribute human-learning,
sensemaking, agency, and prospective study design. Trace similarity alone is
not a human capability label.

### MIT CLEAR / TRAC and Microsoft Research

Joint question: how should uncertainty, provenance, deletion, abstention, and
negative transfer govern release of trace-derived artifacts and skills?

We bring evidence-chain receipts, rollback, authority epochs, changed-system
replay, and fail-closed conformance. They contribute accountability,
robustness, intelligibility, and human-agent learning methodology.

## First joint reproduction

Use the strengthened [enterprise semantic-cohort contract](../../configs/studies/enterprise-semantic-cohort-v1.json), which requires:

- at least 100 targets, 50 hard negatives, and 25 NIL/unclear cases;
- two blinded annotators plus adjudication;
- principal/team/project/system/time holdouts;
- at least five tasks each for no-change, additive drift, approved rename,
  same-surface collision, changed result meaning, stale/revoked authority, and
  changed tool contract;
- frozen candidate pools and explicit source/changed authority epochs; and
- independent outcome, deletion, rollback, and cost/latency receipts.

Pre-register these arms:

1. no artifact / regenerate;
2. exact identifier plus structured scope;
3. lexical and dense candidate retrieval;
4. fold-local identifier-aware adapter;
5. reviewed semantic-ID artifact;
6. reviewed typed-subplan composition; and
7. frontier regeneration when no compatible artifact exists.

Report retrieval, artifact validity, and changed-task utility as separate
endpoints. A positive retrieval delta cannot promote an artifact. A successful
execution cannot establish semantic equivalence. A model judge cannot replace
authority or independent replay.

## Publication lanes

- **SIGIR/ACL Industry:** identifier-aware retrieval, hard negatives, aliases,
  and explicit NIL refusal.
- **SIGMOD/VLDB/MLSys:** governed artifact storage, schema drift, deletion,
  authority, and replay/latency tradeoffs.
- **CHI/CSCW:** friction review, skill-gap explanations, collaboration, and
  prospective human outcomes.

The first paper should choose one lane and publish the protocol, content-free
manifests, deterministic verifiers, and negative results. Raw employee traces
and hidden evaluator data should remain behind a sealed replay API.

## Outreach package

Provide the research branch, machine-readable contracts, receipts, verifiers,
and a license-cleared or synthetic reproduction cohort. Ask partners for
methods review and independent reproduction—not access to raw enterprise logs
and not a promise of positive results.
