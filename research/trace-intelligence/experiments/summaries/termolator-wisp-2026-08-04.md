# Termolator Wisp termhood probe

**Status:** independent capability run; no promotion claim
**Corpus:** pinned Wisp single-contributor subset, 49 non-empty documents
**Split:** 24 foreground documents versus 25 background documents, selected by
stable path order; no target labels were exposed to the extractor

## Result

Termolator completed successfully and emitted 3,000 candidates, the configured
output cap. The mean token count among the top 100 candidates was 1.61. The
receipt stores hashes rather than candidate strings; raw intermediate files
remain in a disposable `/private/tmp` directory.

Receipt:
[`termolator-wisp-2026-08-04-full.json`](../results/termolator-wisp-2026-08-04-full.json)

Independent verification:
[`termolator-wisp-2026-08-04-verification.json`](../results/termolator-wisp-2026-08-04-verification.json)

## Interpretation

This establishes that the interpretable foreground/background termhood
baseline is runnable on the admitted trace shape, not that its terms are
correct or useful for retrieval. The configured cap was reached, so candidate
count is not a quality estimate. The next comparison should use a blinded
enterprise vocabulary set and compare boundary precision, termhood precision,
NIL/ambiguity behavior, wrong-system links, reviewer cost, and retrieval lift
against GLiNER and deterministic identifiers.
