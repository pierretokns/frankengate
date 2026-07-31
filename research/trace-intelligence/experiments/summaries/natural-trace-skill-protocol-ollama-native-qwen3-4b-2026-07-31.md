# Qwen3 4B native-Ollama skill-protocol replication

This run replayed the frozen six-episode, content-free native-tool fixture
through Ollama's native `/api/chat` adapter with Qwen3 4B. It used the same
no-skill, formatting-placebo, and trace-mined-terminal-discipline arms as the
existing model/harness matrix.

| arm | episodes | native tool calls | terminal matches | terminal failures |
| --- | ---: | ---: | ---: | ---: |
| no-skill | 6 | 0 | 0/6 | 6/6 |
| formatting placebo | 6 | 0 | 0/6 | 6/6 |
| trace-mined discipline | 6 | 0 | 0/6 | 6/6 |

All 18 episodes completed, but the model emitted no tool calls. This is a typed
model/harness protocol null, not a semantic task result and not evidence for or
against trace-derived skill improvement. The receipt is included in the paired
skill meta-analysis as one additional protocol stratum.

Machine-readable receipt: [`natural-trace-skill-protocol-ollama-native-qwen3-4b-2026-07-31.json`](../results/natural-trace-skill-protocol-ollama-native-qwen3-4b-2026-07-31.json).
