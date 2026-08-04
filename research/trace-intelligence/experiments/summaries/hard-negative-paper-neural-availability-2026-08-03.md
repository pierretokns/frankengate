# Faithful paper-path availability smoke

This receipt tests the actual six public checkpoint IDs named in Table 7 of
Oracle's ACL 2025 paper, using the clean-room implementation in
`enterprise_hard_negative_paper_reproduction.py`. It is deliberately a tiny
CPU fixture from NVIDIA's public TechQA-RAG-Eval data: 50 candidate pages and
2 train/2 test questions. It tests that the checkpoint can load and that the
two published inequalities select triplets; it is not a quality benchmark.

All six exact checkpoints now complete on CPU. Stella initially failed because
its custom code defaults to `xformers`; the model card documents a CPU path with
`use_memory_efficient_attention=False` and `unpad_inputs=False`, which is now
implemented and succeeds. Jina required fetching its external
`xlm-roberta-flash-implementation` code and using its `retrieval.query` and
`retrieval.passage` adapters; it now succeeds as well. No checkpoint was
silently replaced with a newer model.

On this Apple Silicon host, `mlx-embedding-models` loaded BGE-large and mxbai,
but does not support MPNet. That is a backend compatibility result, not a
retrieval-quality result. MLX is therefore an optional acceleration/portability
track, not part of the faithful paper claim. CPU PyTorch remains the canonical
reference until every model's vectors and pooling agree within tolerance. For
the two models supported by both backends, two-text probes matched at cosine
1.0 with maximum coordinate differences below `3e-7`; this supports using MLX
as an acceleration check for those models, but does not license replacing the
unsupported or custom-code models with substitutes.

The complete aggregate receipt is
`experiments/results/hard-negative-paper-neural-availability-2026-08-03.json`.
