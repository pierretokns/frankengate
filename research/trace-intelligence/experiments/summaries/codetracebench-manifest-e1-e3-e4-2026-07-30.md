# CodeTraceBench manifest-level E1/E3/E4 study

**Run date:** 2026-07-30

**Analysis:** `codetracebench-manifest-e1-e3-e4-v1`

**Dataset:** [NJU-LINK/CodeTraceBench @
`aa213b84ffb6690fc37ca15766d6ca174ec36d4d`](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d),
MIT

**Paper:** [CodeTracer: Towards Traceable Agent
States](https://arxiv.org/abs/2604.11641)

**Result content hash:** `32e3be131f700a7df6a3c377a5ed5f8ad8f1d1b6af76031eaeef10eaa13251f3`

## Abstract

This reproducible study tests three narrow parts of Frankengate's trace-intelligence
program against CodeTraceBench's released manifests.  It uses the 1,000-row verified
set for human labels and the 3,316-row full set solely to verify parent overlap and
split integrity.  Raw trajectory archives were neither downloaded nor committed.

The result is useful but deliberately smaller than the planned E1/E3/E4 factorials:
it measures label-blind structural review selection, deterministic localization
baselines against human incorrect-step labels, and seeded mutation sensitivity of
annotation-derived retrospective assertions.  It does **not** test trace content,
invariants, multimodal evidence, an LLM judge, a resettable environment, or a changed
agent.

## Reproduction

Download exactly these two files from the pinned Hugging Face revision into a
non-repository directory:

```text
bench_manifest.full.parquet
  sha256 0c25108022f518d09505d66cee7a8baeaa2d64708c98e8a66a061819c0b3da6d
bench_manifest.verified.parquet
  sha256 ae5926b496f2f7f4c3f6337c0ad6150311d3650c5f3bd00660556b3e41739505
```

Then run:

```bash
python3 research/trace-intelligence/codetracebench_empirical.py \
  --full /private/tmp/frankengate-codetracebench-aa213b84/bench_manifest.full.parquet \
  --verified /private/tmp/frankengate-codetracebench-aa213b84/bench_manifest.verified.parquet \
  --output-json /tmp/codetracebench-result.json \
  --output-markdown /tmp/codetracebench-result.md
```

The loader fails closed on either file hash.  Output is aggregate-only and deterministic
for the fixed seed `20260730`.

## Corpus and split integrity

- Verified rows: 1000
- Human-labeled informative rows:
  405
- Rows with incorrect-step labels:
  405
- Incorrect-step labels: 1695
- Unuseful-step labels: 224
- Verified rows found in full parent: 1000
- Missing parents: 0
- Parent split mismatches: 0
- Repository groups crossing splits:
  0
- Task groups crossing splits: 0
- Missing source path: 8 verified and
  146 full rows; these remain explicitly unknown.

The assignment is source-stratified and blocks repository family.  TerminalBench
manifests do not expose repository identity, so each task is the indivisible fallback
group.  The verified set is a subset of full, never an independent test set.

| Source family | Train | Dev | Test |
|---|---:|---:|---:|
| `multi-swe-bench` | 31 | 7 | 6 |
| `swe-bench-pro` | 59 | 13 | 12 |
| `swe-bench-verified` | 148 | 32 | 32 |
| `swe-polybench` | 104 | 23 | 22 |
| `terminal-bench` | 353 | 77 | 73 |
| `unknown-source` | 5 | 0 | 3 |

## E1: label-blind review selection

The test budget is 30 of
148 rows (20%).  "Informative"
means the authors released at least one incorrect or unuseful step label.  Scores use
only step count and stage-boundary structure.  Outcome, labels, task category, agent,
model, and difficulty are excluded.

| Arm | Precision | Recall |
|---|---:|---:|
| `uniform_random` | 0.426 | 0.203 |
| `trace_length` | 0.567 | 0.270 |
| `stage_count` | 0.567 | 0.270 |
| `structural_signal` | 0.567 | 0.270 |
| `structural_signal_plus_random_audit` | 0.633 | 0.302 |

This is a deterministic structural baseline, not a preregistered replication of the
Signals paper.  In particular, the manifest cannot expose rephrasing, semantic loops,
tool failures, disengagement, or stagnation in the raw event stream.  Any improvement
over random only justifies a review-queue heuristic; it is not a diagnosis.

## E3: incorrect-step localization

The gold target is the released `incorrect_step_ids`.  The paper calls the earliest
upstream causal-chain origin error-critical, but a manifest row can contain multiple
incorrect steps or chains.  Results therefore measure overlap with the released set,
not independently established causality.

| Method | Evidence class | Top-1 | Top-3 | MRR | Macro F1@|G| |
|---|---|---:|---:|---:|---:|
| `uniform_random` | blind | 0.095 | 0.286 | 0.234 | 0.115 |
| `forward_chronology` | blind | 0.000 | 0.000 | 0.049 | 0.006 |
| `reverse_chronology` | blind | 0.238 | 0.444 | 0.371 | 0.246 |
| `stage_boundary_recency` | blind | 0.238 | 0.444 | 0.406 | 0.174 |
| `longest_stage_end` | blind | 0.032 | 0.238 | 0.208 | 0.081 |
| `critical_stage_start_oracle` | oracle | 0.698 | 0.857 | 0.788 | 0.469 |
| `critical_stage_end_oracle` | oracle | 0.524 | 0.714 | 0.640 | 0.378 |

The critical-stage boundary methods consume the annotated incorrect-stage identity
and are explicitly upper bounds, not deployable baselines.  No method here evaluates
the planned invariant × topology/modal-evidence × calibrated-judge factorial.
Irrelevant-tail injection is the only available content-free negative control.
Timestamp, environment, permission, and evidence-removal controls are impossible from
the manifest and remain untested.

## E4: retrospective assertion mutation

Human-labeled steps were converted into four retrospective audit assertions.  One
supported mutation at a time removes, duplicates, reorders, relabels, or changes an
available action/observation reference.  Injecting one unrelated event is the allowed
variation control.

| Assertion | Harmful mutants | Kill rate | Allowed-variation false positive |
|---|---:|---:|---:|
| `exact_sequence` | 284 | 1.000 | 1.000 |
| `ordered_required` | 284 | 0.401 | 0.000 |
| `unordered_required` | 284 | 0.222 | 0.000 |
| `combined` | 284 | 1.000 | 0.000 |

`exact_sequence` is intentionally brittle.  `combined` retains order, cardinality,
labels, and released reference fingerprints while allowing an unrelated event.  This
validates mutation-harness mechanics only.  Because the assertions are derived from
the same annotations they evaluate, the high kill rate is not evidence of
generalization.  They are audits, not runnable evals; no agent was rerun and no
external state delta was observed.

## What this changes for Frankengate

1. Keep cheap structural signals as label-blind candidate selectors and always retain
   a random audit stratum.  Do not label their output as root cause.
2. Store gold step sets, coarse stages, prediction rankings, alternatives, abstention,
   and evidence IDs separately.  A stage label is useful navigation but cannot be
   counted as a blind step diagnosis.
3. Require every proposed eval to declare whether it is a stored-trace audit or a
   changed-system replay.  Mutation sensitivity and allowed-variation false positives
   are both release gates.
4. Do not use these software-agent labels to infer employee skill, productivity,
   intent, or collaboration fit.  They contain no enterprise authorization,
   intervention, or human-work outcome evidence.

## Limitations and next experiment

CodeTraceBench is filtered: the paper reports removing timeout, truncated,
misconfigured/corrupt, and short correct runs before benchmark curation.  It therefore
cannot estimate natural enterprise failure prevalence.  The released dataset version
also differs from counts reported in the paper; this study treats the pinned files as
the empirical authority and records their hashes.

The next E3/E4 experiment must freeze a license-clean raw-artifact allowlist from the
blocked test groups, parse complete action/observation sequences, and run the full
factorial with invariants, ordered topology/modal evidence, calibrated abstention, and
independent verifier state.  Until then, Frankengate should ship evidence-linked
review and eval proposals, not automatic root-cause or skill claims.
