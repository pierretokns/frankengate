# ALFWorld trace-skill plus working-memory composition (r6)

This composition test added a bounded working-memory layer—the last eight executed admissible actions—to the revised trace-derived procedure. The current observation and admissible-action list remained unchanged, and the memory contained no future outcomes or hidden labels.

Across the same four held-out task families, Llama 3.2 through both Ollama harnesses produced zero wins. The base trace procedure emitted 84 invalid actions per harness; adding working memory emitted 100 per harness. The composition therefore worsened protocol validity and did not improve task success.

The expert solved all four tasks within the 35-step budget, so this is a valid small semantic composition comparison. The combined arm is rejected and remains non-promotable.

Receipt: `experiments/results/alfworld-trace-skill-memory-composition-r6-2026-08-02.json`.
