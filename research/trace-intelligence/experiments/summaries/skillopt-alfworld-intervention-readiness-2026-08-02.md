# SkillOpt/ALFWorld causal-intervention readiness

The latest SkillOpt checkout is present and pinned (`7da46ae`, MIT), but the local assets are not sufficient for a causal replay.

- The checkout contains a path manifest with 39 train, 18 validation, and 134 test IDs, plus adapters, prompts, and seed skills.
- It does **not** contain the ALFWorld game payload required by the adapter to reset and replay an environment.
- The MATM trajectory shard has outcomes and action histories but no independent environment seed or replay snapshot.
- The attested Qwen3.5-9B-OptiQ snapshot exists, but starting `/opt/homebrew/bin/mlx_lm.server` failed during MLX/Metal device initialization in this execution environment. No model response or task episode was emitted.

This is a typed runtime/data null, not a quality result. It prevents us from claiming a causal ALFWorld skill gain. The next executable gate requires the exact game payload and a working attested model runtime, followed by no-skill/placebo/trace-derived/SkillOpt/SkillGen/RHO arms on family-disjoint held-out tasks.

Machine-readable receipt: `experiments/results/skillopt-alfworld-intervention-readiness-2026-08-02.json`.
