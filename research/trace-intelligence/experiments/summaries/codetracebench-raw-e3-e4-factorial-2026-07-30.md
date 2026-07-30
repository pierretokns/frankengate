# CodeTraceBench raw-trajectory E3/E4 factorial

**Issue:** [#104](https://github.com/pierretokns/frankengate/issues/104)

**Bead:** `bif-kyy.17.13.4.2.1`

**Dataset:** [NJU-LINK/CodeTraceBench @
`aa213b84ffb6690fc37ca15766d6ca174ec36d4d`](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d),
MIT

**CodeTracer source:** [untagged `2d302191dd07e7c0c2da6f7a5e9451c7cbb62d34`](
https://github.com/NJU-LINK/CodeTracer/tree/2d302191dd07e7c0c2da6f7a5e9451c7cbb62d34)

**Result hash:** `652ee80b5ad1888ec8c6f583e0b5db0688da402e6d3508b98b567ff08a58577c`

## Abstract

This study acquired every available artifact in the previously frozen,
repository/task-blocked CodeTraceBench test split: 145
archives totaling 26.93 MiB.  Three
blocked-test rows had no artifact path.  Every archive was verified against its
immutable Hugging Face LFS SHA-256 and streamed without committing raw content.

The result is negative/partial.  Of 145 parsed archives,
78 exactly preserved the published manifest step identity.
Only 35 exact-aligned traces also had incorrect-step gold labels
and could enter E3/E4.  The best deterministic arm, `I0T0J0`, reached
0.286 top-1 versus
0.286 for reverse-chronology tie-breaking.  This does not
establish causal diagnosis, and no arm is a calibrated LLM judge.

## Reproduction and admission

The committed allowlist contains only public artifact IDs, byte sizes, and immutable
hashes—not trace content.  Its identity digest is
`23a7a3b70280ad14c2da13431831e9f6e824ff1a854a918188ddb55d17d6b016`.  Raw archives remain under
`/private/tmp` or another non-repository directory.

The dataset repository is MIT.  CodeTracer has no published tag at the reviewed
revision.  Its ordinary checkout failed because GitHub reported an exhausted LFS
budget, so source code was reviewed with LFS smudging disabled.  The Hugging Face
artifacts remained independently available.

## Loss receipts

| Agent | Archives | Exact alignment | Action coverage | Observation coverage | Timestamp coverage |
|---|---:|---:|---:|---:|---:|
| OpenHands | 74 | 32 | 0.770 | 0.770 | 0.770 |
| SWE-agent | 15 | 15 | 0.956 | 1.000 | 0.000 |
| Terminus2 | 34 | 14 | 0.905 | 0.973 | 1.000 |
| mini-SWE-agent | 22 | 17 | 0.818 | 0.770 | 0.818 |

Across the corpus, the adapters observed 5191 native steps,
mapped 4632 steps against 6883 manifest
steps, and read 9341 relevant members.  Mismatches are
quarantined from localization instead of truncated or padded.

The common irreducible losses are authorization/purpose/classification/epoch,
independent step-level causal state, and portable proposal/result events.  OpenHands
tensorblock observations require reconstruction from the following LLM request;
Terminus2 may omit the final observation; SWE-agent lacks absolute timestamps.

## E3 factorial

The eight arms cross:

- `I`: explicit error and missing-observation invariants;
- `T`: repetition plus edit/setup-to-failing-test topology/modal evidence; and
- `J`: a deterministic error/risky-reasoning lexical judge.

No factor reads `solved`, incorrect-stage identity, incorrect-step IDs, difficulty,
agent, model, or category.  Human incorrect-step IDs are used only after ranking.

| Arm | Top-1 | Top-3 | MRR | Macro F1@|G| |
|---|---:|---:|---:|---:|
| `I0T0J0` | 0.286 | 0.543 | 0.434 | 0.276 |
| `I0T0J1` | 0.171 | 0.371 | 0.316 | 0.130 |
| `I0T1J0` | 0.229 | 0.429 | 0.381 | 0.266 |
| `I0T1J1` | 0.229 | 0.286 | 0.358 | 0.127 |
| `I1T0J0` | 0.171 | 0.343 | 0.332 | 0.184 |
| `I1T0J1` | 0.200 | 0.343 | 0.334 | 0.152 |
| `I1T1J0` | 0.229 | 0.314 | 0.359 | 0.164 |
| `I1T1J1` | 0.171 | 0.257 | 0.311 | 0.110 |

The deterministic judge emits no probabilities.  Reporting Brier score or ECE would
fabricate calibration, so calibration is explicitly not applicable.  The study used
zero model calls, zero tokens, and $0 model cost.

### Negative controls

- Gold-step observation removal changed combined top-1 from
  0.171 to
  0.057.
- Benign-tail top-1 change rate:
  0.000.
- Irrelevant-error-tail top-1 change rate:
  0.257.
- Timestamp shuffle top-1 change rate:
  0.000;
  timestamps are deliberately excluded from scoring.
- Environment and authorization swaps are unsupported by the source and were not
  simulated.

## E4 stored-trace assertion mutations

| Assertion | Harmful mutants | Kill rate | Allowed-variation false positive |
|---|---:|---:|---:|
| `exact_sequence` | 191 | 1.000 | 1.000 |
| `ordered_gold_action` | 191 | 0.450 | 0.000 |
| `invariant_non_regression` | 191 | 0.042 | 0.000 |
| `combined_raw_and_verifier` | 191 | 0.969 | 0.486 |

These are stored-trace audits.  No changed agent ran in a resettable environment.
High mutation kill rate is mechanical sensitivity, not evidence of future behavior.
Exact sequence checks are expected to be brittle to benign additions and timestamp
changes.

## Independent verifier boundary

An external terminal verifier was present for
136 archives.  A binary verifier outcome and
manifest comparator were both available for
117;
their agreement was
0.9914529914529915.
There were zero independent step-level causal verifiers.  Terminal pass/fail can
corroborate an outcome but cannot identify the action that caused it.

## Frankengate decision

This run supports loss-aware ingestion, evidence-linked review, and retrospective eval
proposal mechanics.  It does not clear the L3 product gate for automatic cause
language: the deterministic arms must beat simple baselines on an independently
adjudicated holdout, emit calibrated abstention, and survive irrelevant-error
injection.  Frankengate must continue to call these findings hypotheses or audits.

Nothing in this coding-agent corpus supports claims about an employee's skill,
productivity, intent, or ideal collaborator.
