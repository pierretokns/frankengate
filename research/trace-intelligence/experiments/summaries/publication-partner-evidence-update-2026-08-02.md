# Publication and partner evidence update

**Update date:** 2026-08-02
**Status:** methods packet; no partner commitment implied

## Strongest publishable contribution

The new evidence supports a precise systems-and-evaluation contribution:

> **A governed evidence-to-artifact lifecycle for agent traces:** candidate
> mining from longitudinal histories, exact/parameterized binding, explicit
> authority and scope, typed memory/skill provenance, independent replay, and
> changed-system promotion gates.

This is stronger and more falsifiable than “enterprise memory improves agents.”

## New evidence to include in outreach

| Evidence | Result | Partner implication |
|---|---|---|
| Exact versus normalized command reuse | Chronological same-project event reuse: exact `.064`, shape `.159`; any-project exact `.084`, shape `.303` | Shape mining is recall; parameterized binding and replay are the research problem |
| Command parameter diversity | 12,237 command events, 4,297 shapes, 9,387 exact commands; 312 shapes had ≥5 variants | Study typed template induction and changed-tool/schema validation, not nearest-prefix copying |
| Durable artifact lifecycle | 13 sessions referenced `memory.md`, 34 skills, 243 Claude configs; 373 read-like and 343 write-like calls | Memory/skills are real trace events; provenance and release semantics are first-class |
| Longitudinal memory-write association | Post-write shape/exact reuse `.397/.124` versus `.027/.008` without prior writes | Strong observational signal, but project age/task mix confound it; requires randomized replay |
| Friction signals | 121 rephrase pairs and 19 exact repeats, but zero typed tool-result messages | Preserve tool-result edges before claiming failure recovery or friction labels |
| Dataset integrity | A second scrubbed DataClaw export had 9/775 valid rows; a parseable OpenAI projection had 436 sessions | Ingestion integrity and loss accounting are part of the benchmark, not housekeeping |
| Identifier-aware retrieval | On 141 chronological held-out sessions, prompt-only project MRR `.551`; prompt + identifiers `.598`; prompt + shapes + identifiers `.657` | Preserve exact identifiers as a separate candidate lane; this is a project-recurrence proxy, not same-work or alias truth |
| Exact-path versus basename drift | Same-project basename reuse `.303` of path events versus exact-path `.167`; only `.553` of same-project basename hits were exact; 60 exact digests crossed projects in training | Exact identity is a high-precision exposure feature, while basename matching supplies recall and hard negatives; neither is an authority key |
| Within-project memory-write permutation | Prior-write minus no-prior differences `.366` (shape) and `.114` (exact), fixed-project-count permutation p-values `.0042` and `.0186` | Memory/skill writes are a useful sampling stratum for replay, but temporal/user-choice confounding still blocks causal promotion |

All numbers are content-free, local-only receipts; no employee transcripts or
raw commands are in the branch.

The newest identifier results make the partner benchmark more precise. A
same-surface/different-path collision is common enough to supply hard negatives,
but exact paths also cross projects. The benchmark should therefore label four
separate strata—exact identity, same basename/different path, cross-project
basename, and cross-project exact path—before comparing lexical, dense,
identifier-aware, and frontier-review arms.

The partner handoff now includes a machine-checkable [enterprise semantic-cohort
contract](../../configs/studies/enterprise-semantic-cohort-v1.json) and
[validator](../../enterprise_semantic_cohort_validator.rb). A structurally valid
fixture is deliberately still promotion-ineligible until it reaches the target,
hard-negative, NIL/unclear, dual-label, authority, deletion, and independent
outcome gates. This turns the missing cohort into an explicit ingestion and
study-design requirement rather than an informal promise.

The [hard-negative strata supply audit](dataclaw-hard-negative-strata-2026-08-02.md)
shows that the chronological train half of the public export contains 2,610
same-surface/different-path, 1,601 cross-project same-surface/different-path,
306 cross-project exact-path, and 2,125 same-project exact-identity candidate
pairs. This is enough candidate capacity for a partner annotation exercise;
the export still cannot supply semantic labels, consent, changed-system
outcomes, or causal user evidence.

## Partner-specific study asks

### CMU LTI / SkillLearnBench

Jointly build a changed-system memory/skill replay benchmark with:

- no-memory, neutral/placebo, reviewed-memory, generated-memory, and composed
  subplan arms;
- explicit `tool_call -> tool_result -> user correction` trajectories;
- task-family, project, and time holdouts;
- skill quality, trajectory quality, terminal success, rollback, and cost; and
- artifact-specific NIL and contradiction cases.

The key open question is causal downstream utility, not whether a file was
written or a shape recurred.

### MIT DSAIL / Harvard DASlab

Study parameterized artifact storage and retrieval under schema/tool drift:

- exact command/SQL identity versus normalized shape;
- typed argument schemas and semantic IDs;
- authority epochs, deletion, expiry, and RLS; and
- replay-compatible latency and index costs.

The public trace result supplies a workload and hard-negative construction; it
does not supply enterprise semantic labels.

### Harvard CHARM / Variation Lab / CRCS

Run the first prospective human study. Test whether a review-only suggestion
from traces changes the user’s next task, correction burden, time-to-success,
or transferable skill. Require reciprocal opt-in for cross-user suggestions,
explicit `nil`/`unclear`, and a negative-transfer/unwanted-contact measure.

### MIT CLEAR / TRAC and Microsoft Research

Formalize evidence-chain and release semantics: calibrated abstention,
contradiction, deletion, provenance, authority epochs, and rollback. The
memory-write association is a useful observational signal for designing the
randomized study, not an outcome claim.

## First joint protocol

Use a sealed 20–40-task SQL/tool cohort with at least two task families and a
changed system. Pre-register:

1. no artifact/memory;
2. neutral or formatting placebo;
3. exact/structured retrieval;
4. reviewed parameterized artifact or memory;
5. generated artifact/skill;
6. composed subplan; and
7. frontier regeneration when the compatible set is empty.

Each arm must receive the same candidate pool and tool budget. Report semantic
terminal outcome, wrong-system-before-target, stale/unauthorized use,
abstention, reviewer agreement, correction burden, tokens, latency, cost, and
rollback. Do not pool BIRD-Interact clarification outcomes with SQL artifact
outcomes.

## Publication lanes

- **SIGIR/ACL Industry:** exact/structured identity, parameter-aware hard
  negatives, and explicit NIL refusal.
- **SIGMOD/MLSys:** governed artifact storage, schema drift, deletion/RLS, and
  replay/latency trade-offs.
- **CHI/CSCW:** trace-derived review suggestions, friction, and skill-gap
  outcomes.

The branch currently supports a reproduction packet and sealed replay API. It
does not support a claim that enterprise memory, custom embeddings, or
cross-user skill inference already works.

Receipts referenced by this update:

- [Exact versus shape temporal reuse](dataclaw-ronald-exact-vs-shape-temporal-2026-08-02.md)
- [Command-shape variants](dataclaw-ronald-command-shape-variants-2026-08-02.md)
- [Memory/skill artifacts](dataclaw-ronald-memory-skill-artifact-audit-2026-08-02.md)
- [Memory-write association](dataclaw-memory-write-longitudinal-2026-08-02.md)
- [Identifier-aware retrieval](dataclaw-ronald-identifier-aware-retrieval-2026-08-02.md)
- [Temporal identifier reuse](dataclaw-ronald-identifier-temporal-reuse-2026-08-02.md)
- [Within-project memory-write permutation](dataclaw-memory-write-within-project-permutation-2026-08-02.md)
- [Hard-negative strata supply](dataclaw-hard-negative-strata-2026-08-02.md)
- [Structural friction](dataclaw-ronald-structural-friction-audit-2026-08-02.md)
- [Malformed export integrity](dataclaw-mriabov-export-integrity-2026-08-02.md)
