# ALFWorld family-disjoint trace-skill replay (r3)

The revised trace-derived action discipline was replayed against four held-out `valid_unseen` task families: looking at an object in a light, simple placement, cleaning then placement, and heating then placement. Llama 3.2 was tested through both Ollama native and OpenAI-compatible endpoints, with a no-skill control, a 30-step cap, and the same task paths for every arm.

All 16 episodes exhausted the action budget without a win. The no-skill control produced zero invalid actions in either harness; the trace-derived candidate produced 84 invalid actions per harness. Mean latency was 3.81–3.83 seconds per no-skill episode and 5.86–5.97 seconds per candidate episode.

This is stronger negative transfer evidence against the current candidate, not proof that trace-derived skills can never work. The candidate remains proposal-only. A powered study still needs more models, more family-disjoint tasks, sealed independent labels, and a preregistered regression floor.

Receipt: `experiments/results/alfworld-trace-skill-intervention-r3-2026-08-02.json`.
