# Second-harness family-disjoint ALFWorld replay (r11)

The same eight previously unused ALFWorld paths from r9 were replayed with
Llama 3.2 through Ollama's OpenAI-compatible `/v1/chat/completions` endpoint.
The expert horizon remained sufficient for all paths.

Both no-skill and trace-mined arms achieved `0/8` wins. The baseline emitted
zero invalid actions; the trace-derived procedure emitted 66. Mean episode
latency was 4.51s for baseline and 8.52s for the candidate. The result matches
the native-harness direction: the candidate changes protocol behavior without
improving task success. Aggregate projection verification passed; independent
semantic/security recomputation is still required before promotion.

Receipt: `experiments/results/alfworld-family-disjoint-powered-r11-openai-llama-2026-08-02.json`.
