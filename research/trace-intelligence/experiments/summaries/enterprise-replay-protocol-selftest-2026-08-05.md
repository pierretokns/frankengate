# Governed replay protocol self-test (2026-08-05)

The causal replay readiness checker was exercised against a synthetic,
content-free 100-record manifest containing four principals, five projects,
three systems, dual labels, two changed environments, independent outcomes, 50
hard negatives, and 25 NIL/unclear records. The checker now requires non-empty
required values, unique task IDs, and at least two changed environments in
addition to the field-presence and minimum-count gates.

All readiness gates passed. A shape-only control with duplicate task IDs and a
single changed environment was rejected. This proves only that the admission
validator can recognize a properly shaped cohort; it is not enterprise evidence
and must not be used as a skill, alias, retrieval, or outcome result.

Receipt and verifier:
`experiments/results/enterprise-replay-protocol-selftest-2026-08-05.json`.
