# Native-tool model transfer matrix (2026-07-31)

This matrix replays the identical six-episode, content-free native-tool
fixture and the same three intervention arms on two local models through the
same OpenAI-compatible native-tool harness. It compares protocol compliance and
latency only; it is not a SQL-quality or enterprise-outcome benchmark.

| model | arm | terminal matches | terminal failures | mean latency |
| --- | --- | ---: | ---: | ---: |
| Llama 3.2 | no skill | 3/6 | 3/6 | 1.25 s |
| Llama 3.2 | formatting placebo | 3/6 | 3/6 | 1.07 s |
| Llama 3.2 | trace-mined discipline | 3/6 | 3/6 | 1.21 s |
| Qwen3 4B | no skill | 6/6 | 0/6 | 39.59 s |
| Qwen3 4B | formatting placebo | 0/6 | 6/6 | 42.04 s |
| Qwen3 4B | trace-mined discipline | 3/6 | 3/6 | 47.34 s |

The same candidate therefore has model-dependent behavior: it is neutral on
Llama's 3/6 baseline and reduces Qwen's perfect no-skill protocol compliance to
3/6, while adding roughly 20–38 times the latency. The formatting placebo is
also unstable on Qwen (0/6), showing that prompt additions alone can change the
tool protocol substantially. These results reject automatic skill promotion;
they do not show that the candidate is universally harmful because the fixture
is synthetic and only six episodes per arm were run.

This is a **same-harness, two-model transfer result**, not a cross-harness
result. The next experiment must use family-disjoint held-out tasks, an
independent semantic/security verifier, and at least two real harness
implementations before any skill benefit or transfer claim is possible.

Machine-readable aggregate: [`model-harness-transfer-native-tool-2026-07-31.json`](../results/model-harness-transfer-native-tool-2026-07-31.json).
