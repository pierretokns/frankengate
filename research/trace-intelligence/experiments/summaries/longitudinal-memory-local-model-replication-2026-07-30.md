# Longitudinal memory local-model replication

Status: completed exploratory within-corpus replication
Date: 2026-07-30

## Frozen execution

- Manifest-declared model: `mlx-community/Qwen3.5-9B-OptiQ-4bit` at revision `319aed167e31e0bf81ddba0c23f8d218a15be612`. The active server and weight/runtime hashes were not mechanically attested.
- Census: 17 units, 425 attempts, 5 repeated invocations per unit-arm, with a 256-token completion cap.
- Sources: `fable5_top_level` 14, `trace_commons` 3.
- Internal raw audit files verified: 425; set commitment `7a3a691a2269de12b47f5be70a940e93eb301f349ab6caffc967ce70916758f0`.
- The model endpoint was loopback-only. No trace content or PII crossed a third-party boundary, and no raw trace/model payload is committed. This pilot did not mechanically verify the new credential-only input gate, so its raw audit remains restricted.

## Overall results

| Arm | Valid | Exact decision | Exact selection | Stale selection | Wrong context | Correct abstention |
|---|---:|---:|---:|---:|---:|---:|
| `no_memory` | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| `verbatim` | 100.0% | 70.6% | 64.7% | 23.5% | 0.0% | 5.9% |
| `latest_only` | 100.0% | 70.6% | 64.7% | 23.5% | 0.0% | 5.9% |
| `contextual_bitemporal` | 100.0% | 70.6% | 64.7% | 23.5% | 0.0% | 5.9% |
| `proposal_only_dream` | 100.0% | 70.6% | 64.7% | 23.5% | 0.0% | 5.9% |

“Exact selection” is hindsight scoring against a later observed state, not proof that the selected evidence was online ground truth. “Correct abstention” is primarily interpretable for arms where exact evidence was absent.

## Pilot finding

- The four evidence-bearing arms had the same aggregate scores. Their paired behavioral agreement was: `verbatim__latest_only` 94.1%, `verbatim__contextual_bitemporal` 100.0%, `verbatim__proposal_only_dream` 100.0%. This pilot therefore does not demonstrate a benefit from context, bitemporal reasoning, or dreaming.
- `no_memory` reached 100% exact-decision correctness only because it had no evidence and always abstained correctly under the pilot evaluator. That is a scoring/control artifact, not evidence that no memory is superior.
- Exact-decision correctness for evidence-bearing arms was 78.6% on Fable but 33.3% on Trace Commons. With only three Trace Commons units, this is a source-stratum warning rather than a generalizable effect.

## Source-stratified results

### `fable5_top_level`

| Arm | Attempts | Valid | Exact decision | Exact | Stale | Wrong context | Correct abstention | Strict repeatability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `no_memory` | 70 | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% |
| `verbatim` | 70 | 100.0% | 78.6% | 78.6% | 21.4% | 0.0% | 0.0% | 100.0% |
| `latest_only` | 70 | 100.0% | 78.6% | 78.6% | 21.4% | 0.0% | 0.0% | 100.0% |
| `contextual_bitemporal` | 70 | 100.0% | 78.6% | 78.6% | 21.4% | 0.0% | 0.0% | 100.0% |
| `proposal_only_dream` | 70 | 100.0% | 78.6% | 78.6% | 21.4% | 0.0% | 0.0% | 100.0% |

### `trace_commons`

| Arm | Attempts | Valid | Exact decision | Exact | Stale | Wrong context | Correct abstention | Strict repeatability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `no_memory` | 15 | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% |
| `verbatim` | 15 | 100.0% | 33.3% | 0.0% | 33.3% | 0.0% | 33.3% | 100.0% |
| `latest_only` | 15 | 100.0% | 33.3% | 0.0% | 33.3% | 0.0% | 33.3% | 100.0% |
| `contextual_bitemporal` | 15 | 100.0% | 33.3% | 0.0% | 33.3% | 0.0% | 33.3% | 100.0% |
| `proposal_only_dream` | 15 | 100.0% | 33.3% | 0.0% | 33.3% | 0.0% | 33.3% | 100.0% |

## Evidence-budget pressure

| Arm | Packs | Token budget | Min/max pack tokens | Truncated tails | Candidate-limit drops | Token-budget drops |
|---|---:|---:|---:|---:|---:|---:|
| `no_memory` | 17 | 2048 | 285 / 297 | 0 | 0 | 0 |
| `verbatim` | 17 | 2048 | 360 / 2048 | 12 | 155 | 48 |
| `latest_only` | 17 | 2048 | 526 / 2048 | 12 | 0 | 0 |
| `contextual_bitemporal` | 17 | 2048 | 530 / 2048 | 12 | 155 | 48 |
| `proposal_only_dream` | 17 | 2048 | 528 / 2048 | 12 | 155 | 48 |

Budget drops are part of the intervention, not harmless preprocessing: an arm can fail because the relevant state was ranked below the five-candidate or 2,048-token boundary. The full audit retains each budget receipt for internal review.

## Interpretation boundary

- This is an exploratory state-evidence selection study over two source strata, not an employee-skill assessment.
- It does not establish causal memory benefit, enterprise generalization, production safety, or permission for automatic memory promotion.
- The native decision-tool adapter was introduced only after plain-JSON pilot failures and is reported as a protocol amendment rather than a preregistered confirmatory result. The runner still accepted plain JSON, so native tool use was not strictly enforced.
- `proposal_only_dream` did not implement proposal generation or consolidation and must be read only as a labeled contextual control. Arm labels were model-visible; `latest_only` retained context metadata; and `contextual_bitemporal` lacked complete bitemporal semantics.
- The finalizer independently rebuilt aggregate counts from the audit attempts and checked them against the base result, but it did not rederive hindsight evaluator labels from the frozen source corpus.
- The completion cap is operator asserted and bounded by observed usage, not bound into each request receipt.
- The five invocations are a deterministic repeatability check, not five statistically independent samples; the local runtime used temperature zero and does not promise seed support.
- Authorized internal full-fidelity analysis is intentional. Any future third-party, public, cross-scope, or lower-privilege copy requires its own transform and disclosure receipt.

Aggregate result commitment: `f7330a3db98acb6b8378f863aa9fb052d81c693b97878ff8f9bea11a34f22925`.
