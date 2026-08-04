# CMU trajectory access recheck (2026-08-01)

The authenticated Hugging Face account is now recognized and can read dataset
metadata for `cx-cmu/agent_trajectories` at revision
`88e2af82c116a9a57f29be6f21b9924da081c2bd`. A dry-run request for the non-data
`README.md` succeeds. A dry-run request for the pinned `tau2bench.parquet`
trajectory shard still returns: “Access denied. This repository requires
approval.”

Therefore metadata is admitted for planning, but raw trajectory access remains
quarantined. No CMU trajectory files were downloaded, and no CMU metrics or
enterprise claims are made.
