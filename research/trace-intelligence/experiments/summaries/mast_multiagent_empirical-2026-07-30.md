# MAST-Data multi-agent structural and taxonomy audit

**Run date:** 2026-07-30

**Result schema:** `mast-multiagent-empirical-result-v1`

**Result digest:** `abb144d59e5405be50af7dea5bad6de386aa0f75376c0939333fef428a8baad6`

## Research question and claim boundary

This experiment asks what the public MAST release can reproducibly establish
about heterogeneous multi-agent traces, their communication structure, and the
released 14-mode failure labels. It does **not** test single-agent trajectories,
human employees, enterprise work, skill, productivity, learning, or suitable
collaborators. No such transfer claim follows from these results.

Primary sources:

- [MAST paper](https://arxiv.org/abs/2503.13657)
- [MAST source repository](https://github.com/multi-agent-systems-failure-taxonomy/MAST)
  at commit `a70542e541b2104ef8fcd785778179e173fb8d70` (the repository
  has no stable tag and no license file at this revision)
- [MAST-Data on Hugging Face](https://huggingface.co/datasets/mcemri/MAST-Data)
  at immutable revision `5a82e32347f70a701a3c68637de12f8a0be3de3c`,
  declared CC BY 4.0

Raw JSON remained in temporary storage. The committed result contains only
aggregates and content digests.

## Method

The two released JSON files were loaded independently:

| Authority | File | SHA-256 | Released rows |
|---|---|---|---:|
| LLM judge | `MAD_full_dataset.json` | `a182daadb8ded015efc889db8bde29e5e4dd478e0dcc5516f6727a1bbc43eaec` | 1,242 |
| Human votes | `MAD_human_labelled_dataset.json` | `30a0c4075078e9a1b8c39bc608d2b5156cc64c6bda1f6fd262786eb81ff4a286` | 19 |

The adapter made one canonical event per physical source line, retaining the
line ending. Concatenating canonical event content must reproduce the source
byte-for-byte after UTF-8 decoding. A communication edge is `observed` only
when one source marker supplies its endpoint evidence. Edges between successive
explicit speaker markers are `reconstructed`; they are turn adjacency, not
observed handoffs. AppWorld markers that name only a sender or receiver remain
partial and are not silently completed.

Three deterministic baselines were evaluated on an immutable hash split of the
LLM-judge rows (1,009 train; 233 test):

1. predict no failure modes;
2. predict the three most prevalent training codes for every test trace; and
3. apply fixed surface-token rules derived without reading a row's labels.

Human votes were neither training data nor a scoring authority for these
baselines.

Reproduction:

```bash
python3 research/trace-intelligence/mast_empirical.py \
  --full /tmp/mast-data/MAD_full_dataset.json \
  --human /tmp/mast-data/MAD_human_labelled_dataset.json \
  --definitions /tmp/mast-data/definitions.txt \
  --judge-notebook /tmp/mast-data/llm_judge_pipeline.ipynb \
  --output research/trace-intelligence/experiments/results/mast_multiagent_empirical-2026-07-30.json
```

## Structural projection results

All 1,242 traces and 897,277 source lines round-tripped into 897,277 canonical
events with **zero silently dropped lines**.

| Framework | Traces | Lines | Observed complete edges | Observed partial edges | Reconstructed adjacent-speaker edges | Role-available line coverage |
|---|---:|---:|---:|---:|---:|---:|
| AG2 | 597 | 3,407 | 0 | 0 | 246 | 47.26% |
| AppWorld | 30 | 40,628 | 0 | 2,258 | 694 | 99.70% |
| ChatDev | 130 | 503,650 | 1,795 | 0 | 0 | 96.98% |
| HyperAgent | 30 | 82,979 | 0 | 0 | 1,365 | 83.93% |
| Magentic | 195 | 197,876 | 0 | 0 | 4,231 | 81.08% |
| MetaGPT | 230 | 44,589 | 230 | 0 | 496 | 98.45% |
| OpenManus | 30 | 24,148 | 0 | 0 | 0 | 97.30% |

The adapter recovered 2,025 observed complete communication edges, 2,258
observed partial edges, and 7,032 reconstructed adjacency edges. This is a
positive result for lossless text admission and conservative graph extraction,
but a negative result for any proposed universal communication graph: only
ChatDev and MetaGPT provide substantial markers with both endpoints. The other
frameworks require partial or reconstructed structure, and OpenManus exposes
only one observed actor under this conservative parser.

## Annotation release audit

The immutable files do not reproduce the paper's stated cardinalities:

| Artifact | Paper | Released file | Difference |
|---|---:|---:|---:|
| Judge-labeled traces | 1,642 | 1,242 | -400 |
| Human-labeled traces | 21 | 19 | -2 |

The Hugging Face viewer also fails because it attempts to cast the incompatible
human and judge schemas into one table. Direct file loading is required.

The human file is not one 14-mode benchmark:

- 15 traces belong to three taxonomy-development rounds with 17 or 18 modes
  and changing numeric meanings.
- Only four `Generlazability` rows use the finalized ordered 14-code schema.
- Three development traces exactly overlap the judge file by trace SHA-256.
- **Zero finalized-taxonomy human traces overlap the judge file.**

Consequently, this release cannot independently reproduce a finalized
human-versus-judge accuracy estimate. Remapping development-round numeric codes
would change their meanings and was not performed.

The judge file contains only 14 binary codes, not evidence spans or reasons.
There is also an unresolved source inconsistency: the pinned definitions file,
judge notebook, final human titles, and paper do not use identical wording for
verification modes 3.2 and 3.3. The analysis therefore preserves raw code
identity and does not claim those code semantics are resolved.

## Naive baseline results

All metrics below measure agreement with released **LLM-judge codes**, not
ground-truth failure diagnosis.

| Baseline | Exact match | Hamming accuracy | Micro precision | Micro recall | Micro F1 | Macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| Always negative | 21.03% | 81.42% | 0.00% | 0.00% | 0.000 | 0.000 |
| Training top three (`2.6`, `1.3`, `1.1`) | 0.00% | 76.12% | 37.63% | 43.40% | 0.403 | 0.117 |
| Fixed surface rules | 20.17% | 81.21% | 26.67% | 0.66% | 0.0129 | 0.00784 |

High Hamming accuracy for the useless always-negative predictor demonstrates
the danger of reporting per-code accuracy on sparse multi-label data. Surface
keywords retrieve almost none of the judge positives. A global prevalence
baseline improves micro F1 but never predicts an exact label set and has very
low macro F1. None localizes a decisive step or establishes causality.

## Implications for Frankengate research

What is supported:

- a source-line-lossless ingestion layer for the seven released frameworks;
- explicit provenance for observed, partial, reconstructed, and missing
  communication structure;
- preservation of all 14 released judge codes without mixing them with human
  votes; and
- a reproducible warning baseline showing why sparse-label accuracy and lexical
  detectors are insufficient.

What must be added before MAST concepts can support a real diagnostic system:

- stable message, tool-call, result, causal-parent, and handoff identifiers;
- independent task outcomes and replayable verifier evidence;
- evidence spans for every failure-mode annotation;
- a versioned taxonomy authority resolving 3.2/3.3 semantics;
- a released finalized human holdout that actually overlaps judge-scored
  traces; and
- framework-held-out evaluation followed by prospective intervention tests.

Even after those additions, this corpus would validate multi-agent system
failure analysis only. Single-agent and enterprise-human questions require
separate admitted data, labels, governance, and prospective experiments.
