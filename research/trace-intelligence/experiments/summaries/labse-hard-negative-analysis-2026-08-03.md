# Why LaBSE selected more hard negatives in the first transfer smoke

LaBSE is not a new model discovered after the Oracle paper. The underlying
[LaBSE paper](https://aclanthology.org/2022.acl-long.62/) was submitted in 2020
and published at ACL 2022; the paper under study is
[ACL 2025](https://arxiv.org/abs/2505.18366) and lists LaBSE among its six
encoders. The [public checkpoint](https://huggingface.co/sentence-transformers/LaBSE)
maps 109 languages into a shared 768-dimensional space, with a BERT encoder,
CLS pooling, a dense projection, and normalization.

In the 300-page/10-query TechQA transfer smoke, LaBSE made the two published
inequalities hold for 10/10 training questions. On the larger 500-page,
100-query fixture it held for 56/100, versus 23/100 for the six-model
composite. This means LaBSE's geometry provides broader candidate coverage
under the selector. It does **not** show that LaBSE retrieves better answers or
that its negatives are safer; it may simply produce more false negatives. The
next gate must adjudicate the selected candidates and train the same reranker
for every arm.

Likely reasons for the transfer behavior:

- LaBSE's multilingual translation-ranking objective can make short technical
  paraphrases and filename-like text unusually close even in English.
- Its normalized 768-dimensional space may be less conservative than the
  concatenated/PCA ensemble, so more candidates satisfy both inequalities.
- TechQA questions are tied to one source technote; the fixture does not test
  cross-user enterprise aliases, schema versions, or tool-call outcomes.

Likely failure modes for Frankengate:

- The public model card caps the Sentence-Transformers configuration at 256
  tokens; long traces and tool payloads will be truncated.
- Translation alignment can collapse unrelated corporate names, acronyms, or
  code identifiers that happen to resemble words in another language.
- It is not instruction-aware or trained specifically for SQL, code, tool
  schemas, temporal versions, or outcome validity.
- A high inequality-selection rate can increase false negatives, contaminating
  contrastive training and producing bad evals.

LaBSE remains a valuable diversity/control arm, not a promotion candidate. It
should be retained in the matrix because it tests a genuinely different
training objective, then rejected or adapted only after identifier-collision
and audited false-negative slices are measured.
