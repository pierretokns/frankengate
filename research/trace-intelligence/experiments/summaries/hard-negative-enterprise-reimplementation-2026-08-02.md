# Hard Negative Mining for Domain-Specific Retrieval — clean-room reimplementation

## Reproduction status

The target paper is Oracle AI's ACL 2025 Industry Track paper, [Hard Negative
Mining for Domain-Specific Retrieval in Enterprise Systems](https://arxiv.org/abs/2505.18366).
It reports a six-bi-encoder ensemble, concatenation, PCA retaining 95% of
variance, and a two-inequality selector:

```text
d(Q, D) < d(Q, PD)
d(Q, D) < d(PD, D)
```

The selected document is close to the query but sufficiently different from
the positive. The paper then fine-tunes a cross-encoder with triplet loss and
reports internal-corpus MRR@3/MRR@10 of 0.57/0.64 versus 0.42/0.45 without
fine-tuning, plus improvements on FiQA, Climate-FEVER, and TechQA. The paper
uses 36,871 unlabeled cloud-service documents and 5,250 annotated query-positive
pairs, with a 1,000/4,250 train/test split and three-run averages.

No public implementation or the six private encoder checkpoints were found in
the paper record or public search results. Therefore this is **not a fork of
upstream code**. It is a clean-room, OSS-compatible implementation of the
published algorithmic contract. If the authors later publish a repository, we
can add a compatibility adapter or fork it separately with attribution.

## What is implemented

[`enterprise_hard_negative_mining.py`](../../enterprise_hard_negative_mining.py)
implements:

- six deterministic TF-IDF views (word and character n-grams) as a CPU
  surrogate for the six neural bi-encoders;
- concatenation and PCA with 95% variance retention;
- the paper's two hard-negative inequalities;
- random, lexical, and proposed-negative training arms;
- a small linear pair scorer as a transparent cross-encoder surrogate;
- deterministic held-out MRR@3/MRR@10 and selection/match rates.

The code explicitly labels the missing neural encoders and cross-encoder so a
surrogate result cannot be mistaken for a paper reproduction.

## Faithful neural implementation path

[`enterprise_hard_negative_paper_reproduction.py`](../../enterprise_hard_negative_paper_reproduction.py)
now implements the paper's actual model contract behind a bounded, aggregate-
only runner: the six Table 7 encoder IDs, per-model normalized embeddings,
concatenation, PCA(95%), both hard-negative inequalities, and an optional
cross-encoder trained with the published margin triplet objective. It is
covered by pure-mechanics tests and records all modeling choices in its
receipt. It has **not** yet been run end-to-end with all six checkpoints and a
trained reranker in this environment; missing Oracle data/configuration and
model availability prevent calling that a full reproduction. The original
TF-IDF implementation remains the fast control, not a substitute for this
neural path.

The bounded availability receipt first showed five of the six exact public
checkpoint IDs loading and executing the selector on CPU. Stella required its
documented CPU configuration to disable xformers. Jina required its external
remote-code repository and its task-qualified retrieval adapters; those are now
handled by the implementation. The full six-model composite executes on the
300-page transfer fixture. See
[`hard-negative-paper-neural-availability-2026-08-03.md`](hard-negative-paper-neural-availability-2026-08-03.md)
and the composite comparison receipt.

## First transfer test

The run uses the 400-page quality-filtered State of AI wiki corpus and the
first 200 deterministic template questions (160 train / 40 held out). It is a
transfer probe, not the paper's benchmark.

| negative strategy | selected train examples | selection rate | MRR@3 | MRR@10 |
|---|---:|---:|---:|---:|
| random | 160 | 1.000 | .629 | .657 |
| lexical | 160 | 1.000 | .613 | .640 |
| proposed inequalities | 35 | .219 | .000 | .000 |

The proposed selector matched only 2.9% of the corpus's deterministic
silver hard-negative labels. The zero held-out MRR is a warning about this
surrogate/data combination, not a disproof of the paper: (a) the paper's
neural ensemble is absent, (b) the questions are generated from metadata and
are highly templated, (c) the linear scorer is not a cross-encoder, and (d)
the split is not family-disjoint. The result does show that copying the
inequalities alone is not enough; candidate availability and label quality
matter.

## Fair verification plan

1. Reproduce the public FiQA, Climate-FEVER, and TechQA preprocessing and
   official metrics with a family/topic-disjoint split.
2. Run the selector with the exact six open model checkpoints named by the
   paper where licenses and APIs permit; record each checkpoint, pooling,
   normalization, PCA fit scope, and candidate-search implementation.
3. Compare random, BM25/lexical, in-batch, STAR/ADORE+STAR-compatible, and
   proposed negatives under one fixed reranker and fixed training budget.
4. Use a modern open cross-encoder (and a CPU-small control) with triplet loss,
   three seeds, early stopping on validation MRR@10, and exact MRR@3/@10.
5. Add oracle labels for acronym collisions, same-system/different-operation,
   version conflicts, and same-title different-owner cases. Audit false
   negatives before training.
6. Evaluate on the State of AI corpus, the enterprise-like Frankengate wiki,
   NL2SQL schema/column collisions, and a held-out changed-system cohort. Keep
   all enterprise data out of the public repository; publish only fixtures,
   hashes, labels, and aggregate receipts.
7. Report compute cost, latency, index rebuild/update cost, long-document
   degradation, and regression slices—not only average MRR.

### Model-vintage companion

The public transfer gate now has a parallel model-vintage probe rather than
freezing the experiment at the paper-era surrogate. The companion runs the
same bounded TechQA candidate pool with TF-IDF, `all-MiniLM-L6-v2`,
`Snowflake/snowflake-arctic-embed-s`, and `Qwen/Qwen3-Embedding-0.6B`; see
[`hard-negative-public-model-vintage-2026-08-03.md`](hard-negative-public-model-vintage-2026-08-03.md).
This is intentionally a separate retrieval-model comparison: it does not
pretend to reproduce Oracle's private six-encoder ensemble or its
triplet-trained reranker. The model manifest and aggregate receipt make the
model ID, license, dataset hash, seed, and metric deltas independently
auditable.

## Promotion rule

Do not promote the method into Frankengate because it improves a single MRR
number. It must beat lexical/hybrid baselines on family-disjoint held-out
queries, improve enterprise hard-negative slices without increasing false
negatives, and survive replay/answer-grounding checks. The current result is
therefore **implementation complete for the CPU surrogate, empirical claim
open**.

Receipt: [`stateofai-hard-negative-reimplementation-2026-08-02.json`](../results/stateofai-hard-negative-reimplementation-2026-08-02.json)
