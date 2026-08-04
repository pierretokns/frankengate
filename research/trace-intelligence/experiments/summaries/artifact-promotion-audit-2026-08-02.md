# Real-history artifact-promotion audit

This audit combines the current Claude and Codex history receipts to answer a
narrow question: when does recurrence become evidence for a reusable artifact,
and when does normalization or cross-scope transfer make it unsafe? It stores
only receipt hashes and aggregate values. The [machine-readable receipt](../results/artifact-promotion-audit-2026-08-02.json)
contains the recomputed observations.

## Results

| Evidence | Measured result | Promotion implication |
|---|---:|---|
| Claude strict recurrence | `70,949` paired calls; `2,012` successful artifacts recurring across sessions; `1,105` across projects; `431` mixed-outcome identities; `3,866` error→success recoveries | There is enough structure for a governed candidate/recovery queue, but recurrence and recovery are not correctness labels. |
| Claude temporal exact prior | Same-project lift `+.081052`; other-project lift `+.084398` | Exact prior success is useful ranking signal, not permission to execute. |
| Claude frozen drift holdout | Same-project lift `+.063798`; other-project lift `+.053078` | The signal survives time separation but decays; artifacts need expiry and versioning. |
| Claude key-shape control | Cumulative lifts `−.017594/−.015495`; frozen lifts `−.062541/−.090060` | Tool name plus input-key shape is actively unsafe as a reuse policy. |
| Normalized command identity | `140` extra exact-command collisions, `29` multi-command buckets, and `3` mixed-outcome buckets; exact identity had zero mixed buckets | Normalized keys may expand recall only. Preserve exact invocation, bindings, scope, and outcome separately. |
| Cross-cohort transfer | Exact identity: `1` artifact / `3` occurrences. Normalized identity: `9` artifacts / `72` occurrences at `.986111` success | Normalization increases discoverability but does not establish shared intent or safe cross-user reuse. |
| Codex command history | Same-scope prior success `.970863` over `13,797` repeats; other-scope reuse `.870229` over `131` calls; overall `.946811` | Scope is a first-class artifact field; cross-scope reuse is negative transfer. |

## Required artifact contract

The evidence supports promoting only a **candidate** when all of the
following are retained:

```text
immutable invocation identity
  + exact parameter bindings
  + project/team/system scope
  + authority and environment epoch
  + observed outcome and provenance
  + expiry/version
  + clean + changed-system replay evidence
  + semantic intent/NIL review
```

Normalized identities, recurrence counts, process exit codes, and
`is_error=false` statuses are ranking features. They are not semantic
correctness, authorization, or user-success labels.

## What this adds to the broader research

This closes the “do real histories contain reusable material?” question at the
structural level: yes, especially for same-scope shell and mutation work. It
does not close the enterprise-learning question. The missing experiment is a
blinded, consented cohort that joins artifact candidates to task intent,
authority, changed-system replay, and prospective user outcomes. Without that,
the safe product is a review/replay queue, not automatic memory, skill, or
cross-user reuse.

## Claim boundary

No semantic correctness, safe replay, causal user benefit, or cross-user intent
equivalence is established by this audit.
