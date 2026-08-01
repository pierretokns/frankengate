# Changed-system replay for reusable SQL/tool artifacts

## Question

Can a validated SQL/tool artifact survive system evolution without either
being reused unsafely or being discarded on every harmless schema change?

## Protocol

This deterministic SQLite lab replays one validation-carrying customer-total
artifact against five controlled systems: unchanged schema, additive column,
approved semantic rename, semantic collision, and same-name semantic drift.
It compares strict schema fingerprints, name-only compatibility, and explicit
semantic-ID compatibility. A tool parameter rename is also represented as a
semantic-ID-preserving contract adaptation. The receipt contains no source
rows; result values are represented by digests.

Receipt: [`../results/artifact-changed-system-replay-2026-08-03.json`](../results/artifact-changed-system-replay-2026-08-03.json)

Independent verification: [`../results/artifact-changed-system-replay-verification-2026-08-03.json`](../results/artifact-changed-system-replay-verification-2026-08-03.json)

## Result

| Policy | Accepted cases | False semantic accepts |
| --- | ---: | ---: |
| strict fingerprint | 1/5 | 0 |
| name-only compatibility | 5/5 | 2 |
| semantic-ID compatibility | 3/5 | 0 |

Strict matching safely rejected the additive change and approved rename, but
also rejected a harmless change that could have been adapted. Name-only
compatibility reused everything, including both semantic-collision cases.
Semantic-ID compatibility accepted the unchanged, additive, and explicitly
approved rename cases while rejecting both semantic collisions.

## Interpretation

The useful design is not “reuse everything” or “invalidate on any schema
change.” It is a versioned artifact envelope with:

1. exact schema and authority checks;
2. explicit, reviewable identifier mappings for renamed tables, columns, and
   tool parameters;
3. stable semantic IDs for every mapped concept; and
4. result-shape and outcome checks after adaptation.

This is a capability/mechanics result. The schemas and rows are synthetic,
so it does not establish mined-artifact quality, enterprise prevalence,
production database behavior, or user success. The next stronger test is a
held-out public NL2SQL cohort with real schema migrations and human-approved
semantic mappings.
