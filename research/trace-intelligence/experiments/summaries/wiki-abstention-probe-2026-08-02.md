# Wiki NIL/abstention probe — 2026-08-02

The first fixture run returned a candidate for every NIL query. This probe
tests whether a score threshold or a simple unique-identifier gate can repair
that failure. It is a synthetic diagnostic, not a production policy.

At 25 wikis, the raw hybrid baseline accepts all gold and NIL queries, with
Recall@1 `.55` and NIL false-positive rate `1.00`. A threshold of `.65` reduces
NIL false positives to `0.00`, but accepts only `75%` of gold queries and has
`0.667` Recall@1 among accepted gold queries. A unique `Atlas-XX`/
`bluebird-XX` identifier gate also yields zero NIL false positives, but covers
only `75%` of gold queries and has `.667` accepted Recall@1.

This is the expected hard edge: retrieval score alone is not a trustworthy
abstention signal when common enterprise terms dominate the query. An entity
linker, scope/authorization metadata, explicit NIL training examples, and
frontier review for ambiguous cases are separate components—not optional
threshold tuning.

The next real-corpus experiment must include NIL questions, ambiguous aliases,
missing/stale pages, and a calibrated acceptance policy. Never report Recall@k
without NIL false-positive rate and accepted-query coverage.

## Receipt

- [content-minimized abstention result](../results/wiki-abstention-probe-2026-08-02.json)
- [probe implementation](../../wiki_abstention_probe.py)
