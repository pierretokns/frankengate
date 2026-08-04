# EnterpriseRAG-Bench generic dense baseline

Date: 2026-08-02  
Status: completed; generic embedding control, not a custom-domain result

We encoded all 511,962 documents and 125 semantic questions with the public
`sentence-transformers/all-MiniLM-L6-v2` model using full-corpus streaming cosine
similarity. Two document representations were tested:

| representation | MRR | R@1 | R@10 | R@20 |
| --- | ---: | ---: | ---: | ---: |
| source + title + first 256 content characters | 0.0487 | 0.0400 | 0.0720 | 0.1200 |
| source + title only | 0.0270 | 0.0160 | 0.0640 | 0.0640 |

Both are below the lexical top-20 pool recall (`0.224`) and far below the Luna
rerank's ordering once lexical candidates are available (`MRR 0.1947`). The
result is a genuine negative for this generic model and these document views:
semantic similarity did not recover the benchmark's internal concepts.

It is **not** a disproof of domain-specific embeddings. The corpus is synthetic,
the model is general-purpose, and no hard-negative or query–document training
was performed. The right next test is a leakage-safe adapter or stronger
retrieval model trained on held-out query/positive/negative pairs, with source,
question-type, and project-like splits. Until that test wins, exact identifiers,
lexical metadata, and selective frontier review remain the stronger default.

Receipt: [`enterprise-rag-dense-baseline-2026-08-02.json`](../results/enterprise-rag-dense-baseline-2026-08-02.json)  
Runner: [`enterprise_rag_dense_baseline.py`](../../enterprise_rag_dense_baseline.py)
