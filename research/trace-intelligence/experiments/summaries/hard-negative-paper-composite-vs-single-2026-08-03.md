# Six-encoder composite versus single-encoder controls

The first larger public transfer smoke used 300 TechQA pages, 10 training
questions, and 10 held-out questions with the paper's exact inequalities. The
six-encoder composite selected valid negatives for 6/10 training questions.
Single-model controls selected 6/10 (Stella), 6/10 (Jina v3), 7/10 (mxbai),
6/10 (BGE-large), 10/10 (LaBSE), and 7/10 (MPNet).

This is an important correction to the intuition that concatenating six
models must improve mining: it did not improve *coverage* on this fixture.
That does not disprove the paper, because coverage is not the same as
hard-negative quality. The missing test is whether the resulting negatives
produce better triplet-trained reranker MRR and fewer false negatives after
human/audited relevance labels.

The aggregate receipt is
`experiments/results/hard-negative-paper-composite-vs-single-2026-08-03.json`.
