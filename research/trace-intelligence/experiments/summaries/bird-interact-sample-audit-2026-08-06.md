# BIRD-Interact public ADK sample audit (2026-08-06)

The public BIRD-Interact repository includes ten `a-interact` and ten
`c-interact` sample episodes with trajectories, phase outcomes, follow-up
flags, and rewards. This is a schema/reproducibility check only; it is not the
600-task benchmark.

| Mode | Samples | Phase-1 pass | Phase-2 pass | Mean reward | Trajectory length |
|---|---:|---:|---:|---:|---:|
| a-interact | 10 | 5/10 | 3/10 | 0.44 | 12–17 records |
| c-interact | 10 | 5/10 | 4/10 | 0.52 | 3–6 records |

All 20 examples include a follow-up. The agentic samples include an explicit
budget field; the conversational samples do not. The examples therefore prove
that the public schema can carry clarification questions, tool/dialogue
trajectories, phase outcomes, and reward receipts.

They do **not** establish a method effect: the sample is tiny, curated, uses
one model configuration, and is not a randomized intervention. It also cannot
replace the withheld gold SQL/test bundle for the full 600-task cohort.

Receipt: [`bird-interact-sample-audit-2026-08-06.json`](../results/bird-interact-sample-audit-2026-08-06.json)

Verifier result hash: `055ab84bfa363c5b26d92abec740482fe29a79d04e707a73a7580a2910ad5db5`.

The cloned public evaluator is retained only in `/private/tmp`; no raw sample
content was committed.
