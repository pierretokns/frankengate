# GEPA v0.1.4 native-tool protocol arm (2026-08-02)

This is a bounded optimizer-integration experiment, not a semantic SQL or
enterprise-skill result. GEPA v0.1.4 was loaded from pinned source revision
`8b0ce6cd99a234f6b74daf37558a2ac0ce18f975` and evaluated a single text
component against the six-episode content-free native-tool fixture. Three
episodes were used for proposal/evaluation and three were held out until the
selected candidate was fixed. Task and reflection calls both used the local
`llama3.2:latest` model through loopback Ollama; raw model records and GEPA
run logs remain under `/private/tmp/frankengate-gepa-protocol-20260802`.

| arm | train matches | holdout matches | holdout rate |
| --- | ---: | ---: | ---: |
| empty seed / no added instruction | 1/3 | 2/3 | 0.667 |
| GEPA-selected candidate | 1/3 | 2/3 | 0.667 |

GEPA executed 11 metric calls, proposed two text mutations, and rejected both
because their paired subsample scores did not improve. The selected candidate
therefore remained the empty seed. This is a reproducible optimizer null on a
small protocol fixture: the optimizer plumbing, train/holdout boundary, and
rejection behavior ran, but no protocol lift was found.

## Claim boundary

- This does not estimate SQL semantic correctness, enterprise work quality, or
  user skill improvement.
- It does not authorize promotion or external skill sharing.
- The reflective model saw only content-free fixture IDs, terminal actions,
  failure codes, and bounded counters; raw model content was not committed.
- The next GEPA test needs a repaired, domain-valid task protocol and a larger
  family-disjoint semantic outcome set before optimizer comparisons can answer
  whether trace-derived procedures improve work.

Machine-readable receipt: `experiments/results/gepa-native-tool-protocol-2026-08-02-r2.json`.

## Sources

- GEPA source: `gepa-ai/gepa@8b0ce6cd99a234f6b74daf37558a2ac0ce18f975` (`v0.1.4`)
- Frankengate adapter: `gepa_native_tool_protocol.py`
- Fixture: `configs/experiments/natural-trace-skill-protocol-fixture-2026-07-30.json`
- GEPA adapter contract: `src/gepa/core/adapter.py:68-200`
- GEPA default reflective adapter: `src/gepa/adapters/default_adapter/default_adapter.py:87-201`
