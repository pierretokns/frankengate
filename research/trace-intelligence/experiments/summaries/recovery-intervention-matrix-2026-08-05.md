# Recovery intervention matrix preflight (2026-08-05)

The exact 62-task Recovery-Bench failure set is now frozen as a paired
five-arm design:

1. no context;
2. full failed trajectory;
3. structured summary;
4. reviewed/diagnosed skill;
5. formatting placebo.

Every arm carries the same task-set and task-checksum hashes, and the
preflight rejects duplicate task identities or missing trajectory metadata.
The design requires a separate task-disjoint confirmation set before any
promotion claim. Required outcomes are verifier reward, repair regression,
first-attempt success, tool calls, latency, model cost, and false semantic
acceptance.

Receipt:
[`recovery-bench-intervention-matrix-2026-08-05.json`](../manifests/recovery-bench-intervention-matrix-2026-08-05.json).

This is a fairness and reproducibility gate only. Harbor/model execution has
not run, so it establishes no recovery or skill-transfer outcome.

