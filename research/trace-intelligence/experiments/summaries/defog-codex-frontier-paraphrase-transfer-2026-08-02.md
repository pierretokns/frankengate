# Frontier transfer on sealed paraphrased questions (2026-08-02)

## Design

The same four broker tasks were replayed in a fresh isolated PostgreSQL 16
container with the same governed role, proxy, schema injection, and four arms
as the neutral-control run. A sealed mutation replaced only each user
question with a semantically equivalent renamed/paraphrased form. Task IDs,
gold SQL, database contents, authority epoch, and the independent verifier
were unchanged. The receipt records a hash of the mutation mapping and all
16 trajectories passed semantic recomputation and security verification.

## Result

| arm | semantic correct | rate | submitted |
| --- | ---: | ---: | ---: |
| no skill | 3 / 4 | 0.75 | 4 / 4 |
| formatting placebo | 2 / 4 | 0.50 | 3 / 4 |
| length-matched neutral | 3 / 4 | 0.75 | 4 / 4 |
| trace-mined terminal discipline | 4 / 4 | 1.00 | 4 / 4 |

The trace arm exceeded no-skill and neutral by one paired win each, but each
contrast had only one discordant block and exact McNemar p=1.0. This is
suggestive transfer compatibility, not evidence of a causal skill effect: the
same artifact scored 1/4 in the unmutated neutral-control run, while the
neutral arm scored 4/4 there. The result therefore demonstrates why prompt
mutations are necessary but not sufficient.

## Required follow-up

Repeat the mutation across at least three seeds and a second harness/model,
pre-register the task/family-clustered analysis, and include source-literal
redaction plus renamed identifiers. Promotion requires a consistent content
arm advantage over both no-skill and length-matched neutral; this single seed
does not meet that gate.
