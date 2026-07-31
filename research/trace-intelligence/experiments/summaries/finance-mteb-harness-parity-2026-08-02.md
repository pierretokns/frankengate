# FinanceBench embedding harness parity (bounded)

The two arms use the same revision-pinned corpus and the same 2,500-character document projection.

| harness/model | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 |
| --- | ---: | ---: | ---: | ---: | ---: |
| sentence-transformers-local / BalyasnyAI/multilingual-e5-base | 0.8106 | 0.7000 | 0.9600 | 1.0000 | 1.0000 |
| ollama-native-api-loopback / ollama:nomic-embed-text:latest | 0.1661 | 0.0800 | 0.2533 | 0.3333 | 0.4533 |

HF minus Ollama: Recall@20 +0.5467; MRR +0.6445.

This is a public relevance comparison only; it does not authorize production promotion or establish RLS/deletion behavior.
