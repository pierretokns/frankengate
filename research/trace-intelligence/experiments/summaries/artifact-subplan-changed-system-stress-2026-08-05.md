# Changed-system subplan admission stress test (2026-08-05)

The five-case replay was expanded to a fixed 100-target synthetic grid: 20
unchanged systems, 20 additive schema changes, 20 approved semantic renames,
20 same-name semantic drifts, and 20 renamed wrong-semantic collisions. The
same validated status-filter subplan and independent SQLite result check were
used for every target.

| policy | accepted | semantically correct | unsafe accepts | rejected |
| --- | ---: | ---: | ---: | ---: |
| name-only subplan | 100/100 | 60/100 | 40/100 | 0/100 |
| semantic-ID subplan | 60/100 | 60/60 | 0/100 | 40/100 |

The result strengthens the bounded mechanics finding: name-based reuse accepts
all cases and silently admits 40 semantic collisions, while semantic-ID
admission rejects every collision in this grid and preserves every valid
transfer. This is a safety/admission result, not evidence that mined artifacts
are common, useful to users, or causally improve agent outcomes.

The grid is intentionally synthetic and deterministic. The next required test
is a consented or license-cleared cohort with naturally mined subplans,
schema/time/project holdouts, changed-system replay, independent verifiers, and
no-skill/placebo controls.

Receipt:
[`artifact-subplan-changed-system-stress-2026-08-05.json`](../results/artifact-subplan-changed-system-stress-2026-08-05.json)
