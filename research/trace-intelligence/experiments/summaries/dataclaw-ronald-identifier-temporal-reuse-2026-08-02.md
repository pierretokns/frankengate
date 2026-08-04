# DataClaw identifier temporal-reuse audit

## Question

In a chronological history, does an exact normalized path identity provide a
safer reuse signal than a basename surface? This isolates identifier precision
and recall before semantic alias labels exist.

## Dataset and split

- Dataset: `ronaldcmz/Claude-Opus-Dataclaw-Unredacted`
- Pinned revision: `918e6fb39c916d3459ef338b4c3645622b9a5126`
- 436 sessions, 46 projects
- Per-project chronological 70/30 split: 279 train sessions and 141
  evaluation sessions across 30 projects; 16 single-session projects excluded.
- 96 evaluation sessions contained conservative path/file surfaces, yielding
  1,632 unique path-surface events.
- Only basename surfaces and full-path SHA-256 digests were retained; raw paths
  and project labels were not emitted or committed.

Receipt: [dataclaw-ronald-identifier-temporal-reuse-2026-08-02.json](../results/dataclaw-ronald-identifier-temporal-reuse-2026-08-02.json)

## Results

| Signal | Same-project event rate | Any-project event rate | Sessions with same-project hit |
|---|---:|---:|---:|
| Basename surface | `.303` (494/1,632) | `.482` (787/1,632) | `.781` (75/96) |
| Exact full-path digest | `.167` (273/1,632) | `.252` (411/1,632) | `.750` (72/96) |

Among same-project basename hits, only **.553** were also exact full-path
matches. Thus basename matching supplies substantially more recall, but almost
half of those same-project basename hits are different full paths. The same
pattern appears across projects: basename recurrence is broad, while exact
path recurrence is narrower.

The training portion contained 1,677 basename surfaces and 2,629 full-path
digests. **146** basename surfaces crossed project boundaries, while **60** full-
path digests also crossed project boundaries. Exact paths are therefore not a
complete authority key either; shared temporary paths, generated artifacts,
monorepo conventions, and mounts can recur across projects.

## Interpretation

The evidence supports a two-level identifier representation:

1. **Exact path digest:** high-precision exposure/identity feature with lower
   recall; useful for prioritizing likely same-artifact reuse.
2. **Basename surface:** higher-recall candidate and hard-negative feature; it
   must be scoped by project/system/tenant and cannot authorize reuse by itself.

This explains why the previous identifier-aware retrieval arm improved the
project proxy when combined with prompt and command-shape features: basename
surfaces recover related candidates, while exact identity can constrain the
shortlist.

## Claim boundary

Path recurrence does not establish same task, same business meaning, alias
truth, or artifact correctness. Exact paths can be shared, and different paths
can represent a rename, copy, generated output, or unrelated file. Promotion
still requires scope/authority checks, reviewed semantics, temporal validity,
and independent replay.

## Next test

Create a reviewed collision set stratified by (a) exact-path match, (b)
same-basename/different-path, (c) cross-project same-basename, and (d)
cross-project exact-path recurrence. Label same artifact, alias, unrelated,
and NIL; then compare exact, basename, hybrid, dense, and frontier-review arms
on wrong-system acceptance and downstream replay.

## Reproduction

```text
ruby dataclaw_identifier_temporal_reuse_audit.rb \
  /private/tmp/ronald-dataclaw-openai.jsonl \
  experiments/results/dataclaw-ronald-identifier-temporal-reuse-2026-08-02.json
```

