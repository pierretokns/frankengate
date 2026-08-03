# Frontier adjudication of Oracle-style hard negatives

## Question

Does LaBSE's higher inequality-valid selection rate produce semantically useful
hard negatives, or merely more unrelated pages?

## Design

- Same pinned 500-page/100-train/100-test TechQA fixture used by the LaBSE and
  six-encoder runs.
- Twelve candidates per arm, selected deterministically from the training
  triplets; two independent `gpt-5.6-luna` calls per candidate (`48` calls).
- Gold page IDs were withheld from the judge packet.
- The judge saw only the question, selected positive page, and candidate page,
  and returned one of `relevant_false_negative`, `near_miss_hard_negative`,
  `unrelated`, or `indeterminate`.
- The committed receipt contains only labels, confidence-independent hashes,
  and agreement; raw page text remains outside the repository.

## Result

| Arm | Candidates | Valid calls | Near miss | Unrelated | Relevant false negative | Repeat agreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LaBSE | 12 | 24 | 9 (37.5%) | 15 (62.5%) | 0 (0.0%) | 9/12 (75.0%) |
| Six-encoder composite | 12 | 24 | 19 (79.2%) | 5 (20.8%) | 0 (0.0%) | 9/12 (75.0%) |

All valid calls returned `high` confidence, but these are silver labels from a
single frontier model family and must not be treated as ground truth.

Machine-readable summary:
[`hard-negative-frontier-adjudication-2026-08-03.json`](../results/hard-negative-frontier-adjudication-2026-08-03.json).

## Interpretation

This is the first evidence that explains the LaBSE/composite difference:

1. LaBSE's higher selection rate is not producing more explicitly relevant
   pages in this sample (`0/24` calls).
2. The six-model composite produces substantially more semantically close
   near-misses (`79.2%` versus `37.5%`), so it is the better candidate source
   for contrastive training **if** the frontier labels survive SME review.
3. LaBSE's extra coverage is mostly judged unrelated (`62.5%`). Its value is
   therefore diversity/recall, not hard-negative quality on this fixture.
4. The `25%` per-arm disagreement rate is itself a warning: model-selected
   labels require adjudication, and high self-reported confidence is not a
   calibration guarantee.

This does not disprove LaBSE or the Oracle paper. It is a bounded public
transfer test with a small sample, one judge family, no SQL/tool outcomes, and
no corporate identifier/alias labels.

## Next gate

Repeat the exact packets with blinded SME labels and add random and lexical
negative controls. Stratify by exact identifier, acronym, same-scope sibling,
temporal rename, NIL, and changed-system cases. Promote a negative-generation
arm only when it improves downstream reranker/outcome metrics without raising
false-negative or collision rates.
