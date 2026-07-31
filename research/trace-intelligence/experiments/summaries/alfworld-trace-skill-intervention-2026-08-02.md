# Bounded ALFWorld trace-derived skill intervention

This is the first environment-backed semantic intervention in the program. The pinned public `zhangdw/alfworld` archive was materialized and the TextWorld PDDL environment was independently reset. The hand-coded expert solved both held-out `valid_unseen` tasks (7 and 20 steps), proving that the task payload and evaluator are live.

The experiment compared `no_skill`, a formatting-only placebo, and a procedure candidate mined from successful action templates. It ran 18 episodes:

| model / harness | no-skill wins | trace-procedure wins | trace invalid actions | notes |
| --- | ---: | ---: | ---: | --- |
| Llama 3.2 / Ollama native | 0/2 | 0/2 | 36 | 20-step budget |
| Llama 3.2 / OpenAI-compatible | 0/2 | 0/2 | 36 | same task paths and budget |
| Qwen3 4B / Ollama native | 0/2 | 0/2 | 6 | typed 3-step budget due latency |

The trace-derived procedure did not improve performance and increased invalid actions for Llama. This is negative causal evidence for this candidate on this tiny slice, not evidence that trace-derived skills never work. The Qwen arm is a bounded runtime probe rather than a full quality estimate. No candidate is releasable.

Machine-readable receipt: `experiments/results/alfworld-trace-skill-intervention-2026-08-02.json`.
