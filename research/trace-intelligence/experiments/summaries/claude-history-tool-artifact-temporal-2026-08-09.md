# Temporal prior-success prediction for tool artifacts

## Question

Does a strict tool/input identity that succeeded in an earlier session predict
a later observed tool success? This is stronger than counting recurrence: the
prior set is frozen before each session, so same-session repetition cannot leak
into the prediction.

## Protocol

The benchmark uses the 442-file Claude history export and retains the 405
sessions containing paired tool results. Sessions are ordered by their recorded
timestamps. A strict identity is the tool name plus normalized input (paths,
UUIDs, and multi-digit numbers canonicalized). For each paired call, classify
it as:

- **no prior success**: no earlier session succeeded with this identity;
- **prior same-project success**: an earlier session in the same project
  succeeded with it; or
- **prior other-project success only**: an earlier session in another project
  succeeded, but the current project had not.

Prior sets update only after a session completes. Outcomes are the explicit
`tool_result.is_error` flag. No tool names, inputs, paths, or result text are
written to the receipt.

## Results

| Prior condition | Uses | Success rate |
|---|---:|---:|
| No prior success | 53,678 | 88.7216% |
| Prior same-project success | 11,282 | 96.8268% |
| Prior other-project success only | 5,989 | 97.1615% |

Relative to no prior success, the observed lift was **+8.1052 percentage
points** for same-project reuse and **+8.4398 points** for reuse learned in a
different project. The cross-project result is a process-success association,
not proof that the artifact is semantically transferable; it may reflect
stable tool contracts or common harness behavior.

## Interpretation

This is the strongest artifact-reuse result so far because it is temporally
ordered and compares against a no-prior baseline. It supports exposing prior
successful artifacts as ranked candidates, especially when paired with scope,
authority, parameter, and environment checks. It does not authorize automatic
reuse: `is_error=false` only means the tool call did not report an error.

```text
prior-success candidate
  -> scope/authority/environment compatibility
  -> semantic intent and hard-negative review
  -> clean/changed-system replay
  -> promote or refuse with rollback
```

## Claim boundary

There are no independent semantic labels, tool safety contracts, terminal task
outcomes, or changed-environment replays. The association may be confounded by
tool family, project age, harness boilerplate, or repeated setup work. It is
evidence for a governed candidate-prior lane, not causal skill improvement or
cross-user artifact correctness.

## Parameterized key-shape control

The same run also tested a much coarser template identity: tool name plus
input-key set, ignoring all input values. This is the tempting “reuse the
known-good tool template” strategy.

| Prior key-shape condition | Uses | Success rate |
|---|---:|---:|
| No prior key-shape success | 4,890 | 92.3108% |
| Prior same-project key-shape success | 49,076 | 90.5514% |
| Prior other-project key-shape success only | 16,983 | 90.7613% |

The coarse key-shape prior was **worse** than its no-prior control by 1.7594
points within a project and 1.5495 points across projects. This is a valuable
negative result: input-key shape alone is too coarse to authorize reuse and can
select common, failure-prone tool patterns. Preserve exact parameter bindings,
scope, resource identity, and independent replay; treat key-shape matches only
as candidate recall.

## Tool-class stratification

The same exact-identity prior was stratified using deterministic coarse classes
(read/search, mutation, shell, orchestration, and other). The classes are
heuristics, not security policies.

| Class | No prior | Same-project exact prior | Other-project exact prior |
|---|---:|---:|---:|
| Read/search | 99.3934% (10,550) | 96.7794% (10,588) | 97.6752% (5,807) |
| Mutation | 94.1272% (26,989) | 99.3243% (444) | 96.0000% (25) |
| Shell | 69.7511% (13,822) | 93.8326% (227) | 71.4286% (112) |
| Orchestration | 86.4504% (524) | 100.0000% (10) | — |
| Other | 91.4668% (1,793) | 100.0000% (13) | 95.5556% (45) |

The largest practical effect is shell: an exact same-project prior is about
24 percentage points above its no-prior baseline. Mutation also benefits
strongly. Read/search is already near ceiling and the prior association is
lower, so Frankengate should not assume that a prior-success boost is uniform
across tool classes. Small other-project cells are descriptive only.

Parameterized key-shape priors remain unsafe in these strata, especially shell
(78.3237% with no prior key-shape versus 68.1245% after same-project key-shape
history). Exact bindings and a tool-class-specific policy are required.

## Receipts

- [content-free result](../results/claude-history-tool-artifact-temporal-2026-08-09.json)
- [independent verification](../results/claude-history-tool-artifact-temporal-verification-2026-08-09.json)
- [`claude_history_tool_artifact_temporal_benchmark.py`](../../claude_history_tool_artifact_temporal_benchmark.py)
