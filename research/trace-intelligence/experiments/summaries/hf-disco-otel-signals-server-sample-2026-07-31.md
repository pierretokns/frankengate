# Signals selector on bounded dataset-server sample (2026-07-31)

To avoid another large shard download, the HF dataset-server API supplied 20
rows at offset 920 from the pinned revision: 19 `swebench/tool_calling` rows
and one `tau2_airline/claude_code` row. At a 4-row budget, both the error/tool
selector and trace-length selector reached precision 1.0 and recall 0.364;
the seeded random draw reached precision 0.5 and recall 0.182 (random mean
precision 0.551 over 1,000 draws).

This is a bounded mixed-stratum smoke, not a representative sample: the API
response was kept outside the repository, the result contains no raw content,
and the label remains only OTel ERROR status. The tie with length is evidence
against claiming that Signals is uniquely useful on this slice.

See [`hf-disco-otel-signals-server-sample-2026-07-31.json`](../results/hf-disco-otel-signals-server-sample-2026-07-31.json).
