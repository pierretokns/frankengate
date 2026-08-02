# Claude-history term-context model probe (2026-08-09)

## Question

Can a frontier model distinguish recurring surface terms when it is given local
lexical context, and does that context add signal beyond the term alone? This
targets the corporate-alias/hard-negative seam: the same token can refer to
different systems in different projects.

## Protocol

The probe scanned the 442-file Claude history export and formed candidate pairs
from project-local top terms. Six pairs had divergent context neighborhoods
(Jaccard `< 0.05`) and six had overlapping neighborhoods (Jaccard `>= 0.20`).
For each pair, Luna received two arms, each repeated twice:

1. **Term-only:** the recurring surface term without context;
2. **Term-plus-context:** the term plus the top local neighbor tokens for each
   anonymized side.

Paths, URLs, long hexadecimal strings, and long numeric runs were removed.
Only labels, hashes, counts, and timing were written to the receipt.

## Results

| Arm / cohort | Valid calls | Labels | Repeat agreement |
|---|---:|---|---:|
| Term-only / high-context | 12/12 | `12 unclear` | 6/6 |
| Term-only / low-context | 12/12 | `12 unclear` | 6/6 |
| Term-plus-context / high-context | 12/12 | `12 same_concept` | 6/6 |
| Term-plus-context / low-context | 12/12 | `5 different`, `7 related_context` | 3/6 |

Context changed the model from complete abstention to a decisive judgment on
all high-overlap pairs and 5/12 low-overlap calls. The low-context cohort was
less stable and produced more cautious `related_context` labels, which is the
desired direction for a review queue rather than an auto-promotion system.

## Interpretation

This is evidence that local context is a useful model input for recurring-term
review; the surface token alone is insufficient. It is not evidence that the
model labels are correct. The pair cohorts were selected by the same lexical
context statistic shown to the model, so the result is a calibration/mechanism
probe, not an independent alias benchmark.

The practical cascade is:

```text
recurrence / termhood candidate
  -> project/time context and identifier separation
  -> frontier review with explicit same/related/different/unclear abstention
  -> SME alias/NIL adjudication
  -> retrieval impact and changed-system replay
```

The probe supports adding context to a review prompt and preserving an
`unclear` outcome. It does not justify automatic ontology writes, global alias
edges, embedding fine-tuning, or cross-project promotion. It also does not
compare a neural embedding model; the existing MATM and WMH-BIRD receipts
remain the embedding evidence.

## Claim boundary

The labels are silver frontier judgments. There are no independent corporate
alias/NIL labels, temporal replacement labels, user outcomes, or replay
results. The result establishes a useful input/abstention mechanism, not
enterprise semantic correctness.

Tracking: [concept/alias discovery #120](https://github.com/pierretokns/frankengate/issues/120),
[embedding/model cascade #122](https://github.com/pierretokns/frankengate/issues/122),
and [hard-negative mining #123](https://github.com/pierretokns/frankengate/issues/123).

## Receipts

- [content-minimized result](../results/claude-history-term-context-model-probe-2026-08-09.json)
- [independent verification](../results/claude-history-term-context-model-probe-verification-2026-08-09.json)
- [`claude_history_term_context_model_probe.py`](../../claude_history_term_context_model_probe.py)
- [`verify_claude_history_term_context_model_probe.py`](../../verify_claude_history_term_context_model_probe.py)
