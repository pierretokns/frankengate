# Frozen chronological artifact-drift benchmark (2026-08-09)

## Question

Does an artifact that succeeded in the first chronological half of a real
Claude Code history remain predictive in the second half? This is a stricter
test than cumulative temporal reuse: the late evaluation never updates its
prior sets. It therefore exposes drift and reduces leakage from repeated
sessions.

## Protocol

The content-minimized benchmark scanned the same 442-file, 432-session Claude
history export used by the temporal prior study. The first 216 sessions (41,498
paired calls) formed the frozen prior history; the remaining 216 sessions
(29,451 paired calls) were evaluation-only. A strict identity is the tool name
plus normalized input. The parameterized control keeps only the tool name and
input-key set. Outcomes are the explicit `tool_result.is_error` flag. No tool
names, arguments, paths, or result text are emitted.

## Frozen late-history results

| Frozen first-half prior | Late uses | Success rate |
|---|---:|---:|
| No strict prior | 22,246 | 90.7174% |
| Same-project strict prior | 4,513 | 97.0973% |
| Other-project strict prior only | 2,692 | 96.0253% |

Compared with the late no-prior baseline, exact first-half priors retain a
positive association: **+6.3798 percentage points** within project and
**+5.3078 points** from another project. The effect is smaller than the
cumulative benchmark's roughly eight-point lift, which is consistent with
temporal drift and less opportunity for repeated setup to accumulate.

The effect is not uniform by tool class. In the frozen late period, exact
same-project priors were associated with 84.3750% shell success versus
68.5552% with no prior (a +15.82-point difference), while read/search was
already near ceiling (97.1850% with same-project prior versus 99.6962% with no
prior). Small mutation prior cells (five calls each) are descriptive only.

## Parameterized negative control

| Frozen first-half key-shape prior | Late uses | Success rate |
|---|---:|---:|
| No key-shape prior | 3,562 | 98.4278% |
| Same-project key-shape prior | 17,863 | 92.1738% |
| Other-project key-shape prior only | 8,026 | 89.4219% |

The coarse key-shape control is **worse** than its no-prior comparison by
6.2541 points within project and 9.0060 points across projects. This is a
stronger negative result than the cumulative benchmark: input-key shape is not
an authorization or reuse signal and is particularly vulnerable to drift and
common failure-prone templates.

## Interpretation

The result supports a narrow design:

```text
exact prior artifact
  -> time/scope/environment compatibility
  -> identifier and authority checks
  -> semantic/hard-negative review
  -> changed-system replay
  -> promotion with rollback
```

Exact, scoped artifacts retain useful candidate-ranking signal under a frozen
time split, especially for shell/tooling work. Parameterized templates do not.
The benchmark still measures process success, not semantic correctness,
safety, optimality, user intent, or causal skill improvement. The public export
has no independent terminal outcomes or changed-environment replay.

## Decision

Keep exact artifact priors as a governed, time-aware candidate lane. Add
expiration/versioning and monitor drift; do not treat a prior as permission to
execute. Keep key-shape matches as recall-only candidates. Prioritize shell and
mutation recovery/replay evaluation, while treating read/search gains as
limited because that class is already near ceiling.

## Receipts

- [content-free result](../results/claude-history-tool-artifact-drift-2026-08-09.json)
- [independent verification](../results/claude-history-tool-artifact-drift-verification-2026-08-09.json)
- [`claude_history_tool_artifact_drift_benchmark.py`](../../claude_history_tool_artifact_drift_benchmark.py)
- [`verify_claude_history_tool_artifact_drift_benchmark.py`](../../verify_claude_history_tool_artifact_drift_benchmark.py)
