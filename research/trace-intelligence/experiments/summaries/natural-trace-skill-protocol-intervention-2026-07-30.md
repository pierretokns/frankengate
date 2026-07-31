# Natural-trace skill protocol intervention: local model

This is the first executed skill-arm matrix after the NatureBench preflight.
It uses the frozen synthetic native-tool fixture (six episodes, three paired
arms) and the local Ollama `llama3.2:latest` model. The fixture contains no
benchmark questions, SQL data, hidden labels, or enterprise content.

| Arm | Expected terminal match | Terminal failures | Tool calls |
| --- | ---: | ---: | ---: |
| No skill | 3/6 (0.50) | 3/6 (0.50) | 18 |
| Formatting placebo | 3/6 (0.50) | 3/6 (0.50) | 21 |
| Trace-mined terminal discipline | 3/6 (0.50) | 3/6 (0.50) | 18 |

All failures were `text_without_terminal_tool`. The trace-mined procedure did
not improve terminal compliance over either control, and the placebo changed
tool-call count without changing the endpoint. This is a reproducible null for
this model, prompt, synthetic tool loop, and six-episode sample—not evidence
that trace-derived skills are universally ineffective.

The run did execute real model tool calls against a governed synthetic
executor. Raw request/response/tool records remain in disposable storage; the
committed result contains hashes and aggregate counts only.

## Claim boundary

This measures protocol sensitivity only. It does not measure SQL quality,
semantic correctness, benchmark performance, enterprise transfer, or natural
trace skill benefit. The next decisive experiment remains a family-disjoint
replay with a domain-valid mined skill and independent outcome verifier.

Result: `experiments/results/natural-trace-skill-protocol-intervention-2026-07-30.json`.
