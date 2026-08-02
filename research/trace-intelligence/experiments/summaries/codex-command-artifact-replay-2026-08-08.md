# Retrospective command-artifact reuse audit (2026-08-08)

## Question

When a command template has previously succeeded in a project, does that
history predict later success strongly enough to justify treating it as a
reusable artifact? This tests the mechanics of artifact validation using real
local Codex tool calls and explicit process-exit outcomes, without inferring
user intent and without executing logged commands.

## Protocol

- 622 current Codex rollout files, ordered by rollout timestamp.
- Correlate each `function_call`/`custom_tool_call` with its matching output.
- Admit only outputs containing an explicit process exit code (`0` or nonzero).
- Normalize command templates by redacting absolute paths, UUIDs, long values,
  and numeric values; retain only a hash of the normalized template.
- Hash the observed working-directory scope and session; raw commands,
  arguments, outputs, and paths remain external.
- Compare later occurrences after a prior success in the same scope, and a
  later occurrence in a different scope after a success elsewhere.

## Result

| Measure | Count / rate |
|---|---:|
| Labeled command occurrences | 36,549 |
| Successful / failed occurrences | 34,605 / 1,944 |
| Distinct normalized command artifacts | 22,247 |
| Distinct project scopes | 4 |
| Same-scope repeats after prior success | 13,797 |
| Same-scope later success / failure | 13,395 / 402 (**97.09% / 2.91%**) |
| Other-scope reuse later success / failure | 114 / 17 (**87.02% / 12.98%**) |
| Overall success rate | **94.68%** |

The same-scope repeat rate is **+2.41 percentage points** above the overall
baseline. Cross-scope reuse is **−7.66 points** below baseline, a concrete
negative-transfer warning.

## Interpretation

This is the strongest local evidence so far for a useful artifact-learning
primitive, but it is not proof that the command is semantically appropriate:

1. A previously successful command is a good *operational prior* within the
   same project scope.
2. The same template transfers poorly across scopes, even when it succeeded
   elsewhere. Scope must therefore be part of artifact identity and retrieval.
3. The normalization intentionally collapses values and may merge commands that
   are not semantically equivalent. It is a candidate-template audit, not safe
   automatic replay.
4. Process exit is an independent execution signal, not a user-success label;
   a command can exit zero while solving the wrong task.

**Disposition:** retain scope-bound command artifacts with explicit outcome,
provenance, expiry, and replay checks. Do not promote cross-scope reuse from
this result. The next experiment should join artifact templates to blinded
intent labels and changed-environment outcomes.

## Receipt and code

- [content-free receipt](../results/codex-command-artifact-replay-2026-08-08.json)
- [`codex_command_artifact_replay_audit.py`](../../codex_command_artifact_replay_audit.py)
- [`test_codex_command_artifact_replay_audit.py`](../../tests/test_codex_command_artifact_replay_audit.py)

