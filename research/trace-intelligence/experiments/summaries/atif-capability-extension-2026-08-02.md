# Frankengate ATIF capability-extension empirical run

The extension was run against the pinned Wisp coding sessions and MATM ALFWorld trajectories. It retains structural control facts in a namespaced profile and explicitly omits payload/state content.

| Family | Trajectories | Round trips | Failures | Overall structural retention | Omitted fields |
|---|---:|---:|---:|---:|---:|
| wisp_claude_code_tool_rich | 88 | 88 | 0 | 91.7% | 105173 |
| matm_alfworld_rl_environment | 2130 | 2130 | 0 | 87.8% | 66680 |

The extension repairs the schema boundary only for consumers that implement the profile. Generic ATIF readers still see the portable subset and cannot use the extension-only facts.

No raw prompts, tool arguments, state snapshots, identifiers, or exception text are emitted.

- A profile-aware round trip is not a portable ATIF guarantee.
- Retention is exact structural fact equality, not task utility or replay equivalence.
- MATM does not contain environment seed/replay snapshots, so no format can create that evidence.
- Wisp and MATM are not enterprise traces; consented multi-user validation remains open.
