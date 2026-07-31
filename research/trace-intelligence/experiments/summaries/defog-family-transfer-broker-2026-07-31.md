# Governed broker family-transfer pilot (2026-07-31)

This pilot used four pinned broker tasks from the held-out fold, a disposable
PostgreSQL database loaded from the pinned Defog broker fixture, and the
constrained `NOSUPERUSER NOBYPASSRLS` runner. The same no-skill,
formatting-placebo, and trace-mined-terminal-discipline arms were run through
both the OpenAI-compatible and Ollama-native model adapters with Llama 3.2.

All 24 harness/task/arm runs carried a valid authorization epoch and produced
zero unauthorized observations. However, every arm in both harnesses failed to
make a terminal submission:

| harness | arm | terminal submissions | semantic answers | successful SQL attempts |
| --- | --- | ---: | ---: | ---: |
| OpenAI-compatible | no skill | 0/4 | 0/4 | 0 |
| OpenAI-compatible | formatting placebo | 0/4 | 0/4 | 0 |
| OpenAI-compatible | trace-mined discipline | 0/4 | 0/4 | 0 |
| Ollama native | no skill | 0/4 | 0/4 | 0 |
| Ollama native | formatting placebo | 0/4 | 0/4 | 0 |
| Ollama native | trace-mined discipline | 0/4 | 0/4 | 0 |

The trace-mined arm made more SQL attempts than the controls but did not reach
the evaluator. This is a genuine family-transfer execution and authorization
receipt, but it is a **protocol-null**, not a semantic skill result. It shows
that the current Llama SQL runner cannot support a fair skill-quality estimate
on this held-out family. The Qwen version timed out before completing its first
arm and is retained as a typed runtime null, not silently excluded.

The next domain gate is to repair or replace the model/tool protocol, rerun the
same sealed broker fold, and require independent semantic and security verdicts
before comparing trace-mined, expert, SkillOpt, SkillGen, and RHO proposals.

Machine-readable aggregate: [`defog-family-transfer-broker-llama-2026-07-31.json`](../results/defog-family-transfer-broker-llama-2026-07-31.json).
