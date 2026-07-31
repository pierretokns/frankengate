# Skill-optimization paired meta-analysis

Analyzed `10` endpoint/study strata from committed aggregate receipts; raw model and trace content was not read.

| receipt | class | endpoint | tasks | baseline | candidate | risk difference | exact McNemar p | bootstrap 95% CI |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `experiments/results/natural-trace-skill-protocol-intervention-2026-07-30.json` | trace_mined_candidate | protocol | 6 | 3 | 3 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/natural-trace-skill-protocol-intervention-qwen3-4b-2026-07-31.json` | trace_mined_candidate | protocol | 6 | 6 | 3 | -0.5 | 0.25 | [-0.8333333333333334, -0.16666666666666666] |
| `experiments/results/defog-sql-factorial-fold0-terminal-only-p0-2026-07-30.json` | expert_seed_not_trace_mined | protocol | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-sql-factorial-fold0-terminal-only-p0-2026-07-30.json` | expert_seed_not_trace_mined | semantic | 4 | 2 | 2 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-car-fallback-llama-2026-07-31.json` | trace_mined_candidate | protocol | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-car-fallback-llama-2026-07-31.json` | trace_mined_candidate | semantic | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-broker-fallback-openai-llama-2026-07-31.json` | trace_mined_candidate | protocol | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-broker-fallback-openai-llama-2026-07-31.json` | trace_mined_candidate | semantic | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-trace-mined-skill-broker-fold0-llama-2026-07-31.json` | trace_mined_candidate | protocol | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |
| `experiments/results/defog-trace-mined-skill-broker-fold0-llama-2026-07-31.json` | trace_mined_candidate | semantic | 4 | 0 | 0 | 0.0 | 1.0 | [0.0, 0.0] |

The analysis does not pool protocol compliance with semantic correctness and does not authorize skill promotion. The causal claim remains unconfirmed until a larger family-disjoint, held-out semantic replay has independent security and outcome verification.
