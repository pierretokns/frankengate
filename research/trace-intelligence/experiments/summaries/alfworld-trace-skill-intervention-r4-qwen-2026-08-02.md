# ALFWorld Qwen cross-model harness probe (r4)

Qwen 3 4B was run on the same four held-out task paths used by the Llama family-disjoint replay, using the native Ollama API and no-skill versus the revised trace-derived procedure. The 12-step cap makes this a runtime/protocol probe rather than a fair semantic success benchmark.

Both arms had zero wins. The trace-derived candidate emitted 36 invalid actions versus 48 for no-skill and had similar mean episode latency (11.39s versus 11.62s). Because the cap was below the expert solution length for several task families, this does not establish a quality improvement; it only shows that the candidate changed protocol validity on this model/harness.

Receipt: `experiments/results/alfworld-trace-skill-intervention-r4-qwen-2026-08-02.json`.
