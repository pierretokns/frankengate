# ReasoningBank LOCOMO bounded attempt

The pinned upstream RHO/ReasoningBank runner was invoked on the independent
LOCOMO benchmark with two train tasks and two frozen held-out tasks. The local
embedding model downloaded successfully, but the upstream memory judge selected
its Azure Foundry client and attempted to execute `az`; the machine has no
`az` binary. The run therefore stopped before trajectory extraction, memory
construction, or held-out scoring.

This is classified as **provider unavailable**, not as a memory-quality result.
The exact typed receipt is
[`reasoningbank-locomo-bounded-2026-08-02.json`](../results/reasoningbank-locomo-bounded-2026-08-02.json).
