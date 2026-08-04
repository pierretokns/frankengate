# Recovery context-fidelity audit (2026-08-05)

This is a representation/mechanics experiment over the 62 frozen
Recovery-Bench failures. It does **not** run Harbor, a recovery agent, or a
changed-system verifier. The purpose is to quantify the tradeoff between a
full failed trajectory and the deterministic structural summary proposed for
candidate triage.

## Result

| measure | value |
|---|---:|
| failure trajectories present | 62 / 62 |
| mean full trajectory payload | 122,619.23 bytes |
| mean structural summary | 149.06 bytes |
| median summary/full ratio | 0.001585 |
| p95 summary/full ratio | 0.007577 |
| deterministic structural facts retained | 100% |
| command-level repair text retained | no |

The summary retains step/tool/observation counts, dominant tool family,
error flags, and task-completion signal exactly as defined by the extractor.
It deliberately omits command text, arguments, observations, and the causal
sequence needed to replay a repair. This makes it a cheap bounded-context
screen, not a replacement for full trajectory evidence.

Receipt:
[`recovery-context-fidelity-2026-08-05.json`](../results/recovery-context-fidelity-2026-08-05.json)

## Claim boundary

This result supports only the storage/context-sizing decision: summaries can
be used for triage and routing with a large compression ratio. It says
nothing about recovery success, skill transfer, or whether a summary beats a
full trajectory. Those require the pre-registered paired Harbor intervention
matrix and verifier outcomes. Docker/Harbor was unavailable in this
environment, so no recovery outcome is claimed.
