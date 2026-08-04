# Defog trace-mined skill replay with schema-injected protocol repair

This is the same six-task car-dealership schedule used by the earlier replay,
with the same Llama 3.2 loopback model, three arms, authority manifest, and
governed PostgreSQL role. The only harness change was an arm-independent
authorized schema catalog injected into every system context, alongside the
larger terminal budget (10 model turns, 5 SQL attempts, 8,192 episode tokens).
No prompt artifact, task selection, model, or authority binding differed by
arm.

| arm | tasks | submitted candidates | semantic-correct | semantic-incorrect | abstained | unauthorized observations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no-skill | 6 | 2 | 1 | 1 | 4 | 0 |
| formatting placebo | 6 | 2 | 1 | 1 | 4 | 0 |
| trace-mined terminal discipline | 6 | 2 | 1 | 1 | 4 | 0 |

The independent semantic verifier re-executed all six submitted candidates and
the sealed gold alternatives under a fresh governed executor. Stored and
recomputed outcomes matched for all 18 runs; the independent security verifier
also passed all raw-audit, authority, policy, terminal-scheduling, and
unauthorized-observation checks. The paired trace-mined semantic contrast is
therefore 1/6 versus 1/6 (risk difference 0.0), not a skill improvement.

This run establishes that the earlier all-policy-denied result was partly a
schema-navigation/model interaction confound. It does not establish a causal
skill benefit: four of six tasks still abstained in every arm, the schedule is
not a full family-disjoint enterprise estimate, and the common schema injection
is a harness intervention. Promotion remains closed.
