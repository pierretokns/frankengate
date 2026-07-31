# Cross-harness native-tool transfer (2026-07-31)

The identical six-episode, content-free fixture was run with Llama 3.2 through
two independent adapters: the OpenAI-compatible `/v1/chat/completions` path
and Ollama's native `/api/chat` path. Both adapters used the same frozen tool
schemas, seeds, prompt arms, executor, and terminal evaluator.

| harness | arm | terminal matches | terminal failures | mean latency |
| --- | --- | ---: | ---: | ---: |
| OpenAI-compatible | no skill | 3/6 | 3/6 | 1.25 s |
| OpenAI-compatible | formatting placebo | 3/6 | 3/6 | 1.07 s |
| OpenAI-compatible | trace-mined discipline | 3/6 | 3/6 | 1.21 s |
| Ollama native | no skill | 3/6 | 3/6 | 1.22 s |
| Ollama native | formatting placebo | 3/6 | 3/6 | 0.95 s |
| Ollama native | trace-mined discipline | 3/6 | 3/6 | 1.08 s |

The two harnesses agree exactly on terminal outcomes for all arms and are
within the same latency range on this fixture. This validates the adapter
normalization and shows no harness-specific skill effect here. It does **not**
validate semantic task quality, enterprise transfer, or long-term learning;
the fixture is synthetic and six episodes per arm are insufficient for a
general estimate.

Together with the Qwen model matrix, this gives a useful separation: the
candidate is stable across these two harnesses for Llama, but model-sensitive
and harmful for Qwen. Automatic skill promotion remains rejected.

Machine-readable aggregate: [`model-harness-transfer-llama-openai-vs-ollama-2026-07-31.json`](../results/model-harness-transfer-llama-openai-vs-ollama-2026-07-31.json).
