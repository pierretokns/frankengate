# Temporal DataClaw artifact-reuse audit

## Protocol

Using the parseable Ronald DataClaw export, sessions were sorted by
`start_time` **within each project**. For the 30 projects with at least two
sessions, the first 70% formed the library and the later 30% formed evaluation.
The audit compares normalized command shapes seen in the earlier library:

- same-project library recurrence;
- any-project library recurrence; and
- cross-project shape support in the training library.

This is a chronology/provenance probe, not a semantic-reuse benchmark. Raw
commands and transcript text stayed local and are not in the receipt.

## Results

| Measure | Result |
|---|---:|
| Train/evaluation projects | 30; 16 single-session projects excluded |
| Train/evaluation sessions | 279 / 141 |
| Evaluation sessions with command shapes | 105 |
| Evaluation shape events | 2,245 |
| Shape-event reuse from same project | 370 / 2,245 = **0.165** |
| Shape-event reuse from any project | 627 / 2,245 = **0.279** |
| Sessions with at least one same-project reused shape | 88 / 105 = **0.838** |
| Unique train shapes | 2,445 |
| Train shapes supported by multiple projects | 159 = **0.065** |

## Interpretation

The session-level and event-level numbers diverge sharply. Most later sessions
contain at least one previously seen same-project shape, but only 16.5% of
individual command-shape events are same-project repeats. A few generic setup
or harness commands create high session-level recurrence without establishing
that the substantive work is reusable. Cross-project recurrence is even more
important as a hard-negative source: 27.9% of later shape events are already
seen somewhere, while only 6.5% of distinct training shapes have support in
multiple projects.

This supports three design rules:

1. Report event-level support and parameter diversity, not only “a session had
   a reusable artifact.”
2. Use cross-project recurrence to build hard negatives and boilerplate filters.
3. Require semantic labels, authority/schema contracts, and independent replay
   before turning a recurring shape into a validated artifact or skill.

## Decision boundary

Temporal recurrence is strong enough to prioritize review and construct a
candidate library. It does **not** prove task equivalence, artifact
correctness, alias quality, skill improvement, or user benefit. Promotion stays
disabled until a reviewed same-work/NIL cohort and terminal replay outcomes are
available.

Receipt: [`dataclaw-ronald-temporal-artifact-audit-2026-08-02.json`](../results/dataclaw-ronald-temporal-artifact-audit-2026-08-02.json)

Audit implementation: [`dataclaw_temporal_artifact_audit.rb`](../../dataclaw_temporal_artifact_audit.rb)
