# Trace-derived artifact reuse on recorded BIRD SQL trajectories

## What was tested

The World Model Harness BIRD fixture contains 242 task records, 222 indexed
trace tasks, 11 SQLite database families, and gold SQL sidecars. We mined the
last parseable successful `sqlite3` query from each trace, then independently
executed both that query and the gold sidecar against the pinned database.
Only a trace query whose canonical result matched the gold result was admitted
as a validated artifact.

We then measured two different reuse questions:

1. **Natural leave-one-out reuse:** lexical top-1 selection among other
   validated artifacts in the same database family, followed by real SQLite
   execution and result comparison.
2. **Controlled parameter reuse:** each validated artifact with literals was
   replayed after deterministic literal mutations. The mutated target SQL was
   independently executed; the parameterized artifact reconstructed the same
   AST with the mutated literals.

Raw prompts, SQL, and database rows remain outside Git. The receipt records the
trace-index hash and aggregates only.

## Result

| Measure | Result |
|---|---:|
| Trace tasks with a parseable SQL candidate | 205 |
| Candidate SQL statements executed | 193 |
| Candidate statements matching independent gold results | **76** |
| Executed candidate statements disagreeing with gold | 117 |
| Validated artifacts admitted | **76** |
| Natural leave-one-out targets | 76 |
| Natural top-1 result matches | **1/76** |
| Natural top-1 selected the same normalized template | 0/76 |
| Naturally repeated normalized-template groups | 0 |
| Controlled parameter targets | 75 |
| Exact, unparameterized artifact matches after mutation | 1/75 |
| Parameterized artifact matches after mutation | **75/75** |

## Interpretation

The first result is an important mining gate: a successful tool execution is
not a validated reusable artifact. In this cohort, only 76 of 193 executable
trace candidates agreed with the independent gold outcome. A text-similarity
retriever then found almost no natural cross-task reuse: 1/76 result matches,
with no selected artifact sharing the target's normalized SQL template.

The controlled 75/75 result confirms that a typed SQL template can safely carry
new literal parameters when its structure is already known and the artifact
has been independently validated. It does **not** show that traces discover
those templates, infer user intent, or improve an agent. The natural cohort had
no repeated normalized templates, so natural parameter transfer remains
unmeasured rather than negative.

## Architecture decision

Trace mining must first separate:

```text
recorded tool success
  -> independent semantic/outcome validation
  -> typed template + scope/schema/authority capsule
  -> compatibility-filtered parameter replay
  -> refusal or frontier regeneration when no compatible template exists
```

Whole-query lexical similarity is not an artifact authority signal. The next
experiment needs a cohort with repeated intents or reviewed subplans, plus
independent labels and changed-system outcomes; otherwise it can only measure
the controlled template mechanics above.

Receipt: [`bird-trace-artifact-reuse-2026-08-07.json`](../results/bird-trace-artifact-reuse-2026-08-07.json).
Independent content-free verification: [`bird-trace-artifact-reuse-2026-08-07-verification.json`](../results/bird-trace-artifact-reuse-2026-08-07-verification.json).
