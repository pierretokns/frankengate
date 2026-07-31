# ALFWorld fair-horizon Qwen semantic comparison (r5)

The Qwen 3 4B replay used the same four held-out task paths as the Llama family-disjoint experiment, but increased the action budget to 35 steps. A hand-coded expert independently solved all four tasks in 7, 20, 8, and 11 steps, so the horizon covered every task.

Qwen no-skill and the revised trace-derived procedure both produced 0/4 wins. The candidate emitted 105 invalid actions versus 140 for no-skill and had nearly identical mean latency (32.58s versus 32.45s per episode). This is a valid small semantic comparison: the candidate improved protocol validity but did not improve task success.

The result is not a powered causal estimate and does not authorize promotion. It is the first cross-model replay in this family split with an independently verified sufficient horizon.

Receipt: `experiments/results/alfworld-trace-skill-intervention-r5-qwen-2026-08-02.json`.
