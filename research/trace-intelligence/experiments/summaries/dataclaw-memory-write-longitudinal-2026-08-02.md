# Observational memory/skill-write longitudinal audit

## Question

Do later sessions after a memory/skill-file write show more recurrence of
earlier command shapes or exact commands? This is an observational association
test, not a causal memory or skill intervention.

## Protocol

Sessions were ordered by `start_time` within each project. Every session after
the first was compared with all earlier sessions in that project. A write was
inferred only when a write-like tool (`write_file`, `edit_file`, or a
write-shaped command) referenced a memory/skill/harness marker. Shape and exact
command recurrence were counted as content-free digests.

## Results

| Group | Sessions | Shape-hit rate | Exact-hit rate | Sessions with shape hit |
|---|---:|---:|---:|---:|
| Any prior artifact write | 305 | **0.397** | **0.124** | 213 |
| No prior artifact write | 85 | **0.027** | **0.008** | 11 |
| Directly after a write | 130 | **0.393** | **0.095** | 74 |

The association is large, but it is not evidence that writing memory or skills
caused reuse. Artifact writes are concentrated in long-lived, active projects;
project age, task mix, user behavior, and harness setup confound the comparison.
The direct-after-write group shows the same pattern, but still lacks semantic
labels and terminal outcomes.

## What this is useful for

This result justifies a controlled follow-up: randomize reviewed memory,
neutral/placebo, generated memory, and no-memory arms on matched changed-system
tasks, then measure later-task success, correction burden, stale/unsafe use,
rollback, and cost. It does **not** justify automatically promoting a memory
file because later sessions happen to reuse similar commands.

Receipt: [`dataclaw-ronald-memory-write-longitudinal-2026-08-02.json`](../results/dataclaw-ronald-memory-write-longitudinal-2026-08-02.json)

Audit implementation: [`dataclaw_memory_write_longitudinal_audit.rb`](../../dataclaw_memory_write_longitudinal_audit.rb)
