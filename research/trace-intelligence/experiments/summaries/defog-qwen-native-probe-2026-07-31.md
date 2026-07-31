# Qwen native governed SQL probe (2026-07-31)

One pinned car-dealership task was run through the native Ollama `/api/chat`
adapter with Qwen3 4B, under the constrained PostgreSQL role and the same
no-skill, formatting-placebo, and trace-mined arms. Every run validated the
current authority epoch and produced zero unauthorized observations.

The model emitted zero SQL tool calls in all three arms. The deterministic
terminal controller therefore abstained in all three cases. There is no
semantic answer to score, so this is a typed model/runtime null, not a quality
result and not evidence against trace-derived skills.

This probe closes the local adapter question: switching from the
OpenAI-compatible endpoint to Ollama's native endpoint does not make Qwen
domain prompts evaluable. The next useful quality experiment requires a
domain-capable model/runtime or a separately validated SQL solver, with solver
and evaluator authority kept isolated.

Machine-readable result: [`defog-qwen-native-probe-2026-07-31.json`](../results/defog-qwen-native-probe-2026-07-31.json).
