# ATIF × coding traces × RL environment round-trip study

**Status:** completed aggregate-only empirical schema-intersection run

## What was run

Frankengate canonical trajectories were projected into ATIF v1.7 and content-minimized OpenInference/OTel, then deterministically reimported. The unit is an exact capability-bearing fact that was actually present in the source adapter; absent fields are reported as `not_observed`, never as retained or lost.

## wisp_claude_code_tool_rich

88 trajectories and 17293 canonical events.

| Capability | Source facts | Canonical | ATIF profiled | OTel profiled |
|---|---:|---:|---:|---:|
| tool calls | 13254 | 100.0% | 100.0% | 83.3% |
| tool results | 11035 | 100.0% | 100.0% | 80.0% |
| branches | 5496 | 100.0% | 87.7% | 0.0% |
| retries | 0 | not observed | not observed | not observed |
| observations | 11035 | 100.0% | 100.0% | 80.0% |
| rewards | 0 | not observed | not observed | not observed |
| environment reset state | 0 | not observed | not observed | not observed |
| termination | 0 | not observed | not observed | not observed |
| authorization | 0 | not observed | not observed | not observed |
| time | 14643 | 100.0% | 46.2% | 100.0% |
| provenance | 48742 | 100.0% | 65.3% | 13.9% |
| replay identity | 48949 | 100.0% | 32.3% | 99.8% |

Fact-weighted exact retention: canonical 100.0%; ATIF profiled 61.7%; OpenInference/OTel profiled 64.6%.
Equal-weight observed-capability retention: canonical 100.0%; ATIF profiled 75.9%; OpenInference/OTel profiled 65.3%.

## matm_alfworld_rl_environment

2130 trajectories and 25885 canonical events.

| Capability | Source facts | Canonical | ATIF profiled | OTel profiled |
|---|---:|---:|---:|---:|
| tool calls | 0 | not observed | not observed | not observed |
| tool results | 0 | not observed | not observed | not observed |
| branches | 0 | not observed | not observed | not observed |
| retries | 0 | not observed | not observed | not observed |
| observations | 77655 | 100.0% | 0.0% | 33.3% |
| rewards | 56030 | 100.0% | 7.6% | 0.0% |
| environment reset state | 32275 | 100.0% | 0.0% | 0.0% |
| termination | 38665 | 100.0% | 16.5% | 0.0% |
| authorization | 0 | not observed | not observed | not observed |
| time | 0 | not observed | not observed | not observed |
| provenance | 34405 | 100.0% | 24.8% | 0.0% |
| replay identity | 77655 | 100.0% | 2.7% | 100.0% |

Fact-weighted exact retention: canonical 100.0%; ATIF profiled 6.7%; OpenInference/OTel profiled 32.7%.
Equal-weight observed-capability retention: canonical 100.0%; ATIF profiled 8.6%; OpenInference/OTel profiled 22.2%.

## Findings

In the tool-rich coding family, profiled ATIF retained 100% of measured tool-call, tool-result, and observation facts, but only 46.2% of time facts and 32.3% of replay-identity facts. Profiled OTel retained 100% of normalized time and 99.8% of replay identity, while payload omission reduced tool-call and tool-result retention to 83.3% and 80.0%.

In the RL family, profiled OTel retained 100% of replay identity yet 0% of reward, environment/reset-state, and termination facts. This is direct evidence that span identity is not environment replay. Profiled ATIF retained only 2.7% of replay identity and 0% of environment/reset-state facts.

Neither admitted family exposed governance authorization or explicit retry facts. Those cells are `not_observed`; this experiment makes no preservation claim for either construct.

## Interpretation

The numbers are profiled round-trip ceilings, not portable-core guarantees. ATIF event identity and non-native metadata rely on `extra.frankengate`; the OTel import relies on Frankengate canonical attributes. Neither projection becomes an evidence authority.

The fact-weighted overall number is a microaverage dominated by capabilities with many canonical fields. The table and equal-weight observed-capability average are the appropriate construct-level readout.

Most importantly, preserving event identity does not restore RL replay state. The pinned MATM shard explicitly lacks an environment seed and replay snapshot; the study therefore cannot claim reset-equivalent replay in any arm.

## Source pins

- [Harbor ATIF v1.7](https://github.com/harbor-framework/harbor/blob/f5e9d0b71ac4493a4f0620653e2913aee7fc0767/rfcs/0001-trajectory-format.md)
- [OpenInference v0.1.30](https://github.com/Arize-ai/openinference/tree/789d41974c08a9a13147977f28ef4142a07e2106)
- [OpenTelemetry semantic conventions v1.43.0](https://github.com/open-telemetry/semantic-conventions/tree/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d)
- [OpenTelemetry GenAI pre-release conventions](https://github.com/open-telemetry/semantic-conventions-genai/tree/434c91dcc34ed038e3048c07720ddfed2c6bddfc)
- [Wisp Claude Code sessions](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce)
- [MATM trajectories](https://huggingface.co/datasets/toeunkim/matm-trajectories/tree/d84d6454fc5fcc337e2527533f484b79cf6f0872)

## Claim boundaries

- Retention is exact equality of adapter-observed canonical facts; it is not downstream task utility.
- The profiled round trips use Frankengate extensions or attributes; portable third-party readers may discard them.
- The Wisp family is one public contributor and the MATM family is benchmark-generated ALFWorld, not enterprise prevalence.
- MATM lacks environment seed and replay snapshot, so no format can prove reset-equivalent replay from this source.
- Authorization facts absent from these sources cannot validate authorization preservation; synthetic governed fixtures cover that construct separately.
