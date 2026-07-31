# Ollama Llama 3.2 native-tool control

The governed synthetic native-tool matrix was run against the local Ollama
`llama3.2:latest` model: 18 episodes across three protocol variants. Each
variant matched the expected terminal action on 3/6 episodes and failed with a
text-only response on the other 3/6. Remaining-budget annotations and
terminal-only tool availability did not change the result.

This is a real new-model/tool-loop execution, but only a protocol control. It
does not estimate SQL quality, skill benefit, or enterprise transfer. A Qwen3
4B attempt was also made but exceeded the 60-second per-call boundary because
its reasoning output was not disabled by the OpenAI-compatible endpoint; that
attempt is retained as an external typed-null diagnostic, not a partial result.

Receipt: `experiments/results/native-tool-protocol-ollama-llama32-2026-07-30.json`.
