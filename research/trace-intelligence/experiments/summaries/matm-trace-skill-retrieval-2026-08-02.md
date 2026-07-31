# MATM outcome-conditioned trace procedure retrieval

This is an offline leave-one-model-out recommendation study over the pinned MATM ALFWorld shard. It does not rerun an agent or claim causal skill improvement.

- Dataset rows: 2130; held-out model folds: 34; k=8.
- Features: goal tokens and normalized action templates; task outcomes are never available to the held-out query, only to training candidates.

| Method | mean AUC | mean Brier | mean accuracy | top-10% success rate |
| --- | ---: | ---: | ---: | ---: |
| all-trace neighbor | 0.721 | 0.248 | 0.673 | 0.681 |
| outcome-conditioned successful neighbor | 0.665 | 0.243 | 0.531 | 0.747 |
| task-type prior | 0.663 | 0.239 | 0.618 | 0.584 |

The successful-neighbor recommendation precision lift over the all-trace neighbor at the top 10% cutoff was 0.067 (bootstrap 95% CI -0.020 to 0.166); its mean AUC contrast was -0.056 (95% CI -0.112 to 0.002). These are recommendation metrics, not changed-agent outcomes.
The successful-neighbor arm tests whether outcome-conditioned traces identify a useful procedure candidate for an unseen model. A positive predictive result is not an intervention effect: the agent was not rerun with the candidate, and no skill is releasable from this study.

Machine-readable receipt: `experiments/results/matm-trace-skill-retrieval-2026-08-02.json`.
