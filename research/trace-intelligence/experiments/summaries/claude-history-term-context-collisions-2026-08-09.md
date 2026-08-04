# Cross-project term-context collision diagnostic

## Question

When a term recurs across project histories, is lexical recurrence enough to
treat it as a shared corporate concept? This probe tests a cheap hard-negative
signal: compare the local lexical contexts of the same surface term across
projects before proposing an alias link.

## Protocol

Using the same 442-file, 432-session, 65-project Claude history export as the
legacy-port stability study, select each project's top 100 document-frequency
terms. For every term appearing in at least two projects, collect the hashed
tokens within a four-token window, cap each context at the 256 most frequent
neighbors, and compute pairwise Jaccard overlap. A pair below `.05` is counted
as a **candidate lexical hard negative**. Project names, terms, contexts,
paths, and messages are never written to the receipt.

## Results

| Measure | Result |
|---|---:|
| Selected top-term hashes | 2,249 |
| Shared term hashes with context in ≥2 projects | 778 |
| Cross-project context pairs | 37,390 |
| Pairwise Jaccard (min / p10 / median / p90 / max) | `0 / .017301 / .065844 / .166287 / 1.0` |
| Pairs below `.05` | 13,915 (37.22%) |
| Shared terms with at least one pair below `.05` | 543/778 (69.79%) |
| Pairs at or above `.50` | 1,060 |

The result is not dependent on one arbitrary cutoff:

| Context-Jaccard threshold | Pair rate below | Term rate with any pair below |
|---:|---:|---:|
| `.01` | 5.43% | 34.32% |
| `.05` | 37.22% | 69.79% |
| `.10` | 72.13% | 84.32% |
| `.20` | 92.70% | 93.70% |

## Interpretation

This gives Frankengate a practical hard-negative mining primitive: repeated
surface forms are often not supported by a stable lexical neighborhood across
projects. A term that passes frequency recurrence but has disjoint contexts
should be held out of automatic alias promotion and sent to identifier,
scope, temporal, or human review. The high-overlap pairs remain candidate
positives, not truth; shared boilerplate can produce them.

This is **not** a semantic-collision rate. Lexical context is sparse, the
projects are public-research proxies, and no adjudicated wrong-system labels or
outcomes are available. The result supports adding cheap context-separation
features to a review/reranking cascade, not training a corporate embedding or
writing ontology edges automatically.

## Receipts

- [content-free result](../results/claude-history-term-context-collisions-2026-08-09.json)
- [independent verification](../results/claude-history-term-context-collisions-verification-2026-08-09.json)
- [`claude_history_term_context_collisions.py`](../../claude_history_term_context_collisions.py)
