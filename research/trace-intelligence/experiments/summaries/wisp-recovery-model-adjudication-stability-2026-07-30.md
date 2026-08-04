# Wisp recovery local-model adjudication stability

## Outcome

Ran 18 valid decisions across 6 blinded natural recovery candidates and 3 prompt-order/skepticism variants.

The deterministic stratified sample contains three shell, two file-change, and
one file-read episode. The source packet is pinned by SHA-256 and the model is
the loopback-only `mlx-community/Qwen3.5-9B-OptiQ-4bit` snapshot recorded in the
runtime manifest. Median decision latency was 27.152 seconds; maximum latency
was 69.368 seconds.

| Field | Complete | Unanimous | Fraction | Fleiss kappa |
|---|---:|---:|---:|---:|
| `cause` | 6 | 3 | 0.500 | 0.442 |
| `evidence_strength` | 6 | 4 | 0.667 | -0.091 |
| `outcome` | 6 | 4 | 0.667 | 0.556 |
| `productive_exploration` | 6 | 3 | 0.500 | 0.333 |
| `relation` | 6 | 4 | 0.667 | 0.500 |
| `usefulness` | 6 | 3 | 0.500 | 0.085 |

Outcome and relation had the strongest kappa values in this small sample.
Cause, productive exploration, and especially usefulness were materially
prompt-sensitive. Evidence-strength kappa was negative despite four unanimous
cases because the marginal label distribution was highly imbalanced; both
unanimous fraction and kappa are retained to expose that prevalence effect.

This supports a review-queue decision, not an automatic label decision:
usefulness and evidence strength require independent adjudication first, while
outcome and relation remain candidate silver labels until compared with human
or independently sourced judgments.

## Interpretation boundary

This is a same-model stability diagnostic under three prompt variants. It is not human gold, independent-model agreement, causal diagnosis, or evidence that an enterprise intervention works. Low-stability fields must be sent to independent review; high stability only establishes that this pinned model is internally consistent on the sampled packet.

The sample has six episodes from one public source and is intentionally too
small for prevalence or subgroup claims. Prompt variants are correlated
because they use the same weights, tokenizer, evidence, and deterministic
decoding. Fleiss kappa therefore measures within-model perturbation stability,
not inter-rater reliability in the usual human-study sense. Candidate-level
responses and selected blind IDs remain in the mode-0600 external raw audit.
