# DiscoPosse OTel shard audit (2026-07-31)

The first bounded execution against the pinned DiscoPosse revision used one
external-cache Parquet shard (`train-00000-of-00039.parquet`, 24,144,062 bytes).
Only aggregate fields were retained; prompts, tool arguments, tool outputs,
messages, and session identifiers were not emitted.

| Measure | Result |
|---|---:|
| Rows | 46 |
| OTel spans | 925 |
| Complete timestamp spans | 925 |
| Tool-related spans | 917 |
| Spans with OTel ERROR status | 52 |
| Rows with input messages | 925 |
| Rows with output messages | 873 |
| Rows with tool definitions | 917 |
| Harness/benchmark stratum | `claude_code` / `appworld` |

This establishes that the pinned source contains sufficiently rich nested OTel
spans for a real projection and tool-correlation adapter. It does **not** yet
measure ATIF retention, diagnosis quality, memory utility, skill improvement, or
enterprise behavior. The shard is one harness/benchmark stratum, and the source
is benchmark telemetry rather than volunteered enterprise history. The next
step is a deterministic OTel-to-canonical projection with an explicit loss
receipt, followed by the same Signals/AgentRx/AgentEvals selection comparisons
used on the existing cohorts.

Result JSON: [`hf-disco-otel-shard-audit-2026-07-31.json`](../results/hf-disco-otel-shard-audit-2026-07-31.json).
