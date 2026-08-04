# Modern TermSuite/AcronymExpansion concept port

**Status:** current-Python concept port; not claimed equivalent to upstream

The port preserves two useful ideas from the older projects:

- foreground/background termhood ranking with normalized variant groups;
- contextual acronym full-form extraction with ambiguity/NIL abstention.

It replaces the obsolete TreeTagger/Mate and Doc2Vec requirements with
standard-library tokenization and deterministic matching, making the contract
portable under the repository's `uv` environment.

## Result

On the pinned 49-document Wisp cohort, the port emitted 3,000 ranked term
candidates (the configured cap). Its fixed eight-case acronym probe achieved
8/8, including abstention on undefined and conflicting expansions. This is a
capability result, not enterprise term quality or upstream equivalence.

Receipt:
[`modern-term-acronym-port-wisp-2026-08-04.json`](../results/modern-term-acronym-port-wisp-2026-08-04.json)

Verification:
[`modern-term-acronym-port-wisp-2026-08-04-verification.json`](../results/modern-term-acronym-port-wisp-2026-08-04-verification.json)

## Sharing and attribution

The clean port is maintained in the Frankengate research branch and published
through attributed forks for community reuse:

- [Frankengate Termolator modern fork](https://github.com/pierretokns/frankengate-termolator-modern)
- [Frankengate AcronymExpansion modern fork](https://github.com/pierretokns/frankengate-acronym-expansion-modern)

The forks retain upstream history. The new implementation is a clean,
independently authored port; no upstream source files were copied into the
receipt or benchmark.

Published port branches:

- [Termolator `modern-port`](https://github.com/pierretokns/frankengate-termolator-modern/tree/modern-port)
  (upstream source commit `ca2f50e246d307192ceb68372dbe00a182431148`)
- [AcronymExpansion `modern-port`](https://github.com/pierretokns/frankengate-acronym-expansion-modern/tree/modern-port)
  (upstream source commit `8023995a5070bd8bd671cf3ba62b8b2cfc334abf`)
