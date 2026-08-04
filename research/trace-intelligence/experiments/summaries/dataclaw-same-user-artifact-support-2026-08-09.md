# DataClaw same-user artifact support

## Question

Does a user's own longitudinal trace history contain enough recurrence to
justify a scoped artifact library, even when strict identities do not transfer
between users?

## Protocol

The same content-free candidate miner was run without a cap on the Peter and
Vaynelee DataClaw exports. Candidates are non-trivial normalized tool plus input
forms. Support tiers count repeated sessions, repeated projects, and proximity
to broad friction-language context. No command, prompt, path, argument, or
identifier is emitted.

## Result

Peter produced 34,036 candidates. **3,158** recurred in at least two sessions,
**518** in at least two projects, **67** in at least three projects, and **780**
in at least five sessions. **460** were both cross-project and friction-adjacent.
Vaynelee produced 971 candidates, with 14 repeated across sessions, 4 across
projects, and 1 cross-project/friction-adjacent candidate.

The candidate occurrence friction-context rate was `.459924` for Peter and
`.097630` for Vaynelee. This is a prioritization signal, not an error or
quality label. Within Peter, repeated-session candidates had a `.480813` rate
versus `.436807` for single-session candidates; in the much smaller Vaynelee
sample, repeated candidates were lower (`.073171` versus `.098619`). The
direction is therefore cohort-dependent and cannot justify a universal
recurrence→friction rule. Combined with the strict cross-user result (zero
shared identities), the evidence favors per-user/project candidate libraries
with replay and review gates, not a global crowdsourced artifact pool.

## Claim boundary

Recurrence does not establish correctness, safety, task intent, authority
compatibility, or user benefit. Friction context is a broad lexical proxy and
may include productive iteration. The next gate is independent replay of
within-user candidates, then changed-project and changed-system evaluation.

Receipts:

- [content-free result](../results/dataclaw-same-user-artifact-support-2026-08-09.json)
- [independent verification](../results/dataclaw-same-user-artifact-support-verification-2026-08-09.json)
- [`dataclaw_same_user_artifact_support.py`](../../dataclaw_same_user_artifact_support.py)
