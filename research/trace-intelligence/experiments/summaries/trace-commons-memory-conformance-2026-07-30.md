# Trace Commons real versioned-memory conformance

## Result

- Pinned source files/bytes: 2 / 4555068
- Native records and resolved parent edges: 1602 / 1266
- Tool calls/results/unmatched calls: 460 / 459 / 1
- Context calls with exact results: 8/8
- Exact cross-session write/read continuities: 1
- Interval-censored version gaps: 1
- Reconstructable/unreconstructable edits: 2 / 0
- Snapshot mentions/unique session-scoped states: 140 / 6
- Negative controls passed: True

## Interpretation

A real public pair proves one exact write-to-later-read continuity and two exact edit replays. A second artifact changed between observations without a reconstructable tool event, so the adapter emits a version gap instead of manufacturing continuity. Repeated file-history backup labels are not treated as content identities.

Claim boundary: One public project cohort tests deterministic native import, observed write/read continuity, version-gap detection, edit replay, and imported-scope denial. It does not establish human identity, continuous artifact validity, memory utility, correctness, skill, or enterprise transfer.

Result SHA-256: `ce7eee92ff6dc8829c4329b4febd0d290c1a802c403e3d5f1811a2a995a650cd`
