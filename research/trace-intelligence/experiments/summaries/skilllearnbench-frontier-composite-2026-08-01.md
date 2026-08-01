# Composite human + generated SkillLearnBench replay (2026-08-01)

This is a partial, five-instance replay of the public
`enterprise-information-search` family under the Codex subscription
(`gpt-5.6-luna`). The composite skill directory contained the reviewed
`artifact-review-search` procedure plus the published one-shot generated
`enterprise-data-retrieval` and `json-data-analysis` procedures. It was
compared with the previously recorded null, generated-only, and human-only
arms on the same task instances.

## Result

| arm | q1 correct | q1 recall | q1 precision | published-check passes |
|---|---:|---:|---:|---:|
| null, first five | 35/45 | .778 | .957 | 2/5 |
| one-shot generated, first five | 38/45 | .844 | 1.000 | 1/5 |
| reviewed human, first five | 41/45 | .911 | 1.000 | 4/5 |
| **composite human + generated, first five** | **45/45** | **1.000** | **1.000** | **5/5** |

The composite returned all expected q1 IDs and all q3 URLs for each of the
five completed instances, with no observed false positives. Its recorded
input usage was 3,837,841 tokens and output usage was 39,736 tokens across
the five calls. This used fewer input tokens but slightly more output tokens
than the human-only first-five total (5,481,964 input / 38,062 output). The
arms were not randomized and the composite had a different prompt/context
footprint, so this is not a cost claim.

## Interpretation

This is the first bounded signal that a reviewed retrieval procedure can be
composed with generated data-navigation procedures without immediately
diluting verifier performance. It does **not** show that generated skills
caused the improvement: the sample is one public task family, only five of
six instances completed, q2 has no gold labels, and this is a host-path
adaptation rather than the official Docker runner. The sixth instance was
left explicitly `not_completed` after its frontier call was interrupted;
there is no imputed score.

The next fair test is a randomized, task-disjoint matrix with (a) human-only,
(b) generated-only, (c) composite, (d) placebo, and (e) null arms, followed by
changed-system replay and an independent outcome verifier. The composite
should remain a candidate promotion, not a live skill or automatic memory
write.

Receipt: [`skilllearnbench-frontier-composite-2026-08-01.json`](../results/skilllearnbench-frontier-composite-2026-08-01.json)

Runner: [`skilllearnbench_frontier_composite.py`](../../skilllearnbench_frontier_composite.py)
