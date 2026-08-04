# Expanded frontier screen of recurring DataClaw artifacts (2026-08-02)

This is a replication/extension of the earlier eight-candidate screen. It
tests whether a frontier model can provide a stable first-pass review of
recurring tool artifacts after deterministic recurrence mining. It is a
silver-screening experiment, not an artifact-release test.

## Protocol

- Source: pinned `zhiyaowang/dataclaw-zhiyaowang` revision
  `f5157333cbc22489661122a9bc5347b137144900`.
- The fetch sampled 64 rows and selected 16 recurring successful normalized
  tool-input fingerprints. Every selected candidate crossed at least two
  project labels in this sample.
- Each candidate was reviewed three times by `gpt-5.6-luna` through the Codex
  harness under a strict JSON schema.
- Prompts contained only bounded, credential-scrubbed examples. Raw examples
  and model reasons were not written to the repository. The receipt stores
  candidate hashes, coverage counts, labels, latency, and output hashes.

## Results

| measure | value |
| --- | ---: |
| candidates screened | 16 |
| frontier calls | 48/48 valid |
| unanimous candidates | 11/16 (68.75%) |
| mixed-label candidates | 5/16 (31.25%) |
| reusable-procedure judgments | 25/48 (52.08%) |
| context-specific judgments | 18/48 (37.50%) |
| unsafe-or-sensitive judgments | 3/48 (6.25%) |
| insufficient-evidence judgments | 2/48 (4.17%) |
| mean call latency | ~8.76 seconds |

The five disagreements were not parser failures. They were substantive
boundary judgments: reusable versus context-specific, or reusable versus
insufficient evidence. The expanded result is more stable than the first
screen (11/16 versus 5/8 unanimous candidates), but the proportions are nearly
the same and one-third of candidates still lack a stable label.

## Interpretation

The result supports a three-stage review queue:

1. deterministic recurrence, scope, provenance, and success signals select a
   candidate;
2. a frontier model proposes a portability/safety label;
3. independent human review, authority checks, parameter validation, and
   replay decide whether anything can be promoted.

Cross-project recurrence is not a safety or portability proof. In this sample
all candidates were cross-project, yet the model still produced unsafe,
context-specific, and insufficient-evidence labels. This is exactly why
recurrence must be treated as a proposal prior rather than an artifact-quality
label.

## Claim boundary

This screen does **not** establish task correctness, productivity benefit,
skill transfer, semantic equivalence, safety certification, or automatic
promotion. There are no independent task outcomes, SME labels, or changed-
system replay results in this public cohort. The appropriate next experiment is
to attach blinded SME labels and then replay only candidates that pass the
frontier plus authority/parameter gates.

Receipt: [expanded frontier receipt](../results/dataclaw-artifact-frontier-screen-extended-2026-08-02.json).

