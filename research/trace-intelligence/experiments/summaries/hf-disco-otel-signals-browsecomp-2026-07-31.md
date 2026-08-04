# Signals selector on DiscoPosse BrowseCompPlus shard (2026-07-31)

The same frozen selector was run unchanged on a second 46-row shard from the
same pinned revision. This shard is `browsecompplus` rather than `appworld`.
It contains zero OTel spans with `status.code == ERROR`, so every selector arm
has zero precision and recall at the 9-row review budget.

This is a useful negative control: the appworld result must not be generalized
to all benchmarks, and OTel error status is an outcome proxy whose prevalence
depends on the workload and instrumentation. The result does not say that the
traces are successful in a human or task-correctness sense; it says only that
this status field contains no errors in this shard.

See [`hf-disco-otel-signals-browsecomp-2026-07-31.json`](../results/hf-disco-otel-signals-browsecomp-2026-07-31.json).
