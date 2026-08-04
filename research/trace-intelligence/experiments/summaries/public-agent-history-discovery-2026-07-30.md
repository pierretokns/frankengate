# Public agent-history expanded discovery

**Audit date:** 2026-07-30

## Result

- Hugging Face agent-trace dataset hits: 359
- GitHub indexed native Claude/Codex matches: 1364 / 320
- Native files in inspected top repositories: 2362 Claude (2567303953 bytes) and 329 Codex (280394087 bytes)
- Near-complete public Claude home-state trees: 1
- Real researcher-trace and paired trace/memory strata: 2 / 2
- Codex repositories with adjacent auth state: 9/10

## Decision

Public corpus availability is sufficient. Build strict native, portable-bundle, partial-home, and transformed-export adapters. Do not recursively ingest a harness home; trace, versioned context/policy, and unsafe/excluded state are separate lanes.

Claim boundary: discovery establishes corpus availability and import-shape coverage, not independent users, task correctness, employee skill, or enterprise intervention benefit.

Result SHA-256: `cf0d39e22152084421f066004f75e0381644e292ee6a8de640e40a0d5be87720`
