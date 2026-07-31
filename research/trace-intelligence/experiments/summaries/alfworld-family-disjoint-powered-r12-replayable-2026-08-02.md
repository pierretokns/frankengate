# Independently replayable family-disjoint ALFWorld intervention (r12)

The eight-task cohort was rerun with the same two local harnesses and with only
the executed environment actions retained in the external raw receipt. Llama
3.2 produced `0/8` wins for both no-skill and trace-mined arms in both harnesses;
the candidate emitted 66 invalid actions per harness versus 0 for baseline.

A separate verifier loaded the pinned ALFWorld environment, resolved task hashes,
replayed all 32 action sequences in fresh environments, and recomputed terminal
outcomes and step counts. All 32 rows matched with zero mismatches. This closes
the independent task-outcome recomputation gate for this cohort, but it is not a
security/authorization verifier and remains a negative skill result.

Receipts: `experiments/results/alfworld-family-disjoint-powered-r12-replayable-2026-08-02.json` and
`experiments/results/alfworld-family-disjoint-powered-r12-semantic-verification-2026-08-02.json`.
