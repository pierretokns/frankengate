# Real-user candidate artifact miner (2026-08-05)

The licensed 549-session DataClaw history was mined into a content-free review
registry. Harness-management tools (`TaskUpdate`, `TodoWrite`, plan controls,
and similar orchestration calls) were excluded so they could not masquerade as
reusable work artifacts.

- 100 hashed non-management tool/action candidates were retained.
- 63/100 recur across at least two project labels.
- The candidates are primarily `Bash`, `Read`, and `Edit` actions.
- Every candidate has `review_required=true` and `promotion_eligible=false`.
- Nearby broad friction-language counts are attached as review prioritization,
  not correctness or failure labels.

This makes trace-to-artifact mining operationally concrete while preserving the
critical boundary: repetition is not validation. The next review step must
sample candidates, reconstruct task and authority context, execute them in a
sealed changed environment, and attach independent semantic/security outcomes.

Receipt and verifier:
`experiments/results/dataclaw-candidate-artifact-miner-2026-08-05.json`.
No command, prompt, path, argument, or identifier value is emitted; candidate
IDs are content hashes.
