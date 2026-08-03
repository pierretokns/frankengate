# Hard-negative annotated false-negative audit

## Question

Does LaBSE's higher rate of satisfying the Oracle paper's two distance
inequalities mean that it is producing better negatives, or is it selecting
additional relevant documents as negatives?

## Receipt

The audit used the same bounded 500-page/100-train/100-test TechQA fixture and
the pinned CPU implementations. A selected negative was counted as an
**annotated false negative** only when its page ID appeared in that question's
published `gold_page_ids`. An unmarked page was not treated as a true negative.

| Arm | Selected | Annotated false negatives | Rate |
| --- | ---: | ---: | ---: |
| LaBSE | 56 | 0 | 0.0% |
| Six-encoder composite | 23 | 0 | 0.0% |

The machine-readable receipt is
[`hard-negative-paper-annotated-false-negative-audit-2026-08-03.json`](../results/hard-negative-paper-annotated-false-negative-audit-2026-08-03.json).

## Interpretation

This weakens—but does not eliminate—the false-negative explanation for LaBSE's
extra coverage. The public gold annotations do not identify any selected page
as a second relevant page, but they are not a complete relevance judgment.
LaBSE still only has evidence of broader inequality-valid candidate coverage;
its reranker result was tied with the composite (MRR@10 approximately `.6936`
versus `.6950`).

The next decisive test is a blinded relevance audit of selected negatives,
including unmarked pages, with random and lexical controls and project/time/
family-disjoint enterprise-like data. The audit must report false-negative
rate, downstream reranker utility, and inference cost together.
