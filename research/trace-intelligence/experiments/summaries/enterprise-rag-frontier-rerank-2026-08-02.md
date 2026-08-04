# EnterpriseRAG-Bench semantic frontier reranking

Date: 2026-08-02  
Status: completed; frontier reranking of a lexical candidate pool

We ran 125 Luna calls over every `semantic` question. Luna saw only the
question and 20 lexical candidate previews (document ID, source, title, and a
short snippet); it saw no gold answer, expected document ID, or answer facts.
All 125 calls returned valid structured selections.

| arm | MRR | R@1 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: |
| lexical top-10 | 0.1137 | 0.0800 | 0.1600 | 0.2080 |
| Luna rerank of lexical top-20 | **0.1947** | **0.1840** | **0.2080** | 0.2080 |
| lexical top-20 candidate ceiling | — | — | — | **0.2240** |

Frontier review substantially improves ordering (+0.0810 MRR and +0.104 R@1),
but it does not materially increase R@10 beyond the lexical candidate pool.
The top-20 pool itself contains a target for only 22.4% of semantic questions.
This separates the two bottlenecks:

- frontier judgment can rescue ranking among candidates already surfaced;
- semantic candidate generation is the dominant recall bottleneck.

This is evidence for a cascade, not evidence that a frontier model replaces an
embedding model. The missing experiment is a true dense/identifier-aware pool
on the same 125 questions, followed by the same Luna reranker. It must report
pool recall separately from reranking gain.

Receipt: [`enterprise-rag-frontier-rerank-2026-08-02.json`](../results/enterprise-rag-frontier-rerank-2026-08-02.json)  
Runner: [`enterprise_rag_frontier_rerank.py`](../../enterprise_rag_frontier_rerank.py)
