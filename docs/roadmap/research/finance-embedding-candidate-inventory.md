# Finance embedding candidate inventory

Status: candidate list for `bif-kyy.17.12.1`; none is production-approved.

| Candidate | Size / shape | License and availability | Initial role | Required checks |
|---|---:|---|---|---|
| Qwen3-Embedding-0.6B | 0.6B, 32K context, 1024-dim family entry | Apache 2.0 model release; open weights | latency/CPU baseline | instruction format, quantization, FinMTB/FinanceMTEB, p50/p95 |
| Qwen3-Embedding-4B | 4B, larger multilingual capacity | Apache 2.0 model release | quality baseline and teacher | GPU cost, reranker pairing, finance/news slices |
| Qwen3-Embedding-8B | 8B, high-quality reference | Apache 2.0 model release | offline teacher/reference | throughput, domain adaptation, licensing closure |
| EmbeddingGemma | 308M multilingual embedding model | Gemma terms/model-card obligations; verify redistribution and serving terms | small open-weight comparison | exact model terms, tokenizer/prompt instructions, local runtime |
| NVIDIA NV-Embed family | model-specific dimensions and serving requirements | access/license must be checked per model card; do not infer OSS status from NVIDIA branding | research-only comparison until terms clear | access, license, hardware, reproducibility |
| Finance/news-specific candidate (Balyasny-reported) | identity not recovered locally | unknown until original card/repository is found | historical comparison only | recover exact model, base Qwen revision, license, FinMTB run |

The local machine already contains Qwen embedding references in the Bifrost test
fixtures (`Qwen/Qwen3-Embedding-0.6B`, Qwen 4B/8B examples) and cached FinanceMTEB
datasets. These are leads, not evidence of a completed finance benchmark. The original
Balyasny/FinMTB experiment and exact model identifier were not found in the current
filesystem search.

## Selection protocol

Run every candidate with the model-card query/document instruction format and identical
chunking, normalization, batch size, hardware, and index. Record dimensions, memory,
throughput, p50/p95 embedding latency, retrieval recall/nDCG/MRR, reranker impact, and
ACL/deletion behavior. Keep a general baseline and a finance/news cohort; do not select
on aggregate MTEB alone. A candidate cannot enter the serving registry until its model
card, weights, tokenizer, license, and provenance are recorded in the release ledger.

The adjacent local State of AI retrieval fixtures provide a useful benchmark-design
reference: their FinE5/FinanceMTEB notes treat the model as a gated finance benchmark
reference and retain the caveat that bag-of-words can outperform dense embeddings on
some financial semantic-textual-similarity tasks. FrankenGate should therefore keep
BM25/lexical, dense, and hybrid arms in the benchmark rather than promoting a dense
model from one aggregate score. Those fixtures are not copied into this repository and
are not treated as production training data.

## References

- Qwen3 Embedding paper: https://arxiv.org/abs/2506.05176
- Qwen3-Embedding-4B: https://huggingface.co/Qwen/Qwen3-Embedding-4B
- EmbeddingGemma model card: https://ai.google.dev/gemma/docs/embeddinggemma/model_card
- NVIDIA NV-Embed-v2: https://huggingface.co/nvidia/NV-Embed-v2
- FinanceMTEB dataset family: https://huggingface.co/collections/FinanceMTEB
