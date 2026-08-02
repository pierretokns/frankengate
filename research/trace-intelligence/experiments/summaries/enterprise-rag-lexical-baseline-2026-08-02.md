# EnterpriseRAG-Bench lexical baseline

Date: 2026-08-02  
Status: completed; deterministic document-retrieval baseline, not a skill or ontology result

We indexed all 511,962 public documents in SQLite FTS5 and evaluated the 500
question parquet rows. Queries use lowercase alphanumeric terms, stopword
removal, the eight rarest observed terms, OR matching, and SQLite's default
BM25 rank. No model, SQL/tool trace, or frontier judgment was used.

| slice | records | MRR | R@1 | R@10 | evidence R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| all target-bearing questions | 470 | 0.4459 | 0.3787 | 0.5787 | 0.5179 |
| basic | 175 | 0.4883 | 0.4057 | 0.6400 | 0.6400 |
| semantic | 125 | **0.1137** | **0.0800** | **0.2080** | **0.2080** |
| intra-document reasoning | 40 | 0.6549 | 0.6250 | 0.7250 | 0.7250 |
| project-related | 40 | 0.6734 | 0.5500 | 0.9000 | 0.4913 |
| conflicting information | 20 | 0.8042 | 0.7500 | 0.9000 | 0.7500 |
| completeness | 20 | 0.5954 | 0.5500 | 0.7500 | 0.3883 |

The semantic slice is the clear lexical failure mode: low literal overlap is
where alias expansion, identifier-aware representations, dense retrieval, and
frontier reranking should be tested. Completeness also exposes a distinction
between finding one relevant document and recovering all required evidence.

The 30 targetless questions (20 `info_not_found`, 10 `high_level`) must not be
scored as ordinary recall. The lexical baseline returned a non-empty result
for **30/30**, a 100% non-empty retrieval rate on the abstention slice. This is
not proof that every answer would hallucinate, but it proves that retrieval
alone cannot serve as an abstention or artifact-promotion gate.

This baseline therefore supports the planned cascade: structured metadata and
authority filters first, optional dense candidate recall for semantic queries,
frontier review only for ambiguous evidence, and an explicit abstention gate.
It does not measure ontology quality, trace mining, skill improvement, or
cross-user enterprise utility.

Receipt: [`enterprise-rag-lexical-baseline-2026-08-02.json`](../results/enterprise-rag-lexical-baseline-2026-08-02.json)  
Runner: [`enterprise_rag_lexical_baseline.py`](../../enterprise_rag_lexical_baseline.py)
