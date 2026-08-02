# Cross-user insight and skill-gap protocol (2026-08-09)

## What the available traces can support

The 28-session Trace Commons sample has no stable principal identity, semantic
task labels, or prospective outcomes. Using repeated project/workspace as a
workstream proxy, leave-one-session-out retrieval reached:

| Representation | Same-project top-1 | MRR |
|---|---:|---:|
| Event/tool structure | 1/13 | .215 |
| Prompt terms | 13/13 | 1.000 |
| Durable identifiers | 12/13 | .938 |
| Prompt + identifiers | 13/13 | 1.000 |

The leave-one-project-out token adapter tied the already-ceiling baseline. In a
separate eight-candidate DataClaw frontier screen, 16/16 JSON responses were
valid but repeated reviews agreed on only `5/8` candidates. Recurrence produced
reusable, context-specific, unsafe, and insufficient-evidence labels; it did
not establish portability or correctness.

These are useful mechanics results: preserve prompts, exact identifiers, tool
arguments, project scope, provenance, and event order. They are not evidence
that two people are doing the same business work, that a person lacks a skill,
or that a recommendation improves the next task.

## Required data contract for a real cross-user study

Every candidate link must carry:

1. reciprocal principal/team opt-in and a stable pseudonymous principal ID;
2. project, system, authorization scope, and time interval;
3. a blinded task-family label from two reviewers plus `NIL`/`unclear`;
4. exact identifiers and a same-surface/wrong-system negative set;
5. a capability taxonomy with evidence spans, not a model-inferred deficiency;
6. an independent terminal outcome for the source and next task; and
7. recommendation exposure, acceptance, correction burden, unwanted-contact,
   and negative-transfer measurements.

The unit of analysis should be a future task, not a similarity score. A
recommendation is successful only if it improves the recipient's next task or
learning outcome without exposing unauthorized work or creating unwanted
contact.

## Frozen experiment

For a consented cohort, hold out principals and time periods and compare:

1. exact identifier/scope retrieval;
2. lexical + structured reranking;
3. dense candidate expansion;
4. frontier adjudication of candidate links;
5. team-aggregate suggestions with reciprocal opt-in; and
6. no-recommendation control.

Use same-surface/wrong-system, temporal replacement, unrelated exposed
candidate, and true-NIL cases. Report Recall@k, MRR, collision-before-target,
NIL abstention, reviewer agreement, recommendation acceptance, next-task
utility, correction burden, unwanted-contact rate, and latency/cost. Do not
train a custom embedding until it beats the structured baseline on
principal/time/entity-held-out hard negatives and also improves a downstream
outcome.

## Partner/publication fit

- **Harvard CHARM / Variation Lab:** prospective human learning, agency, and
  recommendation outcomes.
- **Harvard CRCS / DASlab:** goal recognition, collaboration boundaries, and
  workload/data-system modeling.
- **MIT CLEAR/TRAC:** uncertainty, abstention, accountability, and negative
  transfer.
- **CMU LTI / SkillLearnBench:** task-family holdouts and skill-quality versus
  trajectory-quality evaluation.

The defensible paper claim is a governed cross-user evidence-to-recommendation
protocol with explicit refusal—not “embeddings discover employee skill gaps.”

## Receipts

- [Trace Commons feature ablation](trace-commons-feature-ablation-2026-08-07.md)
- [Trace Commons domain adapter](trace-commons-domain-adapter-2026-08-07.md)
- [DataClaw artifact frontier screen](dataclaw-artifact-frontier-screen-2026-08-05.md)
- [Publication/partner evidence packet](publication-partner-evidence-packet-2026-08-06.md)

