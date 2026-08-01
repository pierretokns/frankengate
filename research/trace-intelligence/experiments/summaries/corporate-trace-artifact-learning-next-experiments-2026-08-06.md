# Corporate trace-artifact learning: next experiments and promotion gates

This is the current execution plan after the public-proxy and mechanics audit.
It deliberately separates what is already measured from what requires a
consented, outcome-bearing cohort.

## Evidence-backed order of work

| Priority | Experiment | Frozen inputs | Arms | Primary gate | Why now |
|---|---|---|---|---|---|
| P0 | Authorized changed-system SQL/tool cohort | 20–40 tasks, 2+ users/teams, project/time/system IDs, two independent labels, accepted outcomes | no artifact, exact/structured, dense, composed subplan, frontier regeneration | successful changed-system replay with zero unsafe/stale/wrong-scope accepts and a pre-registered utility lift | Public Defog and SkillLearnBench lack identities/outcomes; this is the decisive missing evidence |
| P1 | Alias and hard-negative benchmark | reviewed aliases, NILs, same-surface/wrong-system pairs, temporal renames, acronym ambiguity | exact identifiers, termhood/acronym candidates, dense, learned reranker, frontier adjudication | Recall@20 and MRR plus collision-before-target, abstention, reviewer agreement | Ports are useful candidate generators but termhood transfer and generated composition are not reliable enough for promotion |
| P1 | Artifact retrieval and reuse | parameterized validated SQL/tool capsules with authority and schema versions | lexical, dense, identifier-aware, hybrid, subplan composition, regeneration | semantic correctness, authority/deletion safety, changed-schema success, tool-call/cost budget | Whole-query natural retrieval is a coverage null; composability is promising but still small |
| P1 | Embedding-vs-model cascade | the same labeled insight/alias candidate pool and adversarial NILs | structured→lexical, structured→dense, structured→frontier, model-only | quality at fixed cost/latency and no authorization regression | Existing MATM results show action-embedding recall lift but frontier reranking tied lexical on nine queries |
| P2 | Cross-user skill-gap and collaboration study | opt-in identities, task-family labels, reciprocal-contact policy, capability taxonomy | anonymous similarity, team aggregate, opt-in recommendation | independent same-work labels, unwanted-contact rate, next-task outcome | Current cross-user results are mechanics/silver labels only |
| P2 | Memory and skill release study | bitemporal memories/procedures with citations, contradiction and deletion fixtures | no memory, reviewed memory, generated memory, reviewed+generated | later-query utility, stale/unsafe rate, rollback, reviewer agreement | Natural memory factorial and RHO/ReasoningBank slices do not establish benefit |

## Required dataset contract for P0

Each task must have:

1. a stable principal/team/project identifier and consent scope;
2. source and changed-system environment hashes with a documented mutation;
3. the full request/tool/result trajectory, including failures and retries;
4. two blinded semantic labels plus adjudication and explicit `nil`/`unclear`;
5. an independent terminal outcome (SQL recomputation, tool verifier, or human
   outcome), not a self-judge score; and
6. deletion/retention and authorization-epoch receipts.

No model, embedding, memory, or skill may be promoted from a proxy-only run.

## Promotion thresholds

- **Retrieval:** report Recall@1/5/20, MRR, precision, abstention, and
  wrong-system-before-target. A learned embedding must beat the frozen
  structured baseline by at least 5 absolute Recall@20 points on an entity,
  project, and time-held-out split without increasing collision or latency
  gates.
- **Artifact reuse:** require semantic correctness, valid authority, no stale
  or unauthorized observation, and a changed-system outcome. “The query ran”
  is not sufficient.
- **Skill/memory:** compare no-skill, neutral/placebo, reviewed, generated,
  and composed arms with randomized order or matched seeds; report regressions,
  tool calls, tokens, wall time, and rollback.
- **Cross-user recommendations:** require reciprocal opt-in, minimum cohort
  sizes, blinded labels, abstention, and an unwanted-contact/negative-transfer
  measure.

## Current disposition of the older ports

The [Termolator/AcronymExpansion modernization audit](older-tool-modernization-value-audit-2026-08-05.md)
keeps both ports offline. Termolator is a reproducible candidate generator;
AcronymExpansion is a safe contextual acronym/NIL candidate miner. Neither
has enterprise-quality or downstream utility evidence. They belong in the P1
candidate-generation arm, not in the gateway hot path.

## Partner/publication package

The strongest paper is **a governed evidence-to-artifact lifecycle for
enterprise agent traces**, not “memory improves agents.” The first outreach
package should include the receipts and protocols already published on the
branch, a sealed replay API, and no raw employee traces:

- CMU LTI / SkillLearnBench: sequential skill benchmark and verifier design;
- MIT DSAIL: learned data systems, SQL artifacts, and schema drift;
- Harvard CHARM/Variation Lab/CRCS/DASlab: human outcomes and data-system
  boundaries;
- MIT CLEAR/TRAC and Microsoft Research: accountability, uncertainty, and
  negative-transfer gates.

The [publication/partner map](publication-partner-opportunities-2026-08-02.md)
contains the proposed 6–8 week reproduction package and contact fit. This is
not evidence that any group has agreed to participate.

## Current claim boundary

The program has strong mechanics and bounded proxy evidence for structured
identity, governed artifact capsules, candidate mining, and reviewed
procedure replay. It has not yet proven enterprise alias quality, a useful
custom embedding model, cross-user skill inference, or causal skill/memory
improvement. The active blocker is data/labels/outcomes, not another database
or another vector index.
