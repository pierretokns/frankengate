# Validated subplan transfer under changed systems (2026-08-05)

This deterministic SQLite experiment separates a reusable status-filter
subplan from a source query and composes it into a new COUNT-by-customer task.
The whole source query is therefore not reused; only the validated filter
procedure is transferred. Five target systems cover unchanged, additive,
approved semantic rename, semantic collision, and same-name semantic drift.

| policy | accepted | semantically correct | unsafe accepts |
| --- | ---: | ---: | ---: |
| name-only subplan | 5/5 | 3/5 | 2/5 |
| semantic-ID subplan | 3/5 | 3/3 | 0/5 |

Semantic-ID admission transferred the subplan through the unchanged, additive,
and explicitly approved rename cases, while rejecting both collision cases.
Name-only admission reused every case and silently accepted both semantic
collisions—even where the returned rows happened to look plausible.

This supports storing reusable artifacts at subplan granularity, but only with
typed semantic inputs, explicit mappings, and post-composition verification. It
does not establish mined-artifact quality, enterprise prevalence, or causal
user benefit; the fixture is synthetic and the target query is deterministic.

Receipt:
[`artifact-subplan-changed-system-2026-08-05.json`](../results/artifact-subplan-changed-system-2026-08-05.json).
