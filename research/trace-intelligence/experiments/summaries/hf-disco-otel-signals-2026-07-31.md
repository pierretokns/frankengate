# Signals-style selector on DiscoPosse OTel shard (2026-07-31)

At a fixed 20% review budget (9 of 46 rows), a deterministic selector using
error status plus tool-related span count selected 9/9 error-bearing rows:

| Arm | Precision | Recall |
|---|---:|---:|
| Error + tool signals | 1.00 | 0.375 |
| Trace length | 0.333 | 0.125 |
| Seeded random draw | 0.444 | 0.167 |
| Random mean over 1,000 draws | 0.518 | — |

The label is only `status.code == ERROR`; it is not a human informative-trace
label, a root-cause label, or an outcome label. The result supports using cheap
signals to prioritize review of likely failures in this shard. It does not
support diagnosis, skill inference, enterprise comparisons, or automatic eval
promotion. A larger multi-benchmark run and blinded human labels are required.

No raw content was emitted. See
[`hf-disco-otel-signals-2026-07-31.json`](../results/hf-disco-otel-signals-2026-07-31.json).
