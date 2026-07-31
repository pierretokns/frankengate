# Larger family-disjoint ALFWorld trace-skill replay (r9)

The revised trace-derived procedure was evaluated on eight previously unused
`valid_unseen` paths: two each from look-at-light, simple placement, clean-then-place,
and heat-then-place. An environment-provided expert plan solved all eight within
the 35-step horizon before model evaluation. Both Llama 3.2 and Qwen 3 4B used the
same Ollama-native endpoint and the same task paths.

Both models achieved `0/8` wins for both no-skill and trace-mined arms. Llama's
baseline emitted zero invalid actions versus 66 for the candidate. Qwen's
baseline emitted 280 invalid actions versus 140 for the candidate. Thus the
candidate changed protocol validity in opposite directions by model, but did not
improve task success. This is a larger family-disjoint negative replication, not
a universal claim that trace-derived skills cannot work.

Receipt: `experiments/results/alfworld-family-disjoint-powered-r9-2026-08-02.json`.
