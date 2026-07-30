# Wisp recovery-candidate adjudication packet

Date: 2026-07-30

## Purpose

This checkpoint converts the 89 deterministic structural recovery candidates
previously found in the pinned Wisp corpus into a blinded human-adjudication
packet. It is intended to establish gold labels for enterprise questions that
cannot be answered from a later successful tool result alone.

The adjudication unit is a bounded trace episode, never a person. The rubric
explicitly prohibits person-level skill-gap, employee-capability,
intelligence, aptitude, and productivity inferences.

## Protocol

- Candidate IDs are keyed, deterministic blind IDs.
- Candidate order is deterministically randomized from a frozen seed.
- Native source locators and native tool-call IDs are not shown.
- Context is retained as whole events and is capped at 64 events and 196,608
  serialized bytes.
- Every displayed tool proposal must have exactly one displayed terminal
  result. A candidate is excluded instead of emitting partial tool context.
- Credentials alone are transformed. Authorized internal PII, source code,
  paths, and classified content remain available to the internal adjudicator.
- Every label must cite one or more candidate-local evidence references.
- Submissions use closed enums for relation, outcome, cause, evidence strength,
  productive exploration, and usefulness; there is no free-form person-level
  judgment field.

## Result

| Measure | Count |
|---|---:|
| Source sessions | 104 |
| Structural recovery candidates | 89 |
| Adjudication packets emitted | 87 |
| Excluded for incomplete tool context | 2 |
| Malformed source records represented by content-free loss receipts | 2 |
| File-change candidates | 32 |
| File-read candidates | 2 |
| Shell candidates | 53 |

The credential-only gate transformed zero values in the 87 selected packet
contexts. This means no configured credential detector fired in these bounded
contexts; it does not claim that credentials are absent elsewhere in the
corpus.

Raw packet:

- Location:
  `/private/tmp/frankengate-wisp-recovery-adjudication-20260730.json`
- Mode: `0600`
- Bytes: `1,966,782`
- SHA-256:
  `7a519a7f5666eb50dcc4cbba4f2d5d9568b8481168ad01680ae688fdd517fec4`
- Committed to Git: no

Content-free manifest:

- SHA-256:
  `645b4b9a9d4d24c72b75d5560f8a1a0ccdd8f2f3726251c8aa54cadbdfb01e2b`

## Claim boundary

This artifact prepares blinded human review. It does not itself establish task
recovery, root cause, productive exploration, usefulness, or any enterprise
generalization. Those claims require completed adjudications, agreement
measurement, and held-out replication.
