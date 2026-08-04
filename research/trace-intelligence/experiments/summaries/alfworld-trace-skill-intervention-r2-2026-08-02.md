# ALFWorld trace-skill intervention revision (r2)

The first intervention mixed a long procedure into the user turn and caused invalid actions. This revision shortened the candidate and moved it into the system contract while leaving the observation and admissible-action list unchanged.

The candidate still did not improve task success. On the held-out look task it produced zero wins and zero invalid actions in both Ollama API surfaces, matching the no-skill arm's zero wins. On the held-out pick-and-place task it produced zero wins and 28 invalid actions in each API surface. The revision therefore does not support the hypothesis that prompt placement alone explained the first failure.

This is a diagnostic, unpowered slice: six episodes, one model, two task families, and unequal action budgets. It confirms that the current trace-derived candidate is not promotable and that a skill gate needs family-disjoint evaluation, action-validity checks, and an independent verifier before release.

Receipt: `experiments/results/alfworld-trace-skill-intervention-r2-2026-08-02.json`.
