# MATM ALFWorld paired-memory pilot

**Status:** complete, descriptive paired analysis
**Run date:** 2026-07-30
**Claim boundary:** retrieval-condition contrast, not memory-content attribution

## Result

The admitted MATM shard is a valid **paired treatment-condition corpus** and an
invalid **memory attribution corpus**.

Across 355 complete `(task_id, model)` blocks, no reranked-retrieval depth had a
detectable aggregate success advantage over `no_retrieval`. Point estimates
ranged from -0.85 to +0.85 percentage points. Every task/model-pair and
model-cluster bootstrap interval crossed zero, and every exact paired sign test
had `p >= 0.736`.

That near-null average does not prove retrieval is inert. Exploratory
model-stratified rates are heterogeneous. The clearest warning is
`minimax_minimax-m1`: its baseline succeeded on 7/11 tasks, while `rerank_1`,
`rerank_10`, `rerank_15`, and `rerank_20` succeeded on 0/11 and `rerank_5`
succeeded on 1/11. There are only 10 or 11 tasks per model, five depths, and 34
models, so this is a rerun target—not a confirmatory model-specific claim.

## Source verification

The immutable
[`alfworld/population_runs.parquet`](https://huggingface.co/datasets/toeunkim/matm-trajectories/blob/d84d6454fc5fcc337e2527533f484b79cf6f0872/alfworld/population_runs.parquet)
was downloaded to a temporary cache and not committed.

| Item | Verified value |
|---|---|
| Dataset revision | `d84d6454fc5fcc337e2527533f484b79cf6f0872` |
| Source SHA-256 | `626e2e6351d763739b0e2695a1bc442e1c851c1153c44301017739e3bd1155aa` |
| Source bytes | 4,237,969 |
| Rows / columns | 2,130 / 22 |
| Parquet | format 2.6; one row group; Arrow writer 23.0.1 |
| Dataset-card SHA-256 | `0d7fef0a97505a5fe9fb777d48324f50c9992c6e1ff024faf86ea080826e3634` |
| Declared license | Apache-2.0 |
| Analysis-code SHA-256 | `e92949186c3fcfadef21207a4856f45efe05c662f0221f4b5ce7a1ad3a4a9e48` |

The pinned [dataset card](https://huggingface.co/datasets/toeunkim/matm-trajectories/blob/d84d6454fc5fcc337e2527533f484b79cf6f0872/README.md)
describes the shard as ALFWorld evaluation runs from 34 consumer models and
documents reranked retrieval depths. The raw audit found:

- 355 unique tasks and 34 models;
- exactly six rows for every `(task_id, model)` pair;
- exactly one `no_retrieval` and one each of `rerank_{1,5,10,15,20}`;
- no duplicate treatment rows or pair-invariant violations;
- no trajectory JSON parse failures, empty trajectories, or step-count
  mismatches; and
- exact agreement among `success`, binary `final_score`, and `done`.

All 2,130 source records are represented in a deterministic source-record-set
hash. The adapter retains the complete source row and complete source step. It
does not fabricate separate tool-result spans because the source does not define
whether an observation in a step precedes or follows that step's action.

## Paired effects

The estimand is the within-`(task_id, model)` success-rate difference from
`no_retrieval`. The pair bootstrap resamples the 355 pair units. The more
conservative cluster bootstrap resamples the 34 models and retains every task
assigned to the sampled model. Exact `p` is a two-sided sign test on discordant
pairs. The five contrasts are descriptive and unadjusted for multiplicity.

| Arm | Success | Difference | Improved / worsened | Pair bootstrap 95% CI | Model-cluster 95% CI | Exact p |
|---|---:|---:|---:|---:|---:|---:|
| `no_retrieval` | 152/355 (42.82%) | reference | — | — | — | — |
| `rerank_1` | 155/355 (43.66%) | +0.85 pp | 19 / 16 | [-2.25, +4.23] pp | [-5.04, +5.65] pp | 0.736 |
| `rerank_5` | 150/355 (42.25%) | -0.56 pp | 12 / 14 | [-3.38, +2.25] pp | [-5.07, +2.84] pp | 0.845 |
| `rerank_10` | 151/355 (42.54%) | -0.28 pp | 16 / 17 | [-3.38, +2.82] pp | [-5.56, +3.93] pp | 1.000 |
| `rerank_15` | 149/355 (41.97%) | -0.85 pp | 18 / 21 | [-4.23, +2.54] pp | [-6.48, +4.21] pp | 0.749 |
| `rerank_20` | 154/355 (43.38%) | +0.56 pp | 19 / 17 | [-2.82, +3.94] pp | [-4.84, +4.78] pp | 0.868 |

The full result also records success and mean steps for every model × arm and
task-type × arm cell. These are intentionally exploratory: every task occurs
under exactly one model, so task and model effects are not separately
identified.

## Stability and heterogeneity

- 281/355 pairs (79.2%) had the same binary outcome in all six arms: 165 always
  failed and 116 always succeeded.
- Only 74/355 pairs changed outcome in any retrieval arm.
- 313 pairs had six distinct trajectory strings; 13 had exactly the same
  trajectory under all six labels.
- Depending on depth, only 17–19 treatment trajectories were byte-identical to
  their baseline trajectory.
- Mean step count varied only from 12.07 to 12.24 across arms.

This combination is important. Binary success is mostly stable even though the
generated paths usually differ. The paired outcome is therefore much less
sensitive than a trace-level process metric. Later reruns should evaluate
action efficiency, invalid-action loops, decisive failures, and whether
retrieved content was cited or acted on—not only final success.

## What can and cannot be concluded

Supported:

> Under the recorded MATM run conditions, changing the retrieval-depth label
> produced no reliable aggregate success difference in this 355-pair ALFWorld
> sample.

Not supported:

> Memory did not help, memory harmed a named model, a particular trace was good
> memory, or a memory should be consolidated into a skill.

The source records retrieval assignment but omits the retrieved item IDs,
content, rank scores, source lineage, prompt after injection, episode execution
seed, memory before/after state, and environment replay snapshot. Consequently:

1. the observed within-pair contrast is estimable;
2. a causal treatment effect is not identified from the released fields alone;
3. no effect is attributable to a specific memory; and
4. the failure cannot be separated among retrieval quality, prompt
   construction, context interference, model sensitivity, and run randomness.

The next useful experiment is not another analysis of this same Parquet file.
It is an instrumented rerun of the open MATM mechanism that records:

- query, candidate pool version, item IDs, scores, ranks, and selected content;
- the exact prompt segment and token budget produced by memory injection;
- environment build, initial state, task seed, model sampling parameters, and
  replay handle;
- per-step action/observation ordering and timestamps; and
- memory-use evidence, including citations, copied procedures, contradictions,
  and whether the selected memory changed the decisive action.

## Reproduce

```bash
python3 research/trace-intelligence/matm_pilot.py \
  --input /private/tmp/cache/matm-d84d6454/alfworld-population_runs.parquet \
  --output research/trace-intelligence/experiments/results/matm-alfworld-paired-pilot-2026-07-30.json

python3 -m unittest discover \
  -s research/trace-intelligence/tests \
  -p 'test_*.py'
```

The run uses 10,000 deterministic pair and model-cluster bootstrap replicates
with seed `20260730`. The committed aggregate result is
`matm-alfworld-paired-pilot-2026-07-30.json`; raw records, trajectories, goals,
and reasoning remain in the temporary cache.
